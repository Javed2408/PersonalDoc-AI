"""Crash-safe JSON file writes."""

import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path: Path, payload: object) -> None:
    """Write JSON to a temp file and rename it into place, so readers never see a partial file.

    Raises OSError on failure; the original file (if any) is left untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(payload, tmp, indent=2)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
