"""Support references without exception messages, document data or local paths."""

from importlib.metadata import PackageNotFoundError, version
import logging
from pathlib import Path
import platform
import sys
from uuid import uuid4

BUILD = "v1-guided-review-frontmatter"
BASE = Path(__file__).resolve().parents[1]
logger = logging.getLogger("doclint")


def record_failure(exc, phase):
    reference = "DL-" + uuid4().hex[:12].upper()
    frames = []
    traceback = exc.__traceback__
    while traceback:
        code = traceback.tb_frame.f_code
        try:
            relative = Path(code.co_filename).resolve().relative_to(BASE)
        except ValueError:
            pass
        else:
            if relative.parts[0] in {"v1", "core"}:
                frames.append(
                    {
                        "file": relative.as_posix(),
                        "function": code.co_name,
                        "line": traceback.tb_lineno,
                    }
                )
        traceback = traceback.tb_next
    packages = {}
    for name in ("lxml", "pypdfium2", "Pillow", "fastapi"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not_installed"
    detail = {
        "reference": reference,
        "build": BUILD,
        "phase": phase,
        "exception": type(exc).__name__,
        "frames": frames[-8:],
        "runtime": {
            "python": platform.python_version(),
            "platform": sys.platform,
            "packages": packages,
        },
    }
    if isinstance(exc, OSError):
        detail["os_error"] = {
            key: value
            for key in ("errno", "winerror")
            if isinstance((value := getattr(exc, key, None)), int)
        }
    logger.error(
        "DocLint failure reference=%s phase=%s exception=%s frames=%s os_error=%s",
        reference,
        phase,
        detail["exception"],
        detail["frames"],
        detail.get("os_error", {}),
    )
    return detail
