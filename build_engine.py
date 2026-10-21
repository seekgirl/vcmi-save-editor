#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Compile every editor/server source in a fresh directory; never reuse objects."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import plistlib
import subprocess
import sys
from build_support import ROOT, clean_environment, fresh, load, run, sha256, write

LIBS=['vcmi','boost_filesystem','boost_program_options','boost_locale','boost_container','boost_atomic','tbb']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deps-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--vcmi-app',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=3)
    p.add_argument('--deployment-target',default='13.0')
    a=p.parse_args(); out=fresh(a.output_dir)
    report={'status':'started','fresh_object_directory':True,'commands':[]}
    try:
        if a.jobs<1 or a.jobs>8: raise RuntimeError('jobs must be 1..8')
        deps=a.deps_dir.expanduser().resolve(); app=a.vcmi_app.expanduser().resolve()
        lock=load(ROOT/'dependencies.lock.json'); manifest=load(deps/'dependency-manifest.json')
        if manifest['status']!='success' or manifest['lock_sha256']!=sha256(ROOT/'dependencies.lock.json'): raise RuntimeError('Run prepare_deps.py for this lock first')
        for name in ['vcmi','onetbb']:
            head=subprocess.check_output(['git','-C',str(deps/name),'rev-parse','HEAD'],text=True).strip()
            dirty=subprocess.check_output(['git','-C',str(deps/name),'status','--porcelain','--untracked-files=all'],text=True)
            if head!=lock[name]['commit'] or dirty: raise RuntimeError('Source checkout changed: '+name)
        vcmi=deps/'vcmi'; boost=deps/'boost_1_83_0'; tbb=deps/'onetbb'
        if not manifest['boost'].get('header_sha256'): raise RuntimeError('Re-run prepare_deps.py to record header checksums')
        for name, expected in manifest['boost']['header_sha256'].items():
            if sha256(deps/name)!=expected: raise RuntimeError('Boost header changed since preparation: '+name)
        with (app/'Contents/Info.plist').open('rb') as f: info=plistlib.load(f)
        if info.get('CFBundleShortVersionString')!='1.7.5' or info.get('CFBundleVersion')!=lock['vcmi']['commit']: raise RuntimeError('Expected VCMI 1.7.5 fixed commit')
        frameworks=app/'Contents/Frameworks'
        runtime_lock=load(ROOT/'runtime.lock.json')
        for name,expected in runtime_lock['library_sha256'].items():
            if sha256(frameworks/name)!=expected: raise RuntimeError('Runtime library differs from reviewed lock: '+name)
        report['runtime']={'vcmi_version':'1.7.5','commit':lock['vcmi']['commit'],'library_sha256':runtime_lock['library_sha256'],'app_path':str(app)}
        env=clean_environment()
        report['toolchain']={cmd:subprocess.check_output(args,text=True,env=env).strip() for cmd,args in [('clang',['xcrun','clang++','--version']),('sdk',['xcrun','--show-sdk-version']),('sdk_path',['xcrun','--show-sdk-path'])]}
        objdir=out/'objects'; objdir.mkdir()
        base=['xcrun','clang++','-std=c++20','-arch','arm64','-isysroot',report['toolchain']['sdk_path'],'-O1','-DNDEBUG','-Wno-switch','-fno-aligned-allocation','-DSCRIPTING_ENABLED=0','-DBOOST_FILESYSTEM_VERSION=3','-DBOOST_ALL_NO_LIB',f'-mmacosx-version-min={a.deployment_target}']
        base += ['-I'+str(x) for x in [vcmi,vcmi/'include',vcmi/'lib',vcmi/'server',boost,tbb/'include']]
        files=[(name,vcmi/name) for name in lock['server_sources']]+[('engine.cpp',ROOT/'engine.cpp')]
        report['source_sha256']={name:sha256(src) for name,src in files}
        report['build_scripts_sha256']={name:sha256(ROOT/name) for name in ['build_engine.py','build_support.py','dependencies.lock.json','runtime.lock.json']}
        def compile_one(item):
            name,src=item; obj=objdir/(name.replace('/','_')+'.o')
            record=run(base+['-c',src,'-o',obj],out/'logs',name.replace('/','_'),env=env)
            print(('COMPILED ' if record['returncode']==0 else 'FAILED ')+name,flush=True)
            return record,obj
        with ThreadPoolExecutor(max_workers=a.jobs) as pool: results=list(pool.map(compile_one,files))
        report['commands']=[r for r,o in results]
        if any(r['returncode'] for r,o in results): raise RuntimeError('Compilation failed; see per-file logs')
        output=out/'editor-engine'
        link=['xcrun','clang++','-arch','arm64',f'-mmacosx-version-min={a.deployment_target}',*[str(o) for r,o in results],'-L'+str(frameworks),*['-l'+x for x in LIBS],'-Wl,-rpath,'+str(frameworks),'-o',str(output)]
        record=run(link,out/'logs','link',env=env); report['commands'].append(record)
        if record['returncode']: raise RuntimeError('Link failed; see logs/link.stderr.log')
        report['status']='success'; report['object_files_compiled']=len(files)
        report['binary_sha256']=sha256(output); report['binary_path']=str(output)
        report['dependency_manifest_sha256']=sha256(deps/'dependency-manifest.json')
        report['binary_dependencies']=subprocess.check_output(['otool','-L',str(output)],text=True)
        print('ENGINE_BUILD_OK: 18 source files freshly compiled')
    except Exception as e:
        report['status']='failed'; report['error']=str(e); print(str(e),file=sys.stderr)
    write(out/'build-manifest.json',report)
    return 0 if report['status']=='success' else 1

if __name__=='__main__': raise SystemExit(main())
