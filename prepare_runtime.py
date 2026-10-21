#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Prepare an exact external VCMI runtime from the official pinned DMG.

No game data is installed. All writes stay in explicit build/download folders.
The VCMI dylibs are external build inputs, not source-rebuilt by this script.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from build_support import ROOT, fresh, load, protect, run, sha256, write

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-dir',type=Path,required=True)
    p.add_argument('--download-dir',type=Path,required=True)
    p.add_argument('--offline',action='store_true')
    a=p.parse_args(); output=fresh(a.runtime_dir); cache=protect(a.download_dir)
    cache.mkdir(parents=True,exist_ok=True)
    report={'status':'started','commands':[],'source_rebuild_of_vcmi_libraries':False}
    mount=output/'mount'; mounted=False
    try:
        spec=load(ROOT/'dependencies.lock.json')['runtime_reference']
        archive=cache/'VCMI-macOS-arm.dmg'
        if not archive.exists():
            if a.offline:raise RuntimeError('Missing pinned runtime DMG')
            r=run(['curl','-fL','--retry','2','--connect-timeout','15','--max-time','300','-o',archive,spec['url']],output/'logs','download')
            report['commands'].append(r)
            if r['returncode']:raise RuntimeError('Runtime download failed')
        if sha256(archive)!=spec['sha256']:raise RuntimeError('Runtime archive checksum mismatch')
        r=run(['hdiutil','attach','-readonly','-nobrowse','-mountpoint',mount,archive],output/'logs','attach')
        report['commands'].append(r)
        if r['returncode']:raise RuntimeError('Read-only runtime mount failed')
        mounted=True
        apps=list(mount.glob('*.app'))
        if len(apps)!=1:raise RuntimeError('Expected one VCMI application in DMG')
        app=output/'VCMI.app';shutil.copytree(apps[0],app,symlinks=True)
        for name,h in load(ROOT/'runtime.lock.json')['library_sha256'].items():
            if sha256(app/'Contents/Frameworks'/name)!=h:raise RuntimeError('Runtime library mismatch: '+name)
        report.update(status='success',archive_sha256=sha256(archive),runtime_app=str(app))
    except Exception as e:
        report.update(status='failed',error=str(e));print(str(e),file=sys.stderr)
    finally:
        if mounted:
            r=run(['hdiutil','detach',mount],output/'logs','detach');report['commands'].append(r)
            if r['returncode']:report.update(status='failed',error='Failed to detach temporary runtime mount')
    write(output/'runtime-manifest.json',report)
    print('RUNTIME_PREPARE_'+report['status'].upper())
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
