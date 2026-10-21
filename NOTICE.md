# Copyright, provenance and licensing

Project-owned code, documentation and project artwork in this source preview are offered under **GPL-3.0-or-later**, to the extent the maintainer has rights to license them. Copyright © 2026 **seekgirl**. The maintainer confirmed the authority and licensing choice for this preparation. The complete GNU GPL version 3 text is in [LICENSE](LICENSE); “or later” is the grant for the project-owned portions, not a modification of that license text.

This does **not** relabel third-party works as seekgirl's property. Original notices and grants remain in force:

| Component | Version / source | Copyright and license |
|---|---|---|
| VCMI | 1.7.5, `6901839ae9760dfcd1d5ff2c4aa4ef6968fee752` | VCMI team and individual contributors; **GPL-2.0-or-later**. Retain original source headers, [AUTHORS.h](third_party/vcmi/AUTHORS.h), and [license.txt](third_party/vcmi/license.txt). |
| Boost | Official 1.83.0 archive, locked SHA-256 | Individual Boost contributors; **BSL-1.0**, [original license](third_party/boost/LICENSE_1_0.txt). |
| oneTBB | 2021.13.0, `1c4c93fc5398c4a1acb3492c02db4699f3048dea` | Copyright holders in upstream files, including Intel Corporation; **Apache-2.0**, [original license](third_party/onetbb/LICENSE.txt). Preserve applicable additional notices when redistributing upstream material. |
| macOS frameworks and SDK | Provided by the user's Apple development environment | Apple/system components; no framework or SDK is redistributed here. |

The C++ adapter uses VCMI types, APIs, and save/load ordering. Its custom code is not a substitute implementation of the VCMI engine. The build compiles 17 VCMI server source files and links the external libvcmi/Boost/TBB libraries. Those files are fetched at fixed sources; the checkout is not modified or stripped of its notices. Exact inputs are in [DEPENDENCY_SOURCES.md](DEPENDENCY_SOURCES.md) and the lock files.

VCMI's “or later” grant permits compatible use under a later GPL version. Apache-2.0 is compatible with GPLv3, while it is not compatible with GPLv2 alone; see the [GNU license compatibility explanation](https://www.gnu.org/licenses/license-list.html#apache2). This project uses GPL-3.0-or-later for its own portions and preserves the broader upstream VCMI grant. This notice does not change Boost or oneTBB's original terms.

## Artwork, game data and names

The icon was generated from a text prompt, without supplying an official game image or screenshot. Its provenance and grant are recorded in [assets/ICON_PROVENANCE.md](assets/ICON_PROVENANCE.md) and [assets/LICENSE.md](assets/LICENSE.md). Software/artwork licensing does not grant rights in third-party trademarks, names, or official game artwork.

No commercial Heroes III data, music, map collection, personal save, third-party Mod package, or external VCMI application is included. Users must obtain and configure their own legally usable data. This is an independent, unofficial project, with no claimed affiliation, authorization or endorsement by the VCMI team or Heroes of Might and Magic III's rights holders.

## Source preview and future binaries

This candidate contains **source only**. No application executable, dylib, or installer is distributed in it. Build logs and test save copies remain private. The helper and UI were locally rebuilt for validation, but those development binaries are not publication assets.

Any future binary distribution must separately establish complete corresponding source for the exact build, applicable build/install scripts, third-party notices, and the source/licensing arrangement for all covered non-system components. The existence of this source preview or an upstream repository link is not, by itself, a claim that all future binary-distribution obligations have been fulfilled.

## 中文说明

本项目自有代码、文档与项目图标，按维护者确认的权利范围采用 GPL-3.0-or-later，署名 seekgirl。第三方文件继续归原权利人，并保留 VCMI GPL-2.0-or-later、Boost BSL-1.0、oneTBB Apache-2.0 及各文件原始声明。这里没有把第三方成果重授权为维护者独有作品。

当前仅准备源码预览，不附应用二进制、游戏数据或个人存档。将来分发二进制前仍须核对实际构建对应源码与全部适用义务；图标和软件许可均不代表商标授权或官方背书。
