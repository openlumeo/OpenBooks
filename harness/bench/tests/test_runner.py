import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

from bench import cli, mcp_client, runner
from bench.mcp_client import McpClient, McpTimeout, resolve_executable, split_command
from bench.providers import Provider, ProviderError, Reply, ToolCall, Usage

FAKE_SERVER = Path(__file__).resolve().parent / "fake_mcp_server.py"
API_KEY_ENV = "OBTEST_API_KEY"
API_KEY = "sk-test-canary-7d41c0ffee"
BALANCED = "date,description,amount\n2026-01-02,Sample payment,-100.00\n2026-01-03,Sample deposit,50.00\n"
TAMPERED = "date,description,amount\n2026-01-02,Sample payment,-100.00\n"
UTC_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def fake_argv() -> list[str]:
    return [sys.executable, str(FAKE_SERVER)]


def write_task(tasks_root: Path, task_id: str, prompt: str, files: dict[str, str], outcome: str) -> None:
    folder = tasks_root / task_id
    folder.mkdir(parents=True)
    task = {
        "id": task_id,
        "category": "release",
        "prompt": prompt,
        "files": list(files),
        "params": {"currency": "INR", "opening": "1000.00"},
        "expect": {"outcome": outcome, "fields": {"transaction_count": 2, "closing_balance": "1299.50", "currency": "INR"}},
    }
    (folder / "task.json").write_text(json.dumps(task), encoding="utf-8")
    (folder / "expected.json").write_text(json.dumps({"outcome": outcome}, indent=2), encoding="utf-8")
    for name, content in files.items():
        (folder / name).write_text(content, encoding="utf-8")


def file_from_message(messages: list[dict[str, Any]]) -> str:
    text = messages[0]["content"]
    listed = text.rsplit("Workspace files (relative paths): ", 1)[1]
    return listed.split(",")[0].strip()


def verify_then_answer(system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], with_records: bool = True):
    if messages[-1]["role"] == "tool":
        return Reply(text="Verified: 2 transactions, closing balance 1299.50 INR.", tool_calls=[], usage=Usage(150, 30), stop="end_turn")
    steps = [{"id": "f", "operation": "process_file", "arguments": {"path": file_from_message(messages), "currency": "INR", "opening": "1000.00"}}]
    if with_records:
        steps.append({"id": "b", "operation": "records", "arguments": {"from_step": "f", "collection": "batches", "limit": 5}})
    call = ToolCall(id="call-1", name="execute", arguments={"steps": steps})
    return Reply(text="Verifying.", tool_calls=[call], usage=Usage(100, 20), stop="tool_use")


class ScriptedProvider(Provider):
    name = "scripted"

    def __init__(self, behavior) -> None:
        super().__init__("scripted-model", API_KEY)
        self.behavior = behavior

    def complete(self, system, messages, tools) -> Reply:
        return self.behavior(system, messages, tools)


def make_config(tasks_root: Path, out_dir: Path, **overrides: Any) -> runner.RunConfig:
    values: dict[str, Any] = {
        "provider_name": "anthropic",
        "model": "claude-test",
        "api_key": API_KEY,
        "api_key_env": API_KEY_ENV,
        "tasks_root": tasks_root,
        "out_dir": out_dir,
        "mcp_argv": fake_argv(),
        "max_turns": 4,
        "max_cost_usd": 5.0,
        "task_ids": None,
        "progress": None,
    }
    values.update(overrides)
    return runner.RunConfig(**values)


@pytest.fixture(autouse=True)
def api_key_in_env(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)


@pytest.fixture
def tasks_root(tmp_path: Path) -> Path:
    root = tmp_path / "tasks"
    root.mkdir()
    write_task(root, "csv-balanced-01", "Verify statement.csv and report the closing balance.", {"statement.csv": BALANCED}, "released")
    return root


