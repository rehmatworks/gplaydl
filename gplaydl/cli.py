"""Typer CLI application: link, auth, download, info, search, list-splits."""

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
    AppNotAvailableError,
    AppNotSupportedError,
    AuthExpiredError,
    PlayAPIError,
    get_delivery,
    get_details,
    list_splits as api_list_splits,
    purchase,
    search_apps,
)
from gplaydl.auth import (
    DispenserError,
    clear_auth,
    dispenser_base,
    ensure_auth,
    fetch_token,
    fetch_token_for_profile,
    save_auth,
)
from gplaydl.download import DownloadError, DownloadSpec, download_batch
from gplaydl.onboarding import ensure_linked, link as run_link
from gplaydl.profiles import ABI_TOKENS, get_compat_profiles, get_discovery_profiles

VALID_ARCHS = tuple(ABI_TOKENS) + ("tv",)  # arm64, armv7, x86, x86_64, tv
MAX_COMPAT_RETRIES = 6

console = Console()
err = Console(stderr=True)

app = typer.Typer(
    name="gplaydl",
    help="Download APKs from Google Play using your own linked Google accounts.",
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
    """Download APKs from the Google Play Store."""


# ── link ────────────────────────────────────────────────────────────────────


@app.command()
def link(
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Dispenser to link with."),
    code: Optional[str] = typer.Option(None, "--code", help="Pairing code from the Authenticator app."),
) -> None:
    """Link this machine to the dispenser with a pairing code."""
    run_link(console, dispenser_base(dispenser), code)


# ── auth ────────────────────────────────────────────────────────────────────


@app.command()
def auth(
    arch: str = typer.Option("arm64", help="Device type: arm64, armv7, x86, x86_64 or tv."),
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Custom dispenser URL."),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Pick a specific account by address when you linked several."),
    clear: bool = typer.Option(False, "--clear", help="Remove all cached tokens."),
) -> None:
    """Get an auth token from the dispenser."""
    if clear:
        clear_auth()
        rprint("[green]All cached tokens removed.[/green]")
        raise typer.Exit()

    ensure_linked(console, dispenser)

    rprint(f"[dim]Dispenser:[/dim] {dispenser_base(dispenser)}")
    rprint(f"[dim]Architecture:[/dim] {arch}")
    rprint()

    try:
        with console.status("Rotating through device profiles..."):
            data = fetch_token(dispenser_url=dispenser, arch=arch, email=email)
    except DispenserError as exc:
        _print_dispenser_error(exc, dispenser)
        raise typer.Exit(code=1)

    if not data:
        err.print("[red]Authentication failed. Every device profile was rejected.[/red]")
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
    arch: str = typer.Option(
        "arm64", "--arch", "-a",
        help="Device type: arm64, armv7, x86, x86_64 or tv (Android TV). "
             "Comma-separate to download several at once (e.g. arm64,armv7).",
    ),
    version: Optional[int] = typer.Option(None, "--version", "-v", help="Specific version code."),
    dispenser: Optional[str] = typer.Option(None, "--dispenser", "-d", help="Custom dispenser URL."),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Pick a specific account by address when you linked several."),
    no_splits: bool = typer.Option(False, "--no-splits", help="Skip downloading split APKs."),
    no_extras: bool = typer.Option(False, "--no-extras", help="Skip downloading additional files (OBB, asset packs)."),
    dm: bool = typer.Option(False, "--dm", help="Also download the DEX metadata (.dm) file Play installs with the base APK to speed up first launch."),
) -> None:
    """Download an APK (with splits + additional files) from Google Play."""
    archs = [a.strip() for a in arch.split(",") if a.strip()]
    bad = [a for a in archs if a not in VALID_ARCHS]
    if bad:
        err.print(
            f"[red]Unknown architecture: {', '.join(bad)}. "
            f"Choose from {', '.join(VALID_ARCHS)}.[/red]"
        )
        raise typer.Exit(code=1)

    output.mkdir(parents=True, exist_ok=True)

    specs: dict[str, DownloadSpec] = {}       # dest filename -> spec
    expected: dict[str, int] = {}             # dest filename -> expected bytes
    shown_panel = False
    split_vcs: list[int] = []   # version codes that came with split APKs
    dm_names: dict[int, str] = {}  # version code -> .dm filename

    for arch_item in archs:
        auth_data = _require_auth(arch_item, dispenser, email=email)
        try:
            details, vc, delivery = _acquire(
                package, version, arch_item, auth_data, dispenser, email,
            )
        except PlayAPIError as exc:
            if len(archs) > 1:
                # Keep going: the other architectures may still be available.
                err.print(f"[yellow]{arch_item}: {exc}[/yellow]")
                continue
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

        if not shown_panel:
            if vc == details.version_code and details.version_string:
                ver_line = f"{details.version_string}  (vc {vc})"
            else:
                ver_line = f"vc {vc}"  # pinned to an older version
            rprint(Panel.fit(
                f"[bold]{details.title}[/bold]\n{ver_line}",
                title=package,
            ))
            shown_panel = True
        elif len(archs) > 1:
            rprint(f"[dim]{arch_item}: vc {vc}[/dim]")

        # ── base APK (prefer the gzipped transfer when Play offers it) ──
        base_name = f"{package}-{vc}.apk"
        if base_name not in specs:
            use_gzip = bool(delivery.gzipped_url and delivery.gzipped_size)
            specs[base_name] = DownloadSpec(
                url=delivery.gzipped_url if use_gzip else delivery.download_url,
                dest=output / base_name,
                cookies=delivery.cookies,
                label=base_name,
                gzipped=use_gzip,
                sha256=delivery.sha256,
                sha1=delivery.sha1,
            )
            expected[base_name] = (
                delivery.gzipped_size if use_gzip else delivery.download_size
            )

        if delivery.splits and not no_splits:
            if vc not in split_vcs:
                split_vcs.append(vc)
            for split in delivery.splits:
                name = f"{package}-{vc}-{split.name}.apk"
                if name in specs:
                    continue
                use_gzip = bool(split.gzipped_url and split.gzipped_size)
                specs[name] = DownloadSpec(
                    url=split.gzipped_url if use_gzip else split.url,
                    dest=output / name,
                    label=name,
                    gzipped=use_gzip,
                    sha256=split.sha256,
                )
                expected[name] = split.gzipped_size if use_gzip else split.size

        if dm and delivery.dex_metadata:
            name = f"{package}-{vc}.dm"
            if name not in specs:
                dmeta = delivery.dex_metadata
                specs[name] = DownloadSpec(
                    url=dmeta.url, dest=output / name, label=name,
                    sha256=dmeta.sha256,
                )
                expected[name] = dmeta.size
                dm_names[vc] = name

        if not no_extras and delivery.additional_files:
            for af in delivery.additional_files:
                if af.is_asset_pack:
                    name = f"{package}-{vc}-{af.type_label}{af.extension}"
                else:
                    name = f"{af.type_label}.{af.version_code}.{package}{af.extension}"
                if name in specs:
                    continue
                specs[name] = DownloadSpec(
                    url=af.url, dest=output / name, cookies=af.cookies,
                    label=name, gzipped=af.gzipped,
                )
                expected[name] = af.size

    # ── download ─────────────────────────────────────────────────────────
    all_specs = list(specs.values())
    if not all_specs:
        err.print("[red]Nothing to download: no architecture yielded files.[/red]")
        raise typer.Exit(code=1)
    total_files = len(all_specs)
    file_label = f"{total_files} file{'s' if total_files > 1 else ''}"
    rprint(
        f"\n[bold]Downloading {file_label}[/bold]  "
        f"[dim]({_fmt(sum(expected.values()))} to transfer)[/dim]"
    )
    try:
        download_batch(all_specs)
    except DownloadError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    # ── summary ──────────────────────────────────────────────────────────
    rprint()
    files_table = Table(title="Downloaded files", show_header=True)
    files_table.add_column("File", style="bold")
    files_table.add_column("Size", justify="right")
    for spec in all_specs:
        if spec.dest.exists():
            files_table.add_row(spec.dest.name, _fmt(spec.dest.stat().st_size))
    console.print(files_table)

    if split_vcs:
        # Name the exact files: a bare *.apk would also sweep up any other
        # APKs (or other versions of this app) sitting in the directory,
        # and adb then fails with errors like "Split X defined multiple
        # times" or a base APK conflict.
        rprint("\n[dim]Tip: install split APKs to a device with[/dim]")
        for vc in split_vcs:
            cmd = f"adb install-multiple {package}-{vc}*.apk"
            if vc in dm_names:
                cmd += f" {dm_names[vc]}"
            rprint(f"[dim]  [bold]{cmd}[/bold][/dim]")

    rprint("\n[green bold]Download complete![/green bold]")


