"""
Static Worker — executes a scrape_portal.py script in a sandboxed subprocess.
Returns SuccessPayload on success or ErrorPayload on failure.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from pathlib import Path
from typing import Union

from config import settings
from app.schemas import ErrorPayload, SuccessPayload

# Wrapper that runs the scrape script and serialises its output to stdout as JSON.
_RUNNER_TEMPLATE = textwrap.dedent("""\
    import sys, json, time, traceback
    sys.path.insert(0, {script_dir!r})

    start = time.time()
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("scrape_portal", {script_path!r})
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        data = mod.run()
        duration_ms = int((time.time() - start) * 1000)
        result = {{
            "ok": True,
            "data": data,
            "confidence_raw": data.get("_confidence_raw", 1.0),
            "selectors_used": data.get("_selectors_used", []),
            "duration_ms": duration_ms,
        }}
    except Exception as exc:
        result = {{
            "ok": False,
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "last_selector": getattr(exc, "selector", ""),
            "screenshot_b64": "",
            "html_snapshot": "",
        }}
    print(json.dumps(result))
""")


def _run_subprocess(script_path: Path, timeout: int) -> dict:
    runner_code = _RUNNER_TEMPLATE.format(
        script_dir=str(script_path.parent),
        script_path=str(script_path),
    )
    result = subprocess.run(
        [sys.executable, "-c", runner_code],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0 and not result.stdout.strip():
        return {
            "ok": False,
            "error_type": "SubprocessError",
            "traceback": result.stderr,
            "last_selector": "",
            "screenshot_b64": "",
            "html_snapshot": "",
        }
    return json.loads(result.stdout.strip())


def execute(
    script_path: Path,
    retries: int = settings.scrape_max_retries,
    timeout: int = settings.scrape_timeout_seconds,
) -> Union[SuccessPayload, ErrorPayload]:
    last_error: dict | None = None

    for attempt in range(retries + 1):
        try:
            raw = _run_subprocess(script_path, timeout)
        except subprocess.TimeoutExpired:
            last_error = {
                "ok": False,
                "error_type": "TimeoutExpired",
                "traceback": f"Script exceeded {timeout}s hard timeout.",
                "last_selector": "",
                "screenshot_b64": "",
                "html_snapshot": "",
            }
            # Timeout is not a transient network error — stop retrying
            break
        except Exception as exc:
            last_error = {
                "ok": False,
                "error_type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "last_selector": "",
                "screenshot_b64": "",
                "html_snapshot": "",
            }
            break

        if raw.get("ok"):
            return SuccessPayload(
                data=raw["data"],
                confidence_raw=raw.get("confidence_raw", 1.0),
                selectors_used=raw.get("selectors_used", []),
                duration_ms=raw.get("duration_ms", 0),
            )

        last_error = raw
        # Retry only on likely transient network errors
        if raw["error_type"] not in ("ConnectionError", "TimeoutError", "ReadTimeout"):
            break

    return ErrorPayload(
        error_type=last_error["error_type"],
        traceback=last_error["traceback"],
        last_selector=last_error.get("last_selector", ""),
        screenshot_b64=last_error.get("screenshot_b64", ""),
        html_snapshot=last_error.get("html_snapshot", ""),
    )
