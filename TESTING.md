# Build and copy-test evidence / 构建与副本测试

Validation date: **2026-10-21**. This is a source-only alpha candidate, not a binary release or a claim of full gameplay acceptance.

## Current candidate

The candidate's own C++ adapter and 17 pinned VCMI server files were compiled from source into new, empty output directories. Both native builds compiled **18 objects** and completed **19 successful compiler/linker commands**. No old object files or prebuilt editor helper were reused. A previously verified dependency **source** cache and the fixed official external runtime were reused and rechecked; this was not an empty-machine or full dependency-from-source build.

The first sandboxed attempt built the helper but failed at macOS `iconutil` with `Invalid Iconset`. The failure was retained. A complete replay in a fresh directory outside that restriction succeeded. The final SwiftUI app was rebuilt after correcting the reversed explanation next to the clear-cheat-mark option. The option's behavior and original editing functionality were preserved.

| Check | Observed result |
| --- | --- |
| Platform | Apple Silicon, macOS 27.0.1 |
| Interpreter | Python 3.11.15 |
| Toolchain | Apple clang 21.0.0, Swift 6.3.2, SDK 26.5 |
| Target | arm64, macOS 13.0; no separate minimum-OS device tested |
| VCMI / format | 1.7.5, pinned commit, format 902 |
| Native helper | Fresh source compilation and link passed |
| SwiftUI app | 0.1.5 build 7 development app; final assembly passed |
| App icon | AppIcon.icns generated from assets/AppIcon.png, referenced by Info.plist |
| Signature | Local ad hoc signature verification passed; no notarization |

A matching helper hash across rebuilds is not used as proof of compilation. The command records and newly generated object files provide the compilation evidence. Private manifests include commands, return codes, toolchain details, source and product SHA-256 values. Those raw logs contain local paths and are intentionally excluded from this source preview.

## Copy-only regression

`scripts/test_save_copy.py` produced **14 passed checks**, including six rejected invalid-input cases. Covered checks:

- Inspect format 902 and perform read → save → full native readback.
- Modify attack, defense, power, knowledge and mana.
- Change an army quantity and replace a creature type.
- Verify a spellbook is present after ordinary hero spell learning: 69 entries in this fixture; neither an exhaustive spell-catalog assertion nor a test of missing-book completion on a bookless hero.
- Add/remove secondary skills and increase/decrease their levels; no requested operation skipped.
- Preserve skills when the patch omits them, and remove them when the patch explicitly supplies an empty list.
- Preserve other heroes and inspected day/player metadata.
- Reject invalid fields and an already existing output file.
- Preserve the supplied fixture's SHA-256.

The cheat-field check observed `false` before and after. **A true → false transition was not exercised by this fixture**; the passed observation is not evidence of that transition or of external anti-cheat status.

`scripts/test_backend_copy.py` compiles the actual Swift backend from `ui/Editor.swift`. Its overwrite path passed: one selected file among three fresh copies changed, the other two copies and the supplied fixture remained byte-identical. The final source was tested again after the explanatory-text correction. This checks the backend, not every GUI control.

No personal original save was selected as an output, and no test save is distributed. To reproduce these tests, supply your own legally usable save **copy** using the commands in [BUILDING.md](BUILDING.md). The scripts require an appropriate fixture; missing heroes, stacks or skill-level combinations can fail coverage rather than silently claim a pass.

## Historical evidence and unresolved limits

One earlier representative windowed game test loaded an edited copy once. It is historical evidence, not acceptance of this candidate's complete GUI or gameplay. An earlier headless client test ended with `SIGSEGV (-11)`. Automatic window loading of a combined army/secondary-skills test stopped in the lobby before a successful load was established. Neither failed path proves corruption, nor does either count as successful game reload.

Still unverified: full GUI editing flow, the combined patch loaded and played in game, a complete turn, combat, quit-and-reload, independent clean-machine installation, macOS 13.0 hardware, arbitrary Mods and VCMI versions. External libvcmi/Boost/oneTBB dylibs were pinned official inputs, not fully rebuilt from source. A future binary release needs its own distribution and corresponding-source review.

## 中文结论

候选源码已在新输出目录重编译，应用和图标已组装，原生 14 项副本检查及真实 Swift 覆盖保存后端通过；首次受限图标工具失败记录已保留。输入副本与另外两个保存副本保持不变，未覆盖个人原始存档。

本轮是本机源码构建和副本回归，不等于干净机器安装或完整游戏验收。作弊字段的 true → false 转换未在本轮样本验证，法术 69 条只是观察数量。原始命令日志和测试存档不随源码公开。
