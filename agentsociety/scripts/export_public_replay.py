#!/usr/bin/env python3
"""Export curated GOD replay runs and ExperimentPacks for the static public site."""

from __future__ import annotations

import argparse
from pathlib import Path

from agentsociety2.backend.services.public_replay_export import (
    export_curated_experiment_packs,
    export_known_public_replays,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("quick_experiments"),
        help="Path to the quick_experiments workspace.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../docs/site/public-data"),
        help="Output directory for static public replay data.",
    )
    parser.add_argument(
        "--experiments-only",
        action="store_true",
        help="Export curated ExperimentPack manifests and downloads without requiring replay databases.",
    )
    parser.add_argument(
        "--release-download-base",
        help="Absolute base URL for published download assets, ending at the release tag path.",
    )
    parser.add_argument(
        "--release-repo",
        help="GitHub repo owner/name used to build release download URLs, for example XiaoLuoLYG/GOD.",
    )
    parser.add_argument(
        "--release-tag",
        default="public-site-packs",
        help="GitHub release tag used with --release-repo. Defaults to public-site-packs.",
    )
    args = parser.parse_args()
    release_download_base = args.release_download_base
    if args.release_repo:
        release_download_base = (
            f"https://github.com/{args.release_repo.strip('/')}/releases/download/"
            f"{args.release_tag.strip('/')}/"
        )

    if args.experiments_only:
        manifests = export_curated_experiment_packs(
            workspace_path=args.workspace,
            output_root=args.output,
            download_base_url=release_download_base,
        )
        print(f"Exported {len(manifests)} curated ExperimentPack bundle(s) to {args.output}")
        for manifest in manifests:
            print(f"- {manifest['pack_id']}: {manifest['agent_count']} agents, {manifest['total_steps']} steps")
        return

    manifests = export_known_public_replays(
        workspace_path=args.workspace,
        output_root=args.output,
        download_base_url=release_download_base,
    )
    print(f"Exported {len(manifests)} public replay bundle(s) and curated ExperimentPack index to {args.output}")
    for manifest in manifests:
        print(f"- {manifest['slug']}: {manifest['total_steps']} steps, {manifest['agent_count']} agents")


if __name__ == "__main__":
    main()
