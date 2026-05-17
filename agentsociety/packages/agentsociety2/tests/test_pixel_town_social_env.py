from __future__ import annotations

import asyncio
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sqlite3

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_PATH = _REPO_ROOT / "custom" / "envs" / "pixel_town_social_env.py"
_SPEC = importlib.util.spec_from_file_location("pixel_town_social_env", _ENV_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
PixelTownSocialEnv = _MODULE.PixelTownSocialEnv


def _write_map_package(tmp_path: Path, *, unreachable: bool = False) -> Path:
    width = 5
    height = 5
    collisions = [0] * (width * height)
    if unreachable:
        for y in range(height):
            collisions[y * width + 2] = 1

    (tmp_path / "map.json").write_text(
        json.dumps(
            {
                "type": "map",
                "width": width,
                "height": height,
                "tilewidth": 32,
                "tileheight": 32,
                "tilesets": [],
                "layers": [
                    {
                        "name": "Ground",
                        "type": "tilelayer",
                        "data": [0] * (width * height),
                    },
                    {
                        "name": "Collisions",
                        "type": "tilelayer",
                        "data": collisions,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "town.json"
    manifest.write_text(
        json.dumps(
            {
                "map_id": "test_town",
                "display_name": "测试小镇",
                "tiled_map_path": "map.json",
                "tile_size": 32,
                "locations": [
                    {
                        "id": "park",
                        "name": "公园",
                        "aliases": ["Park", "公园"],
                        "anchor_tile": {"x": 0, "y": 0},
                        "interaction_ids": ["meet_friend", "public_announcement"],
                    },
                    {
                        "id": "cafe",
                        "name": "咖啡馆",
                        "aliases": ["cafe"],
                        "anchor_tile": {"x": 4, "y": 0},
                        "interaction_ids": ["chat_over_coffee"],
                    },
                ],
                "interactions": [
                    {
                        "id": "meet_friend",
                        "name": "见朋友",
                        "description": "在公园见朋友",
                        "allowed_location_ids": ["park"],
                        "effects": {
                            "action": "{agent_name}在公园见朋友：{message}",
                            "status": "活跃",
                            "emotion": "专注",
                            "latest_event": "{agent_name}在公园见朋友。",
                            "group_message": "{agent_name}悄悄说：{message}",
                        },
                    },
                    {
                        "id": "public_announcement",
                        "name": "公告",
                        "description": "在公园发布公告",
                        "allowed_location_ids": ["park"],
                        "effects": {
                            "action": "{agent_name}发布公告",
                            "status": "活跃",
                            "emotion": "专注",
                            "group_message": "公告：{message}",
                            "broadcast": True,
                        },
                    },
                    {
                        "id": "chat_over_coffee",
                        "name": "咖啡聊天",
                        "description": "在咖啡馆聊天",
                        "allowed_location_ids": ["cafe"],
                        "effects": {
                            "action": "{agent_name}在咖啡馆聊天",
                            "status": "活跃",
                            "emotion": "专注",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_pixel_town_alias_movement_and_replay_fields(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"]],
            initial_locations={"1": "Park"},
            map_manifest_path=str(manifest),
            movement_tiles_per_second=8,
        )

        initial = await env.observe_agent(1)
        assert initial["location_id"] == "park"
        assert initial["tile_x"] == 0
        assert initial["tile_y"] == 0
        assert initial["movement_status"] == "idle"
        assert json.loads(initial["movement_segment_json"]) == [{"x": 0, "y": 0}]
        assert initial["movement_path_index"] == 0
        assert initial["movement_path_length"] == 1
        assert json.loads(initial["available_interactions_json"])[0]["id"] == "meet_friend"

        move = await env.move_agent(1, "咖啡馆")
        assert move["ok"] is True
        assert move["path_length"] == 5

        moving = await env.observe_agent(1)
        assert moving["movement_status"] == "moving"
        assert moving["target_location_id"] == "cafe"

        await env.step(10, datetime(2026, 5, 9, 12, 0, 0))
        still_moving = await env.observe_agent(1)
        assert still_moving["movement_status"] == "moving"
        assert still_moving["tile_x"] == 1
        assert still_moving["tile_y"] == 0
        assert json.loads(still_moving["movement_segment_json"]) == [{"x": 0, "y": 0}, {"x": 1, "y": 0}]
        assert still_moving["movement_path_index"] == 1
        assert still_moving["movement_path_length"] == 5

        await env.step(10, datetime(2026, 5, 9, 12, 1, 0))
        await env.step(10, datetime(2026, 5, 9, 12, 2, 0))
        arrived = await env.observe_agent(1)
        assert arrived["location_id"] == "cafe"
        assert arrived["location"] == "咖啡馆"
        assert arrived["movement_status"] == "idle"
        assert arrived["tile_x"] == 4
        assert arrived["tile_y"] == 0
        assert json.loads(arrived["path_json"]) == [{"x": 4, "y": 0}]
        assert json.loads(arrived["movement_segment_json"]) == [
            {"x": 2, "y": 0},
            {"x": 3, "y": 0},
            {"x": 4, "y": 0},
        ]
        assert arrived["movement_path_index"] == 4
        assert arrived["movement_path_length"] == 5

        await env.step(10, datetime(2026, 5, 9, 12, 3, 0))
        idle_after_arrival = await env.observe_agent(1)
        assert json.loads(idle_after_arrival["movement_segment_json"]) == [{"x": 4, "y": 0}]
        assert idle_after_arrival["movement_path_index"] == 0
        assert idle_after_arrival["movement_path_length"] == 1

    asyncio.run(scenario())


def test_pixel_town_snapshot_fields_are_declared_in_replay_schema(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"], [2, "老鲍"]],
            initial_locations={"1": "公园", "2": "Park"},
            map_manifest_path=str(manifest),
        )

        observed = env._snapshot_agent(1)
        declared = {"agent_id", "step", "t", *(column.name for column in env._agent_state_columns)}
        assert set(observed).issubset(declared)
        assert "nearby_agents" in declared

    asyncio.run(scenario())


def test_pixel_town_unreachable_move_does_not_change_position(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path, unreachable=True)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"]],
            initial_locations={"1": "公园"},
            map_manifest_path=str(manifest),
        )

        move = await env.move_agent(1, "cafe")
        assert move["ok"] is False
        assert move["error"] == "unreachable"

        observed = await env.observe_agent(1)
        assert observed["location_id"] == "park"
        assert observed["movement_status"] == "idle"
        assert observed["tile_x"] == 0
        assert observed["tile_y"] == 0
        assert json.loads(observed["movement_segment_json"]) == [{"x": 0, "y": 0}]
        assert observed["movement_path_index"] == 0
        assert observed["movement_path_length"] == 1

    asyncio.run(scenario())


def test_pixel_town_load_replay_tail_infers_legacy_path_index(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"]],
            initial_locations={"1": "公园"},
            map_manifest_path=str(manifest),
            movement_tiles_per_second=1,
        )
        db_path = tmp_path / "legacy.db"
        path_json = json.dumps([{"x": x, "y": 0} for x in range(5)])
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE pixel_town_social_agent_state (
                    agent_id INTEGER,
                    step INTEGER,
                    name TEXT,
                    location TEXT,
                    action TEXT,
                    status TEXT,
                    emotion TEXT,
                    last_message TEXT,
                    tile_x INTEGER,
                    tile_y INTEGER,
                    location_id TEXT,
                    movement_status TEXT,
                    target_location_id TEXT,
                    path_json JSON
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE pixel_town_social_env_state (
                    step INTEGER,
                    total_messages_sent INTEGER,
                    current_phase TEXT,
                    latest_event TEXT,
                    latest_communications JSON
                )
                """
            )
            conn.execute(
                """
                INSERT INTO pixel_town_social_agent_state
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    0,
                    "阿莉",
                    "公园",
                    "moving",
                    "ready",
                    "calm",
                    "",
                    2,
                    0,
                    "park",
                    "moving",
                    "cafe",
                    path_json,
                ),
            )
            conn.execute(
                "INSERT INTO pixel_town_social_env_state VALUES (?, ?, ?, ?, ?)",
                (0, 0, "setup", "", "[]"),
            )
            conn.commit()
        finally:
            conn.close()

        result = await env.load_replay_tail(db_path, 0)
        assert result["restored"] is True

        await env.step(10, datetime(2026, 5, 9, 12, 0, 0))
        observed = await env.observe_agent(1)
        assert observed["tile_x"] == 3
        assert observed["tile_y"] == 0
        assert json.loads(observed["movement_segment_json"]) == [{"x": 2, "y": 0}, {"x": 3, "y": 0}]
        assert observed["movement_path_index"] == 3
        assert observed["movement_path_length"] == 5

    asyncio.run(scenario())


def test_pixel_town_interactions_are_location_scoped(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "Jiuwen Alice"]],
            initial_locations={"1": "公园"},
            map_manifest_path=str(manifest),
            movement_tiles_per_second=10,
        )

        unavailable = await env.interact(1, "chat_over_coffee")
        assert unavailable["ok"] is False
        assert unavailable["error"] == "interaction_not_available_here"

        meet = await env.interact(1, "meet_friend", {"message": "你好"})
        assert meet["ok"] is True
        observed = await env.observe_agent(1)
        assert observed["action"] == "Jiuwen Alice在公园见朋友：你好"
        assert observed["status"] == "活跃"
        assert observed["emotion"] == "专注"

        assert (await env.move_agent(1, "cafe"))["ok"] is True
        await env.step(1, datetime(2026, 5, 9, 12, 0, 0))
        await env.step(1, datetime(2026, 5, 9, 12, 1, 0))
        await env.step(1, datetime(2026, 5, 9, 12, 2, 0))
        chat = await env.interact(1, "chat_over_coffee")
        assert chat["ok"] is True
        observed = await env.observe_agent(1)
        assert observed["action"] == "Jiuwen Alice在咖啡馆聊天"

    asyncio.run(scenario())


def test_english_agent_name_does_not_break_chinese_event_policy(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "Donald Trump"]],
            initial_locations={"1": "公园"},
            map_manifest_path=str(manifest),
        )

        event = await env.publish_event("Trump 抵达西门。")
        assert event["event"] == "Trump 抵达西门。"
        observed = await env.observe_agent(1)
        assert observed["latest_event"] == "Trump 抵达西门。"
        assert observed["recent_messages"][-1]["content"] == "公共环境事件（信息）：Trump 抵达西门。"
        assert env._step_communications[-1]["type"] == "system_event"
        assert env._step_communications[-1]["sender_id"] == 0
        assert env._step_communications[-1]["content"] == "公共环境事件（信息）：Trump 抵达西门。"

        fallback = await env.publish_event("The visitor arrived.")
        assert fallback["event"] == "收到一条公共环境事件。"

    asyncio.run(scenario())


def test_direct_messages_require_same_location_and_expose_nearby_agents(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "Jiuwen Alice"], [2, "Jiuwen Bob"], [3, "Jiuwen Carol"]],
            initial_locations={"1": "公园", "2": "Park", "3": "cafe"},
            map_manifest_path=str(manifest),
        )

        observed = await env.observe_agent(1)
        assert observed["nearby_agents"] == [
            {
                "agent_id": 2,
                "name": "Jiuwen Bob",
                "location_id": "park",
                "location": "公园",
            }
        ]

        sent = await env.send_message(1, 2, "安静问候")
        assert sent["ok"] is True

        sender = await env.observe_agent(1)
        receiver = await env.observe_agent(2)
        far_agent = await env.observe_agent(3)
        assert sender["message_count"] == 0
        assert receiver["message_count"] == 1
        assert receiver["recent_messages"][-1]["type"] == "direct"
        assert receiver["recent_messages"][-1]["content"] == "安静问候"
        assert env._step_communications[-1]["type"] == "direct"
        assert env._step_communications[-1]["sender_id"] == 1
        assert env._step_communications[-1]["receiver_id"] == 2
        assert env._step_communications[-1]["content"] == "安静问候"
        assert far_agent["message_count"] == 0

        blocked = await env.send_message(1, 3, "距离太远")
        assert blocked["ok"] is False
        assert blocked["error"] == "receiver_not_nearby"
        assert (await env.observe_agent(3))["message_count"] == 0

    asyncio.run(scenario())


def test_chat_log_is_authoritative_even_when_mailbox_keeps_old_messages(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"], [2, "老鲍"]],
            initial_locations={"1": "公园", "2": "Park"},
            map_manifest_path=str(manifest),
        )

        sent = await env.send_message(1, 2, "这一条本步发送")
        assert sent["ok"] is True
        receiver = await env.observe_agent(2)
        assert receiver["recent_messages"][-1]["content"] == "这一条本步发送"
        assert env._step_communications == [
            {
                "type": "direct",
                "sender_id": 1,
                "sender_name": "阿莉",
                "content": "这一条本步发送",
                "receiver_id": 2,
                "receiver_name": "老鲍",
            }
        ]

        await env.step(1, datetime(2026, 5, 9, 12, 0, 0))
        assert env._step_communications == []
        receiver_after_step = await env.observe_agent(2)
        assert receiver_after_step["recent_messages"][-1]["content"] == "这一条本步发送"

    asyncio.run(scenario())


def test_scripted_messages_are_also_recorded_in_step_communications(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"], [2, "老鲍"], [3, "小卡"]],
            initial_locations={"1": "公园", "2": "Park", "3": "cafe"},
            map_manifest_path=str(manifest),
            default_group_name="测试公开群",
        )

        observed = await env.apply_scripted_action(
            1,
            {
                "action": "同步消息",
                "direct_messages": [{"to": 2, "content": "私下确认"}],
                "group_messages": [{"group_id": 1, "content": "公开同步"}],
            },
        )
        assert observed["agent_id"] == 1
        assert (await env.observe_agent(2))["recent_messages"][-2]["content"] == "私下确认"
        assert (await env.observe_agent(3))["recent_messages"][-1]["content"] == "公开同步"
        assert env._step_communications[-2:] == [
            {
                "type": "direct",
                "sender_id": 1,
                "sender_name": "阿莉",
                "content": "私下确认",
                "receiver_id": 2,
                "receiver_name": "老鲍",
            },
            {
                "type": "group",
                "sender_id": 1,
                "sender_name": "阿莉",
                "content": "公开同步",
                "group_id": 1,
                "group_name": "测试公开群",
                "recipient_count": 3,
            },
        ]

    asyncio.run(scenario())


def test_interaction_speech_is_local_unless_public(tmp_path: Path) -> None:
    async def scenario() -> None:
        manifest = _write_map_package(tmp_path)
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"], [2, "老鲍"], [3, "小卡"]],
            initial_locations={"1": "公园", "2": "Park", "3": "cafe"},
            map_manifest_path=str(manifest),
            default_group_name="测试公开群",
        )

        local = await env.interact(1, "meet_friend", {"message": "本地消息"})
        assert local["ok"] is True
        assert (await env.observe_agent(1))["message_count"] == 0
        bob = await env.observe_agent(2)
        carol = await env.observe_agent(3)
        assert bob["message_count"] == 1
        assert bob["recent_messages"][-1]["type"] == "direct"
        assert bob["recent_messages"][-1]["content"] == "阿莉悄悄说：本地消息"
        assert carol["message_count"] == 0
        assert env._step_communications[-1]["type"] == "direct"

        public = await env.interact(1, "public_announcement", {"message": "请大家注意"})
        assert public["ok"] is True
        alice = await env.observe_agent(1)
        bob = await env.observe_agent(2)
        carol = await env.observe_agent(3)
        assert alice["recent_messages"][-1]["type"] == "group"
        assert bob["recent_messages"][-1]["type"] == "group"
        assert carol["recent_messages"][-1]["type"] == "group"
        assert carol["recent_messages"][-1]["group_name"] == "测试公开群"
        assert env._step_communications[-1]["type"] == "group"
        assert env._step_communications[-1]["recipient_count"] == 3

    asyncio.run(scenario())


def test_default_manifest_binds_required_real_scenes() -> None:
    async def scenario() -> None:
        env = PixelTownSocialEnv(
            agent_id_name_pairs=[[1, "阿莉"]],
            initial_locations={"1": "park"},
            movement_tiles_per_second=1000,
        )

        locations = await env.list_locations()
        by_id = {location["id"]: location for location in locations["locations"]}
        for location_id in ("home", "school", "library", "cafe", "park", "supply_store", "market", "pharmacy", "pub", "dorm"):
            assert location_id in by_id
            assert by_id[location_id]["bounds"]["w"] >= 4
            assert by_id[location_id]["scene_type"]
            if "source_address" in by_id[location_id]:
                assert by_id[location_id]["source_address"].startswith("the Ville:")

        removed_move = await env.move_agent(1, "prison")
        assert removed_move["ok"] is False
        assert removed_move["error"] == "unknown_location"

        cafe_move = await env.move_agent(1, "cafe")
        assert cafe_move["ok"] is True
        assert cafe_move["path_length"] > 1
        await env.step(1, datetime(2026, 5, 9, 12, 0, 0))
        still_moving = await env.observe_agent(1)
        assert still_moving["movement_status"] == "moving"
        await env.step(1, datetime(2026, 5, 9, 12, 1, 0))
        await env.step(1, datetime(2026, 5, 9, 12, 2, 0))
        cafe_action = await env.interact(1, "chat_over_coffee")
        assert cafe_action["ok"] is True

    asyncio.run(scenario())
