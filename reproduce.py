#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Replay verified dependency preparation, engine compilation and app assembly."""
import argparse
from pathlib import Path
import sys
from build_support import ROOT, fresh, run, sha256, write

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--download-dir',type=Path,required=True)
    p.add_argument('--deps-dir',type=Path,help='optional verified source cache, never an object cache')
    p.add_argument('--vcmi-app',type=Path,required=True)
    p.add_argument('--offline',action='store_true')
    p.add_argument('--jobs',type=int,default=3)
    a=p.parse_args();out=fresh(a.work_dir)
    deps=a.deps_dir.expanduser().resolve() if a.deps_dir else out/'deps'
    report={'status':'started','commands':[],'object_cache_used':False}
    try:
        commands=[['prepare-deps',[sys.executable,str(ROOT/'prepare_deps.py'),'--deps-dir',str(deps),'--download-dir',str(a.download_dir.resolve()),*(['--offline'] if a.offline else [])]],
                  ['build-engine',[sys.executable,str(ROOT/'build_engine.py'),'--deps-dir',str(deps),'--vcmi-app',str(a.vcmi_app.resolve()),'--output-dir',str(out/'engine'),'--jobs',str(a.jobs)]],
                  ['build-app',[sys.executable,str(ROOT/'build_app.py'),'--engine',str(out/'engine/editor-engine'),'--vcmi-app',str(a.vcmi_app.resolve()),'--output-dir',str(out/'app')]]]
        for label,command in commands:
            print('RUN '+label,flush=True)
            r=run(command,out/'logs',label);report['commands'].append(r)
            if r['returncode']:raise RuntimeError(label+' failed; see logs')
        report.update(status='success',engine_sha256=sha256(out/'engine/editor-engine'))
    except Exception as e:report.update(status='failed',error=str(e));print(str(e),file=sys.stderr)
    write(out/'reproduction-manifest.json',report)
    print('REPRODUCTION_'+report['status'].upper())
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
