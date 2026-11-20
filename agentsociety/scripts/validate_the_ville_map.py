#!/usr/bin/env python3
"""Validate the bundled The Ville map package against original source semantics."""

from pathlib import Path

if __package__:
    from . import validate_pixel_town_map
else:
    import validate_pixel_town_map


def validate_manifest(manifest_path: Path, matrix_root: Path | None = None) -> list[str]:
    return validate_pixel_town_map.validate_manifest(manifest_path, matrix_root, require_the_ville=True)


def main() -> int:
    return validate_pixel_town_map.main(require_the_ville=True)


if __name__ == "__main__":
    raise SystemExit(main())
