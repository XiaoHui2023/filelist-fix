from __future__ import annotations

import logging
import subprocess
from time import perf_counter


class SearchFailure(RuntimeError):
    """A search failed; its result must not be treated as a definition miss."""


def run_search(command: list[str]) -> subprocess.CompletedProcess[str]:
    started = perf_counter()
    status = "failed"
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", check=False, timeout=120)
        if result.returncode not in (0, 1):
            raise SearchFailure(f"definition search failed ({result.returncode}): {command[0]}; {result.stderr.strip()}")
        status = "ok"
        return result
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SearchFailure(f"definition search failed: {command[0]}; {exc}") from exc
    finally:
        logging.getLogger("filelist_fix").info("locate tool=%s status=%s elapsed=%.6fs root=%s",
                                              command[0], status, perf_counter()-started, command[-1])
