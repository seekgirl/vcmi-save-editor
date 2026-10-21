# VCMI Save Editor

> **v0.2.0-alpha.1 源码预览**

VCMI Save Editor 是一个独立、非官方的 macOS Apple Silicon 本地工具，用于编辑 VCMI 1.7.5 单机存档中的英雄数据。维护者署名为 **seekgirl**。本目录包含 `v0.2.0-alpha.1` 源码预览：应用开发版为 `0.1.5 build 7`，本预览仅含源码，不附安装包。

VCMI Save Editor 与 VCMI 团队、Ubisoft 或《魔法门之英雄无敌 III》的权利人没有隶属、授权或背书关系。VCMI 与游戏名称、游戏数据及相关商标仍归其各自权利人所有。

## 当前状态

本轮已完成一次独立源码构建和本地副本回归，但这仍是 alpha 预览，不能当作跨机器兼容性或完整游戏可玩性承诺：

- 18 个源码文件（17 个 VCMI server 文件和本项目的 `engine.cpp`）在干净输出目录中重新编译并成功链接。
- SwiftUI 应用已组装为 `0.1.5 build 7` 开发版，使用 ad hoc 签名；该开发版仅用于验证，本预览不附安装包，也没有公证版应用。
- 14 项原生副本检查通过，覆盖存档读取、往返保存、英雄四维、法力、部队、当前库普通英雄法术的一键学习、副技能增删与等级调整、其他英雄和元数据保护、无效输入、覆盖保护及输入哈希检查；法术检查观察到 69 个条目，这只是观察数量，不是穷举证明。
- 从实际 Swift 后端编译出的保存路径对副本测试通过；目标副本被更新，其他副本和原始输入保持不变。
- GUI 全流程、完整游戏回合、战斗、退出后重新加载，以及独立干净机器和 macOS 13.0 实机尚未完成验收。
- 旧的 headless `vcmiclient --headless --testsave` 路径出现 `SIGSEGV (-11)`；这不能判定存档损坏，也不能当作成功加载证据。
- 组合兵种/副技能的窗口自动载入停在大厅；这不能判定存档损坏，也不能当作游戏读取成功。一次旧的代表性窗口测试曾成功加载编辑副本，但本轮没有完成游戏内验收。
- 本轮重建的是编辑器/helper；VCMI、Boost、oneTBB 的外部动态库使用固定官方运行库，没有在本轮从源码完整重建。来源、版本、提交、哈希和参数见 [`DEPENDENCY_SOURCES.md`](DEPENDENCY_SOURCES.md)。
- 脱敏的构建与测试摘要见 [`TESTING.md`](TESTING.md)。

## 功能

- 读取和检查 VCMI 1.7.5、存档格式 902 的二进制 `.vsgm1` 单机存档。
- 默认检测当前用户的 `~/Library/Application Support/vcmi/Saves`；支持“打开最新存档”、手动选档和关闭按钮。保存只覆盖当前选中的文件。
- 选择人类玩家拥有的英雄，编辑攻击、防御、力量、知识四项主属性和法力值。
- 编辑七个部队槽的兵种与数量。
- 一键学习当前库提供的普通英雄法术；英雄缺少魔法书时补上魔法书。当前没有任意移除法术、任意编辑法术书或选择任意法术值的操作。
- 增加、移除或调整已学习的副技能，包括智慧、后勤、土系等由存档支持的技能。
- “清除作弊者标记”默认勾选；勾选时保存会将本地玩家存档中的 `cheated` 字段清为 `false`，取消勾选则保留原状态，不能任意调节该字段。该操作只针对存档数据，不代表账号级、联网或全面反作弊状态。
- 通过临时文件、完整 VCMI 读回、输入未变化检查和原子替换保存所选文件。

## 支持范围与限制

