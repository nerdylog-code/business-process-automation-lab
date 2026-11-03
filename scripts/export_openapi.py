"""Escreve api/openapi.json a partir do app FastAPI — uma fonte de verdade só.

O spec era um arquivo escrito à mão; agora é derivado do próprio código pelo
`make openapi`, e o teste `tests/test_flows.py` confere que ele existe e cobre
as rotas que a documentação cita.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.automation_service import app  # noqa: E402

TARGET = ROOT / "api" / "openapi.json"


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    spec = app.openapi()
    TARGET.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"spec gravado em {TARGET.relative_to(ROOT).as_posix()} ({len(spec['paths'])} rotas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
