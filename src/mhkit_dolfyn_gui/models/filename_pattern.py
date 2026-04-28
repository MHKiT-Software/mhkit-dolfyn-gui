"""Filename template parsing and rendering for export.

Supports tokens:
    {filename} / {stem}       - Original filename without extension
    {start_date:%Y%m%d}      - Start date with strftime format
    {end_date:%Y%m%d}        - End date with strftime format
    {index:03d}              - File index (1-based) with optional format spec
    {profile}                - Profile number (1-based) for multi-profile files
"""

from __future__ import annotations

import re
import string
from datetime import datetime

DEFAULT_TEMPLATE = "{filename}_{start_date:%Y%m%d}.nc"

# Tokens we recognize in the template
VALID_TOKENS = frozenset({"filename", "stem", "start_date", "end_date", "index", "profile"})

# Regex to find all {token} or {token:format} references
_TOKEN_RE = re.compile(r"\{(\w+)(?::([^}]*))?\}")


class _DateFormatter:
    """Wrapper so that format(obj, spec) calls strftime."""

    def __init__(self, dt: datetime | None) -> None:
        self._dt = dt

    def __format__(self, spec: str) -> str:
        if self._dt is None:
            return "no-date"
        if not spec:
            return self._dt.strftime("%Y%m%d")
        return self._dt.strftime(spec)

    def __str__(self) -> str:
        return format(self, "")


class FilenamePattern:
    """Parse and render filename templates."""

    def __init__(self, template: str) -> None:
        self.template = template

    def render(
        self,
        *,
        filename: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        index: int = 1,
        profile: int = 1,
    ) -> str:
        """Render the template with the given values.

        Returns the rendered filename string (without directory).
        """
        mapping: dict[str, object] = {
            "filename": filename,
            "stem": filename,
            "start_date": _DateFormatter(start_date),
            "end_date": _DateFormatter(end_date),
            "index": index,
            "profile": profile,
        }
        try:
            formatter = string.Formatter()
            return formatter.vformat(self.template, (), mapping)
        except (KeyError, ValueError, IndexError) as exc:
            return f"INVALID_PATTERN ({exc})"

    def validate(self) -> list[str]:
        """Return a list of error messages. Empty list means valid."""
        errors: list[str] = []

        # Check for unknown tokens
        for match in _TOKEN_RE.finditer(self.template):
            token_name = match.group(1)
            if token_name not in VALID_TOKENS:
                errors.append(f"Unknown token: {{{token_name}}}")

        # Check that the template can be rendered without error
        test_result = self.render(
            filename="test",
            start_date=datetime(2024, 1, 15, 8, 0, 0),
            end_date=datetime(2024, 1, 16, 12, 30, 0),
            index=1,
            profile=1,
        )
        if test_result.startswith("INVALID_PATTERN"):
            errors.append(test_result)

        # Check that result ends with .nc
        if not test_result.endswith(".nc"):
            errors.append("Filename must end with .nc")

        return errors

    @staticmethod
    def default() -> FilenamePattern:
        return FilenamePattern(DEFAULT_TEMPLATE)


# Preset patterns: (display_label, template_string)
PATTERN_PRESETS: list[tuple[str, str]] = [
    ("Original name + date", "{filename}_{start_date:%Y%m%d}.nc"),
    ("Original name only", "{filename}.nc"),
    ("Date range", "{start_date:%Y%m%d}_{end_date:%Y%m%d}.nc"),
]
