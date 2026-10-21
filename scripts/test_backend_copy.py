#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Compile the real Swift backend into a harness; overwrite only fresh copies."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_support import ROOT, fresh, run, sha256, write

HARNESS=r'''
@main struct BackendCopyCheck {
    static func main() throws {
        let target = URL(fileURLWithPath: CommandLine.arguments[1])
        let before = try EditorBackend.inspect(at: target)
        guard let hero = before.heroes.first(where: { $0.human == true }) else {
            throw NSError(domain: "test", code: 1)
        }
        var army = hero.army
        guard !army.isEmpty else { throw NSError(domain: "test", code: 2) }
        army[0].count = min(army[0].count, 1000000) + 3
        let patch = SavePatch(hero: hero.id, stats: [21,22,23,24], mana: 245,
                              allSpells: true, clearCheated: true,
                              army: army, skills: hero.skills)
        let response = try EditorBackend.overwrite(patch: patch, input: target)
        guard response.ok else { throw NSError(domain: "test", code: 3) }
        let after = try EditorBackend.inspect(at: target)
        guard let changed = after.heroes.first(where: { $0.id == hero.id }),
              [changed.attack,changed.defense,changed.power,changed.knowledge] == [21,22,23,24],
              changed.mana == 245,
              changed.army.first(where: { $0.slot == army[0].slot })?.count == army[0].count,
              changed.skills.map({ [$0.id,$0.level] }) == hero.skills.map({ [$0.id,$0.level] })
        else { throw NSError(domain: "test", code: 4) }
        print("BACKEND_COPY_OVERWRITE_OK")
    }
}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine',type=Path,required=True)
    p.add_argument('--save',type=Path,required=True)
    p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--vcmi-app',type=Path,required=True)
    a=p.parse_args();out=fresh(a.work_dir); original=a.save.expanduser().resolve()
    before=sha256(original); report={'status':'started','commands':[]}
    try:
        copies=[out/('save-copy-'+str(i)+'.vsgm1') for i in range(3)]
        for dst in copies:shutil.copy2(original,dst)
        original_copies=[sha256(x) for x in copies]
        prefix=(ROOT/'ui/Editor.swift').read_text().split('private struct IntegerField:',1)[0]
        if '@main' in prefix or 'enum EditorBackend' not in prefix:raise RuntimeError('Swift backend extraction boundary changed')
        source=out/'BackendHarness.swift';source.write_text(prefix+HARNESS)
        app=out/'BackendHarness.app';contents=app/'Contents'
        macos=contents/'MacOS';resources=contents/'Resources'
        macos.mkdir(parents=True);resources.mkdir()
        info={'CFBundleExecutable':'BackendHarness','CFBundleIdentifier':'local.vcmi.backendtest','CFBundlePackageType':'APPL','VCMIAppPath':str(a.vcmi_app.resolve())}
        with (contents/'Info.plist').open('wb') as f:plistlib.dump(info,f)
        shutil.copy2(a.engine,resources/'editor-engine')
        binary=macos/'BackendHarness'
        command=['xcrun','swiftc','-O','-parse-as-library','-target','arm64-apple-macosx13.0','-module-cache-path',str(out/'module-cache'),str(source),'-framework','SwiftUI','-framework','AppKit','-o',str(binary)]
        r=run(command,out/'logs','compile');report['commands'].append(r)
        if r['returncode']:raise RuntimeError('Harness compilation failed')
        r=run([binary,copies[0]],out/'logs','overwrite');report['commands'].append(r)
        if r['returncode']:raise RuntimeError('Real Swift backend overwrite failed')
        report.update(input_unchanged=sha256(original)==before,other_two_copies_unchanged=[sha256(copies[i])==original_copies[i] for i in [1,2]],target_copy_changed=sha256(copies[0])!=original_copies[0],swift_source_sha256=sha256(ROOT/'ui/Editor.swift'),engine_sha256=sha256(a.engine))
        if not report['input_unchanged'] or not all(report['other_two_copies_unchanged']) or not report['target_copy_changed']:raise RuntimeError('Copy preservation assertion failed')
        report['status']='success'
    except Exception as e:report.update(status='failed',error=str(e))
    report['original_input_hash_unchanged_at_exit']=sha256(original)==before
    write(out/'backend-test-results.json',report)
    print('BACKEND_TEST_'+report['status'].upper())
    return 0 if report['status']=='success' else 1

if __name__=='__main__':raise SystemExit(main())