| 项目 | 当前范围 |
| --- | --- |
| VCMI | 1.7.5，固定提交 `6901839ae9760dfcd1d5ff2c4aa4ef6968fee752` |
| 存档格式 | 902；主要针对二进制 `.vsgm1` |
| 平台 | Apple Silicon / arm64；应用构建目标 macOS 13.0+ |
| 实际构建机 | macOS 27.0.1、Apple clang 21.0.0、Swift 6.3.2；没有据此扩大最低系统承诺 |
| 游戏模式 | 离线、单人、人类玩家英雄 |

当前不承诺支持任意 VCMI 版本、原版 `.gm1`、多人存档、战斗存档、AI 所有的英雄、Windows、Linux 或 Intel Mac。用户必须自行合法安装 VCMI、原版游戏数据和匹配 Mod；本项目不包含这些游戏资源。

## 保存安全

第一次使用时，请在 Finder 中复制存档并打开副本。保存会直接覆盖当前选中的文件，应用不会自动生成永久备份。后端保存流程会先写同目录临时文件，使用完整 VCMI 读取路径验证，再确认输入文件没有变化后原子替换；验证失败时不应替换原文件。GUI 的完整按钮流程仍在继续验收，因此不要把这段后端证据理解为所有界面路径都已验证。

## 从源码构建

需要 Apple Silicon macOS、Python 3.11.4+、Git、curl、Xcode Command Line Tools，以及与锁文件完全匹配的 VCMI 1.7.5 运行库。请先阅读 [`BUILDING.md`](BUILDING.md)，它记录了固定版本、依赖准备、构建参数、离线重放和日志要求。

在包含这些脚本的源码目录中，可以从全新的输出目录开始：

```sh
python3 prepare_runtime.py \
  --runtime-dir ../new-runtime \
  --download-dir ../downloads

python3 reproduce.py \
  --work-dir ../new-build \
  --download-dir ../downloads \
  --vcmi-app ../new-runtime/VCMI.app
```

构建脚本拒绝非空输出目录，也不会回退到旧的 `0.1.4 build 5` 二进制。它会检查 VCMI 版本、固定提交、存档格式、运行库哈希和新生成的编译清单。应用只包含重新编译的编辑器/helper，不捆绑 VCMI、Boost、oneTBB 动态库或游戏数据。

构建完成后，可用副本运行原生和后端回归：

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

`/path/to/a-save-copy.vsgm1` 只是示例路径。不要把个人存档、游戏资源或带有个人路径的构建日志提交到公共仓库。

## 许可证与上游关系

本项目自有部分采用 **GPL-3.0-or-later**；维护者已确认这一选择，并已写入 [`LICENSE`](LICENSE) 和 [`NOTICE.md`](NOTICE.md)。嵌入或改编的上游文件保留原许可证，不因本项目的自有代码声明而被重新授权：

- VCMI 源文件：GPL-2.0-or-later，并保留原始文件头、作者信息和许可证文本。
- Boost 1.83.0：Boost Software License 1.0。
- oneTBB 2021.13.0：Apache-2.0。

对应来源和许可证文件见 [`DEPENDENCY_SOURCES.md`](DEPENDENCY_SOURCES.md) 以及 `third_party/`。请不要把整个组合目录简单描述为单一许可证，也不要删除上游署名或把 Heroes III 游戏资源当作本项目内容分发。

## 参与和问题反馈

请使用仓库内的 issue 模板，并提供编辑器版本、VCMI 版本、macOS/CPU、存档格式和可复现步骤；只使用存档副本，不上传个人存档、版权游戏数据、私钥、账号凭据或本地绝对路径。贡献前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md) 与 [`SECURITY.md`](SECURITY.md)。

版本记录见 [`CHANGELOG.md`](CHANGELOG.md) 和 [`RELEASE_NOTES_ALPHA.md`](RELEASE_NOTES_ALPHA.md)。GUI、游戏读回、干净环境等未验收项会作为 alpha 限制继续记录。