# ── helpers ─────────────────────────────────────────────────────────────────


def _acquire(
    package: str,
    version: Optional[int],
    arch: str,
    auth_data: dict,
    dispenser: Optional[str],
    email: Optional[str],
):
    """Details + purchase + delivery, with token refresh and profile fallback.

    Returns (details, version_code, delivery). When Google refuses to serve
    the version to the current device profile (common for old versions),
    retries with profiles ordered for compatibility: low SDK, many ABIs.
    """
    def flow(auth: dict):
        with console.status(f"Fetching details for [bold]{package}[/bold] ({arch})..."):
            details = get_details(package, auth)
        vc = version or details.version_code
        if not vc:
            raise AppNotAvailableError(
                f"{package} has no version available for the {arch} "
                "device profile."
            )
        with console.status("Acquiring app and fetching download URLs..."):
            delivery_token = purchase(package, vc, auth)
            delivery = get_delivery(package, vc, auth, delivery_token)
        return details, vc, delivery

    def retry_with(profiles):
        """Re-run the flow with freshly minted tokens for other profiles."""
        for key, profile in profiles:
            device = profile.get("UserReadableName", key)
            try:
                with console.status(f"Trying device profile [bold]{device}[/bold]..."):
                    retry_auth = fetch_token_for_profile(
                        profile, dispenser_url=dispenser, email=email,
                    )
                if not retry_auth:
                    continue
                result = flow(retry_auth)
                rprint(f"[dim]Served with device profile: {device}[/dim]")
                return result
            except (PlayAPIError, DispenserError):
                continue
        return None

    try:
        try:
            return flow(auth_data)
        except AuthExpiredError:
            auth_data = _require_auth(arch, dispenser, force=True, email=email)
            return flow(auth_data)
    except AppNotAvailableError as exc:
        # Invisible to this device: maybe a form-factor exclusive (Android
        # TV) or limited to another ABI family. Try one device of each kind.
        rprint(
            "[yellow]Not visible to the current device profile; trying "
            "other device types (TV, other ABIs)...[/yellow]"
        )
        result = retry_with(get_discovery_profiles(arch))
        if result:
            return result
        raise AppNotAvailableError(
            f"{package} was not served to any device profile. It may not "
            "exist, or it may be paid or unavailable in the account's region."
        ) from exc
    except AppNotSupportedError as exc:
        rprint(
            "[yellow]This version is not served to the default device "
            "profile; retrying with compatible profiles...[/yellow]"
        )
        result = retry_with(get_compat_profiles(arch)[:MAX_COMPAT_RETRIES])
        if result:
            return result
        raise exc


