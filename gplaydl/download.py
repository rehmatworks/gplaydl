"""File download with httpx (async) and Rich progress bars."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import httpx
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
MAX_CONCURRENT = 4


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


@dataclass
class DownloadSpec:
    """Everything needed to download a single file."""
    url: str
    dest: Path
    cookies: list[dict] = field(default_factory=list)
    label: str = ""


async def _download_one(
    spec: DownloadSpec,
    client: httpx.AsyncClient,
    progress: Progress,
    sem: asyncio.Semaphore,
) -> Path:
    """Stream-download a single file with progress tracking."""
    async with sem:
        headers: dict[str, str] = {}
        if spec.cookies:
            parts = [f"{c['name']}={c['value']}" for c in spec.cookies]
            headers["Cookie"] = "; ".join(parts)

        label = spec.label or spec.dest.name
        task_id = progress.add_task("download", filename=label, total=None)

        async with client.stream("GET", spec.url, headers=headers) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            if total:
                progress.update(task_id, total=total)

            with open(spec.dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
                    progress.advance(task_id, len(chunk))

    return spec.dest


async def _run_downloads(specs: list[DownloadSpec]) -> None:
    """Download all files in parallel (up to MAX_CONCURRENT at once)."""
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    timeout = httpx.Timeout(connect=15.0, read=300.0, write=30.0, pool=30.0)
    progress = make_progress()

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True,
    ) as client:
        with progress:
            await asyncio.gather(
                *[_download_one(s, client, progress, sem) for s in specs],
            )


def download_batch(specs: list[DownloadSpec]) -> None:
    """Public sync entry point — download all files in parallel."""
    asyncio.run(_run_downloads(specs))
