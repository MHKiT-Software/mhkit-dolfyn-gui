"""Summary template model with YAML persistence.

Templates define which fields appear in the summary card's two columns.
Each field is a DSL path (resolved by ``field_resolver``) plus a display label.
"""

from __future__ import annotations

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SummaryField:
    """A single field in a summary template."""

    path: str
    label: str


@dataclass
class SummaryTemplate:
    """A named template with left and right column fields.

    *mode* is ``"per_file"`` (default) or ``"combined"``.
    """

    name: str
    left: list[SummaryField] = field(default_factory=list)
    right: list[SummaryField] = field(default_factory=list)
    mode: str = "per_file"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "columns": {
                "left": [{"path": f.path, "label": f.label} for f in self.left],
                "right": [{"path": f.path, "label": f.label} for f in self.right],
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SummaryTemplate:
        columns = data.get("columns", {})
        return cls(
            name=data.get("name", "Untitled"),
            left=[SummaryField(**f) for f in columns.get("left", [])],
            right=[SummaryField(**f) for f in columns.get("right", [])],
            mode=data.get("mode", "per_file"),
        )


def load_template(path: Path) -> SummaryTemplate:
    """Load a template from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return SummaryTemplate.from_dict(data)


def save_template(template: SummaryTemplate, path: Path) -> None:
    """Save a template to a YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(template.to_dict(), f, default_flow_style=False, sort_keys=False)


def get_default_template() -> SummaryTemplate:
    """Load the bundled default template from package resources."""
    try:
        ref = importlib.resources.files("mhkit_dolfyn_gui.config").joinpath("default_summary.yaml")
        with importlib.resources.as_file(ref) as p:
            return load_template(p)
    except Exception:
        # Hardcoded fallback if resource loading fails
        return SummaryTemplate(
            name="Default",
            left=[
                SummaryField("computed.instrument", "Instrument"),
                SummaryField("attr.serial_number", "Serial"),
                SummaryField("attr.coord_sys", "Coord System"),
                SummaryField("attr.fs", "Sampling Freq"),
                SummaryField("computed.bins_beams", "Bins / Beams"),
            ],
            right=[
                SummaryField("coord.time.first", "Start"),
                SummaryField("coord.time.last", "End"),
                SummaryField("computed.duration", "Duration"),
                SummaryField("computed.ensembles", "Ensembles"),
                SummaryField("file.name", "Filename"),
            ],
        )


def get_user_templates_dir() -> Path:
    """Return the user templates directory, creating it if needed."""
    d = Path.home() / ".mhkit-dolfyn-gui" / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_default_combined_template() -> SummaryTemplate:
    """Load the bundled default combined template from package resources."""
    try:
        ref = importlib.resources.files("mhkit_dolfyn_gui.config").joinpath(
            "default_combined_summary.yaml"
        )
        with importlib.resources.as_file(ref) as p:
            return load_template(p)
    except Exception:
        return SummaryTemplate(
            name="Default Combined",
            mode="combined",
            left=[
                SummaryField("combined.files_loaded", "Files Loaded"),
                SummaryField("computed.instrument", "Instrument"),
                SummaryField("attr.coord_sys", "Coord System"),
                SummaryField("attr.fs", "Sampling Freq"),
            ],
            right=[
                SummaryField("combined.earliest_start", "Earliest Start"),
                SummaryField("combined.latest_end", "Latest End"),
                SummaryField("combined.total_duration", "Total Duration"),
                SummaryField("combined.total_ensembles", "Total Ensembles"),
            ],
        )


def _load_bundled_templates() -> list[SummaryTemplate]:
    """Load all non-default YAML templates bundled in the config package."""
    results: list[SummaryTemplate] = []
    skip = {"default_summary.yaml", "default_combined_summary.yaml"}
    try:
        pkg = importlib.resources.files("mhkit_dolfyn_gui.config")
        for entry in pkg.iterdir():
            name = entry.name
            if not name.endswith(".yaml") or name in skip:
                continue
            try:
                data = yaml.safe_load(entry.read_text())
                results.append(SummaryTemplate.from_dict(data))
            except Exception:
                continue
    except Exception:
        pass
    return results


def list_templates(
    mode: str | None = None,
) -> list[tuple[str, Path | SummaryTemplate | None]]:
    """Return available templates as ``(name, path-or-template)`` pairs.

    - Bundled default: ``(name, None)``
    - Other bundled templates: ``(name, SummaryTemplate)``
    - User templates on disk: ``(name, Path)``

    When *mode* is given, only templates matching that mode are returned.
    """
    if mode == "combined":
        templates: list[tuple[str, Path | SummaryTemplate | None]] = [("Default Combined", None)]
    else:
        templates = [("Default", None)]

    for t in sorted(_load_bundled_templates(), key=lambda t: t.name):
        if mode is not None and t.mode != mode:
            continue
        templates.append((t.name, t))

    user_dir = get_user_templates_dir()
    for p in sorted(user_dir.glob("*.yaml")):
        try:
            t = load_template(p)
            if mode is not None and t.mode != mode:
                continue
            templates.append((t.name, p))
        except Exception:
            continue

    return templates
