"""Doctor: every failure mode it claims to detect, the exit-code contract, and machine output."""
import json
import subprocess
import sys
from importlib.metadata import EntryPoint

import pytest

from openbooks_core import default_registry
from openbooks_core.registry import Registry
from openbooks_doctor import checks as C
from openbooks_doctor.cli import SCHEMA, DoctorCommand, exit_code, main, report


def by_id(cs):
    return {c.id: c for c in cs}


def test_a_healthy_registry_passes_and_the_self_test_covers_every_installed_family():
    cs = by_id(C.run_checks(registry=default_registry()))
    assert cs["registry.load"].status == C.PASS and cs["registry.coverage"].status == C.PASS
    for layout in ("bank_csv.v1", "mt940.v1", "stripe_balance.v1", "tds_26as.v1"):
        assert cs[f"selftest.{layout}"].status == C.PASS, cs[f"selftest.{layout}"]


def test_a_provider_that_cannot_load_is_a_failure_with_a_fix():
    broken = Registry(layouts={"bank_csv.v1": EntryPoint("bank_csv.v1", "no_such_module_xyz:f", "openbooks.layouts")})
    cs, _ = C.check_registry(broken)
    assert cs[0].id == "registry.load" and cs[0].status == C.FAIL and cs[0].fix


def test_missing_providers_are_a_warning_naming_the_packages_not_a_failure():
    cs, reg = C.check_registry(default_registry().restricted_to(("openbooks-gateways",)))
    cov = by_id(cs)["registry.coverage"]
    assert cov.status == C.WARN and "openbooks-statements" in cov.fix and "openbooks-tax" in cov.fix
    selftest = by_id(C.check_self_test(reg))
    assert "selftest.stripe_balance.v1" in selftest and "selftest.bank_csv.v1" not in selftest


def test_a_false_accept_is_reported_as_a_failure(monkeypatch):
    import openbooks_core

    monkeypatch.setattr(openbooks_core, "process", lambda *a, **k: {"status": "ok"})  # an engine that releases everything
    cs = C.check_self_test(default_registry())
    bad = [c for c in cs if c.status == C.FAIL]
    assert bad and any("FALSE ACCEPT" in c.detail for c in bad)


def test_an_engine_that_refuses_everything_fails_the_self_test_too(monkeypatch):
    import openbooks_core

    monkeypatch.setattr(openbooks_core, "process", lambda *a, **k: {"status": "refused", "error": {"code": "PARSE_ERROR"}})
    assert any(c.status == C.FAIL and "not released" in c.detail for c in C.check_self_test(default_registry()))


def test_weights_that_do_not_match_their_calibration_fail(tmp_path, monkeypatch):
    import openbooks_statements.assets as assets

    (tmp_path / "roles_head.pt").write_bytes(b"weights")
    (tmp_path / "roles_calibration.json").write_text(json.dumps({"weights_sha256": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(assets, "MODELS_DIR", tmp_path)
    cs = C.check_model(deep=False)
    assert cs[0].id == "model.integrity" and cs[0].status == C.FAIL and "reinstall" in cs[0].fix


def test_missing_model_assets_are_a_warning(tmp_path, monkeypatch):
    import openbooks_statements.assets as assets

    monkeypatch.setattr(assets, "MODELS_DIR", tmp_path)
    assert C.check_model(deep=False)[0].status == C.WARN


def test_an_old_python_is_a_failure(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 9, 0, "final", 0))
    assert C.check_python().status == C.FAIL


def test_version_skew_between_core_and_a_provider_is_a_warning(monkeypatch):
    real = C._dist_version
    monkeypatch.setattr(C, "_dist_version", lambda n: "0.2.0" if n == "openbooks-tax" else real(n))
    c = C.check_versions()
    assert c.status == C.WARN and "openbooks-tax 0.2.0" in c.detail


def test_exit_codes_warnings_pass_unless_strict_and_failures_never_do():
    ok, warn, fail = C.Check("a", C.PASS, ""), C.Check("b", C.WARN, "w", "x"), C.Check("c", C.FAIL, "f", "x")
    assert exit_code(report([ok])) == 0
    assert exit_code(report([ok, warn])) == 0 and exit_code(report([ok, warn], strict=True)) == 1
    assert exit_code(report([ok, fail])) == 1
    assert report([ok, warn, fail])["summary"] == {"pass": 1, "warn": 1, "fail": 1, "skip": 0}


def test_json_output_has_the_documented_shape(capsys):
    rc = main(["--json"])
    rep = json.loads(capsys.readouterr().out)
    assert rep["schema"] == SCHEMA == "openbooks.doctor.v1" and rc == (0 if rep["ok"] else 1)
    assert {"ok", "summary", "checks"} <= set(rep) and all({"id", "status", "detail"} <= set(c) for c in rep["checks"])


def test_a_crash_in_doctor_is_exit_3_not_a_pass(monkeypatch, capsys):
    monkeypatch.setattr("openbooks_doctor.cli.run_checks", lambda **k: (_ for _ in ()).throw(RuntimeError("boom")))
    ns = type("A", (), {"json": False, "strict": False, "deep": False})()
    assert DoctorCommand().run(ns) == 3 and "boom" in capsys.readouterr().err


def test_doctor_is_available_as_a_subcommand_of_the_openbooks_cli():
    r = subprocess.run([sys.executable, "-m", "openbooks_core", "doctor", "--json"], capture_output=True, text=True)
    assert r.returncode in (0, 1) and json.loads(r.stdout)["schema"] == "openbooks.doctor.v1", r.stderr


def test_a_broken_command_plugin_does_not_break_the_cli(monkeypatch, capsys):
    from openbooks_core import cli

    ep = EntryPoint("broken", "no_such_module_xyz:COMMAND", "openbooks.commands")
    monkeypatch.setattr(cli, "_entry_points", lambda group: [ep])
    assert cli.main(["engine-info"]) == 0
    assert "broken" in capsys.readouterr().err


def test_doctor_output_never_contains_document_content(tmp_path, capsys):
    secret = tmp_path / "statement.csv"
    secret.write_text("Date,Narration\n01/01/2026,ACCOUNT 4111111111111111\n", encoding="utf-8")
    main(["--json"])
    assert "4111111111111111" not in capsys.readouterr().out
