from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from app_automate.cli._shared import (
    app,
    load_profile_describer,
    load_training_api,
    profile_path,
    run_train_review,
)
from app_automate.config.validation import load_profile


def _validate_profile_checks(profile_path_arg: Path) -> list[str]:
    warnings: list[str] = []
    try:
        loaded = load_profile(profile_path_arg)
    except Exception as exc:
        return [f"FATAL: {exc}"]

    if loaded.type == "semantic":
        if not loaded.backend:
            warnings.append("semantic profile missing 'backend' field")
        if not loaded.semantic_elements:
            warnings.append("semantic profile has no semantic_elements")
        seen_aliases: dict[str, str] = {}
        for eid, el in loaded.semantic_elements.items():
            if el.action.value == "shortcut" and el.shortcut is None:
                warnings.append(
                    f"element '{eid}' has action=shortcut but no shortcut definition"
                )
            if el.action.value == "type" and not el.role and not el.selector:
                warnings.append(
                    f"element '{eid}' has action=type but no role or selector"
                )
            for alias in el.aliases:
                lower = alias.lower()
                if lower in seen_aliases:
                    warnings.append(
                        f"duplicate alias '{alias}' in elements "
                        f"'{seen_aliases[lower]}' and '{eid}'"
                    )
                seen_aliases[lower] = eid
        for sname, sdef in loaded.shortcuts.items():
            if not sdef.keys.strip():
                warnings.append(f"shortcut '{sname}' has empty keys")
    else:
        if not loaded.elements and not loaded.states:
            warnings.append("visual profile has no elements or states")
        if loaded.elements and loaded.anchors is None:
            warnings.append("visual profile with elements but no anchors")

    return warnings


@app.command("validate")
def validate_profile(
    profile: Annotated[
        Path,
        typer.Argument(help="Path to a profile directory or profile JSON file."),
    ],
) -> None:
    p = profile_path(profile)
    if not p.exists():
        typer.echo(f"Profile not found: {p}", err=True)
        raise typer.Exit(code=1)
    warnings = _validate_profile_checks(p)
    if not warnings:
        typer.echo(f"OK: {p} is valid")
        return
    has_fatal = any(w.startswith("FATAL") for w in warnings)
    for w in warnings:
        typer.echo(f"  {w}", err=True)
    typer.echo(f"\n{len(warnings)} issue(s) found in {p}", err=True)
    raise typer.Exit(code=1 if has_fatal else 2)


@app.command("train")
def train(
    screenshot: Annotated[
        Path | None,
        typer.Option(
            "--screenshot",
            help=(
                "Optional path to an existing screenshot. Captures the main "
                "display if omitted."
            ),
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            help=(
                "Capture and crop the front window of an app "
                "by name (macOS or Windows)."
            ),
        ),
    ] = None,
    settings: Annotated[
        Path | None,
        typer.Option(
            "--settings",
            help="Path to app-automate settings TOML.",
        ),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory for generated training assets.",
        ),
    ] = Path("examples/profiles/new-profile"),
    grid_size: Annotated[
        int | None,
        typer.Option(
            "--grid-size",
            min=40,
            help="Grid cell size in pixels for the numbered overlay.",
        ),
    ] = None,
    run_llm: Annotated[
        bool,
        typer.Option(
            "--run-llm/--skip-llm",
            help="Call the configured LLM and save a generated profile.",
        ),
    ] = True,
    review: Annotated[
        bool,
        typer.Option(
            "--review/--no-review",
            help="Prompt for manual anchor review after LLM training completes.",
        ),
    ] = False,
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help=(
                "Build a semantic profile from a live accessibility backend "
                "instead of the visual/LLM path. Use 'uia', 'cdp', or 'atspi'."
            ),
        ),
    ] = None,
) -> None:
    if backend is not None:
        if not app_name and backend == "uia":
            typer.echo("--app is required with --backend uia", err=True)
            raise typer.Exit(code=1)
        try:
            from app_automate.builder.semantic_profile import build_semantic_profile

            path = build_semantic_profile(
                app_name=app_name or "",
                backend=backend,
                output_dir=output_dir,
            )
        except Exception as exc:
            typer.echo(f"train failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Saved semantic profile: {path}")
        return
    try:
        create_training_bundle, _ = load_training_api()
        bundle = create_training_bundle(
            output_dir=output_dir,
            screenshot_path=screenshot,
            app_name=app_name,
            settings_path=settings,
            grid_size=grid_size,
            run_llm=run_llm,
        )
    except Exception as exc:
        typer.echo(f"train failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Saved screenshot: {bundle.screenshot_path}")
    typer.echo(f"Saved grid overlay: {bundle.grid_path}")
    typer.echo(f"Saved prompt input: {bundle.prompt_path}")
    if bundle.llm_output_path is not None:
        typer.echo(f"Saved LLM output: {bundle.llm_output_path}")
    if bundle.profile_path is not None:
        typer.echo(f"Saved profile: {bundle.profile_path}")
    if bundle.review_path is not None:
        typer.echo(f"Saved anchor review: {bundle.review_path}")
    if bundle.review_image_path is not None:
        typer.echo(f"Saved anchor review image: {bundle.review_image_path}")
    if review and run_llm:
        run_train_review(
            bundle=bundle,
            output_dir=output_dir,
            settings_path=settings,
        )


@app.command("inspect")
def inspect_profile(
    profile: Annotated[
        Path,
        typer.Argument(help="Path to a profile directory or profile JSON file."),
    ],
) -> None:
    loaded = load_profile(profile_path(profile))
    if loaded.type == "semantic":
        typer.echo(f"Profile: {loaded.profile_id} (semantic, backend={loaded.backend})")
        typer.echo(f"App: {loaded.app_name}")
        typer.echo(f"Elements: {len(loaded.semantic_elements)}")
        typer.echo("")
        for eid, el in sorted(loaded.semantic_elements.items()):
            parts = [f"  {eid}: {el.label} [{el.action.value}]"]
            if el.role:
                parts.append(f"role={el.role}")
            if el.automation_id:
                parts.append(f"automation_id={el.automation_id}")
            if el.selector:
                parts.append(f"selector={el.selector}")
            typer.echo(" ".join(parts))
        return
    describe_profile = load_profile_describer()
    typer.echo(describe_profile(loaded))


@app.command("list-elements")
def list_elements(
    profile: Annotated[
        Path,
        typer.Argument(help="Path to a profile directory or profile JSON file."),
    ],
) -> None:
    loaded = load_profile(profile_path(profile))
    if loaded.type == "semantic":
        for eid, el in sorted(loaded.semantic_elements.items()):
            typer.echo(f"{eid}: {el.label} [{el.action.value}]")
        return
    for element_id, element in sorted(loaded.elements.items()):
        typer.echo(f"{element_id}: {element.label} [{element.layout.value}]")
