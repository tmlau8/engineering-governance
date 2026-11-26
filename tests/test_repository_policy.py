import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib

from build_release import build
from load_policy import ROOT
from repository_policy import (ResolutionError, git, identity, inspect, materialize,
    object_bytes, preflight, register, registry, scope_for, validate_registry, verify_inventory)


def command(root,*args):
    return subprocess.check_output(['/usr/bin/git','-C',str(root),*args],stderr=subprocess.DEVNULL).decode().strip()


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name).resolve();self.root=self.home/'canonical repo';self.root.mkdir()
        command(self.root,'init','-b','master');command(self.root,'config','user.name','Synthetic Tester');command(self.root,'config','user.email','fixture@example.invalid')
        (self.root/'AGENTS.md').write_text('Original instructions, no adoption yet.\n');command(self.root,'add','.');command(self.root,'commit','-m','initial fixture');self.old=command(self.root,'rev-parse','HEAD')
        command(self.root,'remote','add','origin','https://github.com/fixture/repo.git')
        gov=self.root/'.governance';gov.mkdir();built=build(gov/'baseline')
        self.version=built['version'];self.digest=built['manifest_sha256']
        self.adoption={'repository':'fixture/repo','policy_source':{'repository':'fixture/policy','commit_sha':'c'*40,'manifest_sha256':self.digest,'version':self.version}}
        (gov/'adoption.json').write_text(json.dumps(self.adoption))
        project=json.loads((ROOT/'adapters/my-ea.json').read_text());project['repository']='fixture/repo';(gov/'project.json').write_text(json.dumps(project))
        (self.root/'AGENTS.md').write_text('Read .governance/adoption.json and the adopted policy.\n')
        command(self.root,'add','.');command(self.root,'commit','-m','approved adoption fixture');self.approved=command(self.root,'rev-parse','HEAD')
        self.path=self.home/'private/registry.json';self.cache=self.home/'private/cache'
        self.entry=register(self.path,self.cache,self.root,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)

    def add_worktree(self,name='older branch',branch='feature/old'):
        path=self.home/name;command(self.root,'worktree','add','-b',branch,str(path),self.old);return path

    def repin_fixture(self, version, status=None):
        """Authenticate a test bundle with the actual published 1.0 gate bytes."""
        baseline=self.root/'.governance/baseline'
        if version=='1.0.0-rc.1':
            raw=(ROOT/'tests/fixtures/policy-v1.0.0-rc.1/gates.yaml').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),'811531eab756e35cc0b7f02816f8dfbf2d076e96fbccf309fb7d2a4868604c51')
            (baseline/'policy/gates.yaml').write_bytes(raw)
        else:
            gates=json.loads((baseline/'policy/gates.yaml').read_text());gates['version']=version
            (baseline/'policy/gates.yaml').write_text(json.dumps(gates))
        manifest=json.loads((baseline/'manifest.json').read_text());manifest['version']=version
        manifest['files']={name:hashlib.sha256((baseline/name).read_bytes()).hexdigest() for name in manifest['files']}
        raw=(json.dumps(manifest,indent=2)+'\n').encode();(baseline/'manifest.json').write_bytes(raw)
        self.version=version;self.digest=hashlib.sha256(raw).hexdigest()
        self.adoption['policy_source'].update(version=version,manifest_sha256=self.digest)
        if status:self.adoption['status']=status
        (self.root/'.governance/adoption.json').write_text(json.dumps(self.adoption))
        command(self.root,'add','.');command(self.root,'commit','-m','version compatibility fixture')
        self.approved=command(self.root,'rev-parse','HEAD');self.path=self.home/'private/repinned.json'
        self.entry=register(self.path,self.cache,self.root,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)

    def runtime(self, legacy=False):
        runtime=self.home/'runtime';runtime.mkdir(exist_ok=True)
        shutil.copyfile(self.path,runtime/'repositories.json')
        sessions=self.home/'sessions';sessions.mkdir(exist_ok=True)
        config={'repository_registry':str(runtime/'repositories.json'),'usage_scopes':[],
                'repositories':['fixture/repo'],'sessions_root':str(sessions)}
        if legacy:config['usage_scopes']=[{'cwd':str(self.home),'repository':'other/repo'}]
        (runtime/'settings.json').write_text(json.dumps(config));return runtime,config

    def test_approved_versions_do_not_borrow_candidate_policy_or_certify_gates(self):
        from collect import workspace_context,run_once
        from load_policy import load_observation_policy
        from check_gate import evaluate
        from store import Store
        from test_evidence import FakeAPI
        from github import observe
        for version in ['1.1.0-rc.1','1.0.0-rc.1']:
            if version!=self.version:self.repin_fixture(version)
            runtime,config=self.runtime();store=Store(runtime/'data/evidence.sqlite')
            with patch('load_policy.ROOT',self.home/'nonexistent-candidate'), \
                 patch('review_records.load_requirements',side_effect=AssertionError('candidate contract read')), \
                 patch('check_gate.evaluate',side_effect=AssertionError('observation attempted clearance')):
                policies,_,_=workspace_context(runtime,config,store)
                policy=policies['fixture/repo'];self.assertEqual(policy['version'],version)
                result=observe(FakeAPI(),'fixture/repo',1,policy)
                self.assertEqual(result['metadata_gate'],'not_evaluated_observation_only')
                self.assertEqual(result['policy_evaluation_scope'],'approved_data_path_risk_only')
                with patch('collect.API',return_value=FakeAPI()), \
                     patch('collect.github_collect',side_effect=lambda api,repo,p:{repo:observe(api,repo,1,p)}):
                    run_once(runtime)
                self.assertEqual(store.records('github:')[0]['data']['evaluated_policy_version'],version)
            with self.assertRaisesRegex(ValueError,'cannot clear'):evaluate(policy,{},['x'],'before_merge')
            self.assertFalse(preflight(self.path,self.cache,self.root,'feature')['permission_to_execute'])
            store.close()

    def test_unknown_policy_keeps_last_good_pr_records(self):
        from collect import run_once
        from store import Store
        self.repin_fixture('future-unsupported');runtime,_=self.runtime()
        store=Store(runtime/'data/evidence.sqlite');store.snapshot('github:fixture/repo',{'old':{'sentinel':'last_good'}});store.close()
        store=Store(runtime/'data/evidence.sqlite');store.snapshot('workspace:fixture/repo',{'old':{'sentinel':'last_good_workspace'}});store.close()
        result=run_once(runtime)
        self.assertTrue(any(r['error_code']=='REPOSITORY_CONTEXT_UNAVAILABLE' for r in result))
        store=Store(runtime/'data/evidence.sqlite');self.assertEqual(store.records('github:')[0]['data'],{'sentinel':'last_good'})
        self.assertEqual(store.records('workspace:')[0]['data'],{'sentinel':'last_good_workspace'});store.close()

    def test_failed_inventory_never_reasserts_last_good_authority(self):
        from collect import workspace_context
        from store import Store
        from views import workspaces
        runtime,config=self.runtime();store=Store(runtime/'data/evidence.sqlite')
        workspace_context(runtime,config,store)
        before=store.records('workspace:fixture/repo')
        with patch('collect.inspect',side_effect=ResolutionError('APPROVED_ADOPTION_IS_DRAFT')):
            with self.assertRaises(ResolutionError):workspace_context(runtime,config,store)
        row=workspaces(store,'fixture/repo')[0]
        self.assertEqual(before,store.records('workspace:fixture/repo'))
        self.assertEqual(row['Effective approved policy'],'unknown_latest_inventory_failed')
        self.assertEqual(row['Last-known policy'],self.version)
        self.assertIn('APPROVED_ADOPTION_IS_DRAFT',row['Issues'])
        self.assertIn('latest attempt failed',row['Freshness'])
        workspace_context(runtime,config,store)
        store.failure('workspace:registry','REPOSITORY_CONTEXT_UNAVAILABLE')
        row=workspaces(store,'fixture/repo')[0]
        self.assertEqual(row['Effective approved policy'],'unknown_latest_inventory_failed')
        self.assertEqual(row['Inventory status'],'error')
        self.assertIn('REPOSITORY_CONTEXT_UNAVAILABLE',row['Issues']);store.close()

    def test_explicit_draft_approved_source_cannot_be_registered(self):
        with self.assertRaisesRegex(ResolutionError,'ADOPTION_IS_DRAFT'):
            self.repin_fixture('1.0.0-rc.1','draft_human_approval_required')

    def test_registry_case_and_canonical_identity_collisions(self):
        first=copy.deepcopy(self.entry);second=copy.deepcopy(first)
        second.update(repository='FIXTURE/REPO',repository_id=456)
        with self.assertRaises(ResolutionError):validate_registry({'schema_version':1,'repositories':[first,second]})
        second['repository']='other/repo'
        for common in [str(self.root/'.git'), str(self.root/'.git/../.git')]:
            second['clones']=[{'root':str(self.home/'other'),'common_dir':common}]
            with self.assertRaisesRegex(ResolutionError,'AMBIGUOUS'):validate_registry({'schema_version':1,'repositories':[first,second]})
        alias=self.home/'alias';alias.symlink_to(self.root,target_is_directory=True)
        second['clones']=[{'root':str(alias),'common_dir':str(alias/'.git')}]
        with self.assertRaises(ResolutionError):validate_registry({'schema_version':1,'repositories':[first,second]})

    def test_empty_directory_inventory_and_entry_and_time_bounds(self):
        approved=materialize(self.entry,self.cache);extra=approved/'extra-empty';extra.mkdir()
        with self.assertRaises(ResolutionError):materialize(self.entry,self.cache)
        extra.rmdir();local=self.root/'.governance/baseline/unlisted';local.mkdir()
        rows,_,_=inspect(self.entry,self.cache)
        self.assertIn('LOCAL_POLICY_INVALID',next(iter(rows.values()))['issues'])
        local.rmdir()
        expected={'project.json':hashlib.sha256((approved/'project.json').read_bytes()).hexdigest()}
        with patch('repository_policy.MAX_FILES',0),self.assertRaises(ResolutionError):
            verify_inventory(approved,expected,'BOUNDED')
        with patch('repository_policy.time.monotonic',side_effect=[0,6]),self.assertRaisesRegex(ResolutionError,'BOUNDED'):
            verify_inventory(approved,expected,'BOUNDED')

    def test_unverified_scopes_do_not_attribute_or_erase_old_usage(self):
        from collect import workspace_context,run_once
        from store import Store
        from usage import repository
        from test_evidence import meta,token
        runtime,config=self.runtime(legacy=True);store=Store(runtime/'data/evidence.sqlite')
        store.snapshot('usage:codex',{'legacy':{'repository':'other/repo','total_tokens':100}})
        before=store.records('usage:codex')
        _,scopes,_=workspace_context(runtime,config,store)
        self.assertEqual({s['repository'] for s in scopes},{'fixture/repo'})
        self.assertIsNone(repository(str(self.root),config['usage_scopes']))
        self.assertTrue(any(r['error_code']=='UNVERIFIED_LEGACY_SCOPES_NOT_ATTRIBUTED' for r in store.health()))
        with patch('collect.github_collect',return_value={}):result=run_once(runtime)
        self.assertEqual(before,store.records('usage:codex'))
        self.assertTrue(any(r['error_code']=='USAGE_SCOPE_MIGRATION_REQUIRES_REVIEW' for r in result))
        self.assertTrue(any(r['source']=='usage:scope-migration' for r in store.health()))
        store.close()

    def test_concurrent_clone_registrations_are_serialized(self):
        import concurrent.futures
        clones=[]
        for i in range(2):
            clone=self.home/('clone'+str(i));subprocess.check_call(['/usr/bin/git','clone','--no-local',str(self.root),str(clone)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            command(clone,'remote','set-url','origin','https://github.com/fixture/repo.git');clones.append(clone)
        def add(clone):register(self.path,self.cache,clone,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(add,clones))
        self.assertEqual(len(registry(self.path)[0]['clones']),3)

    def test_all_four_worktrees_same_policy_without_local_files(self):
        roots=[self.root]+[self.add_worktree('workspace '+str(i),'feature/'+str(i)) for i in range(3)]
        rows,scopes,approved=inspect(self.entry,self.cache)
        self.assertEqual(len(rows),4);self.assertEqual(sum(r['local_status']=='attention_required' for r in rows.values()),3)
        self.assertEqual({r['approved_manifest_sha256'] for r in rows.values()},{self.digest})
        for root in roots:
            self.assertEqual(scope_for(root,scopes)['repository'],'fixture/repo')
            report=preflight(self.path,self.cache,root,'fix')
            self.assertEqual(report['workspace']['effective_policy_version'],self.version);self.assertFalse(report['permission_to_execute'])
            self.assertIn(str(approved),report['effective_policy_path'])

    def test_moved_and_missing_worktree_remain_visible(self):
        old=self.add_worktree();new=self.home/'renamed workspace';command(self.root,'worktree','move',str(old),str(new))
        rows,scopes,_=inspect(self.entry,self.cache);self.assertEqual(len(rows),2);self.assertIsNotNone(scope_for(new,scopes))
        shutil.rmtree(new)
        rows,scopes,_=inspect(self.entry,self.cache)
        self.assertEqual(len(rows),2);self.assertTrue(any('WORKSPACE_UNAVAILABLE' in r['issues'] for r in rows.values()))

    def test_candidate_pin_and_adapter_cannot_self_approve(self):
        local=self.root/'.governance';candidate=copy.deepcopy(self.adoption);candidate['policy_source']['commit_sha']='d'*40
        (local/'adoption.json').write_text(json.dumps(candidate));(local/'project.json').write_text('{"repository":"attacker/repo"}')
        rows,_,approved=inspect(self.entry,self.cache)
        self.assertIn('LOCAL_ADOPTION_DIFFERS',next(iter(rows.values()))['issues'])
        self.assertEqual(json.loads((approved/'project.json').read_text())['repository'],'fixture/repo')
        changed=copy.deepcopy(self.entry)
        with self.assertRaises(ResolutionError):register(self.path,self.cache,self.root,'fixture/repo',123,self.approved,'d'*40,self.digest,self.version)

    def test_registered_clone_and_unregistered_same_remote(self):
        clone=self.home/'another clone';subprocess.check_call(['/usr/bin/git','clone','--no-local',str(self.root),str(clone)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        command(clone,'remote','set-url','origin','https://github.com/fixture/repo.git')
        with self.assertRaises(ResolutionError):preflight(self.path,self.cache,clone)
        register(self.path,self.cache,clone,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)
        rows,scopes,_=inspect(registry(self.path)[0],self.cache);self.assertEqual(len(rows),2);self.assertIsNotNone(scope_for(clone,scopes))

    def test_nested_foreign_and_same_common_indirection_excluded(self):
        rows,scopes,_=inspect(self.entry,self.cache)
        sub=self.root/'ordinary subdir';sub.mkdir();self.assertIsNotNone(scope_for(sub,scopes));self.assertIsNone(scope_for(self.home,scopes))
        foreign=self.root/'foreign';foreign.mkdir();command(foreign,'init','-b','master');self.assertIsNone(scope_for(foreign,scopes))
        disguised=self.root/'nested pointer';disguised.mkdir();(disguised/'.git').write_text('gitdir: '+str(self.root/'.git')+'\n')
        self.assertIsNone(scope_for(disguised,scopes))
        with self.assertRaisesRegex(ResolutionError,'WORKSPACE_IDENTITY_MISMATCH'):
            register(self.path,self.cache,disguised,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)

    def test_replace_refs_and_corrupt_object_payloads(self):
        oid=command(self.root,'rev-parse',self.approved+':.governance/project.json')
        replacement=subprocess.check_output(['/usr/bin/git','-C',str(self.root),'hash-object','-w','--stdin'],input=b'{"repository":"wrong/repo"}').decode().strip()
        command(self.root,'replace',oid,replacement)
        self.assertIn(b'fixture/repo',object_bytes(self.root,oid,'blob'))
        command(self.root,'replace','-d',oid)
        file=self.root/'.git/objects'/oid[:2]/oid[2:];old=file.read_bytes();file.chmod(0o600)
        payload=b'{"repository":"wrong/repo"}';file.write_bytes(zlib.compress(b'blob '+str(len(payload)).encode()+b'\0'+payload))
        try:
            with self.assertRaisesRegex(ResolutionError,'GIT_OBJECT_INTEGRITY_FAILURE'):materialize(self.entry,self.cache)
        finally:file.write_bytes(old)

    def test_git_env_and_no_lazy_fetch_or_candidate_commands(self):
        sentinel=self.home/'executed';script=self.home/'candidate-command.sh';script.write_text('#!/bin/sh\ntouch "'+str(sentinel)+'"\n');script.chmod(0o700)
        for key,value in [('core.fsmonitor',str(script)),('core.pager',str(script)),('credential.helper','!'+str(script)),('filter.fake.clean',str(script)),('diff.fake.textconv',str(script)),('core.hooksPath',str(self.home))]:command(self.root,'config',key,value)
        foreign=self.home/'outside';foreign.mkdir();command(foreign,'init','-b','master')
        with patch.dict(os.environ,{'GIT_DIR':str(foreign/'.git'),'GIT_WORK_TREE':str(foreign),'GIT_OBJECT_DIRECTORY':str(foreign/'.git/objects'),'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'alias.probe','GIT_CONFIG_VALUE_0':'!'+str(script)}):
            self.assertEqual(identity(self.root)[0],self.root)
        command(self.root,'config','extensions.partialClone','origin');command(self.root,'config','remote.origin.promisor','true')
        command(self.root,'config','remote.origin.url','ext::'+str(script))
        with self.assertRaises(ResolutionError):object_bytes(self.root,'f'*40,'blob')
        self.assertFalse(sentinel.exists())

    def test_cache_extra_symlink_fifo_and_bytes_rejected(self):
        approved=materialize(self.entry,self.cache)
        for mode in ['bytes','extra','symlink','fifo']:
            target=approved/'project.json';original=target.read_bytes();extra=approved/'unlisted'
            if mode=='bytes':target.write_bytes(b'changed')
            elif mode=='extra':extra.write_text('unlisted')
            elif mode=='symlink':target.unlink();target.symlink_to(self.root/'.governance/project.json')
            else:os.mkfifo(extra)
            try:
                with self.assertRaises(ResolutionError):materialize(self.entry,self.cache)
            finally:
                if target.is_symlink():target.unlink()
                target.write_bytes(original);extra.unlink(missing_ok=True)

    def test_missing_pin_and_local_symlink_do_not_fallback(self):
        entry=copy.deepcopy(self.entry);entry['adoption_revision']='f'*40
        with self.assertRaises(ResolutionError):materialize(entry,self.cache)
        p=self.root/'.governance/adoption.json';p.unlink();p.symlink_to(self.home/'outside-secret')
        rows,_,_=inspect(self.entry,self.cache);self.assertIn('LOCAL_POLICY_INVALID',next(iter(rows.values()))['issues'])

    def test_registry_and_source_change_are_fail_closed(self):
        command(self.root,'remote','set-url','origin','https://github.com/other/repo.git')
        with self.assertRaises(ResolutionError):inspect(self.entry,self.cache)
        with self.assertRaisesRegex(ResolutionError,'REGISTERED_IDENTITY_CHANGED'):
            register(self.path,self.cache,self.root,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)
        self.path.write_text('{"schema_version":1,"schema_version":2,"repositories":[]}')
        with self.assertRaises(ResolutionError):registry(self.path)

    def test_output_is_bounded_while_reading(self):
        with patch('repository_policy.MAX_OBJECT',1),self.assertRaises(ResolutionError):materialize(self.entry,self.cache)
        with self.assertRaisesRegex(ResolutionError,'GIT_OUTPUT_LIMIT'):git(self.root,'log','--all',limit=1)

    def test_commit_and_tree_integrity_and_unsafe_bundle(self):
        for oid,kind in [(self.approved,'commit'),(command(self.root,'rev-parse',self.approved+'^{tree}'),'tree')]:
            file=self.root/'.git/objects'/oid[:2]/oid[2:];old=file.read_bytes();file.chmod(0o600)
            payload=b'changed';file.write_bytes(zlib.compress(kind.encode()+b' 7\0'+payload))
            try:
                with self.assertRaises(ResolutionError):materialize(self.entry,self.cache)
            finally:file.write_bytes(old)
        bad=self.root/'.governance/baseline/unlisted';bad.symlink_to(self.home/'unread-secret')
        command(self.root,'add','.');command(self.root,'commit','-m','unsafe source fixture')
        entry=copy.deepcopy(self.entry);entry['adoption_revision']=command(self.root,'rev-parse','HEAD')
        with self.assertRaises(ResolutionError):materialize(entry,self.cache)

    def test_changed_discovery_never_commits_a_partial_snapshot(self):
        import repository_policy
        original=repository_policy.worktrees;calls=0
        def changing(entry):
            nonlocal calls
            calls+=1;result=original(entry)
            if calls==1:self.add_worktree()
            return result
        with patch('repository_policy.worktrees',side_effect=changing),self.assertRaisesRegex(ResolutionError,'WORKSPACE_INVENTORY_CHANGED'):
            inspect(self.entry,self.cache)

    def test_failed_cache_or_registry_preserves_last_good_store(self):
        from collect import workspace_context,run_once
        from store import Store
        runtime=self.home/'runtime';runtime.mkdir();shutil.copyfile(self.path,runtime/'repositories.json')
        config={'repository_registry':str(runtime/'repositories.json'),'usage_scopes':[],'repositories':[]}
        store=Store(runtime/'data/evidence.sqlite')
        workspace_context(runtime,config,store);before=store.records('workspace:')
        cached=materialize(self.entry,runtime/'approved-policy');(cached/'project.json').write_text('tampered')
        with self.assertRaises(ResolutionError):workspace_context(runtime,config,store)
        self.assertEqual(before,store.records('workspace:'))
        self.assertEqual(next(r for r in store.health() if r['source']=='workspace:fixture/repo')['status'],'error');store.close()
        (runtime/'settings.json').write_text(json.dumps(config));(runtime/'repositories.json').unlink()
        self.assertTrue(any(r['error_code']=='REPOSITORY_CONTEXT_UNAVAILABLE' for r in run_once(runtime)))
        store=Store(runtime/'data/evidence.sqlite');self.assertEqual(before,store.records('workspace:'));store.close()

    def test_usage_current_identity_and_broad_or_nested_exclusion(self):
        from usage import collect as usage_collect
        from test_evidence import meta,token
        old=self.add_worktree();foreign=self.root/'foreign';foreign.mkdir();command(foreign,'init','-b','master')
        _,scopes,_=inspect(self.entry,self.cache);sessions=self.home/'sessions';sessions.mkdir()
        for i,cwd in enumerate([self.root,old,self.home,foreign]):
            sid=f'{i+1:08d}-1111-1111-1111-111111111111'
            records=[{'type':'session_meta','payload':meta(str(cwd),sid)},token(100)]
            (sessions/(str(i)+'.jsonl')).write_text('\n'.join(json.dumps(r) for r in records))
        result=usage_collect(sessions,scopes);self.assertEqual(len(result),2)
        self.assertTrue(all('observed_at_collection' in r['association'] for r in result.values()))
        first=json.loads((sessions/'0.jsonl').read_text().splitlines()[0]);first['payload']['cwd']=str(old)
        (sessions/'conflict.jsonl').write_text('\n'.join(json.dumps(r) for r in [first,token(100)]))
        with self.assertRaisesRegex(ValueError,'USAGE_SESSION_IDENTITY_CONFLICT'):usage_collect(sessions,scopes)

    def test_atomic_registry_write_and_duplicate_clone_identity(self):
        original=self.path.read_bytes()
        clone=self.home/'clone';subprocess.check_call(['/usr/bin/git','clone','--no-local',str(self.root),str(clone)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        command(clone,'remote','set-url','origin','https://github.com/fixture/repo.git')
        with patch('repository_policy.os.replace',side_effect=OSError('interrupted registry write')),self.assertRaises(OSError):
            register(self.path,self.cache,clone,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)
        self.assertEqual(self.path.read_bytes(),original)
        older=self.add_worktree();register(self.path,self.cache,older,'fixture/repo',123,self.approved,'c'*40,self.digest,self.version)
        self.assertEqual(len(registry(self.path)[0]['clones']),1)


if __name__=='__main__':unittest.main()
