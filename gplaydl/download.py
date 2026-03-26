"""File download with Rich progress bars."""

from __future__ import annotations

from pathlib import Path

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

CHUNK_SIZE = 64 * 1024  # 64 KB


def make_progress() -> Progress:
    """Create a pre-configured Rich progress bar for downloads."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.fields[filename]}"),
        BarColumn(bar_width=30),
        "[progress.percentage]{task.percentage:>3.0f}%",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )


def download_file(
    url: str,
    dest: Path,
    cookies: list[dict] | None = None,
    filename_label: str | None = None,
    progress: Progress | None = None,
) -> Path:
    """Stream-download a file with an optional Rich progress bar.

    If *progress* is provided the caller manages start/stop; otherwise a
    standalone progress context is created for this single file.
    """
    headers: dict[str, str] = {}
    if cookies:
        parts = [f"{c['name']}={c['value']}" for c in cookies]
        headers["Cookie"] = "; ".join(parts)

    resp = requests.get(url, headers=headers, stream=True, timeout=(15, 300))
    resp.raise_for_status()

    total = int(resp.headers.get("Content-Length", 0))
    label = filename_label or dest.name

    own_progress = progress is None
    if own_progress:
        progress = make_progress()

    task_id = progress.add_task("download", filename=label, total=total or None)

    ctx = progress if own_progress else _noop_ctx(progress)
    with ctx:
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    progress.advance(task_id, len(chunk))

    return dest


class _noop_ctx:
    """No-op context manager so we can unify code paths."""

    def __init__(self, obj):
        self._obj = obj

    def __enter__(self):
        return self._obj

    def __exit__(self, *_):
        pass
