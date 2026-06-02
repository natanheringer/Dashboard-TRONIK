"""CLI health monitor: python -m jobs.prospeccao monitor"""

from __future__ import annotations

import json
import sys

from jobs.prospeccao.db import session_scope
from jobs.prospeccao.pipeline_health import build_pipeline_health_report


def run_monitor(*, model_version: str | None = None) -> int:
    with session_scope() as db:
        report = build_pipeline_health_report(db, model_version=model_version)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # errors = fatal for cron (sem modelo ativo, modelo inativo, etc.); warnings = heuristic_bootstrap / empty scores
    healthy = bool(report.get("modelo_ativo")) and not (report.get("errors") or [])
    return 0 if healthy else 1


if __name__ == "__main__":
    version = None
    if len(sys.argv) > 1 and sys.argv[1] not in ("-h", "--help"):
        version = sys.argv[1]
    raise SystemExit(run_monitor(model_version=version))
