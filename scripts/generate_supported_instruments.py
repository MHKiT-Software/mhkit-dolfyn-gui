"""Generate supported_instruments.json by inspecting mhkit.dolfyn source.

DOLFyN does not expose a single registry of supported file extensions or
instruments — it dispatches by magic-byte sniffing in
`mhkit.dolfyn.io.api._get_filetype` and identifies instruments inside each
reader. This script extracts everything it can directly from the live
DOLFyN source code so the generated JSON tracks upstream changes:

  * Magic bytes      → parsed from `_get_filetype` source
  * File extensions  → parsed from `dolfyn.read()` docstring
  * Nortek model IDs → parsed from `nortek.py` (serial-number prefixes,
                       inst_type / inst_model assignments)
  * Signature type   → parsed from `nortek2.py` (inst_type assignment)
  * RDI model table  → read live from `rdi_defs.adcp_type`

If DOLFyN's internals change, this script will either pick up the change
automatically or fail loudly. Re-run it whenever upgrading mhkit.

Usage:
    python scripts/generate_supported_instruments.py

Output:
    src/mhkit_dolfyn_gui/data/supported_instruments.json
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import mhkit
from mhkit.dolfyn.io import api as dolfyn_api
from mhkit.dolfyn.io import nortek as dolfyn_nortek
from mhkit.dolfyn.io import nortek2 as dolfyn_nortek2
from mhkit.dolfyn.io import rdi_defs

OUTPUT = (
    Path(__file__).parent.parent
    / "src"
    / "mhkit_dolfyn_gui"
    / "data"
    / "supported_instruments.json"
)

# Extra RDI extensions produced by post-processing tools (VMDAS, WinRiver).
# DOLFyN's _get_filetype dispatches by magic bytes so any of these are
# accepted, but they aren't enumerated anywhere in the source. Listed here
# explicitly so the source of every extension is auditable.
RDI_POSTPROCESS_EXTENSIONS = [".enx", ".ens", ".lta", ".sta"]

# Classic-Nortek (magic byte 0xa505) serial-prefix -> real-world file
# extension. DOLFyN dispatches by magic bytes only and never enumerates
# per-instrument extensions in source, so this table cannot be parsed out of
# DOLFyN - it's sourced externally from Nortek's own file-format docs
# (Nortek Support Center FAQ; IMOS toolbox Nortek parser wiki) and must be
# extended by hand if DOLFyN adds another classic-Nortek serial prefix.
EXTENSION_BY_PREFIX = {
    "WPR": ".wpr",  # AWAC
    "VEC": ".vec",  # Vector
    "AQD": ".aqd",  # Aquadopp (single-point current meter)
    "PRF": ".prf",  # Aquadopp Profiler
}

# DOLFyN's own inst_model ("Aquadopp") doesn't distinguish the Profiler
# variant even though it's a different file type on disk - override the
# display name per serial prefix where that matters.
NAME_OVERRIDE_BY_PREFIX = {"PRF": "Aquadopp Profiler"}


def extract_magic_bytes() -> dict[str, list[str]]:
    """Parse `_get_filetype` source for which hex codes map to which reader.

    Returns mapping of reader-tag → list of hex code strings.
    Tag is whatever `_get_filetype` returns ('RDI', 'signature', 'nortek').
    """
    src = inspect.getsource(dolfyn_api._get_filetype)
    # Match: code in [ ... ]: ... return "..."
    pattern = re.compile(
        r'code\s+in\s+\[([^\]]+)\].*?return\s+"([^"]+)"',
        re.DOTALL,
    )
    out: dict[str, list[str]] = {}
    for codes_blob, tag in pattern.findall(src):
        codes = [f"0x{c.strip().strip(chr(34)).strip(chr(39))}" for c in codes_blob.split(",")]
        out[tag] = codes
    if not out:
        raise RuntimeError("Failed to parse magic bytes from _get_filetype source")
    return out


def extract_extensions_from_docstring() -> list[str]:
    """Pull file extensions from the `dolfyn.read()` docstring."""
    doc = dolfyn_api.read.__doc__ or ""
    # Match full .xxx tokens at word boundaries (so we don't truncate
    # .userdata to .userda or .dataset to .datase).
    raw = re.findall(r"\.([A-Za-z0-9]+)\b", doc)
    # Filter to plausible extensions (2-5 chars) and drop internal/non-ext words.
    bad = {"json", "etc", "userdata", "dataset"}
    exts = sorted({f".{e.lower()}" for e in raw if 2 <= len(e) <= 5 and e.lower() not in bad})
    if not exts:
        raise RuntimeError("Failed to extract extensions from dolfyn.read docstring")
    return exts


def extract_nortek_classic_models() -> list[dict[str, object]]:
    """Parse nortek.py for serial-prefix → instrument mappings.

    The classic Nortek reader checks the serial number prefix to decide
    which instrument produced the file, then assigns `self._inst` and calls
    `init_<_inst>()`. A single `_inst` value can be reached from more than
    one serial prefix (e.g. Aquadopp and Aquadopp Profiler both set
    `self._inst = "AQD"` via `in ["AQD", "PRF"]`), so each match expands to
    one instrument entry per prefix.
    """
    src = inspect.getsource(dolfyn_nortek)

    # Find: serial_number[0:3].upper() == "XXX" / in ["XXX", "YYY"] → self._inst = "NAME"
    prefix_pattern = re.compile(
        r'serial_number"\]\[0:3\]\.upper\(\)\s*'
        r'(?:==\s*"([A-Z]{3})"|in\s*\[([^\]]+)\])\s*:\s*\n'
        r'\s*self\._inst\s*=\s*"([A-Za-z]+)"',
    )
    prefix_matches = prefix_pattern.findall(src)
    if not prefix_matches:
        raise RuntimeError("Failed to parse Nortek serial-prefix checks")

    # For each init_<NAME> method, find the inst_type / inst_model strings.
    init_info: dict[str, dict[str, str]] = {}
    for match in re.finditer(
        r"def\s+(init_[A-Za-z]+)\s*\(self.*?(?=\n    def |\nclass |\Z)",
        src,
        re.DOTALL,
    ):
        name = match.group(1)
        block = match.group(0)
        inst_type = re.search(r'da\["inst_type"\]\s*=\s*"([^"]+)"', block)
        inst_model = re.search(r'da\["inst_model"\]\s*=\s*"([^"]+)"', block)
        init_info[name] = {
            "inst_type": inst_type.group(1) if inst_type else "",
            "inst_model": inst_model.group(1) if inst_model else "",
        }

    instruments: list[dict[str, object]] = []
    for single_prefix, prefix_list, inst in prefix_matches:
        prefixes = (
            [single_prefix]
            if single_prefix
            else [p.strip().strip("\"'") for p in prefix_list.split(",")]
        )
        info = init_info.get(f"init_{inst}", {})
        for prefix in prefixes:
            extension = EXTENSION_BY_PREFIX.get(prefix)
            if extension is None:
                raise RuntimeError(
                    f"No known file extension for Nortek serial prefix {prefix!r}. "
                    "DOLFyN doesn't enumerate extensions (magic-byte dispatch only) "
                    "- add it to EXTENSION_BY_PREFIX after checking Nortek's own "
                    "file-format documentation."
                )
            # A per-prefix override (e.g. "Aquadopp Profiler") wins over the
            # inst_model string from init_*() (e.g. "Vector"), since DOLFyN's
            # inst_model doesn't distinguish variants that share one _inst.
            name = NAME_OVERRIDE_BY_PREFIX.get(prefix) or info.get("inst_model") or inst
            instruments.append(
                {
                    "manufacturer": "Nortek",
                    "name": name,
                    "type": info.get("inst_type") or inst,
                    "model": info.get("inst_model") or inst,
                    "serial_prefix": prefix,
                    "extensions": [extension],
                    "reader": "read_nortek",
                }
            )
    return instruments


def extract_signature_inst_type() -> str:
    """Parse nortek2.py for the hardcoded Signature inst_type."""
    src = inspect.getsource(dolfyn_nortek2)
    match = re.search(r'\["inst_type"\]\s*=\s*"([^"]+)"', src)
    if not match:
        raise RuntimeError("Failed to parse Signature inst_type from nortek2.py")
    return match.group(1)


def main() -> None:
    magic = extract_magic_bytes()
    doc_extensions = extract_extensions_from_docstring()
    nortek_classic = extract_nortek_classic_models()
    signature_type = extract_signature_inst_type()
    rdi_models = sorted(set(rdi_defs.adcp_type.values()))

    # Assemble instruments. Each entry carries provenance for traceability.
    instruments: list[dict] = []

    # Nortek Signature (ad2cp) — inst_type from nortek2.py source
    instruments.append(
        {
            "manufacturer": "Nortek",
            "name": "Signature",
            "type": signature_type,
            "extensions": [".ad2cp"],
            "reader": "read_signature",
            "magic_bytes": magic.get("signature", []),
            "provenance": {
                "inst_type": "mhkit.dolfyn.io.nortek2 (parsed)",
                "magic_bytes": "mhkit.dolfyn.io.api._get_filetype (parsed)",
                "extensions": "dolfyn.read.__doc__ (parsed)",
            },
        }
    )

    # Nortek classic (Vector, AWAC, Aquadopp, Aquadopp Profiler) — parsed from nortek.py
    for inst in nortek_classic:
        inst["magic_bytes"] = magic.get("nortek", [])
        inst["provenance"] = {
            "name_and_type": "mhkit.dolfyn.io.nortek (parsed serial-prefix and init_*)",
            "magic_bytes": "mhkit.dolfyn.io.api._get_filetype (parsed)",
            "extensions": (
                "external: Nortek Support Center / IMOS toolbox docs "
                "(DOLFyN dispatches by magic bytes only and never enumerates "
                "per-instrument extensions in source; see EXTENSION_BY_PREFIX)"
            ),
        }
        instruments.append(inst)

    # Teledyne RDI — model list from rdi_defs.adcp_type
    instruments.append(
        {
            "manufacturer": "Teledyne RDI",
            "name": "ADCP",
            "type": "ADCP",
            "extensions": sorted(
                {e for e in doc_extensions if e in {".000", ".pd0", ".enx"}}
                | set(RDI_POSTPROCESS_EXTENSIONS)
            ),
            "reader": "read_rdi",
            "magic_bytes": magic.get("RDI", []),
            "models": rdi_models,
            "provenance": {
                "models": "mhkit.dolfyn.io.rdi_defs.adcp_type (live)",
                "magic_bytes": "mhkit.dolfyn.io.api._get_filetype (parsed)",
                "extensions": (
                    "dolfyn.read.__doc__ (parsed) + RDI_POSTPROCESS_EXTENSIONS "
                    "(VMDAS/WinRiver outputs, not enumerated upstream)"
                ),
            },
        }
    )

    all_extensions = sorted({ext for inst in instruments for ext in inst["extensions"]})

    payload = {
        "generated_from": f"mhkit {mhkit.__version__}",
        "note": (
            "DOLFyN dispatches readers by magic-byte sniffing, not by file "
            "extension. This file is generated from DOLFyN source by "
            "scripts/generate_supported_instruments.py — do not edit by hand. "
            "Each instrument carries a 'provenance' field describing where "
            "in DOLFyN each value was extracted."
        ),
        "all_extensions": all_extensions,
        "all_extensions_from_docstring": doc_extensions,
        "magic_bytes": magic,
        "instruments": instruments,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUTPUT}")
    print(f"  mhkit version: {mhkit.__version__}")
    print(f"  {len(instruments)} instruments, {len(all_extensions)} extensions")
    print(f"  RDI models: {len(rdi_models)}")
    print(f"  magic bytes: {magic}")
    print(f"  doc extensions: {doc_extensions}")


if __name__ == "__main__":
    main()
