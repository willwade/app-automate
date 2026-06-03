from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from app_automate.cli._shared import app


@app.command("extract-shortcuts")
def extract_shortcuts(
    app_name: Annotated[
        str,
        typer.Argument(help="Application name to extract shortcuts for."),
    ],
    source: Annotated[
        str,
        typer.Option(
            "--source",
            help=(
                "Extraction source: auto, desktop, gnome-wm, "
                "atspi-menu, uia-menu, ax-menu, file."
            ),
        ),
    ] = "auto",
    shortcuts_file: Annotated[
        Path | None,
        typer.Option(
            "--shortcuts-file",
            help="Path to a JSON/TXT shortcuts file (for source=file).",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json/--text", help="Output format."),
    ] = False,
    save: Annotated[
        Path | None,
        typer.Option("--save", help="Save extracted shortcuts to a JSON file."),
    ] = None,
) -> None:
    try:
        from app_automate.shortcuts import (
            ExtractedShortcut,
            extract_all,
            extract_from_atspi_menus,
            extract_from_ax_menu_items,
            extract_from_desktop_file,
            extract_from_gnome_wm,
            extract_from_shortcuts_file,
            extract_from_uia_accelerators,
        )

        results: list[ExtractedShortcut] = []

        if source == "auto":
            results = extract_all(app_name)
        elif source == "desktop":
            results = extract_from_desktop_file(app_name)
        elif source == "gnome-wm":
            results = extract_from_gnome_wm()
        elif source == "atspi-menu":
            results = extract_from_atspi_menus(app_name)
        elif source == "uia-menu":
            results = extract_from_uia_accelerators(app_name)
        elif source == "ax-menu":
            results = extract_from_ax_menu_items(app_name)
        elif source == "file":
            if shortcuts_file is None:
                typer.echo("--shortcuts-file is required with --source file", err=True)
                raise typer.Exit(code=1)
            results = extract_from_shortcuts_file(shortcuts_file)
        else:
            typer.echo(f"unknown source: {source}", err=True)
            raise typer.Exit(code=1)

        if not results:
            typer.echo(f"No shortcuts found for '{app_name}' via {source}")
            return

        if save:
            data = {}
            for s in results:
                data[s.action] = s.to_definition().model_dump()
            save.parent.mkdir(parents=True, exist_ok=True)
            save.write_text(json.dumps(data, indent=2))
            typer.echo(f"Saved {len(results)} shortcuts to {save}")

        if as_json:
            output = [
                {
                    "action": s.action,
                    "keys": s.keys,
                    "source": s.source,
                    "description": s.description,
                    "platform": s.platform,
                }
                for s in results
            ]
            typer.echo(json.dumps(output, indent=2))
            return

        typer.echo(f"Found {len(results)} shortcuts:\n")
        for s in results:
            plat = f" [{s.platform}]" if s.platform else ""
            typer.echo(f"  {s.action:<40} {s.keys:<25} ({s.source}){plat}")
    except Exception as exc:
        typer.echo(f"extract-shortcuts failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
