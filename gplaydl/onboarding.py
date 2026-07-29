"""First-run setup: linking this machine to a dispenser.

gplaydl downloads through Google accounts you add yourself in the Authenticator
app, so setup is: add an account, then link this machine. Linking hands this
machine an API key in exchange for the one-time pairing code the app shows.
"""

from __future__ import annotations

import platform
import sys
from typing import Optional

import httpx
import typer
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from gplaydl.auth import (
    DEFAULT_DISPENSER,
    DispenserError,
    api_key_for,
    dispenser_base,
    save_link,
)


def ensure_linked(console: Console, dispenser_url: Optional[str] = None) -> None:
    """Walk a new user through linking before their first dispense.

    Runs only when the target dispenser is the linked or default one and no
    key exists for it yet. Someone pointing -d at a server we hold no key for
    gets a clean refusal from that server instead of a wizard for it.
    """
    if dispenser_url:
        return
    base = dispenser_base()
    if api_key_for(base):
        return

    if not _interactive():
        console.print(
            "[red]This machine is not linked to the dispenser yet.[/red] "
            "Run [bold]gplaydl link[/bold] in a terminal once, or set "
            "GPLAYDL_API_KEY. Setup takes about two minutes:"
        )
        console.print(_steps_text(base))
        raise typer.Exit(code=1)

    link(console, base, first_run=True)


def link(
    console: Console,
    base: Optional[str] = None,
    code: Optional[str] = None,
    first_run: bool = False,
) -> None:
    """Show the setup steps, claim a pairing code, and store the key."""
    base = base or dispenser_base()

    console.print()
    console.print(_walkthrough_panel(console, base, first_run))
    console.print()

    attempts = 3
    while True:
        if not code:
            try:
                code = Prompt.ask("[bold]Pairing code[/bold]", console=console)
            except (EOFError, KeyboardInterrupt):
                console.print()
                raise typer.Exit(code=1)
        code = code.strip()
        if not code:
            continue
        try:
            api_key = _claim(base, code)
        except DispenserError as exc:
            attempts -= 1
            code = None
            if attempts <= 0:
                console.print(f"[red]{exc.message}[/red]")
                raise typer.Exit(code=1)
            console.print(
                f"[red]{exc.message}[/red] Codes are single-use and expire "
                "after ten minutes; generate a fresh one in the app."
            )
            continue
        except httpx.HTTPError as exc:
            console.print(f"[red]Could not reach {base}: {exc}[/red]")
            raise typer.Exit(code=1)
        break

    path = save_link(base, api_key)
    console.print(
        f"\n[bold green]Linked.[/bold green] This machine can now download "
        f"through {base}.\n[dim]Key saved to {path}[/dim]\n"
    )


def _claim(base: str, code: str) -> str:
    """Trade a pairing code for this machine's own API key."""
    resp = httpx.post(
        base + "/api/v1/pair/claim-cli",
        json={"code": code, "label": _label()},
        timeout=30,
    )
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code != 200 or not body.get("apiKey"):
        raise DispenserError(
            resp.status_code,
            body.get("error") or f"dispenser returned HTTP {resp.status_code}",
        )
    return body["apiKey"]


def _label() -> str:
    # Shows up in the dispenser as the name of this linked machine.
    return (platform.node() or "gplaydl")[:64]


def _walkthrough_panel(console: Console, base: str, first_run: bool) -> Panel:
    intro = (
        "gplaydl downloads through a Google account you add yourself. "
        "Setting up takes a spare account and about two minutes:"
        if first_run
        else "Linking replaces any key this machine already holds:"
    )
    return Panel(
        Group(intro, "", _steps_table(base)),
        title="[bold]Set up gplaydl[/bold]" if first_run else "[bold]Link gplaydl[/bold]",
        title_align="left",
        border_style="bright_black",
        box=box.ROUNDED,
        padding=(1, 2),
        width=min(74, console.width),
    )


def _steps_table(base: str) -> Table:
    steps = Table(box=None, show_header=False, padding=(0, 1))
    steps.add_column(style="bold cyan", justify="right", width=1)
    steps.add_column()
    steps.add_row("1", f"Install the Authenticator app on any Android phone: [bold cyan]{base}[/bold cyan]")
    steps.add_row("2", "Sign in with a spare Google account. It stays private to you; add more than one and pick between them later with --email.")
    steps.add_row("3", "Open [bold]Link gplaydl[/bold] in the app and type the code here.")
    return steps


def _steps_text(base: str) -> str:
    return (
        f"  1. Install the Authenticator app on any Android phone: {base}\n"
        "  2. Sign in with a spare Google account (it stays private to you).\n"
        "  3. Open Link gplaydl in the app and run gplaydl link with the code."
    )


def _interactive() -> bool:
    # Both directions have to be a terminal: the wizard prints a panel and
    # reads a code back.
    return sys.stdin.isatty() and sys.stdout.isatty()
