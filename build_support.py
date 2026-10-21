# SPDX-FileCopyrightText: 2026 seekgirl
# SPDX-License-Identifier: GPL-3.0-or-later

"""Helpers for isolated source builds."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parent

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()

def load(path):
    return json.loads(Path(path).read_text())

def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def protect(path):
    path = Path(path).expanduser().resolve()
    if path == ROOT or path in ROOT.parents:
        raise RuntimeError('Output must not be the source root or its ancestor')
    if ROOT in path.parents and path.relative_to(ROOT).parts[0] in {'.git', 'assets', 'ui', 'scripts', 'third_party'}:
        raise RuntimeError('Refusing a build write inside a source or notice directory')
    return path

def fresh(path):
    path = protect(path)
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise RuntimeError('Output must be a new or empty directory: ' + str(path))
    path.mkdir(parents=True, exist_ok=True)
    return path

def run(command, logdir, label, cwd=None, env=None):
    logdir = Path(logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with (logdir / (label + '.stdout.log')).open('wb') as out, (logdir / (label + '.stderr.log')).open('wb') as err:
        r = subprocess.run(list(map(str, command)), cwd=cwd, env=env, stdout=out, stderr=err)
    return {'command': list(map(str, command)), 'returncode': r.returncode,
            'seconds': round(time.monotonic()-start, 3),
            'stdout': str(logdir / (label + '.stdout.log')),
            'stderr': str(logdir / (label + '.stderr.log'))}

def clean_environment():
    env = dict(os.environ)
    for key in list(env):
        if key.startswith('DYLD_') or key in ('CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'SDKROOT', 'MACOSX_DEPLOYMENT_TARGET'):
            env.pop(key)
    return env
