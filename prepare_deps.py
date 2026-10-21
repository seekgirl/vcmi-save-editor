#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fetch/verify pinned source dependencies. Installs no system software."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tarfile
from build_support import ROOT, load, protect, run, sha256, write

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deps-dir', type=Path, required=True)
    p.add_argument('--download-dir', type=Path, required=True)
    p.add_argument('--offline', action='store_true')
    a=p.parse_args()
    deps=protect(a.deps_dir); downloads=protect(a.download_dir)
    deps.mkdir(parents=True,exist_ok=True); downloads.mkdir(parents=True,exist_ok=True)
    lock=load(ROOT/'dependencies.lock.json')
    report={'status':'started','lock_sha256':sha256(ROOT/'dependencies.lock.json'),'commands':[]}
    try:
        for name in ['vcmi','onetbb']:
            spec=lock[name]; dst=deps/name
            if not dst.exists():
                if a.offline: raise RuntimeError('Missing offline dependency: '+name)
                rec=run(['git','clone','--depth','1','--branch',spec['tag'],spec['repository'],dst],deps/'prepare-logs','clone-'+name)
                report['commands'].append(rec)
                if rec['returncode']: raise RuntimeError('Clone failed: '+name)
            head=subprocess.check_output(['git','-C',str(dst),'rev-parse','HEAD'],text=True).strip()
            dirty=subprocess.check_output(['git','-C',str(dst),'status','--porcelain','--untracked-files=all'],text=True)
            if head!=spec['commit'] or dirty: raise RuntimeError('Dependency commit/tree mismatch: '+name)
            report[name]={'commit':head,'git_tree_clean':True}
        spec=lock['boost']; archive=downloads/Path(spec['url']).name
        if not archive.exists():
            if a.offline: raise RuntimeError('Missing Boost source archive')
            rec=run(['curl','-fL','--retry','2','--connect-timeout','15','--max-time','600','-o',archive,spec['url']],deps/'prepare-logs','download-boost')
            report['commands'].append(rec)
            if rec['returncode']: raise RuntimeError('Boost download failed; incomplete download not trusted')
        if sha256(archive)!=spec['sha256']: raise RuntimeError('Boost checksum mismatch')
        boost=deps/'boost_1_83_0'
        if not boost.exists():
            with tarfile.open(archive) as t: t.extractall(deps,filter='data')
        if '#define BOOST_VERSION 108300' not in (boost/'boost/version.hpp').read_text(): raise RuntimeError('Boost header version mismatch')
        headers={}
        with tarfile.open(archive) as t:
            for m in t:
                if m.isfile() and (m.name.startswith('boost_1_83_0/boost/') or m.name=='boost_1_83_0/LICENSE_1_0.txt'):
                    f=t.extractfile(m)
                    expected=hashlib.sha256(f.read()).hexdigest() if f else None
                    if not expected or expected!=sha256(deps/m.name): raise RuntimeError('Boost extracted file mismatch: '+m.name)
                    headers[m.name]=expected
        report['boost']={'version':spec['version'],'archive_sha256':sha256(archive),'verified_files':len(headers),'header_sha256':headers}
        report['server_source_sha256']={name:sha256(deps/'vcmi'/name) for name in lock['server_sources']}
        report['status']='success'
        print('DEPENDENCIES_VERIFIED: VCMI 1.7.5, Boost 1.83.0, oneTBB 2021.13.0')
    except Exception as e:
        report['status']='failed'; report['error']=str(e); print(str(e),file=sys.stderr)
    write(deps/'dependency-manifest.json',report)
    return 0 if report['status']=='success' else 1

if __name__=='__main__': raise SystemExit(main())
