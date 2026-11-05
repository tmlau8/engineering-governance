"""Verify catalogue synchronization and deterministic bundle construction in CI."""
import json
from pathlib import Path
import tempfile
from build_release import build
from load_policy import ROOT
from render_policy import render
from verify_bundle import verify


def check():
    catalogue = json.loads((ROOT / 'policy/requirements.json').read_text())
    policy = json.loads((ROOT / 'policy/gates.yaml').read_text())
    coverage = json.loads((ROOT / 'policy/control-coverage.json').read_text())
    if catalogue['version'] != policy['version'] or (ROOT / 'policy/engineering.md').read_text() != render():
        raise ValueError('CATALOGUE_VIEW_OR_VERSION_MISMATCH')
    rules = {r['id'] for r in catalogue['rules']}
    if rules != {r['id'] for r in coverage['requirements']}:
        raise ValueError('COVERAGE_INVENTORY_MISMATCH')
    for status in ['enforced','detected','guidance_only']:
        if coverage[status] != sum(r['status'] == status for r in coverage['requirements']):
            raise ValueError('COVERAGE_TOTAL_MISMATCH')
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp)/'a', Path(tmp)/'b'
        first, second = build(a), build(b)
        if first != second or (a/'manifest.json').read_bytes() != (b/'manifest.json').read_bytes():
            raise ValueError('NONDETERMINISTIC_BUNDLE')
        verify(a,first['manifest_sha256']); verify(b,second['manifest_sha256'])
        print(json.dumps({'result':'byte_integrity_verified','rules':len(rules),**first}))


if __name__ == '__main__':check()
