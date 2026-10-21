#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Build and assemble an isolated development app bundle.

This script deliberately accepts an already rebuilt editor-engine.  It never
falls back to the 0.1.4 binary or copies any VCMI/Boost/oneTBB libraries into
the bundle.  A fresh, empty output directory is required for every build.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shlex
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from build_support import protect, clean_environment


EXPECTED_VCMI_VERSION = "1.7.5"
EXPECTED_VCMI_COMMIT = "6901839ae9760dfcd1d5ff2c4aa4ef6968fee752"
EXPECTED_SAVE_FORMAT = 902
APP_NAME = "VCMI Save Editor Dev.app"
EXECUTABLE_NAME = "VCMISaveEditor"
HELPER_NAME = "editor-engine"


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_string(command: list[str]) -> str:
    return shlex.join(command)


def ensure_empty_output(path: Path) -> None:
    protect(path)
    if path.exists():
        if not path.is_dir():
            raise BuildError(f"output directory is not a directory: {path}")
        if any(path.iterdir()):
            raise BuildError(f"refusing to overwrite non-empty output directory: {path}")
    else:
        path.mkdir(parents=True)


def load_plist(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            value = plistlib.load(stream)
    except (OSError, plistlib.InvalidFileException) as error:
        raise BuildError(f"cannot read property list: {path}: {error}") from error
    if not isinstance(value, dict):
        raise BuildError(f"property list is not a dictionary: {path}")
    return value


def validate_vcmi_app(path: Path) -> dict[str, str]:
    app = path.expanduser().resolve()
    if not app.is_dir():
        raise BuildError(f"VCMI app directory does not exist: {app}")

    info_path = app / "Contents" / "Info.plist"
    info = load_plist(info_path)
    version = str(info.get("CFBundleShortVersionString", ""))
    commit = str(info.get("CFBundleVersion", ""))
    if version != EXPECTED_VCMI_VERSION or commit != EXPECTED_VCMI_COMMIT:
        raise BuildError(
            "VCMI version mismatch: expected "
            f"{EXPECTED_VCMI_VERSION} / {EXPECTED_VCMI_COMMIT}, got {version or 'unknown'} / "
            f"{commit or 'unknown'} ({info_path})"
        )

    frameworks = app / "Contents" / "Frameworks"
    macos = app / "Contents" / "MacOS"
    if not frameworks.is_dir():
        raise BuildError(f"VCMI Frameworks directory does not exist: {frameworks}")
    if not macos.is_dir():
        raise BuildError(f"VCMI MacOS directory does not exist: {macos}")
    return {
        "path": str(app),
        "infoPlist": str(info_path),
        "version": version,
        "commit": commit,
        "frameworks": str(frameworks),
        "macos": str(macos),
        "infoSha256": sha256(info_path),
    }


def validate_engine(path: Path, root: Path) -> tuple[Path, str, str]:
    engine = path.expanduser().resolve()
    if not engine.is_file():
        raise BuildError(f"editor-engine does not exist: {engine}")
    if not os.access(engine, os.X_OK):
        raise BuildError(f"editor-engine is not executable: {engine}")

    digest = sha256(engine)
    # Evidence of compilation is required even if deterministic output ever
    # becomes byte-identical to a previous binary. A changed hash is no proof.
    proof = engine.parent / "build-manifest.json"
    if not proof.is_file():
        raise BuildError("missing fresh engine build-manifest.json")
    record = json.loads(proof.read_text())
    if (record.get("status") != "success"
        or record.get("object_files_compiled") != 18
        or record.get("binary_sha256") != digest
        or record.get("source_sha256", {}).get("engine.cpp") != sha256(root / "engine.cpp")
        or record.get("binary_path") != str(engine)
        or len(record.get("commands", [])) != 19
        or any(c.get("returncode") != 0 for c in record["commands"])):
        raise BuildError("engine build evidence is incomplete or does not match the binary")

    file_result = subprocess.run(
        ["file", "-b", str(engine)], capture_output=True, text=True, check=False
    )
    description = (file_result.stdout or file_result.stderr).strip()
    if file_result.returncode != 0:
        raise BuildError(f"cannot inspect editor-engine architecture: {description}")
    if "Mach-O" not in description or "arm64" not in description:
        raise BuildError(f"editor-engine must be an arm64 Mach-O executable: {description}")
    return engine, digest, description


def run_logged(
    label: str,
    command: list[str],
    logs_dir: Path,
    records: list[dict[str, Any]],
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False,
                            env=clean_environment())
    stdout_path = logs_dir / f"{label}.stdout.log"
    stderr_path = logs_dir / f"{label}.stderr.log"
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")
    records.append(
        {
            "label": label,
            "command": command,
            "commandString": command_string(command),
            "returnCode": result.returncode,
            "stdoutLog": str(stdout_path),
            "stderrLog": str(stderr_path),
        }
    )
    return result


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path, help="freshly rebuilt editor-engine")
    parser.add_argument("--output-dir", required=True, type=Path, help="new or empty output directory")
    parser.add_argument("--vcmi-app", required=True, type=Path, help="VCMI 1.7.5 application bundle")
    parser.add_argument("--deployment-target", default="13.0")
    parser.add_argument("--version", default="0.1.5")
    parser.add_argument("--build", default="7")
    parser.add_argument("--icon", type=Path, default=None, help="PNG icon; defaults to assets/AppIcon.png")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent
    swift_source = root / "ui" / "Editor.swift"
    output_dir = protect(args.output_dir)
    manifest_path = output_dir / "build-manifest.json"
    logs_dir = output_dir / "build-logs"
    command_records: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "status": "not_started",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "sourceRoot": str(root),
        "sourceFiles": {"ui/Editor.swift": str(swift_source)},
        "engineInput": str(args.engine.expanduser().resolve()),
        "outputDir": str(output_dir),
        "appName": APP_NAME,
        "version": args.version,
        "build": str(args.build),
        "deploymentTarget": args.deployment_target,
        "supportedVCMI": {
            "version": EXPECTED_VCMI_VERSION,
            "commit": EXPECTED_VCMI_COMMIT,
            "saveFormat": EXPECTED_SAVE_FORMAT,
        },
        "bundlesThirdPartyLibraries": False,
        "commands": command_records,
    }

    output_owned = False
    try:
        ensure_empty_output(output_dir)
        output_owned = True
        logs_dir.mkdir()
        if not swift_source.is_file():
            raise BuildError(f"Swift source does not exist: {swift_source}")

        engine, engine_digest, engine_description = validate_engine(args.engine, root)
        vcmi = validate_vcmi_app(args.vcmi_app)
        manifest["vcmi"] = vcmi
        manifest["sourceSha256"] = {"ui/Editor.swift": sha256(swift_source), "build_app.py": sha256(Path(__file__))}
        manifest["engineInputSha256"] = engine_digest
        manifest["engineInputFile"] = engine_description

        app = output_dir / APP_NAME
        contents = app / "Contents"
        macos_dir = contents / "MacOS"
        resources_dir = contents / "Resources"
        macos_dir.mkdir(parents=True)
        resources_dir.mkdir()

        icon_source = (args.icon or root / "assets" / "AppIcon.png").expanduser().resolve()
        if not icon_source.is_file():
            raise BuildError(f"Application icon is missing: {icon_source}")
        iconset = output_dir / "AppIcon.iconset"
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                pixels = points * scale
                suffix = "@2x" if scale == 2 else ""
                destination = iconset / f"icon_{points}x{points}{suffix}.png"
                conversion = run_logged(
                    f"icon-{points}-{scale}",
                    ["sips", "-z", str(pixels), str(pixels), str(icon_source), "--out", str(destination)],
                    logs_dir, command_records,
                )
                if conversion.returncode:
                    raise BuildError("Application icon size conversion failed")
        icon_file = resources_dir / "AppIcon.icns"
        conversion = run_logged(
            "icon-icns", ["iconutil", "-c", "icns", str(iconset), "-o", str(icon_file)],
            logs_dir, command_records,
        )
        if conversion.returncode:
            raise BuildError("Application ICNS assembly failed")
        manifest["icon"] = {
            "source": str(icon_source), "sourceSha256": sha256(icon_source),
            "bundleFile": "Contents/Resources/AppIcon.icns", "icnsSha256": sha256(icon_file),
        }

        info = {
            "CFBundleDisplayName": "VCMI Save Editor Dev",
            "CFBundleExecutable": EXECUTABLE_NAME,
            "CFBundleIdentifier": "local.gg.vcmisaveeditor.dev",
            "CFBundleName": "VCMI Save Editor Dev",
            "CFBundlePackageType": "APPL",
            "CFBundleIconFile": "AppIcon.icns",
            "CFBundleShortVersionString": args.version,
            "CFBundleVersion": str(args.build),
            "LSMinimumSystemVersion": args.deployment_target,
            "NSHighResolutionCapable": True,
            "VCMIAppPath": vcmi["path"],
            "VCMIExpectedVersion": EXPECTED_VCMI_VERSION,
            "VCMIExpectedCommit": EXPECTED_VCMI_COMMIT,
            "VCMISaveFormatVersion": EXPECTED_SAVE_FORMAT,
        }
        info_path = contents / "Info.plist"
        with info_path.open("wb") as stream:
            plistlib.dump(info, stream, fmt=plistlib.FMT_XML, sort_keys=False)

        main_binary = macos_dir / EXECUTABLE_NAME
        sdk_path = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
        manifest["toolchain"] = {
            "swift": subprocess.check_output(["xcrun", "swift", "--version"], text=True).strip(),
            "sdkPath": sdk_path,
            "sdkVersion": subprocess.check_output(["xcrun", "--show-sdk-version"], text=True).strip(),
        }
        compile_command = [
            "xcrun",
            "swiftc",
            "-O",
            "-parse-as-library",
            "-target",
            f"arm64-apple-macosx{args.deployment_target}",
            "-sdk",
            sdk_path,
            "-module-cache-path",
            str(output_dir / "module-cache"),
            str(swift_source),
            "-framework",
            "SwiftUI",
            "-framework",
            "AppKit",
            "-o",
            str(main_binary),
        ]
        compile_result = run_logged("swift-compile", compile_command, logs_dir, command_records)
        if compile_result.returncode != 0:
            raise BuildError(f"SwiftUI compilation failed with exit code {compile_result.returncode}")

        helper = resources_dir / HELPER_NAME
        shutil.copy2(engine, helper)
        helper.chmod(helper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        sign_command = [
            "codesign",
            "--force",
            "--deep",
            "--sign",
            "-",
            "--timestamp=none",
            str(app),
        ]
        sign_result = run_logged("codesign-adhoc", sign_command, logs_dir, command_records)
        if sign_result.returncode != 0:
            raise BuildError(f"ad hoc code signing failed with exit code {sign_result.returncode}")

        manifest["status"] = "success"
        manifest["appPath"] = str(app)
        manifest["binarySha256"] = {
            "Contents/MacOS/VCMISaveEditor": sha256(main_binary),
            "Contents/Resources/editor-engine": sha256(helper),
            "Contents/Info.plist": sha256(info_path),
            "Contents/Resources/AppIcon.icns": sha256(icon_file),
        }
        manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()
        write_manifest(manifest_path, manifest)
        print(f"BUILD_APP_OK {app}")
        return 0
    except (BuildError, OSError, subprocess.SubprocessError) as error:
        manifest["status"] = "failed"
        manifest["error"] = str(error)
        manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()
        if output_owned and logs_dir.exists():
            write_manifest(manifest_path, manifest)
        print(f"BUILD_APP_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
