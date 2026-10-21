# VCMI Save Editor v0.2.0-alpha.1

**Independent, unofficial `v0.2.0-alpha.1` source preview for Apple Silicon macOS users of VCMI 1.7.5 (save format 902).** The validated application is development build `0.1.5 build 7`; this preview contains source only and no installer. This project is not affiliated with, authorized by, or endorsed by the VCMI team, Ubisoft, or the rights holders of *Heroes of Might and Magic III*.

Maintainer attribution: **seekgirl**.

## Included functions

- Select an offline single-player binary `.vsgm1` save and a hero owned by a human player.
- Edit attack, defense, power, knowledge, and mana.
- Edit the seven army slots. One-click learn the ordinary hero spells currently provided by the library; add a spellbook when the hero lacks one. Arbitrary spell removal, spellbook editing, and arbitrary spell-value control are not included.
- Add, remove, or change the level of learned secondary skills, including Wisdom, Logistics, Earth Magic, and other skills represented by the save.
- The clear-cheat-mark option is enabled by default. When enabled, saving clears the local owning player's `cheated` field to `false`; disabling it preserves the original state. It cannot set arbitrary values. This is a save-data change with limited scope, not an account-level or comprehensive anti-cheat reset.
- Save the selected file through temporary output, full readback, input-change checking, and atomic replacement.

## Requirements and compatibility

- Apple Silicon macOS; application deployment target macOS 13.0+. The minimum target has not been tested on a separate macOS 13.0 machine.
- VCMI **1.7.5**, fixed commit `6901839ae9760dfcd1d5ff2c4aa4ef6968fee752`, save format **902**, matching local game data and Mods.
- No support claim for arbitrary VCMI versions, original `.gm1` files, multiplayer, battle saves, AI-owned heroes, Windows/Linux, or Intel Macs.
- First use: duplicate the save in Finder and open the duplicate. Saving overwrites the selected file; the app does not create a permanent backup automatically.

## Verification status

- 18 source files were freshly compiled and linked in a clean output directory.
- The SwiftUI development app was assembled as `0.1.5 build 7` with ad hoc signing; it is not notarized and no binary is attached to this preview.
- Fourteen native copy checks and the real Swift-backend copy path passed for the covered fields and save-protection checks. The spell check observed 69 entries; this is an observation count, not an exhaustive enumeration.
- Full GUI automation, a complete game turn, combat, quit-and-reload, a separate clean machine, and a macOS 13.0 device remain unverified.
- An older headless `vcmiclient --headless --testsave` path ended with `SIGSEGV (-11)`; this is evidence about that client test path, not proof of a corrupt save or a successful load.
- Combined army/secondary-skill window automation reached automatic loading and stopped in the lobby; it is evidence of neither a corrupt save nor a successful game load. One older representative window test loaded an edited copy once, but this round did not complete in-game verification.
- External VCMI/Boost/oneTBB runtime libraries were fixed and checked but were not rebuilt fully from source in this round. See [`DEPENDENCY_SOURCES.md`](DEPENDENCY_SOURCES.md).
- A redacted build and test summary is provided in [`TESTING.md`](TESTING.md).

## Installation and source build

This preview is source-only. Follow [`README.md`](README.md) and [`BUILDING.md`](BUILDING.md). The validated `0.1.5 build 7` application is not included as an installer or Release asset. The unverified game checks above remain alpha limitations.

## Reporting issues

Use the repository's issue templates with the VCMI version, save format, macOS version/CPU, editor build, exact steps, and redacted diagnostics. Do not attach copyrighted game data or personal saves without appropriate rights. For security reports, follow [`SECURITY.md`](SECURITY.md).

