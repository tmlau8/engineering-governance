"""Final local validation; --reload-preview explicitly reloads owned services.

No merge, release, GitHub writes, model requests or global client changes.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python312',default='/tmp/governance-coverage-py312/bin/python')
    parser.add_argument('--reload-preview',action='store_true')
    parser.add_argument('--runtime-only',action='store_true',help='Reuse separately completed test evidence and check/reload only the live preview')
    args=parser.parse_args()
    env=dict(os.environ,PYTHONPATH='tooling:evidence:tests',PYTHONDONTWRITEBYTECODE='1')
    if args.runtime_only:print('Runtime-only check: regression suites and package checks skipped.',flush=True)
    if not args.runtime_only:
        for executable,expected in [(str(ROOT/'.venv/bin/python'),[3,9]),(args.python312,[3,12])]:
            version=json.loads(subprocess.check_output([executable,'-B','-c','import json,sys;print(json.dumps(list(sys.version_info[:2])))'],cwd=ROOT,env=env))
            if version!=expected:raise SystemExit('EXPECTED_PYTHON_VERSION_UNAVAILABLE')
            subprocess.run([executable,'-B','-m','unittest','discover','-s','tests'],cwd=ROOT,env=env,check=True)
        subprocess.run([sys.executable,'-B','tooling/check_package.py'],cwd=ROOT,env=env,check=True)
    if not args.reload_preview:
        print('Preview not reloaded.' if args.runtime_only else 'Full regression suites and package checks passed; preview not reloaded.')
        return
    runtime=ROOT/'.runtime'
    credentials=json.loads((runtime/'secrets/credentials.json').read_text())
    settings=json.loads((runtime/'settings.json').read_text())
    spec=importlib.util.spec_from_file_location('usage_dashboard',ROOT/'dashboard/build.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.provision(runtime,credentials,settings['api_port'],settings['grafana_port'])
    for action in ['stop','start']:
        subprocess.run([sys.executable,'-B','evidence/manage.py',action],cwd=ROOT,env=env,check=True)
    subprocess.run([sys.executable,'-B','tests/check_grafana_runtime.py','check'],cwd=ROOT,env=env,check=True)
    print('Live panel/filter queries passed. Browser inspection and fixture cleanup remain required.')


if __name__=='__main__':main()
