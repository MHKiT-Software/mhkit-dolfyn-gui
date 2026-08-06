"""
Extract version and release info for GitHub Actions workflows.

Usage:
    python scripts/release_info.py --ref <git_ref> --event <event_name> --run <run_number>

Outputs GitHub Actions format to stdout (append to $GITHUB_OUTPUT).
"""

import argparse
from pathlib import Path

# Global application name - used across all workflows
APP_NAME = "MHKiT-DOLFyN"


def get_version() -> str:
    """Get version from src package _version.py (pyproject.toml uses dynamic versioning)."""
    version_file = Path(__file__).parent.parent / "src" / "mhkit_dolfyn_gui" / "_version.py"
    namespace: dict = {}
    exec(version_file.read_text(encoding="utf-8"), namespace)
    return namespace["__version__"]


def get_release_info(ref: str, event_name: str, run_number: str) -> dict:
    """Determine release info based on git ref and event."""
    version = get_version()

    is_main = ref == "refs/heads/main"
    is_develop = ref == "refs/heads/develop"
    is_push = event_name == "push"

    # Determine tag and release name
    # Use space in display name for readability
    display_name = APP_NAME.replace("-", " ")
    if is_main:
        tag_name = f"v{version}"
        release_name = f"{display_name} {version}"
    else:
        tag_name = f"v{version}-pre.{run_number}"
        release_name = f"{display_name} {version} (Prerelease {run_number})"

    # Determine release type
    is_release = is_push and is_main
    is_prerelease = is_push and is_develop

    return {
        "app_name": APP_NAME,
        "version": version,
        "tag_name": tag_name,
        "release_name": release_name,
        "is_release": str(is_release).lower(),
        "is_prerelease": str(is_prerelease).lower(),
    }


def main():
    parser = argparse.ArgumentParser(description="Get release info for GitHub Actions")
    parser.add_argument("--ref", required=True, help="Git ref (e.g., refs/heads/main)")
    parser.add_argument("--event", required=True, help="GitHub event name (e.g., push)")
    parser.add_argument("--run", required=True, help="GitHub run number")
    args = parser.parse_args()

    info = get_release_info(args.ref, args.event, args.run)

    # Output in GitHub Actions format
    for key, value in info.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
