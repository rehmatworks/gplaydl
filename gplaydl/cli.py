"""Typer CLI application — auth, download, info, search, list-splits."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gplaydl import __version__
from gplaydl.api import (
    AuthExpiredError,
    PlayAPIError,
    get_delivery,
    get_details,
    list_splits as api_list_splits,
    purchase,
    search_apps,
)
from gplaydl.auth import (
    clear_auth,
    ensure_auth,
    fetch_token,
    load_cached_auth,
    save_auth,
)
from gplaydl.download import DownloadSpec, download_batch

console = Console()
err = Console(stderr=True)

app = typer.Typer(
    name="gplaydl",
    help="Download APKs from Google Play Store with anonymous authentication.",
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        rprint(f"gplaydl [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """GPlay APK Downloader — download APKs from Google Play Store."""


# ── auth ────────────────────────────────────────────────────────────────────


@app.command()
def auth(
    arch: str = typer.Option("arm64", help="Architecture: arm64 or armv7."),
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Custom dispenser URL."),
    clear: bool = typer.Option(False, "--clear", help="Remove all cached tokens."),
) -> None:
    """Acquire an anonymous auth token from the dispenser."""
    if clear:
        clear_auth()
        rprint("[green]All cached tokens removed.[/green]")
        raise typer.Exit()

    rprint(f"[dim]Dispenser:[/dim] {dispenser or 'https://auroraoss.com/api/auth'}")
    rprint(f"[dim]Architecture:[/dim] {arch}")
    rprint()

    with console.status("Rotating through device profiles..."):
        data = fetch_token(dispenser_url=dispenser, arch=arch)

    if not data:
        err.print("[red]Authentication failed — all profiles rejected.[/red]")
        raise typer.Exit(code=1)

    path = save_auth(data, arch)
    rprint(Panel.fit(
        f"[bold green]Authenticated[/bold green]\n"
        f"Email  : {data.get('email', 'N/A')}\n"
        f"GSF ID : {data.get('gsfId', 'N/A')}\n"
        f"Saved  : {path}",
        title="Token",
    ))


# ── info ────────────────────────────────────────────────────────────────────


@app.command()
def info(
    package: str = typer.Argument(..., help="Package name (e.g. com.whatsapp)."),
    arch: str = typer.Option("arm64", help="Architecture for token."),
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Custom dispenser URL."),
) -> None:
    """Show app details from Google Play."""
    auth_data = _require_auth(arch, dispenser)

    with console.status(f"Fetching details for [bold]{package}[/bold]..."):
        try:
            try:
                details = get_details(package, auth_data)
            except AuthExpiredError:
                auth_data = _require_auth(arch, dispenser, force=True)
                details = get_details(package, auth_data)
        except PlayAPIError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

    table = Table(title=details.title or package, show_header=False, title_style="bold")
    table.add_column("Field", style="dim")
    table.add_column("Value")
    table.add_row("Package", details.package)
    table.add_row("Version", f"{details.version_string} ({details.version_code})")
    table.add_row("Developer", details.developer or "N/A")
    table.add_row("Rating", details.rating or "N/A")
    table.add_row("Downloads", details.downloads or "N/A")
    table.add_row("Play Store", details.play_url)
    console.print(table)


# ── search ──────────────────────────────────────────────────────────────────


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results."),
    arch: str = typer.Option("arm64", help="Architecture for token."),
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Custom dispenser URL."),
) -> None:
    """Search for apps on Google Play."""
    auth_data = _require_auth(arch, dispenser)

    with console.status(f"Searching for [bold]{query}[/bold]..."):
        try:
            try:
                results = search_apps(query, auth_data, limit=limit)
            except AuthExpiredError:
                auth_data = _require_auth(arch, dispenser, force=True)
                results = search_apps(query, auth_data, limit=limit)
        except PlayAPIError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

    if not results:
        rprint("[yellow]No results found.[/yellow]")
        raise typer.Exit()

    table = Table(title=f"Results for \"{query}\"")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold")
    table.add_column("Package")
    for i, app_item in enumerate(results, 1):
        table.add_row(str(i), app_item["title"], app_item["package"])
    console.print(table)


# ── list-splits ─────────────────────────────────────────────────────────────


@app.command("list-splits")
def list_splits_cmd(
    package: str = typer.Argument(..., help="Package name."),
    arch: str = typer.Option("arm64", help="Architecture for token."),
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Custom dispenser URL."),
) -> None:
    """List available split APKs for an app."""
    auth_data = _require_auth(arch, dispenser)

    with console.status(f"Fetching splits for [bold]{package}[/bold]..."):
        try:
            try:
                splits = api_list_splits(package, auth_data)
            except AuthExpiredError:
                auth_data = _require_auth(arch, dispenser, force=True)
                splits = api_list_splits(package, auth_data)
        except PlayAPIError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

    if not splits:
        rprint(f"[yellow]{package} has no split APKs.[/yellow]")
        raise typer.Exit()

    table = Table(title=f"Splits for {package}")
    table.add_column("#", style="dim", width=4)
    table.add_column("Split name")
    for i, name in enumerate(splits, 1):
        table.add_row(str(i), name)
    console.print(table)
    rprint(f"\n[dim]Total: {len(splits)} splits[/dim]")


# ── download ────────────────────────────────────────────────────────────────


@app.command()
def download(
    package: str = typer.Argument(..., help="Package name (e.g. com.whatsapp)."),
    output: Path = typer.Option(".", "--output", "-o", help="Output directory."),
    arch: str = typer.Option("arm64", "--arch", "-a", help="Architecture: arm64 or armv7."),
    version: Optional[int] = typer.Option(None, "--version", "-v", help="Specific version code."),
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Custom dispenser URL."),
    no_splits: bool = typer.Option(False, "--no-splits", help="Skip downloading split APKs."),
    no_extras: bool = typer.Option(False, "--no-extras", help="Skip downloading additional files (OBB, asset packs)."),
) -> None:
    """Download an APK (with splits + additional files) from Google Play."""
    auth_data = _require_auth(arch, dispenser)
    output.mkdir(parents=True, exist_ok=True)

    # ── details + purchase + delivery (with auto-retry on expired token) ─
    try:
        try:
            with console.status(f"Fetching details for [bold]{package}[/bold]..."):
                details = get_details(package, auth_data)
            vc = version or details.version_code
            with console.status("Acquiring app and fetching download URLs..."):
                purchase(package, vc, auth_data)
                delivery = get_delivery(package, vc, auth_data)
        except AuthExpiredError:
            auth_data = _require_auth(arch, dispenser, force=True)
            with console.status(f"Fetching details for [bold]{package}[/bold]..."):
                details = get_details(package, auth_data)
            vc = version or details.version_code
            with console.status("Acquiring app and fetching download URLs..."):
                purchase(package, vc, auth_data)
                delivery = get_delivery(package, vc, auth_data)
    except PlayAPIError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    rprint(Panel.fit(
        f"[bold]{details.title}[/bold]\n"
        f"{details.version_string}  (vc {vc})",
        title=package,
    ))

    # ── build download specs ────────────────────────────────────────────
    base_name = f"{package}-{vc}.apk"
    base_path = output / base_name
    base_spec = DownloadSpec(
        url=delivery.download_url, dest=base_path,
        cookies=delivery.cookies, label=base_name,
    )

    extras: list[DownloadSpec] = []
    if delivery.splits and not no_splits:
        for split in delivery.splits:
            name = f"{package}-{vc}-{split.name}.apk"
            extras.append(DownloadSpec(url=split.url, dest=output / name, label=name))
    if not no_extras and delivery.additional_files:
        for af in delivery.additional_files:
            if af.is_asset_pack:
                name = f"{package}-{vc}-{af.type_label}{af.extension}"
            else:
                name = f"{af.type_label}.{af.version_code}.{package}{af.extension}"
            extras.append(DownloadSpec(
                url=af.url, dest=output / name, cookies=af.cookies,
                label=name, gzipped=af.gzipped,
            ))

    all_specs = [base_spec] + extras
    total_files = len(all_specs)
    total_size = delivery.download_size + sum(s.size for s in delivery.splits if not no_splits)
    if not no_extras:
        total_size += sum(af.size for af in delivery.additional_files)
    file_label = f"{total_files} file{'s' if total_files > 1 else ''}"
    rprint(f"\n[bold]Downloading {file_label}[/bold]  [dim]({_fmt(total_size)})[/dim]")
    download_batch(all_specs)

    # ── summary ──────────────────────────────────────────────────────────
    rprint()
    files_table = Table(title="Downloaded files", show_header=True)
    files_table.add_column("File", style="bold")
    files_table.add_column("Size", justify="right")
    files_table.add_row(base_name, _fmt(base_path.stat().st_size))

    if delivery.splits and not no_splits:
        for split in delivery.splits:
            sp = output / f"{package}-{vc}-{split.name}.apk"
            if sp.exists():
                files_table.add_row(sp.name, _fmt(sp.stat().st_size))

    if not no_extras and delivery.additional_files:
        for af in delivery.additional_files:
            if af.is_asset_pack:
                fname = f"{package}-{vc}-{af.type_label}{af.extension}"
            else:
                fname = f"{af.type_label}.{af.version_code}.{package}{af.extension}"
            ap = output / fname
            if ap.exists():
                files_table.add_row(ap.name, _fmt(ap.stat().st_size))

    console.print(files_table)

    if delivery.splits and not no_splits:
        rprint(
            "\n[dim]Tip: install split APKs to a device with "
            "[bold]adb install-multiple *.apk[/bold][/dim]"
        )

    rprint("\n[green bold]Download complete![/green bold]")


# ── helpers ─────────────────────────────────────────────────────────────────


def _require_auth(arch: str, dispenser: Optional[str], *, force: bool = False) -> dict:
    """Return auth dict or exit with a helpful error."""
    data = ensure_auth(arch=arch, dispenser_url=dispenser, force_refresh=force)
    if not data:
        err.print(
            "[red]Could not obtain an auth token. "
            "Try running [bold]gplaydl auth[/bold] first.[/red]"
        )
        raise typer.Exit(code=1)
    return data


def _fmt(size_bytes: int | float) -> str:
    """Format bytes as a human-readable string."""
    if not size_bytes:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
