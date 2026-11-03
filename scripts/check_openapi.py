"""Confere que o spec commitado corresponde às rotas que o app realmente expõe.

Compara rotas e nomes de schema, não o arquivo byte a byte: a serialização do
OpenAPI muda entre versões de FastAPI/pydantic, e um gate que quebra a cada bump
de dependência vira ruído e acaba desativado.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.automation_service import app  # noqa: E402

TARGET = ROOT / "api" / "openapi.json"


def main() -> int:
    if not TARGET.exists():
        print(f"::error::{TARGET.relative_to(ROOT).as_posix()} não existe; rode 'make openapi'")
        return 1
    commitado = json.loads(TARGET.read_text(encoding="utf-8"))
    gerado = app.openapi()

    rotas_commitadas = set(commitado.get("paths", {}))
    rotas_do_app = set(gerado.get("paths", {}))
    problemas = []
    if rotas_commitadas != rotas_do_app:
        problemas.append(f"rotas divergentes: sobrando no arquivo {sorted(rotas_commitadas - rotas_do_app)}, "
                         f"faltando {sorted(rotas_do_app - rotas_commitadas)}")

    schemas_commitados = set(commitado.get("components", {}).get("schemas", {}))
    schemas_do_app = set(gerado.get("components", {}).get("schemas", {}))
    if schemas_commitados != schemas_do_app:
        problemas.append(f"schemas divergentes: {sorted(schemas_do_app ^ schemas_commitados)}")

    if problemas:
        for p in problemas:
            print(f"::error::{p}")
        print("rode 'make openapi' e commite api/openapi.json")
        return 1
    print(f"spec em dia: {len(rotas_do_app)} rotas e {len(schemas_do_app)} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
