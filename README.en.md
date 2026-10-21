# VCMI Save Editor

> **v0.2.0-alpha.1 source preview**

VCMI Save Editor is an independent, unofficial local macOS Apple Silicon tool for editing hero data in VCMI 1.7.5 single-player saves. The maintainer attribution is **seekgirl**. This directory contains the `v0.2.0-alpha.1` source preview: the validated development app is `0.1.5 build 7`, and this preview contains source only with no installer.

VCMI Save Editor is not affiliated with, authorized by, or endorsed by the VCMI team, Ubisoft, or the rights holders of *Heroes of Might and Magic III*. VCMI and the game names, data, and trademarks remain the property of their respective rights holders.

## Current status

One clean source build and local copy regression pass have been completed. This is still an alpha preview and does not promise cross-machine compatibility or complete game playability:

- 18 source files (17 VCMI server files plus this project's `engine.cpp`) were compiled and linked in a clean output directory.
- The SwiftUI app was assembled as development build `0.1.5 build 7` with ad hoc signing for validation only. This preview includes no installer or notarized application.
- Fourteen native copy checks passed, covering save inspection, round-trip save, hero primary stats, mana, armies, one-click learning of the current library's ordinary hero spells, secondary-skill add/remove/level changes, other-hero and metadata protection, invalid inputs, overwrite protection, and input-hash checks. The spell check observed 69 entries; that is an observation count, not an exhaustive enumeration.
- The save path compiled from the actual Swift backend passed copy tests; the target copy changed while other copies and the original input stayed unchanged.
- The complete GUI flow, a full game turn, combat, quit-and-reload, a separate clean machine, and a macOS 13.0 device are still unverified.
- An older headless `vcmiclient --headless --testsave` path ended with `SIGSEGV (-11)`; this does not establish a corrupt save or a successful load.
- The combined army/secondary-skill window automation reached automatic loading and stopped in the lobby; this is evidence of neither a corrupt save nor a successful game load. One older representative window test did load an edited copy once, but this round did not complete in-game verification.
- This round rebuilt the editor/helper. The external VCMI, Boost, and oneTBB dynamic libraries came from a fixed official runtime and were not rebuilt entirely from source in this round. See [`DEPENDENCY_SOURCES.md`](DEPENDENCY_SOURCES.md) for sources, versions, commits, hashes, and parameters.
- A redacted build and test summary is in [`TESTING.md`](TESTING.md).

## Features

- Detect the current user's `~/Library/Application Support/vcmi/Saves`; open the latest save or choose a file manually, and close the app with its Close button. Saving replaces only the selected file.

- Read and validate binary `.vsgm1` single-player saves for VCMI 1.7.5, save format 902.
- Select a hero owned by a human player and edit attack, defense, power, knowledge, and mana.
- Edit unit types and counts in all seven army slots.
- One-click learn the ordinary hero spells currently provided by the library; add a spellbook when the hero lacks one. There is currently no arbitrary spell removal, spellbook editing, or arbitrary spell-value control.
- Add, remove, or change the level of learned secondary skills, including Wisdom, Logistics, Earth Magic, and other skills represented by the save.
- The clear-cheat-mark option is enabled by default. When enabled, saving clears the local owning player's `cheated` field to `false`; disabling it preserves the original state. The field cannot be set to arbitrary values. This only changes save data; it is not an account-level, network, or comprehensive anti-cheat status reset.
- Save through a temporary file, a full VCMI readback, an input-unchanged check, and an atomic replacement of the selected file.

## Support and limitations

| Item | Current scope |
| --- | --- |
| VCMI | 1.7.5, fixed commit `6901839ae9760dfcd1d5ff2c4aa4ef6968fee752` |
| Save format | 902; primarily binary `.vsgm1` |
| Platform | Apple Silicon / arm64; app deployment target macOS 13.0+ |
| Actual build host | macOS 27.0.1, Apple clang 21.0.0, Swift 6.3.2; this does not extend the minimum OS claim |
| Game mode | Offline, single-player, human-player heroes |

There is currently no compatibility claim for arbitrary VCMI versions, original `.gm1` files, multiplayer saves, battle saves, AI-owned heroes, Windows, Linux, or Intel Macs. Users must obtain VCMI, the original game data, and matching Mods lawfully; this project does not include those game assets.

## Save safety

On first use, duplicate the save in Finder and open the copy. Saving directly replaces the selected file; the app does not create a permanent backup automatically. The backend first writes a same-directory temporary file, validates it through the full VCMI read path, confirms that the input has not changed, and then performs an atomic replacement. A failed validation should leave the original file untouched. The complete GUI button flow is still under test, so the backend evidence should not be read as validation of every UI path.

## Build from source

You need Apple Silicon macOS, Python 3.11.4+, Git, curl, Xcode Command Line Tools, and a VCMI 1.7.5 runtime matching the lock files. Read [`BUILDING.md`](BUILDING.md) first; it records the pinned versions, dependency preparation, build parameters, offline replay, and logging requirements.

From the source directory containing these scripts, start with fresh output directories:

```sh
python3 prepare_runtime.py \
  --runtime-dir ../new-runtime \
  --download-dir ../downloads

python3 reproduce.py \
  --work-dir ../new-build \
  --download-dir ../downloads \
  --vcmi-app ../new-runtime/VCMI.app
```

The build scripts reject non-empty output directories and never fall back to the old `0.1.4 build 5` binary. They check the VCMI version, fixed commit, save format, runtime hashes, and a fresh compilation manifest. The app contains only the rebuilt editor/helper; it does not bundle VCMI, Boost, or oneTBB dynamic libraries or game data.

After building, run the native and backend regressions on a copy:

```sh
python3 scripts/test_save_copy.py \
  --engine ../new-build/engine/editor-engine \
  --save /path/to/a-save-copy.vsgm1 \
  --work-dir ../test-native-new

python3 scripts/test_backend_copy.py \
  --engine ../new-build/engine/editor-engine \
  --save /path/to/a-save-copy.vsgm1 \
  --work-dir ../test-backend-new \
  --vcmi-app /Applications/VCMI.app
```

`/path/to/a-save-copy.vsgm1` is only an example. Do not commit personal saves, game assets, or build logs containing personal absolute paths to a public repository.

## Licensing and upstream relationship

Project-owned portions use **GPL-3.0-or-later**; the maintainer has confirmed this choice and recorded it in [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md). Embedded or adapted upstream files retain their original licenses and are not relicensed by the project-owned code declaration:

- VCMI source files: GPL-2.0-or-later, with original file headers, author information, and license text retained.
- Boost 1.83.0: Boost Software License 1.0.
- oneTBB 2021.13.0: Apache-2.0.

See [`DEPENDENCY_SOURCES.md`](DEPENDENCY_SOURCES.md) and `third_party/` for the corresponding sources and license files. Do not describe the complete combination directory as having one blanket license, remove upstream attribution, or distribute Heroes III game assets as project content.

## Contributions and issue reports

Use the repository's issue templates and provide the editor version, VCMI version, macOS/CPU, save format, and reproducible steps. Use a copy of the save; do not upload personal saves, copyrighted game data, private keys, account credentials, or local absolute paths. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md) before contributing.

Version history is in [`CHANGELOG.md`](CHANGELOG.md) and [`RELEASE_NOTES_ALPHA.md`](RELEASE_NOTES_ALPHA.md). GUI, in-game reload, and clean-environment gaps remain documented alpha limitations.
