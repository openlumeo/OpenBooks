"""The npm publishing mirror must contain only the six packages' sources and must never leak private material."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_npm as npm  # noqa: E402
import export_public as ex  # noqa: E402

PACKAGES = set(npm.PACKAGES)
ALLOWED_TOP = PACKAGES | {"package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "tsconfig.base.json", "tsconfig.json",
                          "README.md", "NOTICE", "LICENSE", ".gitignore", ".github"}


@pytest.fixture(scope="module")
def tree():
    return npm.build((ROOT / "tools" / "public" / "LICENSE").read_bytes())


def test_the_mirror_has_no_private_material(tree):
    assert ex.scan_tree(tree) == []


def test_only_the_six_packages_and_their_workspace_files_are_mirrored(tree):
    assert {rel.split("/")[0] for rel in tree} <= ALLOWED_TOP


@pytest.mark.parametrize("private", ["server/", "web/", "docs/", "models/", "packages/", "tests/", "scripts/", "deploy/"])
def test_no_private_directory_is_mirrored(tree, private):
    assert not [rel for rel in tree if rel.startswith(private)]


def test_tests_and_build_output_stay_out(tree):
    banned = ("/test/", "/tests/", "/dist/", "node_modules/", ".tsbuildinfo", "core/scripts/", "vitest.config")
    assert not [rel for rel in tree if any(b in f"/{rel}" for b in banned)]


def test_every_package_is_present_with_its_manifest_and_licence(tree):
    for pkg in PACKAGES:
        for needed in ("package.json", "LICENSE", "src/index.ts"):
            assert f"{pkg}/{needed}" in tree, (pkg, needed)


def test_every_manifest_points_provenance_at_the_public_repository():
    import json

    for pkg in PACKAGES:
        meta = json.loads((ROOT / "packages" / "js" / pkg / "package.json").read_text(encoding="utf-8"))
        assert meta["repository"]["url"] == "git+https://github.com/Sagexd08/openbooks-js.git", pkg
        assert meta["repository"]["directory"] == pkg


def test_the_workflow_publishes_with_provenance_and_holds_no_token(tree):
    flow = tree[".github/workflows/publish.yml"].decode()
    assert "--provenance" in flow and "id-token: write" in flow
    assert "NPM_TOKEN" not in flow and "NODE_AUTH_TOKEN" not in flow and "|| true" not in flow


def test_a_non_empty_target_is_refused(tmp_path):
    (tmp_path / "x").write_text("keep")
    assert npm.main([str(tmp_path)]) == 2
    assert (tmp_path / "x").read_text() == "keep"


def test_a_real_export_writes_the_tree_and_a_dry_run_writes_nothing(tmp_path):
    out = tmp_path / "out"
    assert npm.main([str(out), "--dry-run"]) == 0 and not out.exists()
    assert npm.main([str(out)]) == 0 and (out / "core" / "package.json").exists() and (out / "LICENSE").exists()
