"""Fail if the campaign rules start depending on a web framework."""

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "src" / "hexcampaign" / "domain"
FORBIDDEN = {"django", "fastapi", "rest_framework"}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_domain_does_not_import_web_frameworks() -> None:
    python_files = list(DOMAIN_ROOT.rglob("*.py"))
    assert python_files, "the domain package must exist"
    offenders = [
        f"{path.relative_to(DOMAIN_ROOT)} imports {sorted(roots & FORBIDDEN)}"
        for path in python_files
        if (roots := _imported_roots(path)) & FORBIDDEN
    ]
    assert offenders == []
