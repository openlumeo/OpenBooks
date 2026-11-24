from __future__ import annotations

import argparse
import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "out" / "risk-coverage"
INPUT_SCHEMA = "ocr-compare.v1"
OUTPUT_SCHEMA = "risk-coverage.v1"
OUTPUT_JSON = "risk-coverage.v1.json"
OUTPUT_MARKDOWN = "risk-coverage.md"
RULE_OF_THREE = 3.0
SELF_CHECK_SEED = 20260611
SELF_CHECK_DOCS = 40
SELF_CHECK_REFUSAL_RATE = 0.15
SELF_CHECK_ERROR_FLOOR = 0.7
NOTES = (
    "Coverage is the share of all documents released. The curve releases released documents whose confidence is at or above each threshold.",
    "Rule of three: 3/n approximates the one-sided 95% upper bound on the wrong-release rate when zero wrong releases are observed among n released documents. It is an approximation.",
    "overall_only mode: the input has no per-document confidence and correctness, so only the overall wrong-release count is reported; coverage at zero wrong is not determined when errors exist.",
)


@dataclass(frozen=True)
class Release:
    confidence: float
    correct: bool


@dataclass(frozen=True)
class Tally:
    documents: int
    released: int
    wrong: int
    releases: tuple[Release, ...]
    scored: bool


@dataclass(frozen=True)
class CurvePoint:
    threshold: float
    released: int
    coverage: float
    wrong: int


@dataclass(frozen=True)
class ProviderRisk:
    provider_id: str
    mode: str
    documents: int
    released: int
    wrong_release_count: int
    max_coverage_at_zero_wrong: float | None
    zero_wrong_upper_bound: float | None
    curve: tuple[CurvePoint, ...]


def merge(left: Tally | None, right: Tally) -> Tally:
    if left is None:
        return right
    return Tally(
        documents=left.documents + right.documents,
        released=left.released + right.released,
        wrong=left.wrong + right.wrong,
        releases=left.releases + right.releases,
        scored=left.scored and right.scored,
    )


