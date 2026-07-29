"""Static (AST) privacy guard over the whole ``src/`` tree.

The behavioural privacy tests in ``test_privacy.py`` only exercise the synthetic
pipeline (the pure code paths that never had a reason to touch the network or
disk). This module closes that gap: it parses *every* source file — including the
real adapters (MediaPipe, OpenCV, Qt) that are not importable in CI — and fails if
any of them imports a network/persistence module or calls a disk-write/network
function. It enforces the PRIVACY.md guarantees by code review, mechanically.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.privacy

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "privacy_guard"

# The single, documented network exception: the self-updater. It only fetches release
# metadata + the installer, never any camera/biometric data (proven by the isolation
# test below). Every other source file stays fully network-free.
QUARANTINE = {Path("update") / "checker.py"}

# Files allowed to write OUTSIDE QSettings, each for one narrow, argued reason.
# Being on this list buys nothing else: they are still forbidden from touching the
# network (except the updater) and from importing any camera/vision code, and each
# has its own isolation test below.
#
#   update/checker.py — writes the downloaded installer (verified, then launched).
#   ui/autostart.py   — writes the login item (a launcher path and a flag). AM-1:
#                       before it existed, the "start at login" switch registered
#                       nothing at all and the app silently never started.
DISK_WRITE_ALLOWED = {Path("update") / "checker.py", Path("ui") / "autostart.py"}

# The updater must never be able to reach a camera frame or biometric pipeline.
CAMERA_THIRD_PARTY_ROOTS = {"cv2", "mediapipe", "PIL"}
CAMERA_INTERNAL_PREFIXES = (
    "privacy_guard.capture",
    "privacy_guard.vision",
    "privacy_guard.app",
)


def _is_camera_import(name: str) -> bool:
    if _module_root(name) in CAMERA_THIRD_PARTY_ROOTS:
        return True
    return any(name == p or name.startswith(p + ".") for p in CAMERA_INTERNAL_PREFIXES)


# Violations are typed, because the two exemptions are not the same exemption:
# the updater may reach the network, the autostart module may only write a file.
NETWORK = "network"
WRITE = "write"

# Importing any of these modules would enable outbound network.
NETWORK_IMPORTS = {
    "socket",
    "ssl",
    "http",
    "http.client",
    "urllib",
    "urllib.request",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
    "wget",
}

# Importing any of these would enable (serialised) persistence.
PERSISTENCE_IMPORTS = {"pickle", "shelve", "dbm"}

FORBIDDEN_IMPORTS = NETWORK_IMPORTS | PERSISTENCE_IMPORTS

# Calls that fetch URLs.
NETWORK_CALL_NAMES = {"urlopen", "urlretrieve", "create_connection"}

# Calls that write image/array/arbitrary data to disk. `write_text`/`write_bytes`
# and `os.open` are here so a write cannot simply route around the `open(..., "w")`
# check below — the guard is only worth having if it has no obvious side door.
WRITE_CALL_NAMES = {
    "imwrite",
    "imsave",
    "savez",
    "savez_compressed",
    "savetxt",
    "tofile",
    "write_text",
    "write_bytes",
}

FORBIDDEN_CALL_NAMES = NETWORK_CALL_NAMES | WRITE_CALL_NAMES

WRITE_MODE_FLAGS = ("w", "a", "x", "+")


def _source_files() -> list[Path]:
    files = sorted(SRC_ROOT.rglob("*.py"))
    assert files, f"no source files found under {SRC_ROOT}"
    return files


def _module_root(name: str) -> str:
    return name.split(".")[0]


def _kind_for_import(name: str) -> str:
    return NETWORK if (name in NETWORK_IMPORTS or _module_root(name) in NETWORK_IMPORTS) else WRITE


class _HygieneVisitor(ast.NodeVisitor):
    """Collects ``(kind, message)`` violations so each can be judged on its own."""

    def __init__(self) -> None:
        self.found: list[tuple[str, str]] = []

    @property
    def violations(self) -> list[str]:
        """Flat messages (kept for readability in failure output)."""
        return [message for _kind, message in self.found]

    def kinds(self, kind: str) -> list[str]:
        """Messages of one kind only."""
        return [message for k, message in self.found if k == kind]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in FORBIDDEN_IMPORTS or _module_root(alias.name) in FORBIDDEN_IMPORTS:
                self.found.append(
                    (_kind_for_import(alias.name), f"import {alias.name} (line {node.lineno})")
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if mod in FORBIDDEN_IMPORTS or _module_root(mod) in FORBIDDEN_IMPORTS:
            self.found.append(
                (_kind_for_import(mod), f"from {mod} import ... (line {node.lineno})")
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        # `np.save`, `cv2.imwrite`, `path.write_text`, `urlopen`, ...
        if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_CALL_NAMES:
            kind = NETWORK if func.attr in NETWORK_CALL_NAMES else WRITE
            self.found.append((kind, f"call .{func.attr}(...) (line {node.lineno})"))
        if isinstance(func, ast.Attribute) and func.attr == "save":
            # numpy.save / cv2-like .save(path). Path.open("rb") is unaffected.
            self.found.append((WRITE, f"call .save(...) (line {node.lineno})"))
        # Bare names: urlopen, ...
        if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
            kind = NETWORK if func.id in NETWORK_CALL_NAMES else WRITE
            self.found.append((kind, f"call {func.id}(...) (line {node.lineno})"))
        self._check_os_open(node)
        # open(..., "w"/"a"/"x"/"+") anywhere.
        self._check_open_for_write(node)
        self.generic_visit(node)

    def _check_os_open(self, node: ast.Call) -> None:
        # `os.open(path, os.O_WRONLY)` takes int flags, so the mode check below
        # would never see it. Treat any os.open as a write attempt.
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "open"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
        ):
            self.found.append((WRITE, f"call os.open(...) (line {node.lineno})"))

    def _check_open_for_write(self, node: ast.Call) -> None:
        func = node.func
        is_open = (isinstance(func, ast.Name) and func.id == "open") or (
            isinstance(func, ast.Attribute) and func.attr == "open"
        )
        if not is_open:
            return
        mode: str | None = None
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            value = node.args[1].value
            mode = value if isinstance(value, str) else None
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                value = kw.value.value
                mode = value if isinstance(value, str) else mode
        if mode is not None and any(flag in mode for flag in WRITE_MODE_FLAGS):
            self.found.append((WRITE, f"open(..., {mode!r}) (line {node.lineno})"))


def _scan(path: Path) -> _HygieneVisitor:
    visitor = _HygieneVisitor()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return visitor


def test_no_source_file_touches_the_network() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _source_files():
        rel = path.relative_to(SRC_ROOT)
        if rel in QUARANTINE:
            continue  # the updater is the single allow-listed network module
        found = _scan(path).kinds(NETWORK)
        if found:
            offenders[str(rel)] = found
    assert not offenders, f"network access found outside the quarantined updater: {offenders}"


def test_no_source_file_writes_to_disk() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _source_files():
        rel = path.relative_to(SRC_ROOT)
        if rel in DISK_WRITE_ALLOWED:
            continue  # each entry is argued at the top of this file
        found = _scan(path).kinds(WRITE)
        if found:
            offenders[str(rel)] = found
    assert not offenders, f"disk writes found outside the allow-list: {offenders}"


def test_allow_lists_point_at_real_files() -> None:
    # The allow-lists must point at real files (catches renames that would silently
    # drop the exemption or leave a dead entry granting nothing).
    for rel in QUARANTINE | DISK_WRITE_ALLOWED:
        assert (SRC_ROOT / rel).is_file(), f"allow-listed file missing: {rel}"


def test_disk_write_allow_list_stays_minimal() -> None:
    # Growing this list is a privacy decision, not a refactor: a new entry must be
    # a deliberate change to this test, argued in the comment above.
    expected = {Path("update") / "checker.py", Path("ui") / "autostart.py"}
    assert expected == DISK_WRITE_ALLOWED


def test_autostart_is_isolated_from_camera_network_and_biometrics() -> None:
    # The one module allowed to write a launcher entry must not be able to reach a
    # camera frame, nor the network: it writes a path and a flag, nothing else.
    path = SRC_ROOT / "ui" / "autostart.py"
    visitor = _scan(path)
    assert not visitor.kinds(NETWORK), f"autostart must stay offline: {visitor.kinds(NETWORK)}"

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bad: list[str] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        bad += [n for n in names if _is_camera_import(n)]
    assert not bad, f"autostart must not import camera/biometric modules: {bad}"


def test_updater_is_isolated_from_camera_and_biometrics() -> None:
    # The network-capable updater must not be able to import any camera/vision/frame
    # code. This mechanically guarantees it can never exfiltrate biometric data.
    update_dir = SRC_ROOT / "update"
    offenders: dict[str, list[str]] = {}
    for path in sorted(update_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        bad: list[str] = []
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            bad += [n for n in names if _is_camera_import(n)]
        if bad:
            offenders[path.name] = bad
    assert not offenders, f"updater must not import camera/biometric modules: {offenders}"


def test_guard_detects_a_planted_violation() -> None:
    # Proves the scanner actually catches forbidden constructs (anti-tautology).
    snippet = "import socket\ncv2.imwrite('x.png', frame)\nopen('f', 'w')\n"
    visitor = _HygieneVisitor()
    visitor.visit(ast.parse(snippet))
    found = " ".join(visitor.violations)
    assert "socket" in found
    assert "imwrite" in found
    assert "'w'" in found


def test_guard_detects_writes_that_route_around_open() -> None:
    # A guard with an obvious side door is worse than none: these three forms all
    # write to disk without ever calling `open(..., "w")`.
    snippet = (
        "Path('f').write_text('x')\n"
        "Path('f').write_bytes(b'x')\n"
        "os.open('f', os.O_WRONLY | os.O_CREAT)\n"
    )
    visitor = _HygieneVisitor()
    visitor.visit(ast.parse(snippet))
    writes = " ".join(visitor.kinds(WRITE))
    assert "write_text" in writes
    assert "write_bytes" in writes
    assert "os.open" in writes


def test_guard_separates_network_from_write_violations() -> None:
    # The two exemptions are different: the updater may reach the network, the
    # autostart module may only write. Conflating them would silently widen both.
    visitor = _HygieneVisitor()
    visitor.visit(ast.parse("import socket\nopen('f', 'w')\n"))
    assert visitor.kinds(NETWORK) and "socket" in visitor.kinds(NETWORK)[0]
    assert visitor.kinds(WRITE) and "'w'" in visitor.kinds(WRITE)[0]
