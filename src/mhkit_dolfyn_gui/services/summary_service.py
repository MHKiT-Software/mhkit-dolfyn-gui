"""Pure resolution of summary templates against datasets.

The widget layer (``SummaryCard``) is responsible only for rendering the
returned rows into a Qt layout. Field resolution itself is a pure function
of (template, data) and lives here so it can be unit-tested without Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from mhkit_dolfyn_gui.models.field_resolver import resolve_combined_field, resolve_field

if TYPE_CHECKING:
    import xarray as xr

    from mhkit_dolfyn_gui.models.file_item import FileItem
    from mhkit_dolfyn_gui.models.summary_template import SummaryField, SummaryTemplate


Column = Literal["left", "right"]


@dataclass(frozen=True)
class ResolvedRow:
    """A single rendered row of a summary template."""

    column: Column
    field: SummaryField
    value: str


def resolve_template(
    template: SummaryTemplate,
    ds: xr.Dataset | None,
    file_item: FileItem | None,
    items: list[FileItem] | None = None,
) -> list[ResolvedRow]:
    """Resolve every field in *template* and return rows in display order.

    When *items* is provided (combined mode), each field is resolved against
    the full list via ``resolve_combined_field``. Otherwise fields are
    resolved against *ds* / *file_item* via ``resolve_field``.

    Pure: no Qt, no I/O.
    """
    rows: list[ResolvedRow] = []
    columns: tuple[tuple[Column, list[SummaryField]], ...] = (
        ("left", template.left),
        ("right", template.right),
    )
    for column, fields in columns:
        for sf in fields:
            if items is not None:
                value = resolve_combined_field(items, sf.path)
            elif ds is not None:
                value = resolve_field(ds, sf.path, file_item)
            else:
                value = "N/A"
            rows.append(ResolvedRow(column=column, field=sf, value=value))
    return rows
