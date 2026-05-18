## Summary

- TBD

## Scope

- [ ] This PR is focused on one logical change.
- [ ] I did not commit runtime outputs, local credentials, `.god/`, `.live/`, `.DS_Store`, `promos/`, `docs/press-kit/`, or local-only large map assets.
- [ ] If this PR changes public docs, both English and Chinese docs were updated where applicable.
- [ ] If this PR changes maps or experiments, the added assets are intentionally part of the public repository.

## Validation

- [ ] `bash -n scripts/god.sh`
- [ ] `npm run build --prefix agentsociety/frontend`
- [ ] `cd agentsociety && uv run pytest -q packages/agentsociety2/tests/test_god_setup_router.py packages/agentsociety2/tests/test_map_packages.py packages/agentsociety2/tests/test_pixel_town_social_env.py`
- [ ] Map package validation, if applicable: `cd agentsociety && uv run python scripts/validate_map_package.py custom/maps/<map_id>`

## Screenshots / Clips

Add screenshots or short clips for UI, replay, map, setup, or docs changes.
