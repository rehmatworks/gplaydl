"""The ask for spare accounts: the full pitch once, a nudge now and then."""

from __future__ import annotations

import os
import time

from rich import box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from gplaydl.auth import CONFIG_DIR

DISPENSER_URL = "https://dispenser.gplaydl.com"

# Rare enough to stay welcome. Someone who downloads every day still only
# reads this a handful of times a year.
_INTERVAL = 7 * 24 * 60 * 60
_STAMP = CONFIG_DIR / "last-banner"


def show_banner(console: Console) -> None:
    """Invite the reader to share a spare account.

    Newcomers get the walkthrough, because the first download is when it
    lands: they have just seen the thing work and know what the pool bought
    them. Everyone else gets a one-liner at most once a week.
    """
    # Ask the stream directly. rich reports is_terminal as true whenever
    # FORCE_COLOR is set to anything at all, including "0", which would put
    # the banner into piped output.
    isatty = getattr(console.file, "isatty", None)
    if os.environ.get("GPLAYDL_NO_BANNER") or not (isatty and isatty()):
        return

    first_run = not _STAMP.exists()
    if not first_run and not _is_due():
        return
    _mark_shown()

    console.print()
    console.print(_panel(
        _walkthrough() if first_run else _nudge(),
        "Somebody lent you a Google account" if first_run
        else "Keep gplaydl anonymous",
        console,
    ))


def _walkthrough() -> RenderableType:
    steps = Table(box=None, show_header=False, padding=(0, 1))
    steps.add_column(style="bold cyan", justify="right", width=1)
    steps.add_column()
    steps.add_row("1", f"Install the Authenticator app from [bold cyan]{DISPENSER_URL}[/bold cyan]")
    steps.add_row("2", "Sign in with a throwaway Google account, never your real one")
    steps.add_row("3", "Turn sharing on for it")

    return Group(
        "That download signed in as a Google account somebody chose to share, "
        "so you never had to hand over one of your own.",
        "",
        "The pool only holds what people put in it. Adding an account takes "
        "about two minutes:",
        "",
        steps,
        "",
        "[dim]Nothing to set up on this end. The pool starts handing your "
        "account out on its own, and you can pull it back whenever you like."
        "[/dim]",
    )


def _nudge() -> RenderableType:
    return Group(
        "Every anonymous download borrows a Google account that somebody chose "
        "to share. If you have a throwaway account to spare, adding it to the "
        "pool takes about two minutes.",
        "",
        f"[bold cyan]{DISPENSER_URL}[/bold cyan]",
    )


def _panel(body: RenderableType, title: str, console: Console) -> Panel:
    return Panel(
        body,
        title=f"[bold]{title}[/bold]",
        title_align="left",
        subtitle="[dim]GPLAYDL_NO_BANNER=1 to hide this[/dim]",
        subtitle_align="right",
        border_style="bright_black",
        box=box.ROUNDED,
        padding=(1, 2),
        # Let the prose reflow rather than run past a narrow terminal.
        width=min(74, console.width),
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
