import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from load_policy import ROOT
from review_records import loads, read, validate_set, validator
from review_fixtures import bundle, subject


class ReviewTests(unittest.TestCase):
    def setUp(self):self.subject=subject();self.bundle=bundle(self.subject)
    def result(self):return validate_set(self.bundle,self.subject)
    def test_complete_set_only_metadata_and_gaps(self):
        r=self.result(); self.assertEqual(r['result'],'metadata_conforming'); self.assertEqual(len(r['accepted_record_ids']),3)
        self.assertIn('review_origin_not_authenticated',r['gaps'])
    def test_remove_each_required_role_and_trigger_coverage(self):
        for role in ['adversarial','quality','specialist']:
            b=bundle();b['records']=[r for r in b['records'] if r['review_type']!=role]
            self.assertEqual(validate_set(b,self.subject)['result'],'failed')
        b=bundle();b['records'][-1]['trigger_ids']=['security'];self.assertEqual(validate_set(b,self.subject)['result'],'failed')
    def test_subject_external_not_candidate_agreement(self):
        for key,value in [('repository','other/repo'),('change_id','other'),('policy_version','other'),('head_sha','c'*40),('base_sha','c'*40)]:
            s=subject();s[key]=value
            self.assertEqual(validate_set(bundle(),s)['result'],'failed',key)
        s=subject();s['policy_version']='unrecognised'
        self.assertEqual(validate_set(bundle(s),s)['result'],'failed')
    def test_artifact_bytes_changed_missing_hash_and_reference(self):
        for mode in ['changed','missing','hash']:
            b=bundle();first=next(iter(b['artifacts']))
            if mode=='changed':b['artifacts'][first]=base64.b64encode(b'changed').decode()
            elif mode=='missing':del b['artifacts'][first]
            else:b['records'][0]['artifacts_inspected'][0].pop('sha256')
            self.assertEqual(validate_set(b,self.subject)['result'],'failed')
    def test_conditional_unavailable_and_not_cleared_never_count(self):
        for outcome in ['cleared_with_conditions','unavailable','not_cleared']:
            b=bundle();r=b['records'][0];r['outcome']=outcome
            if outcome=='cleared_with_conditions':r['conditions']=['unresolved action']
            if outcome=='unavailable':r.update(unavailable_reason='reviewer unavailable',no_substantive_challenge=False);r.pop('findings')
            self.assertFalse(list(validator().iter_errors(r)))
            self.assertEqual(validate_set(b,self.subject)['result'],'failed')
    def test_cleared_with_hidden_conditions_family_contradiction_and_deferral(self):
        for mode in ['conditions','family','deferral']:
            b=bundle();r=b['records'][0]
            if mode=='conditions':r['conditions']=['Still requires security approval']
            elif mode=='family':
                r['builder']['provenance']['model_family']='same-family';r['reviewer']['provenance']['model_family']='same-family'
                r['reviewer']['provenance']['model']='other-model';r['independence'].update(basis='different_model_family',same_model_as_builder=False,same_model_family_as_builder=False)
            else:
                r['findings'][0].update(severity='high',disposition={'state':'deferred_with_owner','rationale':'later','decided_by':r['builder']})
            self.assertEqual(validate_set(b,self.subject)['result'],'failed',mode)
    def test_superseding_nonclear_retires_clear_record(self):
        old=copy.deepcopy(self.bundle['records'][0]);new=copy.deepcopy(old);new.update(record_id='NEW',supersedes=old['record_id'],outcome='not_cleared')
        self.bundle['records'].append(new);r=self.result();self.assertEqual(r['result'],'failed');self.assertIn(old['record_id'],r['superseded_record_ids'])
    def test_superseding_cleared_can_retire_old_conditional(self):
        old=self.bundle['records'][0];new=copy.deepcopy(old);new.update(record_id='NEW',supersedes=old['record_id'])
        old.update(outcome='cleared_with_conditions',conditions=['then resolved by new evidence']);self.bundle['records'].append(new)
        self.assertEqual(self.result()['result'],'metadata_conforming')
    def test_duplicate_dangling_fork_and_cycle(self):
        for mode in ['duplicate','dangling','fork','cycle']:
            b=bundle();a=b['records'][0]
            if mode=='duplicate':b['records'].append(copy.deepcopy(a))
            elif mode=='dangling':a['supersedes']='missing'
            else:
                c=copy.deepcopy(a);c['record_id']='C';c['supersedes']=a['record_id'];b['records'].append(c)
                if mode=='cycle':a['supersedes']='C'
                else:
                    d=copy.deepcopy(c);d['record_id']='D';b['records'].append(d)
            self.assertEqual(validate_set(b,self.subject)['result'],'failed',mode)
    def test_identity_context_model_and_credential_conflicts(self):
        for mode in ['identity','session','premise','shared','unknown','basis','model']:
            b=bundle();r=b['records'][0]
            if mode=='identity':r['reviewer']['id']=r['builder']['id']
            elif mode=='session':r['reviewer']['session_id']=r['builder']['session_id']
            elif mode=='premise':r['independence']['builder_conclusions_as_premises']=True
            elif mode in ['shared','unknown']:r['independence']['credential_separation']=mode
            elif mode=='basis':r['independence']['basis']='different_human'
            else:r['independence']['same_model_as_builder']=False
            self.assertEqual(validate_set(b,self.subject)['result'],'failed',mode)
        self.bundle['records'][0]['independence']['shared_context_with_builder']=True
        self.assertEqual(self.result()['result'],'metadata_conforming')
    def test_external_builder_and_head_bound_artifact_required(self):
        for mode in ['builder','revision','family_unknown']:
            b=bundle();r=b['records'][0]
            if mode=='builder':r['builder']['id']='another-builder'
            elif mode=='revision':
                for a in r['artifacts_inspected']:a.pop('revision',None)
            else:r['independence'].update(basis='different_model_family',same_model_family_as_builder=False,same_model_as_builder=False);r['reviewer']['provenance']['model']='other'
            self.assertEqual(validate_set(b,self.subject)['result'],'failed',mode)
    def test_supported_claims_need_evidence_and_counterexamples_resolution(self):
        for mode in ['evidence','refuted','not_testable']:
            b=bundle();r=b['records'][0]
            if mode=='evidence':r['claims_examined'][0]['evidence']=[]
            else:r['counterexamples_attempted'][0]['outcome']=mode
            self.assertEqual(validate_set(b,self.subject)['result'],'failed')
    def test_principal_exact_account_digest(self):
        r=self.bundle['records'][0];r['review_type']='principal'
        self.assertTrue(list(validator().iter_errors(r)))
        r['account_reviewed']=copy.deepcopy(r['artifacts_inspected'][0]);self.assertFalse(list(validator().iter_errors(r)))
        self.bundle['artifacts'][r['account_reviewed']['reference']]=base64.b64encode(b'changed account').decode()
        self.assertEqual(self.result()['result'],'failed')
    def test_principal_binds_externally_selected_account(self):
        s=subject(triggers=[]);b=bundle(s);b['records']=[b['records'][0]];r=b['records'][0];r['review_type']='principal';r['account_reviewed']=copy.deepcopy(r['artifacts_inspected'][0])
        self.assertEqual(validate_set(b,s)['result'],'failed')
        s['account_sha256']=r['account_reviewed']['sha256'];self.assertEqual(validate_set(b,s)['result'],'metadata_conforming')
        s['account_sha256']='0'*64;self.assertEqual(validate_set(b,s)['result'],'failed')
    def test_invalid_date_unknown_fields_versions_and_empty_evidence(self):
        for mode in ['date','field','version','artifact']:
            b=bundle();r=b['records'][0]
            if mode=='date':r['created_at']='2026-99-99T99:00:00Z'
            elif mode=='field':r['invented']=True
            elif mode=='version':r['schema_version']=2
            else:r['artifacts_inspected']=[]
            self.assertEqual(validate_set(b,self.subject)['result'],'failed')
    def test_duplicate_json_and_resource_bounds(self):
        with self.assertRaises(ValueError):loads('{"a":1,"a":2}')
        with self.assertRaises(ValueError):loads('{"a":NaN}')
        with patch('review_records.MAX_RECORDS',0),self.assertRaises(ValueError):self.result()
        with patch('review_records.MAX_BYTES',1),self.assertRaises(ValueError):self.result()
    def test_external_schema_resolution_forbidden(self):
        import review_records
        original=review_records.read
        def changed(path):
            value=original(path)
            if str(path).endswith('schema.json'):value['properties']['record_id']={'$ref':'https://evil.invalid/schema'}
            return value
        with patch('review_records.read',side_effect=changed),self.assertRaisesRegex(ValueError,'EXTERNAL_SCHEMA_REFERENCE'):validator()
    def test_missing_dependency_fails_closed(self):
        code='import sys;sys.path.insert(0,"tooling");from review_records import validator;validator()'
        r=subprocess.run([sys.executable,'-S','-B','-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('VALIDATOR_UNAVAILABLE',r.stderr)
    def test_review_requirement_configuration_cannot_be_ignored(self):
        import review_records
        original=review_records.read
        def updated(path):
            value=original(path)
            if str(path).endswith('review-requirements.json'):value['per_detected_trigger']['specialist']=2
            return value
        with patch('review_records.read',side_effect=updated):self.assertEqual(self.result()['result'],'failed')
        def unsupported(path):
            value=original(path)
            if str(path).endswith('review-requirements.json'):value['stage']='before_delegation'
            return value
        with patch('review_records.read',side_effect=unsupported),self.assertRaisesRegex(ValueError,'UNSUPPORTED_REVIEW_REQUIREMENTS'):self.result()
    def test_cli_valid_set_and_duplicate_key_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp)/'bundle.json';s=Path(tmp)/'subject.json';b.write_text(json.dumps(self.bundle));s.write_text(json.dumps(self.subject))
            command=[sys.executable,'-B',str(ROOT/'tooling/review_records.py'),'--bundle',str(b),'--subject',str(s)]
            self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
            s.write_text('{"head_sha":"a","head_sha":"b"}');self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)


if __name__=='__main__':unittest.main()