def test_bundle_shape_digest_and_engine_outcomes(tasks_root, tmp_path):
    out = tmp_path / "out"
    progress: list[str] = []
    config = make_config(tasks_root, out, progress=progress.append)
    bundle, path = runner.run_bench(config, ScriptedProvider(verify_then_answer))

    assert list(bundle) == ["schema", "kit_version", "run_id", "created_at", "model", "tasks", "scores", "tasks_digest"]
    assert bundle["schema"] == "openbooks.bench.v1"
    assert bundle["kit_version"] == "0.2.5"
    assert str(uuid.UUID(bundle["run_id"])) == bundle["run_id"]
    assert UTC_STAMP.match(bundle["created_at"])
    assert bundle["model"] == {"provider": "anthropic", "name": "claude-test"}
    assert set(bundle["scores"]) >= {"release_accuracy", "field_accuracy", "efficiency", "safety", "overall"}

    expected_bytes = (tasks_root / "csv-balanced-01" / "expected.json").read_bytes()
    digest_input = f"csv-balanced-01:{hashlib.sha256(expected_bytes).hexdigest()}"
    assert bundle["tasks_digest"] == hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    task = bundle["tasks"][0]
    assert task["id"] == "csv-balanced-01"
    assert task["final_answer"] == "Verified: 2 transactions, closing balance 1299.50 INR."
    assert task["tool_calls"] == 1
    assert task["input_tokens"] == 250
    assert task["output_tokens"] == 50
    assert task["elapsed_s"] > 0
    assert task["error"] is None
    assert task["engine_outcomes"] == [
        {
            "layout": "bank_csv.v1",
            "status": "released",
            "refusal_code": None,
            "fields": {"transaction_count": 2, "closing_balance": "1299.50", "currency": "INR"},
            "file": "statement.csv",
        }
    ]
    assert len(progress) == 1 and "csv-balanced-01" in progress[0]
    assert (out / "bench-result.v1.json").exists()
    assert (out / "results.md").read_text(encoding="utf-8").startswith("# Open Books bench")
    assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == bundle["run_id"]


def test_probe_fills_fields_when_model_never_reads_records(tasks_root, tmp_path):
    bundle, _ = runner.run_bench(
        make_config(tasks_root, tmp_path / "out"),
        ScriptedProvider(lambda s, m, t: verify_then_answer(s, m, t, with_records=False)),
    )
    outcome = bundle["tasks"][0]["engine_outcomes"][0]
    assert outcome["fields"] == {"transaction_count": 2, "closing_balance": "1299.50", "currency": "INR"}


def test_refused_document_is_captured_without_layout(tmp_path):
    root = tmp_path / "tasks"
    root.mkdir()
    write_task(root, "tamper-01", "Verify statement_tampered.csv.", {"statement_tampered.csv": TAMPERED}, "refused")
    bundle, _ = runner.run_bench(
        make_config(root, tmp_path / "out"),
        ScriptedProvider(lambda s, m, t: verify_then_answer(s, m, t, with_records=False)),
    )
    assert bundle["tasks"][0]["engine_outcomes"] == [
        {"layout": None, "status": "refused", "refusal_code": "BALANCE_MISMATCH", "fields": {}}
    ]


def test_engine_log_records_file_basename_from_document_and_verify_many():
    log = runner.EngineLog()
    requested = {
        "f": {"id": "f", "operation": "process_file", "arguments": {"path": "statement.csv"}},
        "g": {"id": "g", "operation": "process_file", "arguments": {"path": "bank/tampered.csv"}},
    }
    log.observe(requested, {"steps": [{"id": "f", "result": {"status": "ok", "file": {"layout_version": "bank_csv.v1", "name": "statement.csv"}, "counts": {"transactions": 8}}}]})
    log.observe({"v": {"id": "v", "operation": "verify_many"}}, {"steps": [{"id": "v", "result": {"files": [{"name": "C:\\docs\\other.ofx", "status": "refused", "code": "UNKNOWN_LAYOUT"}]}}]})
    log.observe(requested, {"steps": [{"id": "g", "result": {"status": "refused", "error": {"code": "BALANCE_MISMATCH"}}}]})
    assert log.outcomes == [
        {"layout": "bank_csv.v1", "status": "released", "refusal_code": None, "fields": {"transaction_count": 8}, "file": "statement.csv"},
        {"layout": None, "status": "refused", "refusal_code": "UNKNOWN_LAYOUT", "fields": {}, "file": "other.ofx"},
        {"layout": None, "status": "refused", "refusal_code": "BALANCE_MISMATCH", "fields": {}},
    ]