def _require_auth(
    arch: str,
    dispenser: Optional[str],
    *,
    force: bool = False,
    email: Optional[str] = None,
) -> dict:
    """Return auth dict or exit with a helpful error."""
    ensure_linked(console, dispenser)
    try:
        data = ensure_auth(
            arch=arch, dispenser_url=dispenser, force_refresh=force, email=email,
        )
    except DispenserError as exc:
        _print_dispenser_error(exc, dispenser)
        raise typer.Exit(code=1)
    if not data:
        err.print(
            "[red]Could not obtain an auth token. "
            "Try running [bold]gplaydl auth[/bold] first.[/red]"
        )
        raise typer.Exit(code=1)
    return data


def _print_dispenser_error(exc: DispenserError, dispenser: Optional[str]) -> None:
    """Show the dispenser's refusal, plus the way out when we know it."""
    err.print(f"[red]{exc.message}[/red]")
    if exc.status == 401 and dispenser:
        err.print(
            f"[dim]No key is stored for this dispenser. Link it with "
            f"[bold]gplaydl link -d {dispenser_base(dispenser)}[/bold][/dim]"
        )


def _fmt(size_bytes: int | float) -> str:
    """Format bytes as a human-readable string (decimal units, like the
    progress bars, so the summary matches what was shown while downloading)."""
    if not size_bytes:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1000:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1000
    return f"{size_bytes:.1f} TB"
