import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_persona_skill_uses_local_speech_and_keeps_old_default(tmp_path):
    catalog = ROOT / "custom" / "skills"
    skill = tmp_path / "community.coordinate"
    shutil.copytree(catalog / skill.name, skill)
    shutil.copytree(catalog / "_shared", tmp_path / "_shared")
    spec_file = skill / "skill.json"
    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    original = spec["speech"]
    location = spec["target_locations"][0]

    def run(current_location):
        spec_file.write_text(json.dumps(spec), encoding="utf-8")
        args = {"observation": {"location_id": current_location, "known_locations": [location]},
                "agent_work_dir": str(tmp_path)}
        output = subprocess.check_output(
            [sys.executable, str(skill / "scripts" / "run_skill.py"), "--args-json", json.dumps(args)],
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return json.loads(output)["speech_effect"]

    spec["speech"] = "Meet at the park."
    assert run(location) == {"type": "group_message", "group_id": 1, "content": spec["speech"]}
    assert run("away") is None
    spec["speech"] = ""
    assert run(location) is None
    del spec["speech"]
    assert run(location)["content"] == original


def test_map_validators_keep_strict_ville_checks_and_report_invalid_dimensions(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import validate_pixel_town_map
    import validate_the_ville_map

    pku = ROOT / "custom/maps/pku/map.yaml"
    assert not validate_pixel_town_map.validate_manifest(pku)
    assert any("should reference original map file" in m for m in validate_the_ville_map.validate_manifest(pku))

    manifest = tmp_path / "demo.json"
    manifest.write_text(json.dumps({"map_id": "sample", "tiled_map_path": "tiles.json"}), encoding="utf-8")
    tile_map = {"width": 0, "height": 1, "layers": [{"name": "Collisions", "type": "tilelayer", "data": [0]}]}
    (tmp_path / "tiles.json").write_text(json.dumps(tile_map), encoding="utf-8")
    assert validate_pixel_town_map.validate_manifest(manifest) == ["ERROR map must have positive width and height, got 0x1"]
