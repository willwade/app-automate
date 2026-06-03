from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from app_automate.cli._shared import (
    app,
    create_action_adapter,
    load_runner_actions,
    load_runtime_api,
    profile_path,
    runtime_context,
    write_debug_outputs,
)
from app_automate.config.validation import load_profile


@app.command("dry-run")
def dry_run(
    command: Annotated[
        str,
        typer.Argument(help="Natural language element name or alias."),
    ],
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help="Optional full-screen screenshot path for anchor detection.",
        ),
    ] = None,
    primary_x: Annotated[
        float | None,
        typer.Option("--primary-x", help="Live primary anchor x-coordinate."),
    ] = None,
    primary_y: Annotated[
        float | None,
        typer.Option("--primary-y", help="Live primary anchor y-coordinate."),
    ] = None,
    secondary_x: Annotated[
        float | None,
        typer.Option("--secondary-x", help="Live secondary anchor x-coordinate."),
    ] = None,
    secondary_y: Annotated[
        float | None,
        typer.Option("--secondary-y", help="Live secondary anchor y-coordinate."),
    ] = None,
) -> None:
    loaded = load_profile(profile_path(profile))
    if loaded.type == "semantic":
        from app_automate.runner.runtime import dry_run_semantic_command

        result = dry_run_semantic_command(command, loaded)
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    context = runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=primary_x,
        primary_y=primary_y,
        secondary_x=secondary_x,
        secondary_y=secondary_y,
    )
    _, _, dry_run_command, _ = load_runtime_api()
    result = dry_run_command(command, context)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@app.command("click")
def click(
    command: Annotated[
        str,
        typer.Argument(help="Natural language element name or alias."),
    ],
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help="Optional full-screen screenshot path for anchor detection.",
        ),
    ] = None,
    primary_x: Annotated[
        float | None,
        typer.Option("--primary-x", help="Live primary anchor x-coordinate."),
    ] = None,
    primary_y: Annotated[
        float | None,
        typer.Option("--primary-y", help="Live primary anchor y-coordinate."),
    ] = None,
    secondary_x: Annotated[
        float | None,
        typer.Option("--secondary-x", help="Live secondary anchor x-coordinate."),
    ] = None,
    secondary_y: Annotated[
        float | None,
        typer.Option("--secondary-y", help="Live secondary anchor y-coordinate."),
    ] = None,
    text: Annotated[
        str | None,
        typer.Option("--text", help="Text to type for semantic type actions."),
    ] = None,
) -> None:
    loaded = load_profile(profile_path(profile))
    if loaded.type == "semantic":
        from app_automate.runner.runtime import execute_semantic_command

        result = execute_semantic_command(command, loaded, text=text)
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    context = runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=primary_x,
        primary_y=primary_y,
        secondary_x=secondary_x,
        secondary_y=secondary_y,
    )
    _, _, dry_run_command, _ = load_runtime_api()
    result = dry_run_command(command, context)
    adapter = create_action_adapter()
    click_resolved_command = load_runner_actions()
    click_resolved_command(adapter, result)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@app.command("locate-anchors")
def locate_anchors(
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help=(
                "Optional full-screen screenshot path. Captures the main "
                "display if omitted."
            ),
        ),
    ] = None,
) -> None:
    context = runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=None,
        primary_y=None,
        secondary_x=None,
        secondary_y=None,
    )
    _, _, _, summarize_detected_anchors = load_runtime_api()
    typer.echo(json.dumps(summarize_detected_anchors(context).model_dump(), indent=2))


@app.command("debug-target")
def debug_target(
    command: Annotated[
        str,
        typer.Argument(help="Natural language element name or alias."),
    ],
    profile: Annotated[
        Path,
        typer.Option(
            "--profile", help="Path to a profile directory or profile JSON file."
        ),
    ] = Path("examples/profiles/camera-demo/profile.json"),
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help=(
                "Optional full-screen screenshot path. Captures the main "
                "display if omitted."
            ),
        ),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory for annotated debug images.",
        ),
    ] = Path("debug-output"),
    primary_x: Annotated[
        float | None,
        typer.Option("--primary-x", help="Live primary anchor x-coordinate."),
    ] = None,
    primary_y: Annotated[
        float | None,
        typer.Option("--primary-y", help="Live primary anchor y-coordinate."),
    ] = None,
    secondary_x: Annotated[
        float | None,
        typer.Option("--secondary-x", help="Live secondary anchor x-coordinate."),
    ] = None,
    secondary_y: Annotated[
        float | None,
        typer.Option("--secondary-y", help="Live secondary anchor y-coordinate."),
    ] = None,
) -> None:
    context = runtime_context(
        profile=profile,
        screenshot=screenshot,
        primary_x=primary_x,
        primary_y=primary_y,
        secondary_x=secondary_x,
        secondary_y=secondary_y,
    )
    _, _, dry_run_command, summarize_detected_anchors = load_runtime_api()
    result = dry_run_command(command, context)
    overlay_path, window_path = write_debug_outputs(
        context=context,
        result=result,
        output_dir=output_dir,
    )

    payload = {
        "result": result.model_dump(mode="json"),
        "overlay_path": str(overlay_path),
        "window_path": str(window_path) if window_path is not None else None,
        "anchors": summarize_detected_anchors(context).model_dump(mode="json"),
    }
    typer.echo(json.dumps(payload, indent=2))
