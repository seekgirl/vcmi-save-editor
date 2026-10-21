# Contributing to VCMI Save Editor

Thank you for helping improve this independent, unofficial VCMI save-editing tool. The maintainer attribution for the current candidate is **seekgirl**.

## Scope

The current pre-release target is Apple Silicon macOS with VCMI 1.7.5, fixed commit `6901839ae9760dfcd1d5ff2c4aa4ef6968fee752`, and save format 902. The supported use case is offline single-player saves with human-owned heroes. Changes for other platforms, formats, or game modes should begin with a compatibility discussion and evidence.

## Bug reports

Use the bug-report template once a public issue tracker exists. Include the editor version, exact VCMI version and commit when known, save format, macOS version/CPU, test type, steps, expected result, and actual result. Reproduce with a copy of the save.

Do not post personal saves, private file paths, account credentials, secrets, original game data, Mods, or copyrighted game assets. A minimal synthetic or clearly redistributable test fixture is preferable. Redact build logs before sharing them because they may contain local paths.

## Code changes

1. Discuss changes that affect save serialization, write behavior, version checks, or licensing before implementing them.
2. Preserve the existing hero stats, mana, armies, one-click learning of current ordinary hero spells with missing-spellbook completion, secondary skills, clearing the local `cheated` field to `false`, and atomic-save behavior.
3. Test only on copies of saves. Never overwrite a player's original as part of a test.
4. Run the clean-source build and the native/backend copy regressions described in [`BUILDING.md`](BUILDING.md), or explain exactly why a check could not run.
5. Include commands, relevant return codes, and compatibility limits in the change description. Do not attach private logs or personal data.
6. Keep VCMI headers, author information, third-party notices, and license files intact. Do not add unreviewed upstream code or game resources.

## Licensing

Project-owned portions use GPL-3.0-or-later as confirmed by the maintainer. VCMI source remains GPL-2.0-or-later; Boost and oneTBB retain their respective licenses. Contributions must be compatible with these boundaries and must identify any copied or adapted code and its original license. See [`LICENSE`](LICENSE), [`NOTICE.md`](NOTICE.md), and [`DEPENDENCY_SOURCES.md`](DEPENDENCY_SOURCES.md).

## Release quality

Alpha versions may have known bugs, but data integrity, accurate documentation, source provenance, and protection of personal data are required. A successful local build is not evidence of complete GUI, game-turn, battle, clean-machine, minimum-OS, or notarization support.