def test_tool_timeout_default_is_ten_minutes_and_flag_is_validated(monkeypatch, capsys, tmp_path):
    assert mcp_client.CALL_TIMEOUT_S == 600.0
    base = ["run", "--provider", "anthropic", "--model", "m", "--api-key-env", API_KEY_ENV, "--out", str(tmp_path / "o")]
    assert cli.build_parser().parse_args(base).tool_timeout == 600.0
    assert cli.build_parser().parse_args(base + ["--tool-timeout", "900"]).tool_timeout == 900.0
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    assert cli.main(base + ["--tool-timeout", "0"]) == 2
    assert "--tool-timeout must be positive" in capsys.readouterr().err
    assert "PNG and handwriting" in " ".join(_run_help("run").split())


def test_run_config_timeout_reaches_the_mcp_client(tasks_root, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MCP_SILENT", "1")
    config = make_config(tasks_root, tmp_path / "out", tool_timeout_s=0.5)
    bundle, _ = runner.run_bench(config, ScriptedProvider(verify_then_answer))
    assert "timed out after 0.5s" in bundle["tasks"][0]["error"]


def _run_help(command: str) -> str:
    for action in cli.build_parser()._subparsers._group_actions:
        choice = action.choices.get(command)
        if choice is not None:
            return choice.format_help()
    return ""


def test_api_key_never_reaches_written_files_or_output(tasks_root, tmp_path, capsys):
    root = tasks_root
    write_task(root, "csv-second-02", "Second statement.", {"statement.csv": BALANCED}, "released")

    def leaky(system, messages, tools):
        if messages[0]["content"].startswith("Second"):
            raise ProviderError(f"upstream rejected key {API_KEY}")
        return verify_then_answer(system, messages, tools)

    out = tmp_path / "out"
    progress: list[str] = []
    bundle, _ = runner.run_bench(make_config(root, out, progress=progress.append), ScriptedProvider(leaky))
    captured = capsys.readouterr()

    for file in out.rglob("*"):
        if file.is_file():
            assert API_KEY not in file.read_text(encoding="utf-8"), file.name
    assert API_KEY not in json.dumps(bundle)
    assert API_KEY not in captured.out + captured.err
    assert all(API_KEY not in line for line in progress)
    assert "[REDACTED]" in bundle["tasks"][1]["error"]


def test_child_environment_drops_the_key_variable(monkeypatch):
    monkeypatch.setenv("OBTEST_OTHER", "kept")
    env = runner.child_environment(API_KEY_ENV)
    assert API_KEY_ENV not in env
    assert env["OBTEST_OTHER"] == "kept"


def test_provider_error_is_recorded_and_run_continues(tasks_root, tmp_path):
    write_task(tasks_root, "csv-second-02", "Second statement.", {"statement.csv": BALANCED}, "released")

    def flaky(system, messages, tools):
        if messages[0]["content"].startswith("Second"):
            return verify_then_answer(system, messages, tools)
        raise ProviderError("HTTP 500 from scripted")

    bundle, _ = runner.run_bench(make_config(tasks_root, tmp_path / "out"), ScriptedProvider(flaky))
    first, second = bundle["tasks"]
    assert first["id"] == "csv-balanced-01"
    assert first["error"] == "ProviderError: HTTP 500 from scripted"
    assert first["tool_calls"] == 0
    assert second["error"] is None
    assert second["tool_calls"] == 1


def test_cost_cap_is_a_hard_stop(tasks_root, tmp_path):
    write_task(tasks_root, "csv-second-02", "Second statement.", {"statement.csv": BALANCED}, "released")
    bundle, _ = runner.run_bench(
        make_config(tasks_root, tmp_path / "out", max_cost_usd=0.001),
        ScriptedProvider(verify_then_answer),
    )
    first, second = bundle["tasks"]
    assert first["error"].startswith("CostCapExceeded")
    assert (first["input_tokens"], first["output_tokens"]) == (100, 20)
    assert second["error"] == "not run: cost cap reached"
    assert second["tool_calls"] == 0


def test_max_turns_limits_the_loop(tasks_root, tmp_path):
    def never_answers(system, messages, tools):
        call = ToolCall(id=f"call-{len(messages)}", name="search", arguments={"query": "records"})
        return Reply(text="", tool_calls=[call], usage=Usage(10, 5), stop="tool_use")

    bundle, _ = runner.run_bench(make_config(tasks_root, tmp_path / "out", max_turns=2), ScriptedProvider(never_answers))
    task = bundle["tasks"][0]
    assert task["tool_calls"] == 2
    assert task["error"] == "stopped after 2 turns without a final answer"


def test_unknown_tool_is_reported_back_to_the_model(tasks_root, tmp_path):
    seen: list[dict[str, Any]] = []

    def wrong_tool(system, messages, tools):
        seen.extend(messages)
        if messages[-1]["role"] == "tool":
            return Reply(text="Done.", tool_calls=[], usage=Usage(1, 1), stop="end_turn")
        return Reply(text="", tool_calls=[ToolCall(id="x1", name="shell", arguments={})], usage=Usage(1, 1), stop="tool_use")

    bundle, _ = runner.run_bench(make_config(tasks_root, tmp_path / "out"), ScriptedProvider(wrong_tool))
    tool_message = seen[-1]
    assert tool_message["role"] == "tool" and "Unknown tool 'shell'" in tool_message["content"]
    assert bundle["tasks"][0]["error"] is None


def test_mcp_client_handshake_and_tool_listing():
    with McpClient(fake_argv() + ["--root", "."]) as client:
        tools = client.list_tools()
        assert [tool["name"] for tool in tools] == ["search", "execute"]
        assert tools[1]["inputSchema"]["required"] == ["steps"]
        result = client.call_tool("search", {"query": ""})
        assert result["structuredContent"]["max_steps"] == 8


def test_mcp_call_times_out_without_hanging(monkeypatch):
    monkeypatch.setenv("FAKE_MCP_SILENT", "1")
    with McpClient(fake_argv() + ["--root", "."], call_timeout=0.5) as client:
        with pytest.raises(McpTimeout):
            client.call_tool("search", {})


def test_split_command_and_windows_resolution(monkeypatch):
    assert split_command("npx -y @lumeo_hq/openbooks mcp") == ["npx", "-y", "@lumeo_hq/openbooks", "mcp"]
    monkeypatch.setattr(mcp_client, "IS_WINDOWS", True)
    assert split_command('"C:\\Program Files\\node.exe" mcp') == ["C:\\Program Files\\node.exe", "mcp"]
    monkeypatch.setattr(mcp_client.shutil, "which", lambda name: None)
    assert resolve_executable(["npx", "-y", "pkg"]) == ["npx.cmd", "-y", "pkg"]


def test_price_table_matches_prefix_and_defaults_conservatively():
    assert runner.price_for("anthropic", "claude-sonnet-4-5") == (3.0, 15.0)
    assert runner.price_for("openai", "gpt-4o-mini-2025") == (0.15, 0.6)
    assert runner.price_for("compat", "some-unknown-model") == runner.DEFAULT_PRICE_USD_PER_MILLION


def test_cli_run_requires_the_key_env_var(monkeypatch, capsys):
    monkeypatch.delenv("OBTEST_MISSING_KEY", raising=False)
    code = cli.main(["run", "--provider", "anthropic", "--model", "m", "--api-key-env", "OBTEST_MISSING_KEY"])
    assert code == 2
    assert "OBTEST_MISSING_KEY is not set" in capsys.readouterr().err


def test_cli_run_end_to_end_without_leaking_the_key(tasks_root, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "TASKS_ROOT", tasks_root)
    monkeypatch.setattr(cli, "make_provider", lambda name, model, key, base_url=None: ScriptedProvider(verify_then_answer))
    out = tmp_path / "cli-out"
    code = cli.main(
        [
            "run",
            "--provider", "anthropic",
            "--model", "claude-test",
            "--api-key-env", API_KEY_ENV,
            "--out", str(out),
            "--mcp-command", f'"{sys.executable}" "{FAKE_SERVER}"',
            "--max-turns", "3",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert (out / "bench-result.v1.json").exists()
    assert API_KEY not in captured.out + captured.err
    for file in out.rglob("*"):
        if file.is_file():
            assert API_KEY not in file.read_text(encoding="utf-8")
