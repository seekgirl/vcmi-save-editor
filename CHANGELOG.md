# Changelog

This changelog covers the `v0.2.0-alpha.1` source preview and later work.

## Unreleased

- Complete GUI-flow, clean-machine, minimum-OS, and full in-game reload validation.
- Recheck distribution obligations for the project-owned code and every embedded dependency before attaching any binary.

## v0.2.0-alpha.1 — source preview

- First source preview for Apple Silicon macOS and VCMI 1.7.5 / save format 902.
- Edit human-controlled heroes' primary stats, mana, army stacks, and secondary skills.
- One-click learn the current library's ordinary hero spells, adding a missing spellbook when needed; arbitrary spell removal or spellbook editing is not included.
- Clear the local save `cheated` field to `false`; arbitrary values are not supported, and this is not an account-level or comprehensive anti-cheat guarantee.
- Correct the reversed explanation of the clear-cheat-mark option without changing its behavior.
- Include the generated application icon and provenance; keep third-party trademark rights separate.
- Add a reproducible dependency-preparation, engine-build, SwiftUI assembly, and copy-regression workflow.
- Record the fixed VCMI, Boost, oneTBB, and external-runtime sources in `DEPENDENCY_SOURCES.md`.
- Preserve the earlier `0.1.4 build 5` as a baseline; the fresh development build is `0.1.5 build 7`.

This source preview contains source only; the validated `0.1.5 build 7` development app is not distributed as an installer or Release asset. See TESTING.md for the gameplay, clean-machine, minimum-OS, notarization, and GUI-flow limitations.
