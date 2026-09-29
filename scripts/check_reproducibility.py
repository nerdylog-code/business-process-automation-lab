#!/usr/bin/env python3
"""Roda o pipeline 2x e falha se algum artefato mudar de bytes sem mudança de código."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = [
    "data/event_log.csv",
    "data/documents.csv",
    "reports/mining.json",
    "reports/dfg.json",
    "reports/impact.json",
    "bpmn/as_is.bpmn",
    "bpmn/to_be.bpmn",
    "dashboard/process_report.html",
]
STEPS = ["src.generate_event_log", "src.mining", "src.bpmn", "src.impact", "src.report"]


def run_pipeline() -> None:
    for step in STEPS:
        result = subprocess.run([sys.executable, "-m", step], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"{step} falhou:\n{result.stdout}\n{result.stderr}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    snapshots = []
    for _ in range(2):
        run_pipeline()
        snapshots.append({rel: digest(ROOT / rel) for rel in ARTIFACTS})
    for rel, sha in sorted(snapshots[0].items()):
        print(f"{sha[:12]}  {rel}")
    changed = [rel for rel in ARTIFACTS if snapshots[0][rel] != snapshots[1][rel]]
    if changed:
        print("\nREPRODUTIBILIDADE QUEBRADA: " + ", ".join(changed))
        return 1
    print("\nOK — duas execucoes geraram bytes identicos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
