# 固定构建输入与来源

日期：2026-10-21。此文件说明固定构建输入。自有部分采用 GPL-3.0-or-later；不重授权上游文件，详见 [NOTICE.md](NOTICE.md)。

| 输入 | 本轮固定来源 | 校验 / 许可 |
|---|---|---|
| VCMI 源码 | [vcmi/vcmi](https://github.com/vcmi/vcmi/tree/6901839ae9760dfcd1d5ff2c4aa4ef6968fee752)，1.7.5，`6901839ae9760dfcd1d5ff2c4aa4ef6968fee752` | checkout 提交及工作树核验；GPL-2.0-or-later |
| Boost 头文件 | [官方 1.83.0 归档](https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.bz2)，commit `564e2ac16907019696cdaba8a93e3588ec596062` | [官方元数据](https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.bz2.json)，SHA-256 `6478edfe2f3305127cffe8caf73ea0176c53769f4bf1585be237eb30798c3b8e`；BSL-1.0 |
| oneTBB 头文件 | [oneTBB v2021.13.0](https://github.com/uxlfoundation/oneTBB/tree/1c4c93fc5398c4a1acb3492c02db4699f3048dea)，commit `1c4c93fc5398c4a1acb3492c02db4699f3048dea` | checkout 提交及工作树核验；Apache-2.0 |
| 外部 VCMI macOS arm 运行库 | [官方 1.7.5 DMG](https://github.com/vcmi/vcmi/releases/download/1.7.5/VCMI-macOS-arm.dmg) | SHA-256 `b56b55d0671ae604effb12d0394b74a552f203426cafa165f82488505fb465e3`；所用 17 个库文件另按 `runtime.lock.json` 逐文件锁定 |
| 官方依赖包参考 | [dependencies-mac-arm.txz，标签 2026-07-07](https://github.com/vcmi/vcmi-dependencies/releases/tag/2026-07-07) | SHA-256 `88c0a27d137ae27cc86da5762d9f50c9080be13380afd2b416de3335a4ac8dd0`；本轮已下载并验证其元数据；不是标签 1.7.5 |

VCMI 固定提交引用的 dependencies 子模块为 `2e1924490c80547a8f85ed88aca29223057e832b`，与上述依赖发布的源码提交对应。其 [Conan recipe](https://github.com/vcmi/vcmi-dependencies/blob/2e1924490c80547a8f85ed88aca29223057e832b/conanfile.py) 包含范围约束，不能单凭它推出某次二进制的具体版本；本轮还核查了固定发布条目、包内 version 头文件、conaninfo/conandata 和运行库。

本机相关 17 个 dylib 与官方 DMG 中对应文件 SHA-256 一致。oneTBB 运行时 API 返回 `2021.13.0`，接口版本 `12130`。包内 Boost 头文件 `BOOST_VERSION=108300`；依赖发布记录和包元数据标明 Boost 1.83.0。依赖包中的原库与最终签名应用中的库并非逐字节相同；最终运行库以 DMG 的逐文件哈希锁定，不混写为“原 Conan 库哈希相同”。

旧脚本的 `boost_1_90_0` 目录名不证明旧 helper 的确切历史输入。本轮改为明确锁定 1.83.0，不声称复原旧 helper 的全部原始构建参数或生成相同字节。

## 参数

- 本轮 helper：Apple clang 21.0.0、C++20、arm64、`-O1 -DNDEBUG -fno-aligned-allocation`；`SCRIPTING_ENABLED=0`、`BOOST_FILESYSTEM_VERSION=3`、`BOOST_ALL_NO_LIB`；最低 macOS 13.0，显式 SDK。原脚本的功能源文件集合和关键宏保留。
- 编入 helper 的 **17 个 server 文件**逐一列于 `dependencies.lock.json` 的 `server_sources`，连同自定义 `engine.cpp` 共 18 个文件，每次全部重新编译。每个文件的命令、输出及 SHA-256 记录在引擎 build-manifest 和日志中。
- 外部 Boost 包的 conaninfo：armv8、Release、apple-clang 16、C++20、libc++、macOS 11.0、shared=true、layout=system、multithreading=true、visibility=hidden；locale 使用 iconv，ICU 关闭，zlib/bzip2 开启。这些是固定官方依赖包的已核查参数；原始本机证据未随源码预览分发。可从上表锁定的官方依赖包中复核 conaninfo、version 头文件及对应 recipe。
- 外部 oneTBB 包：armv8、Release、apple-clang 16、C++20、libc++、macOS 11.0；interprocedural_optimization=true、tbbbind=false、tbbmalloc=false、build_apple_frameworks=false。
- 外部 libvcmi 的完整原始编译命令与签名重定位过程没有在本轮从源码复现。引用固定官方二进制能固定 helper 链接输入，但不能冒充“所有依赖源码重建成功”。若下一轮要求全栈源码构建，仍须重放上游 CI/Conan 锁和所有传递依赖。

## 版权与声明

VCMI 原始文件头、[作者表](third_party/vcmi/AUTHORS.h) 和 [GPL 文本](third_party/vcmi/license.txt) 必须保留；Boost 的 [BSL](third_party/boost/LICENSE_1_0.txt) 和 oneTBB 的 [Apache 许可证](third_party/onetbb/LICENSE.txt) 已从本轮固定源码原样保留。各贡献者继续拥有各自文件中声明的权利。

本项目不修改上游 checkout，不捆绑外部 dylib 到开发版应用，也不许可商业 Heroes III 游戏资源。维护者已确认有权将自有部分按 GPL-3.0-or-later 提供，署名 seekgirl；VCMI 的 GPL-2.0-or-later、Boost BSL-1.0 和 oneTBB Apache-2.0 保持不变。未来二进制分发仍须单独核对完整对应源码及全部适用义务；构建成功不等于这些义务已全部处理。
