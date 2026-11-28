"""Synthetic review metadata only; never live governance evidence."""
import copy
import json
from load_policy import ROOT


def subject(head="a"*40, base="b"*40, triggers=None):
    return {"repository":"tmlau8/my-ea", "change_id":"FIX-EXAMPLE", "policy_version":"1.1.0-rc.1", "head_sha":head, "base_sha":base, "trigger_ids":["assurance"] if triggers is None else triggers, "builder_id":"builder-agent-1", "builder_session_id":"synthetic-builder-session"}


def bundle(expected=None):
    expected = expected or subject()
    source = json.loads((ROOT/'templates/review-bundle.example.json').read_text())
    seed = json.loads((ROOT/'templates/review-record.example.json').read_text())
    records = []
    for role in ["adversarial", "quality", "specialist"]:
        r = copy.deepcopy(seed); r['record_id'] = 'SYNTHETIC-'+role
        r['review_type'] = role; r['reviewer']['id'] = 'synthetic-reviewer-'+role; r['reviewer']['session_id'] = 'synthetic-session-'+role
        r.update({k:expected[k] for k in ['repository','change_id','policy_version']})
        r['reviewed_revision']={'head_sha':expected['head_sha'],'base_sha':expected['base_sha']}
        r['trigger_ids']=expected['trigger_ids']
        if role=='specialist':r['specialist']='synthetic-test-specialist'
        for artifact in r['artifacts_inspected']:
            if 'revision' in artifact:artifact['revision']=expected['head_sha']
        records.append(r)
    return {'records':records,'artifacts':source['artifacts']}
