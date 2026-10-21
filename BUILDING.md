# 本地源码构建

本目录是可独立取用的源码预览 `v0.2.0-alpha.1`。本流程只向新目录写入，不覆盖已有应用或存档。构建生成 **VCMI Save Editor Dev**，应用版本 **0.1.5 / build 7**；源码预览标签和开发版应用版本分别记录，本预览不附应用二进制。

要求：Apple Silicon macOS、Python **3.11.4+**、Git、curl、Xcode Command Line Tools，以及固定 VCMI 1.7.5 运行库。实际验证环境为 macOS 27.0.1、Apple clang 21.0.0、Swift 6.3.2、SDK 26.5；应用明确以 macOS 13.0 为目标，未在 13.0 实机验证。

归档提取使用 `tarfile` 的 data filter；最低 Python 版本来自该参数在 [Python 3.11.4 的加入记录](https://docs.python.org/3.11/library/tarfile.html#tarfile.TarFile.extractall)。本轮实际运行 Python 3.11.15。

## 全新环境步骤

以下在包含这些脚本的项目根目录执行。输出目录必须不存在或为空；命令中的 `../new-*` 为示例，每次重建换一个空目录。脚本不删除旧输出，不从中取对象缓存。

```sh
# 校验/提取外部 VCMI 官方运行库；只读挂载后会自动卸载。
python3 prepare_runtime.py \
  --runtime-dir ../new-runtime \
  --download-dir ../downloads

# 拉取固定源码、校验 Boost 归档及头文件、编译引擎并组装应用。
python3 reproduce.py \
  --work-dir ../new-build \
  --download-dir ../downloads \
  --vcmi-app ../new-runtime/VCMI.app
```

运行库镜像如果已被其他程序挂载，准备步骤会报告资源忙并停止。先自行关闭/卸载对应镜像，再使用另一个空输出目录重试；脚本不会擅自卸载已有挂载。

也可提供已有 `/Applications/VCMI.app`，但其版本、提交及被使用库的 SHA-256 必须与锁文件完全匹配。不能用任意最新版替代。

已有下载缓存与已核验源码可重用；仍逐一检查，不复用编译对象：

```sh
python3 reproduce.py \
  --work-dir ../another-clean-build \
  --download-dir ../downloads \
  --deps-dir ../verified-source-cache \
  --vcmi-app /Applications/VCMI.app \
  --offline
```

`--offline` 只在下载和源码都已准备时成功；任何缺失或校验不符都停止。网络失败留下的不完整下载不会被信任；保留失败日志，换新下载目录或人工确认后处理该文件。

## 分步构建及运行

```sh
python3 prepare_deps.py --deps-dir ../deps --download-dir ../downloads
python3 build_engine.py --deps-dir ../deps --vcmi-app /Applications/VCMI.app --output-dir ../engine-new
python3 build_app.py --engine ../engine-new/editor-engine --vcmi-app /Applications/VCMI.app --output-dir ../app-new

python3 run_engine.py --engine ../engine-new/editor-engine \
  --vcmi-app /Applications/VCMI.app inspect /path/to/a-save-copy.vsgm1
```

`run_engine.py` 在启动 helper 前校验 VCMI 版本/提交及全部锁定库，设置受控的库路径。直接调用 helper 不具备包装器的全部预检。界面使用 `VCMI_APP_PATH` 环境变量优先，其次应用 Info.plist 的 `VCMIAppPath`，最后默认 `/Applications/VCMI.app`；界面会检查版本和提交，并为子进程设置所选库路径。配置到其他安装时必须提供完整匹配安装，不能只复制 Info.plist。

应用只捆绑重编译 helper，不捆绑 VCMI/Boost/TBB 动态库或游戏数据。原版 Heroes III 数据和匹配 Mod 由用户自行合法配置。这里只重建编辑器及编入它的 17 个 VCMI server 源文件；**没有从源码重建外部 libvcmi、Boost、TBB 动态库**。这些库的官方二进制来源、哈希和已知构建参数见 [DEPENDENCY_SOURCES.md](DEPENDENCY_SOURCES.md)。

## 回归测试

首次使用手动选择副本。界面保存会覆盖所选文件；不自动生成永久备份。

```sh
python3 scripts/test_save_copy.py \
  --engine ../engine-new/editor-engine --save /path/to/a-save-copy.vsgm1 \
  --work-dir ../test-native-new

python3 scripts/test_backend_copy.py \
  --engine ../engine-new/editor-engine --save /path/to/a-save-copy.vsgm1 \
  --work-dir ../test-backend-new --vcmi-app /Applications/VCMI.app
```

第一个测试引擎读写和编辑；第二个从实际 Swift 源码编译保存后端，以三个新副本测试原子覆盖和其他副本保护。它们不等于完整游戏回合/战斗或所有 GUI 按钮验收。

每个阶段保存命令、返回码、stdout/stderr、源码及产物 SHA-256。日志含实际本机路径，属于本地构建证据，公开前应另行脱敏。脚本不会在项目中写死个人 home 路径，自有部分采用 GPL-3.0-or-later，第三方保持原许可，见 [NOTICE.md](NOTICE.md)。构建可重放不等于跨工具链逐字节一致、干净机器验收或获准公开发布。