def tally_provider(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> Tally:
    documents = int(summary["documents"])
    refused = sum(int(count) for count in summary.get("refusal_codes", {}).values())
    released = documents - refused
    releases = tuple(
        Release(float(row["confidence"]), bool(row["correct"]))
        for row in rows
        if row.get("status") == "released" and "confidence" in row and "correct" in row
    )
    return Tally(documents, released, int(summary["wrong_release_count"]), releases, len(releases) == released)



def tallies_from(payload: Mapping[str, Any]) -> dict[str, Tally]:
    observations = payload.get("observations", {})
    return {
        summary["provider_id"]: tally_provider(summary, observations.get(summary["provider_id"], []))
        for summary in payload["providers"]
    }


def sweep(tally: Tally) -> tuple[CurvePoint, ...]:
    ordered = sorted(tally.releases, key=lambda release: release.confidence, reverse=True)
    points: list[CurvePoint] = []
    released = 0
    wrong = 0
    for position, release in enumerate(ordered):
        released += 1
        wrong += 0 if release.correct else 1
        ends_level = position + 1 == len(ordered) or ordered[position + 1].confidence < release.confidence
        if ends_level:
            points.append(CurvePoint(release.confidence, released, released / tally.documents, wrong))
    return tuple(points)


def summarize(provider_id: str, tally: Tally) -> ProviderRisk:
    if tally.scored and tally.released > 0:
        curve = sweep(tally)
        zero_wrong = [point for point in curve if point.wrong == 0]
        best = max(zero_wrong, key=lambda point: point.coverage, default=None)
        mode = "confidence_sweep"
        max_coverage = best.coverage if best else 0.0
        bound_base = best.released if best else 0
    else:
        curve = ()
        mode = "overall_only"
        if tally.wrong == 0:
            max_coverage = tally.released / tally.documents if tally.documents else 0.0
            bound_base = tally.released
        else:
            max_coverage = None
            bound_base = 0
    bound = RULE_OF_THREE / bound_base if bound_base else None
    return ProviderRisk(provider_id, mode, tally.documents, tally.released, tally.wrong, max_coverage, bound, curve)


def assess(payloads: Sequence[Mapping[str, Any]]) -> tuple[ProviderRisk, ...]:
    merged: dict[str, Tally] = {}
    for payload in payloads:
        for provider_id, tally in tallies_from(payload).items():
            merged[provider_id] = merge(merged.get(provider_id), tally)
    return tuple(summarize(provider_id, merged[provider_id]) for provider_id in sorted(merged))


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != INPUT_SCHEMA:
        raise SystemExit(f"{path}: expected schema {INPUT_SCHEMA}")
    return payload


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _bound(value: float | None) -> str:
    return "n/a" if value is None else f"<= {value:.2%}"


def render_markdown(risks: Sequence[ProviderRisk]) -> str:
    lines = [
        "| Provider | Mode | Docs | Released | Wrong released | Max coverage at 0 wrong | Rule-of-three bound (approx.) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {risk.provider_id} | {risk.mode} | {risk.documents} | {risk.released} | {risk.wrong_release_count} "
        f"| {_percent(risk.max_coverage_at_zero_wrong)} | {_bound(risk.zero_wrong_upper_bound)} |"
        for risk in risks
    ]
    lines.append("")
    if any(risk.mode == "overall_only" for risk in risks):
        lines.append("overall_only: the input has no per-document confidence or correctness, so only the overall wrong-release count is reported.")
    lines.append("Rule-of-three bound is an approximation (3/n, one-sided 95%) and applies only when zero wrong releases are observed.")
    return "\n".join(lines) + "\n"


def write_outputs(risks: Sequence[ProviderRisk], sources: Sequence[Path], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": OUTPUT_SCHEMA,
        "sources": [str(source) for source in sources],
        "notes": list(NOTES),
        "providers": [asdict(risk) for risk in risks],
    }
    (out_dir / OUTPUT_JSON).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    (out_dir / OUTPUT_MARKDOWN).write_text(render_markdown(risks), encoding="utf-8")


def synthetic_payload(rng: random.Random, provider_id: str, with_confidence: bool, error_floor: float | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    refusals = 0
    wrong = 0
    for index in range(SELF_CHECK_DOCS):
        confidence = round(rng.uniform(0.5, 1.0), 3)
        refused = rng.random() < SELF_CHECK_REFUSAL_RATE
        status = "refused" if refused else "released"
        row: dict[str, Any] = {"name": f"{provider_id}/{index:03d}", "status": status, "code": "low_confidence" if refused else None, "latencies_s": [0.5], "pages": 1}
        if refused:
            refusals += 1
        else:
            correct = error_floor is None or confidence >= error_floor
            wrong += 0 if correct else 1
            if with_confidence:
                row.update(confidence=confidence, correct=correct)
        rows.append(row)
    summary = {"provider_id": provider_id, "status": "ok", "documents": SELF_CHECK_DOCS, "wrong_release_count": wrong, "refusal_codes": {"low_confidence": refusals} if refusals else {}}
    return {"schema": INPUT_SCHEMA, "providers": [summary], "observations": {provider_id: rows}}


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def self_check() -> int:
    rng = random.Random(SELF_CHECK_SEED)
    (zero,) = assess([synthetic_payload(rng, "zero-error", True, None)])
    (leaky,) = assess([synthetic_payload(rng, "non-zero-error", True, SELF_CHECK_ERROR_FLOOR)])
    (legacy,) = assess([synthetic_payload(rng, "overall-errors", False, SELF_CHECK_ERROR_FLOOR)])
    (legacy_zero,) = assess([synthetic_payload(rng, "overall-zero", False, None)])

    _expect(zero.mode == "confidence_sweep" and zero.wrong_release_count == 0, "zero-error case uses sweep")
    _expect(zero.max_coverage_at_zero_wrong == zero.released / zero.documents, "zero-error coverage is full release")
    _expect(zero.zero_wrong_upper_bound == RULE_OF_THREE / zero.released, "zero-error rule of three")

    _expect(leaky.mode == "confidence_sweep" and leaky.wrong_release_count > 0, "non-zero case has wrong releases")
    _expect(0 < (leaky.max_coverage_at_zero_wrong or 0) < leaky.released / leaky.documents, "non-zero partial coverage")
    _expect(leaky.zero_wrong_upper_bound is not None, "non-zero bound at zero-wrong point")
    _expect(legacy.mode == "overall_only" and legacy.wrong_release_count > 0 and legacy.max_coverage_at_zero_wrong is None, "overall-only with errors")
    _expect(legacy_zero.max_coverage_at_zero_wrong == legacy_zero.released / legacy_zero.documents, "overall-only zero-error coverage")
    _expect(legacy_zero.zero_wrong_upper_bound == RULE_OF_THREE / legacy_zero.released, "overall-only zero-error rule of three")
    print("risk_coverage self-check ok")
    return 0


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bench.risk_coverage", description="Risk-coverage report from ocr-compare.v1 files.")
    parser.add_argument("inputs", nargs="*", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_check:
        return self_check()
    if not args.inputs:
        raise SystemExit("pass ocr-compare.v1.json files or --self-check")
    risks = assess([load_payload(path) for path in args.inputs])
    write_outputs(risks, args.inputs, args.out)
    print(render_markdown(risks), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
