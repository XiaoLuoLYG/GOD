#!/usr/bin/env python3
"""Upload GOD public site download packs to a GitHub Release.

The static site should link to release asset URLs while the ZIP files stay out of
Git. This script reads those URLs from docs/site, finds matching local ZIP files,
validates the archives, and uploads them with gh release upload.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile


DEFAULT_RELEASE_TAG = "public-site-packs"
MAX_RELEASE_ASSET_BYTES = 2 * 1024 * 1024 * 1024
RELEASE_URL_RE = re.compile(
    r"https://github\.com/(?P<repo>[^/]+/[^/]+)/releases/download/"
    r"(?P<tag>[^/]+)/(?P<asset>[^\"'()<>\s]+?\.zip)"
)
SCAN_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".txt", ".yaml", ".yml"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path("docs/site"))
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=Path("docs/site/public-data"),
        help="Local generated public-data tree that still contains ignored downloads/*.zip files.",
    )
    parser.add_argument("--repo", help="GitHub repo owner/name. Defaults to the repo found in site URLs.")
    parser.add_argument("--tag", help=f"Release tag. Defaults to {DEFAULT_RELEASE_TAG} or the tag found in site URLs.")
    parser.add_argument("--title", default="GOD public site packs")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the upload plan without uploading.")
    parser.add_argument(
        "--staging-dir",
        type=Path,
        help="Copy or rebuild clean release ZIPs here before validation/upload.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Only list missing local files instead of failing. Useful for CI/link audits.",
    )
    args = parser.parse_args()

    site_root = args.site_root.resolve()
    asset_root = args.asset_root.resolve()
    references = collect_release_references(site_root)
    if not references:
        print(f"No release asset URLs found under {site_root}", file=sys.stderr)
        return 1

    repo = args.repo or unique_value({item["repo"] for item in references}, "repo")
    tag = args.tag or unique_value({item["tag"] for item in references}, "tag")
    if tag is None:
        tag = DEFAULT_RELEASE_TAG

    expected_assets = sorted({item["asset"] for item in references if item["repo"] == repo and item["tag"] == tag})
    if not expected_assets:
        print(f"No release asset URLs found for {repo} tag {tag}", file=sys.stderr)
        return 1

    local_assets = index_local_assets(asset_root)
    missing = [name for name in expected_assets if name not in local_assets]
    if missing:
        print("Missing local ZIP files for release assets:", file=sys.stderr)
        for name in missing:
            print(f"- {name}", file=sys.stderr)
        if not args.allow_missing:
            return 1

    upload_paths: list[Path] = []
    for name in expected_assets:
        matches = local_assets.get(name)
        if not matches:
            continue
        chosen = matches[0]
        if len(matches) > 1:
            print(f"Using {chosen} for duplicate asset name {name}")
        if args.staging_dir is not None:
            chosen = stage_zip_asset(
                source_zip=chosen,
                asset_root=asset_root,
                target_dir=args.staging_dir.resolve(),
            )
        try:
            validate_zip_asset(chosen)
        except AssetValidationError as exc:
            raise SystemExit(str(exc)) from exc
        upload_paths.append(chosen)

    print(f"Release: {repo} {tag}")
    print(f"Assets referenced by site: {len(expected_assets)}")
    print(f"Local assets ready: {len(upload_paths)}")
    for path in upload_paths:
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"- {path.name} ({size_mb:.1f} MiB)")

    if args.dry_run or not upload_paths:
        return 0

    require_gh()
    ensure_release(repo=repo, tag=tag, title=args.title)
    subprocess.run(
        ["gh", "release", "upload", tag, "--repo", repo, "--clobber", *map(str, upload_paths)],
        check=True,
    )
    return 0


def collect_release_references(site_root: Path) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for path in sorted(site_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in RELEASE_URL_RE.finditer(text):
            references.append(match.groupdict())
    return references


def unique_value(values: set[str], label: str) -> str | None:
    values = {value for value in values if value}
    if not values:
        return None
    if len(values) == 1:
        return next(iter(values))
    formatted = ", ".join(sorted(values))
    raise SystemExit(f"Found multiple {label} values in site URLs: {formatted}")


def index_local_assets(asset_root: Path) -> dict[str, list[Path]]:
    assets: dict[str, list[Path]] = defaultdict(list)
    if not asset_root.exists():
        return assets
    for path in sorted(asset_root.rglob("*.zip")):
        if path.is_file():
            assets[path.name].append(path)
    return assets


class AssetValidationError(ValueError):
    pass


def validate_zip_asset(path: Path) -> None:
    size = path.stat().st_size
    if size > MAX_RELEASE_ASSET_BYTES:
        raise AssetValidationError(f"{path} is larger than GitHub Releases' 2 GiB per-file limit")
    try:
        with ZipFile(path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise AssetValidationError(f"{path} has a corrupt ZIP member: {bad_member}")
            for member in archive.infolist():
                name = member.filename
                parts = PurePosixPath(name).parts
                if name.startswith("/") or ".." in parts:
                    raise AssetValidationError(f"{path} contains unsafe ZIP member: {name}")
                if "downloads" in parts:
                    raise AssetValidationError(f"{path} contains nested download artifact: {name}")
                if any(part.startswith(".") for part in parts):
                    raise AssetValidationError(f"{path} contains hidden/system ZIP member: {name}")
    except BadZipFile as exc:
        raise AssetValidationError(f"{path} is not a readable ZIP file") from exc


def stage_zip_asset(*, source_zip: Path, asset_root: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source_zip.name
    try:
        validate_zip_asset(source_zip)
    except AssetValidationError as exc:
        if "nested download artifact" not in str(exc):
            raise SystemExit(str(exc)) from exc
        rebuild_zip_without_downloads(source_zip=source_zip, asset_root=asset_root, target=target)
    else:
        shutil.copy2(source_zip, target)
    return target


def rebuild_zip_without_downloads(*, source_zip: Path, asset_root: Path, target: Path) -> None:
    rel = source_zip.resolve().relative_to(asset_root.resolve())
    parts = rel.parts
    if "agent-packs" in parts:
        slug = parts[parts.index("agent-packs") + 1]
        zip_directory(asset_root / "agent-packs" / slug, target)
        return
    if "map-packs" in parts:
        slug = parts[parts.index("map-packs") + 1]
        zip_directory(asset_root / "map-packs" / slug, target)
        return
    if "replays" in parts:
        slug = parts[parts.index("replays") + 1]
        manifest_path = asset_root / "replays" / slug / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if source_zip.name.endswith("-replay-data.zip"):
            zip_replay_data(asset_root / "replays" / slug, target)
            return
        if source_zip.name.endswith("-agent-pack.zip"):
            zip_directory(asset_root / "agent-packs" / str(manifest["agent_pack"]), target)
            return
        if source_zip.name.endswith("-map-pack.zip"):
            zip_directory(asset_root / "map-packs" / str(manifest["map_pack"]), target)
            return
    raise SystemExit(f"{source_zip} contains nested downloads and cannot be repaired automatically")


def zip_directory(source_dir: Path, target: Path) -> None:
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir() or path.name.startswith("."):
                continue
            rel = path.relative_to(source_dir)
            if "downloads" in rel.parts:
                continue
            archive.write(path, rel.as_posix())


def zip_replay_data(source_dir: Path, target: Path) -> None:
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir() or path.name.startswith("."):
                continue
            rel = path.relative_to(source_dir)
            if "downloads" in rel.parts:
                continue
            if len(rel.parts) >= 2 and rel.parts[0] == "map" and rel.parts[1] in {
                "assets",
                "characters",
                "location-assets",
            }:
                continue
            if rel.parts == ("map", "preview.png"):
                continue
            archive.write(path, rel.as_posix())


def require_gh() -> None:
    if shutil.which("gh") is None:
        raise SystemExit("GitHub CLI gh is required for upload")
    subprocess.run(["gh", "auth", "status"], check=True)


def ensure_release(*, repo: str, tag: str, title: str) -> None:
    existing = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if existing.returncode == 0:
        return
    notes = (
        "Download assets for the GOD public static site. "
        "These ZIP files are intentionally kept out of Git history."
    )
    subprocess.run(
        ["gh", "release", "create", tag, "--repo", repo, "--title", title, "--notes", notes],
        check=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
