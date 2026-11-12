"""Make one real TypeSafe request through GOD's Jev comparison code."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/agentsociety2"))
sys.path.insert(0, str(ROOT / "custom/agents"))

from jiuwenclaw_agent import JiuwenClawAgent


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT.parent / ".env")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    os.environ["GOD_JEV_SHADOW"] = "1"
    result = await JiuwenClawAgent._request_jev_skill_choice(
        state={"observation": {"recent_messages": [{"sender_id": 2, "content": "Hello, can you reply?"}]}},
        catalog=[
            {"name": "routine.daily", "description": "Continue the daily routine."},
            {"name": "social.reply", "description": "Reply to a recent message."},
        ],
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result and result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
