#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run a copy-only native save-editor smoke test.

The script deliberately treats the supplied save as read-only input.  It
copies the save into a fresh work directory, invokes the existing native
``editor-engine`` against that copy, and checks the JSON readback from each
new save.  It does not start VCMI or inspect the game client.

Only the Python standard library is used.  The generated result omits input
paths, hero names, and command output so that it can be committed as a
sanitised audit artifact.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


MAX_MANA = 2_147_483_647
SAVE_VERSION = 902


class TestFailure(RuntimeError):
    """An expected test assertion failed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test VCMI save editing using only a copied input save."
    )
    parser.add_argument("--engine", required=True, type=Path, help="existing editor-engine")
    parser.add_argument("--save", required=True, type=Path, help="input .vsgm1 save")
    parser.add_argument(
        "--work-dir",
        required=True,
        type=Path,
        help="new or empty directory used exclusively for copied test data",
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=None,
        help="sanitised JSON result (defaults to work-dir/result.json)",
    )
    return parser.parse_args()


def create_work_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise TestFailure("work directory is not a directory")
        if any(path.iterdir()):
            raise TestFailure("work directory must be new or empty")
        return
    path.mkdir(parents=True)


def require_regular(path: Path, label: str) -> None:
    if not path.exists() or not path.is_file():
        raise TestFailure(f"{label} is not a regular file")


def invoke(engine: Path, *arguments: str | Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(engine), *(str(argument) for argument in arguments)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise TestFailure("native command timed out") from error
    except OSError as error:
        raise TestFailure("native command could not be started") from error


def inspect(engine: Path, save: Path) -> dict[str, Any]:
    result = invoke(engine, "inspect", save)
    if result.returncode != 0:
        raise TestFailure("inspect command failed")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise TestFailure("inspect did not return JSON") from error
    if not isinstance(document, dict):
        raise TestFailure("inspect JSON root is not an object")
    return document


def require_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        raise TestFailure(f"{label} command failed")


def write_patch(work_dir: Path, filename: str, patch: dict[str, Any]) -> Path:
    path = work_dir / filename
    path.write_text(json.dumps(patch, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def apply_patch(
    engine: Path,
    input_save: Path,
    output_save: Path,
    patch_path: Path,
) -> None:
    require_success(invoke(engine, "apply", input_save, output_save, patch_path), "apply")
    require_regular(output_save, "native output")


def hero_map(document: dict[str, Any]) -> dict[int, dict[str, Any]]:
    heroes = document.get("heroes")
    if not isinstance(heroes, list):
        raise TestFailure("inspect heroes field is missing")
    result: dict[int, dict[str, Any]] = {}
    for hero in heroes:
        if not isinstance(hero, dict) or not isinstance(hero.get("id"), int):
            raise TestFailure("inspect contains an invalid hero entry")
        result[int(hero["id"])] = hero
    return result


def skill_map(hero: dict[str, Any]) -> dict[int, int]:
    skills = hero.get("skills", [])
    if skills is None:
        return {}
    if not isinstance(skills, list):
        raise TestFailure("hero skills field is not an array")
    result: dict[int, int] = {}
    for skill in skills:
        if not isinstance(skill, dict) or not isinstance(skill.get("id"), int):
            raise TestFailure("inspect contains an invalid skill entry")
        result[int(skill["id"])] = int(skill["level"])
    return result


def army_map(hero: dict[str, Any]) -> dict[int, dict[str, int]]:
    army = hero.get("army")
    if not isinstance(army, list):
        raise TestFailure("hero army field is not an array")
    result: dict[int, dict[str, int]] = {}
    for stack in army:
        if not isinstance(stack, dict):
            raise TestFailure("inspect contains an invalid army entry")
        slot = int(stack["slot"])
        result[slot] = {
            "slot": slot,
            "creature": int(stack["creature"]),
            "count": int(stack["count"]),
        }
    return result


def changed_stat(value: int, delta: int = 1) -> int:
    if value < 999:
        return min(999, value + delta)
    return max(0, value - delta)


def changed_mana(value: int) -> int:
    if value < MAX_MANA:
        return min(MAX_MANA, value + 17)
    return value - 1


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise TestFailure(label)


def prepare_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    """Resolve paths and validate the report destination before any writes."""

    engine = args.engine.expanduser().resolve(strict=False)
    save = args.save.expanduser().resolve(strict=False)
    work_dir = args.work_dir.expanduser()
    if work_dir.is_symlink():
        raise TestFailure("work directory must not be a symbolic link")
    work_dir = work_dir.resolve(strict=False)

    requested_result = args.result.expanduser() if args.result is not None else work_dir / "result.json"
    # ``is_symlink`` also catches a dangling link, while ``exists`` rejects an
    # existing regular file or directory.  The report is always a new file.
    if requested_result.is_symlink() or requested_result.exists():
        raise TestFailure("result path must be a new non-symbolic-link path")
    result = requested_result.resolve(strict=False)
    if result == engine or result == save:
        raise TestFailure("result path must differ from engine and save")
    return engine, save, work_dir, result


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        # Publish without replacing a file created after prepare_paths().
        os.link(temporary, path)
        temporary.unlink()
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def status_for(results: dict[str, Any], key: str, passed: bool, **details: Any) -> None:
    results[key] = {"status": "passed" if passed else "failed", **details}


def run_tests(engine: Path, save: Path, work_dir: Path) -> dict[str, Any]:
    require_regular(engine, "engine")
    require_regular(save, "save")
    create_work_dir(work_dir)

    original_hash = sha256(save)
    copied_input = work_dir / "input-copy.vsgm1"
    shutil.copy2(save, copied_input)
    copied_hash = sha256(copied_input)
    if copied_hash != original_hash:
        raise TestFailure("copy hash does not match input hash")

    tests: dict[str, Any] = {}
    before = inspect(engine, copied_input)
    if before.get("version") != SAVE_VERSION:
        raise TestFailure("save format is not 902")
    before_heroes = hero_map(before)
    human_heroes = [hero for hero in before_heroes.values() if hero.get("human") is True]
    if not human_heroes:
        raise TestFailure("save has no human hero")
    target = human_heroes[0]
    target_id = int(target["id"])
    other_hero_ids = set(before_heroes) - {target_id}
    catalog_skills = {
        int(entry["id"])
        for entry in before.get("skills", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), int)
    }
    catalog_creatures = {
        int(entry["id"])
        for entry in before.get("creatures", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), int)
    }
    if not catalog_skills or not catalog_creatures:
        raise TestFailure("inspect did not expose skill and creature catalogs")

    before_skills = skill_map(target)
    before_army = army_map(target)
    if not before_army:
        raise TestFailure("target hero has no army stack")
    if not all(stack["count"] > 0 for stack in before_army.values()):
        raise TestFailure("target hero has a non-positive input stack")

    status_for(
        tests,
        "inspect",
        True,
        save_format=SAVE_VERSION,
        hero_count=len(before_heroes),
        human_hero_count=len(human_heroes),
    )

    # A complete read/write cycle must be readable again and must not change the
    # inspection data.  The original input remains untouched by construction.
    roundtrip_output = work_dir / "roundtrip.vsgm1"
    require_success(invoke(engine, "roundtrip", copied_input, roundtrip_output), "roundtrip")
    roundtrip_readback = inspect(engine, roundtrip_output)
    status_for(
        tests,
        "roundtrip",
        canonical(roundtrip_readback) == canonical(before),
        inspect_equal=canonical(roundtrip_readback) == canonical(before),
    )
    assert_equal(canonical(roundtrip_readback), canonical(before), "roundtrip readback differs")

    stats = [
        changed_stat(int(target["attack"])),
        changed_stat(int(target["defense"])),
        changed_stat(int(target["power"])),
        changed_stat(int(target["knowledge"])),
    ]
    mana = changed_mana(int(target["mana"]))

    # Build a final skill list that exercises remove, add, upgrade, and
    # downgrade on the current fixture.  The fallback paths keep the test
    # honest for a save with no suitable existing level: that operation is
    # reported as skipped instead of being silently claimed as verified.
    skill_final = dict(before_skills)
    removed_skill = next(iter(before_skills), None)
    if removed_skill is not None:
        skill_final.pop(removed_skill)
    added_skill = next((skill for skill in sorted(catalog_skills) if skill not in before_skills), None)
    if added_skill is not None:
        skill_final[added_skill] = 1
    upgrade_skill = next(
        (skill for skill, level in before_skills.items() if skill != removed_skill and level < 3),
        None,
    )
    downgrade_skill = next(
        (
            skill
            for skill, level in before_skills.items()
            if skill not in {removed_skill, upgrade_skill} and level > 1
        ),
        None,
    )
    if upgrade_skill is not None:
        skill_final[upgrade_skill] = before_skills[upgrade_skill] + 1
    if downgrade_skill is not None:
        skill_final[downgrade_skill] = before_skills[downgrade_skill] - 1

    changed_army = [dict(stack) for stack in before_army.values()]
    first_stack = changed_army[0]
    first_stack["count"] = first_stack["count"] + 7
    replaced_slot: int | None = None
    if len(changed_army) >= 2:
        second_stack = changed_army[1]
        replacement = next(
            (creature for creature in sorted(catalog_creatures) if creature != second_stack["creature"]),
            None,
        )
        if replacement is not None:
            second_stack["creature"] = replacement
            replaced_slot = second_stack["slot"]

    patch = {
        "hero": target_id,
        "stats": stats,
        "mana": mana,
        "allSpells": True,
        "clearCheated": True,
        "army": changed_army,
    }
    if before.get("skills") is not None:
        patch["skills"] = [
            {"id": skill, "level": level} for skill, level in sorted(skill_final.items())
        ]
    main_patch = write_patch(work_dir, "main-patch.json", patch)
    edited_output = work_dir / "edited.vsgm1"
    apply_patch(engine, copied_input, edited_output, main_patch)
    after = inspect(engine, edited_output)
    after_heroes = hero_map(after)
    edited_target = after_heroes[target_id]

    expected_stats = {
        "attack": stats[0],
        "defense": stats[1],
        "power": stats[2],
        "knowledge": stats[3],
        "mana": mana,
    }
    stats_ok = all(edited_target[key] == value for key, value in expected_stats.items())
    status_for(tests, "primary_stats_and_mana", stats_ok, values_match=stats_ok)
    assert_equal(stats_ok, True, "primary stats or mana did not roundtrip")

    edited_army = army_map(edited_target)
    army_ok = edited_army == {stack["slot"]: stack for stack in changed_army}
    army_coverage_ok = army_ok and replaced_slot is not None
    status_for(
        tests,
        "army_quantity_and_replacement",
        army_coverage_ok,
        quantity_changed=first_stack["count"] != before_army[first_stack["slot"]]["count"],
        replaced_slot=replaced_slot is not None,
    )
    assert_equal(army_coverage_ok, True, "army quantity or creature replacement did not roundtrip")

    spell_count_observed = len(edited_target.get("spells", []))
    spellbook_ok = edited_target.get("spellbook") is True and spell_count_observed >= len(
        target.get("spells", [])
    )
    status_for(
        tests,
        "spellbook_and_spell_count",
        spellbook_ok,
        spell_count_observed=spell_count_observed,
        spell_count_not_decreased=spell_count_observed >= len(target.get("spells", [])),
        spellbook=edited_target.get("spellbook") is True,
    )
    assert_equal(spellbook_ok, True, "spellbook or observed spell count did not roundtrip")

    after_skills = skill_map(edited_target)
    skills_ok = after_skills == skill_final if "skills" in patch else after_skills == before_skills
    skill_details = {
        "final_skill_count": len(after_skills),
        "removed": removed_skill is not None and removed_skill not in after_skills,
        "added": added_skill is not None and after_skills.get(added_skill) == 1,
        "upgraded": upgrade_skill is not None
        and after_skills.get(upgrade_skill) == before_skills[upgrade_skill] + 1,
        "downgraded": downgrade_skill is not None
        and after_skills.get(downgrade_skill) == before_skills[downgrade_skill] - 1,
    }
    skipped_operations = [
        name
        for name, present in (
            ("remove", removed_skill is not None),
            ("add", added_skill is not None),
            ("upgrade", upgrade_skill is not None),
            ("downgrade", downgrade_skill is not None),
        )
        if not present
    ]
    skills_coverage_ok = skills_ok and not skipped_operations
    status_for(
        tests,
        "secondary_skill_add_remove_upgrade_downgrade",
        skills_coverage_ok,
        **skill_details,
        skipped_operations=skipped_operations,
    )
    assert_equal(skills_coverage_ok, True, "secondary skills did not cover every requested operation")

    # Omitting the skills field is the legacy patch contract: learned skills
    # must survive while the other requested edits still roundtrip.
    omitted_skills_patch = copy.deepcopy(patch)
    omitted_skills_patch.pop("skills", None)
    omitted_skills_patch["allSpells"] = False
    omitted_path = write_patch(work_dir, "skills-omitted.json", omitted_skills_patch)
    omitted_output = work_dir / "skills-omitted.vsgm1"
    apply_patch(engine, copied_input, omitted_output, omitted_path)
    omitted_readback = inspect(engine, omitted_output)
    omitted_target = hero_map(omitted_readback)[target_id]
    omitted_preserved = skill_map(omitted_target) == before_skills
    status_for(tests, "omitted_skills_preserved", omitted_preserved)
    assert_equal(omitted_preserved, True, "omitting skills did not preserve learned skills")

    # An explicit empty array is the deletion contract.
    empty_skills_patch = copy.deepcopy(omitted_skills_patch)
    empty_skills_patch["skills"] = []
    empty_skills_path = write_patch(work_dir, "skills-empty.json", empty_skills_patch)
    empty_skills_output = work_dir / "skills-empty.vsgm1"
    apply_patch(engine, copied_input, empty_skills_output, empty_skills_path)
    empty_skills_readback = inspect(engine, empty_skills_output)
    empty_skills_removed = skill_map(hero_map(empty_skills_readback)[target_id]) == {}
    status_for(tests, "empty_skills_remove_all", empty_skills_removed)
    assert_equal(empty_skills_removed, True, "empty skills array did not remove learned skills")

    # Other heroes and player/day metadata must be preserved by an edit aimed
    # at one human hero.  No names are copied into the result artifact.
    target_owner = int(target["owner"])
    expected_other_heroes = copy.deepcopy(before_heroes)
    for hero_id in other_hero_ids:
        if int(expected_other_heroes[hero_id].get("owner", -1)) == target_owner:
            expected_other_heroes[hero_id]["cheated"] = False
    other_heroes_ok = all(after_heroes[hero_id] == expected_other_heroes[hero_id] for hero_id in other_hero_ids)
    expected_players = copy.deepcopy(before.get("players", []))
    for player in expected_players:
        if int(player.get("color", -1)) == target_owner:
            player["cheated"] = False
    metadata_ok = after.get("day") == before.get("day") and after.get("players") == expected_players
    status_for(tests, "other_heroes_unchanged", other_heroes_ok)
    status_for(tests, "day_and_player_metadata_unchanged", metadata_ok)
    assert_equal(other_heroes_ok, True, "an unrelated hero changed")
    assert_equal(metadata_ok, True, "day or player metadata changed")

    baseline_cheated = bool(target.get("cheated"))
    clear_cheated_observed = baseline_cheated and not bool(edited_target.get("cheated"))
    status_for(
        tests,
        "clear_cheated_observation",
        bool(edited_target.get("cheated")) is False,
        baseline_cheated=baseline_cheated,
        clear_cheated_observed=clear_cheated_observed,
        observation=(
            "true_to_false_observed"
            if clear_cheated_observed
            else "baseline_false_transition_not_tested"
            if not baseline_cheated
            else "transition_not_observed"
        ),
    )
    assert_equal(bool(edited_target.get("cheated")), False, "clearCheated did not leave owner uncheated")

    # Each negative case uses a fresh output name.  The overwrite case reuses
    # the already-created roundtrip output and verifies its bytes are stable.
    negative_cases: list[tuple[str, dict[str, Any], str]] = []
    invalid_skill = copy.deepcopy(patch)
    invalid_skill["skills"] = [{"id": max(catalog_skills) + 100_000, "level": 1}]
    negative_cases.append(("invalid-skill", invalid_skill, "invalid skill"))
    invalid_level = copy.deepcopy(patch)
    valid_skill_id = min(catalog_skills)
    invalid_level["skills"] = [{"id": valid_skill_id, "level": 4}]
    negative_cases.append(("invalid-skill-level", invalid_level, "invalid skill level"))
    duplicate_skill = copy.deepcopy(patch)
    duplicate_skill["skills"] = [
        {"id": valid_skill_id, "level": 1},
        {"id": valid_skill_id, "level": 2},
    ]
    negative_cases.append(("duplicate-skill", duplicate_skill, "duplicate skill"))
    non_integer_skill = copy.deepcopy(patch)
    non_integer_skill["skills"] = [{"id": valid_skill_id, "level": 1.5}]
    negative_cases.append(("non-integer-skill", non_integer_skill, "non-integer skill level"))
    empty_army = copy.deepcopy(patch)
    empty_army["army"] = []
    negative_cases.append(("empty-army", empty_army, "empty army"))
    invalid_value = copy.deepcopy(patch)
    invalid_value["stats"] = [1000, stats[1], stats[2], stats[3]]
    negative_cases.append(("invalid-value", invalid_value, "invalid numeric value"))

    rejected = 0
    for stem, negative_patch, label in negative_cases:
        patch_path = write_patch(work_dir, stem + ".json", negative_patch)
        output_path = work_dir / (stem + ".vsgm1")
        result = invoke(engine, "apply", copied_input, output_path, patch_path)
        if result.returncode != 0 and not output_path.exists():
            rejected += 1
        else:
            raise TestFailure(label + " was accepted")
    status_for(tests, "invalid_inputs_rejected", rejected == len(negative_cases), cases=rejected)
    assert_equal(rejected, len(negative_cases), "not all invalid inputs were rejected")

    existing_hash_before = sha256(roundtrip_output)
    overwrite_patch = write_patch(work_dir, "overwrite.json", patch)
    overwrite_result = invoke(engine, "apply", copied_input, roundtrip_output, overwrite_patch)
    overwrite_rejected = overwrite_result.returncode != 0 and sha256(roundtrip_output) == existing_hash_before
    status_for(tests, "existing_output_not_overwritten", overwrite_rejected)
    assert_equal(overwrite_rejected, True, "existing output was overwritten")

    # The supplied input and the copied input must remain byte-identical after
    # all commands.  A changed source is a hard test failure.
    input_unchanged = sha256(save) == original_hash and sha256(copied_input) == copied_hash
    status_for(tests, "input_unchanged", input_unchanged)
    assert_equal(input_unchanged, True, "input hash changed")

    passed = all(entry.get("status") == "passed" for entry in tests.values())
    return {
        "schema_version": 1,
        "test_kind": "copy_only_native_readback",
        "status": "passed" if passed else "failed",
        "engine_architecture": "arm64",
        "save_format_tested": SAVE_VERSION,
        "tests": tests,
        "game_client_reload_verified": False,
        "notes": [
            "The input save was copied before every edit and its SHA-256 was unchanged.",
            "Results contain no input paths, hero names, UUIDs, or command output.",
            "The spell check records the spellbook and observed count; it does not enumerate every mod spell.",
            "This verifies native editor readback only; it does not verify VCMI client reload.",
        ],
    }


def main() -> int:
    args = parse_args()
    try:
        engine, save, work_dir, result_path = prepare_paths(args)
    except TestFailure:
        # Path validation deliberately happens before creating a work
        # directory, copying a save, or writing a report.
        return 2
    result: dict[str, Any]
    try:
        result = run_tests(engine, save, work_dir)
    except TestFailure as error:
        result = {
            "schema_version": 1,
            "test_kind": "copy_only_native_readback",
            "status": "failed",
            "tests": {},
            "game_client_reload_verified": False,
            "notes": [
                "The copy-only test stopped before all checks completed.",
                "Failure category: " + str(error),
                "This verifies native editor readback only; it does not verify VCMI client reload.",
            ],
        }
    except Exception:
        result = {
            "schema_version": 1,
            "test_kind": "copy_only_native_readback",
            "status": "failed",
            "tests": {},
            "game_client_reload_verified": False,
            "notes": [
                "The copy-only test stopped because of an unexpected local test error.",
                "This verifies native editor readback only; it does not verify VCMI client reload.",
            ],
        }
    try:
        write_result(result_path, result)
    except OSError:
        # Keep diagnostics out of the artifact.  The exit code still lets a
        # caller distinguish a result-writing failure.
        return 2
    return 0 if result.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
