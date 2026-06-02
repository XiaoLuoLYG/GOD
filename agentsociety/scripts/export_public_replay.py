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
    args = parser.parse_args()

    if args.experiments_only:
        manifests = export_curated_experiment_packs(
            workspace_path=args.workspace,
            output_root=args.output,
        )
        print(f"Exported {len(manifests)} curated ExperimentPack bundle(s) to {args.output}")
        for manifest in manifests:
            print(f"- {manifest['pack_id']}: {manifest['agent_count']} agents, {manifest['total_steps']} steps")
        return

    manifests = export_known_public_replays(
        workspace_path=args.workspace,
        output_root=args.output,
    )
    print(f"Exported {len(manifests)} public replay bundle(s) and curated ExperimentPack index to {args.output}")
    for manifest in manifests:
        print(f"- {manifest['slug']}: {manifest['total_steps']} steps, {manifest['agent_count']} agents")


if __name__ == "__main__":
    main()
