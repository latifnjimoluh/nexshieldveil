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

# Importing any of these modules would enable outbound network or persistence.
FORBIDDEN_IMPORTS = {
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
    "pickle",
    "shelve",
    "dbm",
    "wget",
}

# Calls (by attribute / function name) that write image/array data or fetch URLs.
FORBIDDEN_CALL_NAMES = {
    "imwrite",
    "imsave",
    "savez",
    "savez_compressed",
    "savetxt",
    "tofile",
    "urlopen",
    "urlretrieve",
    "create_connection",
}

WRITE_MODE_FLAGS = ("w", "a", "x", "+")


def _source_files() -> list[Path]:
    files = sorted(SRC_ROOT.rglob("*.py"))
    assert files, f"no source files found under {SRC_ROOT}"
    return files


def _module_root(name: str) -> str:
    return name.split(".")[0]


class _HygieneVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in FORBIDDEN_IMPORTS or _module_root(alias.name) in FORBIDDEN_IMPORTS:
                self.violations.append(f"import {alias.name} (line {node.lineno})")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if mod in FORBIDDEN_IMPORTS or _module_root(mod) in FORBIDDEN_IMPORTS:
            self.violations.append(f"from {mod} import ... (line {node.lineno})")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        # `np.save`, `cv2.imwrite`, `pickle.dump`, ...
        if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_CALL_NAMES:
            self.violations.append(f"call .{func.attr}(...) (line {node.lineno})")
        if isinstance(func, ast.Attribute) and func.attr == "save":
            # numpy.save / cv2-like .save(path). Path.open("rb") is unaffected.
            self.violations.append(f"call .save(...) (line {node.lineno})")
        # Bare names: dump, urlopen, ...
        if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
            self.violations.append(f"call {func.id}(...) (line {node.lineno})")
        # open(..., "w"/"a"/"x"/"+") anywhere.
        self._check_open_for_write(node)
        self.generic_visit(node)

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
            self.violations.append(f"open(..., {mode!r}) (line {node.lineno})")


def test_no_source_file_imports_network_or_persistence() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _HygieneVisitor()
        visitor.visit(tree)
        if visitor.violations:
            offenders[str(path.relative_to(SRC_ROOT))] = visitor.violations
    assert not offenders, f"privacy-forbidden constructs found in src/: {offenders}"


def test_guard_detects_a_planted_violation() -> None:
    # Proves the scanner actually catches forbidden constructs (anti-tautology).
    snippet = "import socket\ncv2.imwrite('x.png', frame)\nopen('f', 'w')\n"
    visitor = _HygieneVisitor()
    visitor.visit(ast.parse(snippet))
    found = " ".join(visitor.violations)
    assert "socket" in found
    assert "imwrite" in found
    assert "'w'" in found
