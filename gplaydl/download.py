"""File download with httpx (async) and Rich progress bars."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import zlib
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


class DownloadError(Exception):
    """A file arrived broken (hash mismatch with what Google Play declared)."""
    pass


@dataclass
class DownloadSpec:
    """Everything needed to download a single file."""
    url: str
    dest: Path
    cookies: list[dict] = field(default_factory=list)
    label: str = ""
    gzipped: bool = False
    # Expected digests as Play reports them: base64url without padding.
    # The digest is of the final file (after gzip decompression).
    sha256: str = ""
    sha1: str = ""


def _b64_digest(hasher) -> str:
    return base64.urlsafe_b64encode(hasher.digest()).decode().rstrip("=")


def _file_digest(path: Path, sha256: bool) -> str:
    """Hash an existing file, returning the Play-style base64url digest."""
    hasher = hashlib.sha256() if sha256 else hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return _b64_digest(hasher)


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

        # Skip files that are already present and verify against the digest
        # Play declared -- this is what makes re-runs (e.g. to add another
        # architecture or language) download only what is missing.
        expected = (spec.sha256 or spec.sha1).rstrip("=")
        if expected and spec.dest.exists():
            digest = await asyncio.to_thread(
                _file_digest, spec.dest, bool(spec.sha256),
            )
            if digest == expected:
                size = spec.dest.stat().st_size
                progress.add_task(
                    "download", filename=f"{label} [dim](already downloaded)[/dim]",
                    total=size, completed=size,
                )
                return spec.dest

        task_id = progress.add_task("download", filename=label, total=None)

        decompressor = (
            zlib.decompressobj(zlib.MAX_WBITS | 16) if spec.gzipped else None
        )

        if spec.sha256:
            hasher, expected = hashlib.sha256(), spec.sha256
        elif spec.sha1:
            hasher, expected = hashlib.sha1(), spec.sha1
        else:
            hasher, expected = None, ""

        async with client.stream("GET", spec.url, headers=headers) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            if total:
                progress.update(task_id, total=total)

            with open(spec.dest, "wb") as f:

                def write(data: bytes) -> None:
                    f.write(data)
                    if hasher:
                        hasher.update(data)

                async for chunk in resp.aiter_bytes(chunk_size=CHUNK_SIZE):
                    if decompressor:
                        write(decompressor.decompress(chunk))
                    else:
                        write(chunk)
                    progress.advance(task_id, len(chunk))

                if decompressor:
                    remaining = decompressor.flush()
                    if remaining:
                        write(remaining)

        if hasher:
            actual = _b64_digest(hasher)
            if actual != expected.rstrip("="):
                raise DownloadError(
                    f"{spec.dest.name} failed integrity verification: Google "
                    f"Play declared {expected} but the download hashed to "
                    f"{actual}. Delete the file and try again."
                )

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
    """Public sync entry point: download all files in parallel."""
    asyncio.run(_run_downloads(specs))
