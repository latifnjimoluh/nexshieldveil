"""The CI workflows must at least be valid YAML (AM-6/AM-17).

Written after shipping a step whose name contained an unquoted colon: the file
stopped parsing, and nothing in the repository noticed — the one place a broken
CI definition cannot be caught is CI itself. A workflow is configuration we ship
like any other, so it gets the same treatment as the rest.

Deliberately shallow: this checks structure, not semantics. It cannot tell
whether a job does what it claims — only that GitHub will be able to read it, and
that the steps we depend on are still there.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML comes with pre-commit in the dev extra")

pytestmark = pytest.mark.unit

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))


def _workflow_files() -> list[Path]:
    files = sorted(_WORKFLOWS.glob("*.yml")) + sorted(_WORKFLOWS.glob("*.yaml"))
    assert files, "no workflow files found"
    return files


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda p: p.name)
def test_every_workflow_parses(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} is not a mapping"
    assert data.get("jobs"), f"{path.name} defines no jobs"


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda p: p.name)
def test_every_step_has_a_command_or_an_action(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for job_name, job in data["jobs"].items():
        for step in job["steps"]:
            assert "run" in step or "uses" in step, f"{path.name}:{job_name} has an inert step"


def test_ci_still_runs_the_checks_the_project_relies_on() -> None:
    # These are the gates the contributing guide promises; losing one silently
    # would be worse than never having had it.
    commands = " ".join(
        step.get("run", "") for job in _load("ci.yml")["jobs"].values() for step in job["steps"]
    )
    for expected in ("ruff check", "ruff format", "mypy", "bandit", "pip-audit", "pytest"):
        assert expected in commands, f"CI no longer runs {expected}"
    assert "nexshieldveil --check" in commands, "CI no longer runs the QML selfcheck"
    assert "-m privacy" in commands, "CI no longer runs the privacy guarantees"


def test_ci_installs_the_locked_dependencies() -> None:
    commands = " ".join(step.get("run", "") for step in _load("ci.yml")["jobs"]["test"]["steps"])
    assert "--require-hashes -r requirements-ci.txt" in commands


def test_the_release_publishes_the_checksums_the_updater_needs() -> None:
    # Without SHA256SUMS attached to the release, `check_for_update` finds no
    # digest and the app refuses to auto-install (AM-4). The workflow producing
    # and uploading that file is therefore part of the feature, not packaging
    # decoration.
    steps = _load("release.yml")["jobs"]["windows-installer"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "sha256sum NexShieldVeil-Setup.exe > SHA256SUMS" in commands
    assert "SHA256SUMS" in commands.split("gh release upload")[-1]


def test_the_release_verifies_the_model_it_embeds() -> None:
    data = _load("release.yml")
    assert len(data["env"]["MODEL_SHA256"]) == 64
    commands = " ".join(step.get("run", "") for step in data["jobs"]["windows-installer"]["steps"])
    assert "sha256sum -c -" in commands, "the downloaded model is not verified"


def test_the_release_selfchecks_the_frozen_binary() -> None:
    # A bundle can start while missing a QML file; only running the shipped
    # binary catches that.
    commands = " ".join(
        step.get("run", "") for step in _load("release.yml")["jobs"]["windows-installer"]["steps"]
    )
    assert "NexShieldVeil.exe --check" in commands
