"""Scheduled prospection ML pipeline (ingest → normalize → link-crm → ML → score)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_cli_step(step_args: list[str], *, timeout_s: int | None = None) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "jobs.prospeccao", *step_args]
    logger.info("[Prospeccao pipeline] %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "step": step_args[0] if step_args else "?",
            "ok": False,
            "exit_code": -1,
            "error": f"timeout after {timeout_s}s",
            "stdout_tail": (exc.stdout or "")[-2000:] if exc.stdout else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if exc.stderr else "",
        }
    ok = proc.returncode == 0
    if not ok:
        logger.error(
            "[Prospeccao pipeline] step %s failed exit=%s stderr=%s",
            step_args[0] if step_args else "?",
            proc.returncode,
            (proc.stderr or "")[-500:],
        )
    return {
        "step": step_args[0] if step_args else "?",
        "ok": ok,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def _run_powershell_pipeline(
    *,
    version: str,
    skip_internal_labels: bool,
    build_limit: int | None,
) -> dict[str, Any]:
    ps1 = _REPO_ROOT / "run_pipeline.ps1"
    if not ps1.is_file():
        return {"ok": False, "error": f"run_pipeline.ps1 not found at {ps1}"}

    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-SkipFetch",
        "-SkipCnefe",
        "-SkipReceita",
        "-Version",
        version,
    ]
    if skip_internal_labels:
        args.append("-SkipInternalLabels")
    if build_limit and build_limit > 0:
        args.extend(["-BuildLimit", str(build_limit)])

    logger.info("[Prospeccao pipeline] invoking %s", " ".join(args))
    proc = subprocess.run(args, cwd=str(_REPO_ROOT), capture_output=True, text=True)
    return {
        "mode": "run_pipeline.ps1",
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-3000:],
    }


def run_scheduled_pipeline() -> dict[str, Any]:
    """Run ingest→normalize→link-crm→build-features→train→score (publish via score-candidates)."""
    version = os.getenv("PROSPECCAO_PIPELINE_VERSION", "prospeccao-ree-v3.2")
    use_internal = os.getenv("PROSPECCAO_PIPELINE_USE_INTERNAL_LABELS", "true").lower() == "true"
    skip_ingest = os.getenv("PROSPECCAO_PIPELINE_SKIP_INGEST", "false").lower() == "true"
    skip_normalize = os.getenv("PROSPECCAO_PIPELINE_SKIP_NORMALIZE", "false").lower() == "true"
    use_ps1 = os.getenv("PROSPECCAO_PIPELINE_USE_PS1", "false").lower() == "true"
    build_limit_raw = os.getenv("PROSPECCAO_PIPELINE_BUILD_LIMIT", "").strip()
    build_limit = int(build_limit_raw) if build_limit_raw.isdigit() and int(build_limit_raw) > 0 else None
    step_timeout = int(os.getenv("PROSPECCAO_PIPELINE_STEP_TIMEOUT_S", "7200"))

    if use_ps1 and sys.platform == "win32":
        return _run_powershell_pipeline(
            version=version,
            skip_internal_labels=not use_internal,
            build_limit=build_limit,
        )

    if use_ps1 and sys.platform != "win32":
        logger.warning("PROSPECCAO_PIPELINE_USE_PS1=true ignored on non-Windows; using Python steps")

    steps_out: list[dict[str, Any]] = []

    def _step(step_args: list[str]) -> bool:
        steps_out.append(_run_cli_step(step_args, timeout_s=step_timeout))
        return bool(steps_out[-1].get("ok"))

    if not skip_ingest:
        harvest_steps = os.getenv(
            "PROSPECCAO_PIPELINE_INGEST_STEPS",
            "ibge,geoportal,ckan_meta,pncp",
        )
        if not _step(["harvest", "--steps", harvest_steps]):
            return {
                "ok": False,
                "mode": "python_cli",
                "version": version,
                "steps": steps_out,
                "short_circuited_after": steps_out[-1].get("step"),
            }

    if not skip_normalize and not _step(["normalize"]):
        return {
            "ok": False,
            "mode": "python_cli",
            "version": version,
            "steps": steps_out,
            "short_circuited_after": steps_out[-1].get("step"),
        }

    if not _step(["link-crm"]):
        return {
            "ok": False,
            "mode": "python_cli",
            "version": version,
            "steps": steps_out,
            "short_circuited_after": steps_out[-1].get("step"),
        }

    if (
        os.getenv("PROSPECCAO_BUILD_ENRICHMENT", "false").lower() == "true"
        and not _step(["build-enrichment"])
    ):
        return {
            "ok": False,
            "mode": "python_cli",
            "version": version,
            "steps": steps_out,
            "short_circuited_after": steps_out[-1].get("step"),
        }

    build_args = ["build-features", "--version", version]
    if use_internal:
        build_args.append("--use-internal-labels")
    if build_limit:
        build_args.extend(["--limit", str(build_limit)])
    if not _step(build_args):
        return {
            "ok": False,
            "mode": "python_cli",
            "version": version,
            "steps": steps_out,
            "short_circuited_after": steps_out[-1].get("step"),
        }

    if not _step(["train-ranker", "--pipeline-version", version]):
        return {
            "ok": False,
            "mode": "python_cli",
            "version": version,
            "steps": steps_out,
            "short_circuited_after": steps_out[-1].get("step"),
        }

    if not _step(["score-candidates"]):
        return {
            "ok": False,
            "mode": "python_cli",
            "version": version,
            "steps": steps_out,
            "short_circuited_after": steps_out[-1].get("step"),
        }

    return {"ok": True, "mode": "python_cli", "version": version, "steps": steps_out}
