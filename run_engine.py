#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Validate the configured VCMI runtime before launching the rebuilt helper."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
from build_support import ROOT, clean_environment, load, sha256

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine',type=Path,required=True)
    p.add_argument('--vcmi-app',type=Path,default=Path(os.environ.get('VCMI_APP_PATH','/Applications/VCMI.app')))
    p.add_argument('arguments',nargs=argparse.REMAINDER)
    a=p.parse_args();app=a.vcmi_app.expanduser().resolve();engine=a.engine.expanduser().resolve()
    with (app/'Contents/Info.plist').open('rb') as f:info=plistlib.load(f)
    lock=load(ROOT/'dependencies.lock.json')
    if info.get('CFBundleShortVersionString')!='1.7.5' or info.get('CFBundleVersion')!=lock['vcmi']['commit']:raise RuntimeError('VCMI version/commit mismatch')
    framework=app/'Contents/Frameworks'
    for name,h in load(ROOT/'runtime.lock.json')['library_sha256'].items():
        if sha256(framework/name)!=h:raise RuntimeError('Runtime library hash mismatch: '+name)
    env=clean_environment();env['VCMI_APP_PATH']=str(app);env['DYLD_LIBRARY_PATH']=str(framework)
    return subprocess.call([str(engine),*a.arguments],env=env)

if __name__=='__main__':raise SystemExit(main())
