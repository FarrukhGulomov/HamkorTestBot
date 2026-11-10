"""Clean Architecture qoidalari: bog'liqlik faqat ichkariga qarab yo'naladi."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

# qatlam -> import qilishi MUMKIN BO'LMAGAN modullar
FORBIDDEN = {
    "domain": ["src.application", "src.infrastructure", "src.presentation", "aiogram", "sqlalchemy", "pydantic"],
    "application": ["src.infrastructure", "src.presentation", "aiogram", "sqlalchemy", "pydantic"],
    "infrastructure": ["src.presentation", "aiogram"],
    "presentation": ["src.infrastructure", "sqlalchemy"],
}


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("layer", FORBIDDEN)
def test_layer_does_not_import_forbidden_modules(layer):
    violations = []
    for path in (SRC / layer).rglob("*.py"):
        for module in imported_modules(path):
            for forbidden in FORBIDDEN[layer]:
                if module == forbidden or module.startswith(forbidden + "."):
                    violations.append(f"{path.relative_to(SRC)} imports {module}")

    assert not violations, "\n".join(violations)
