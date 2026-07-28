"""The occasional reminder that the token pool runs on donated accounts."""

from __future__ import annotations

import os
import time

from rich import box
from rich.console import Console
from rich.panel import Panel

from gplaydl.auth import CONFIG_DIR

DISPENSER_URL = "https://dispenser.gplaydl.com"

# Rare enough to stay welcome. Someone who downloads every day still only
# reads this a handful of times a year.
_INTERVAL = 7 * 24 * 60 * 60
_STAMP = CONFIG_DIR / "last-banner"


def show_banner(console: Console) -> None:
    """Invite the reader to share a spare account, at most once a week."""
    # Ask the stream directly. rich reports is_terminal as true whenever
    # FORCE_COLOR is set to anything at all, including "0", which would put
    # the banner into piped output.
    isatty = getattr(console.file, "isatty", None)
    if os.environ.get("GPLAYDL_NO_BANNER") or not (isatty and isatty()):
        return
    if not _is_due():
        return
    _mark_shown()

    console.print()
    console.print(
        Panel(
            "Every anonymous download borrows a Google account that somebody "
            "chose to share. If you have a throwaway account to spare, adding "
            "it to the pool takes about two minutes.\n\n"
            f"[bold cyan]{DISPENSER_URL}[/bold cyan]",
            title="[bold]Keep gplaydl anonymous[/bold]",
            title_align="left",
            subtitle="[dim]GPLAYDL_NO_BANNER=1 to hide this[/dim]",
            subtitle_align="right",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
            # Let the prose reflow rather than run past a narrow terminal.
            width=min(70, console.width),
        )
    )


def _is_due() -> bool:
    try:
        return time.time() - _STAMP.stat().st_mtime > _INTERVAL
    except OSError:
        return True  # never shown, or the stamp is unreadable


def _mark_shown() -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _STAMP.touch()
    except OSError:
        pass  # a read-only home should never break a download
