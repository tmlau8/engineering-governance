import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import guarded_task as gate


class TaskGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.runtime=self.root/'owner';self.workspace=self.root/'worker';self.workspace.mkdir();(self.workspace/'code.py').write_text('before')
        self.bundle=self.root/'reviews.json';self.bundle.write_text('{}')
        self.snapshot={'root':str(self.workspace),'head':'a'*40,'common_dir':str(self.workspace/'.git'),'files':{'code.py':'x'},'branch':'feature/test','index_sha256':'x'}
        self.packet={'id':'synthetic-id','task':'SYNTHETIC','source':self.snapshot,'expires_at':time.time()+60,'controller_sha256':gate.code_digest(),'reviews_sha256':gate.digest({}),'review_bundle_path':str(self.bundle),'adapter_path':str(self.bundle),'adapter_sha256':gate.hashlib.sha256(self.bundle.read_bytes()).hexdigest(),'repository':'example/repo','profile':'feature','risk':'high','writable':['code.py'],'model':'example','provider':'approved','spec':'code.py','review_record_ids':['review-1'],'review_assurance':'metadata_only','timeout_seconds':10}
        db=gate.database(self.runtime)
        with db:db.execute('INSERT INTO tasks VALUES(?,?,?)',(self.packet['id'],json.dumps(self.packet),'prepared'))
        db.close()
    def tearDown(self):self.tmp.cleanup()
    def approve(self):gate.approve(self.runtime,self.packet['id'],gate.digest(self.packet))
    def test_missing_approval_blocks_without_worker(self):
        with patch.object(gate.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'APPROVAL'):gate.execute(self.runtime,self.packet['id'],'/unused')
            spawn.assert_not_called()
    def test_exact_confirmation_required(self):
        with self.assertRaisesRegex(ValueError,'EXACT_OWNER'):gate.approve(self.runtime,self.packet['id'],'different')
    def test_single_use_and_changed_source_fail_closed(self):
        self.approve()
        with patch.object(gate,'source',return_value=dict(self.snapshot,head='b'*40)):
            with self.assertRaisesRegex(ValueError,'SOURCE_OR_SCOPE_CHANGED'):gate.claim(self.runtime,self.packet['id'])
        with self.assertRaisesRegex(ValueError,'APPROVAL'):gate.claim(self.runtime,self.packet['id'])
    def test_approved_bound_source_can_be_claimed_once(self):
        self.approve()
        with patch.object(gate,'source',return_value=self.snapshot):self.assertEqual(gate.claim(self.runtime,self.packet['id'])['id'],self.packet['id'])
        with self.assertRaisesRegex(ValueError,'APPROVAL'):gate.claim(self.runtime,self.packet['id'])
    def test_expired_claim_consumes_approved_permit(self):
        self.approve()
        with patch.object(gate.time,'time',return_value=time.time()+100):
            with self.assertRaisesRegex(ValueError,'EXPIRED'):gate.claim(self.runtime,self.packet['id'])
        with self.assertRaisesRegex(ValueError,'APPROVAL'):gate.claim(self.runtime,self.packet['id'])
    def test_review_and_controller_drift_reject(self):
        self.approve();self.bundle.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'ADAPTER_CHANGED'):gate.claim(self.runtime,self.packet['id'])
    def test_controller_drift_reject(self):
        self.approve()
        with patch.object(gate,'code_digest',return_value='different'):
            with self.assertRaisesRegex(ValueError,'CONTROLLER_CHANGED'):gate.claim(self.runtime,self.packet['id'])
    def test_missing_capability_receipt_cannot_spawn(self):
        self.approve()
        with patch.object(gate,'source',return_value=self.snapshot),patch.object(gate.subprocess,'Popen') as spawn:
            with self.assertRaises(OSError):gate.execute(self.runtime,self.packet['id'],gate.sys.executable)
            spawn.assert_not_called()
    def test_permission_scope_omits_git_ignored_and_secrets(self):
        self.packet['source']['files'].update({'.git/config':'x','.env':'x','.governance/project.json':'x','other.py':'x'})
        fs=gate.permissions(self.packet)['filesystem']
        self.assertEqual(fs[str(self.workspace/'code.py')],'write');self.assertEqual(fs[str(self.workspace/'other.py')],'read')
        for name in ['.git/config','.env','untracked-secret']:self.assertNotIn(str(self.workspace/name),fs)
        self.assertEqual(fs[':root'],'deny');self.assertFalse(gate.permissions(self.packet)['network']['enabled'])
    def test_scope_traversal_and_symlink_reject(self):
        for name in ['../outside','/tmp/outside','.GiT/config','.codex/config.toml','.env.local','a/../../outside']:
            with self.assertRaises(ValueError):gate.safe_path(self.workspace,name)
        (self.workspace/'alias').symlink_to(self.root)
        with self.assertRaises(ValueError):gate.safe_path(self.workspace,'alias/file')
    def test_state_alias_or_permissions_reject(self):
        os.chmod(self.runtime,0o755)
        with self.assertRaisesRegex(ValueError,'PRIVATE_STATE'):gate.database(self.runtime)
        os.chmod(self.runtime,0o700);(self.root/'alias').symlink_to(self.runtime)
        with self.assertRaisesRegex(ValueError,'UNSAFE_STATE'):gate.database(self.root/'alias')
    def test_client_argv_no_passthrough_and_explicit_controls(self):
        args=gate.client_args('/trusted/codex','/driver',self.packet)
        for flag in ['--no-daemon','never','--ignore-user-config','--ignore-rules','--strict-config','mcp_servers={}','web_search="disabled"','image_generation','view_image']:self.assertIn(flag,args)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)
    def test_observations_exclude_private_paths_and_artifacts(self):
        rows=gate.observations(self.runtime);encoded=json.dumps(rows)
        self.assertEqual(rows[0]['state'],'prepared');self.assertNotIn(str(self.workspace),encoded);self.assertNotIn(str(self.bundle),encoded)


if __name__=='__main__':unittest.main()

class RealSourceTests(unittest.TestCase):
    def test_clean_source_dirty_source_and_no_filter_execution(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();marker=root/'FILTER_RAN'
            def git(*args):return subprocess.check_output(['/usr/bin/git','-C',str(root),*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init','-b','feature/test');git('config','user.email','synthetic@example.invalid');git('config','user.name','Synthetic')
            (root/'code.py').write_text('before\n');git('add','.');git('commit','-m','synthetic source')
            (root/'.gitattributes').write_text('code.py filter=trap\n');git('add','.gitattributes');git('commit','-m','synthetic attribute')
            git('config','filter.trap.clean','touch '+str(marker))
            snap=gate.source(root);self.assertEqual(snap['head'],git('rev-parse','HEAD'));self.assertFalse(marker.exists())
            (root/'code.py').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'SOURCE_NOT_CLEAN'):gate.source(root)
            self.assertFalse(marker.exists())
            (root/'code.py').write_text('before\n');(root/'untracked').touch()
            with self.assertRaisesRegex(ValueError,'SOURCE_NOT_CLEAN'):gate.source(root)
    def test_default_branch_cannot_be_granted(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            for args in [('init','-b','main'),('config','user.email','synthetic@example.invalid'),('config','user.name','Synthetic')]:subprocess.check_call(['/usr/bin/git','-C',str(root),*args],stdout=subprocess.DEVNULL)
            (root/'file').touch();subprocess.check_call(['/usr/bin/git','-C',str(root),'add','.']);subprocess.check_call(['/usr/bin/git','-C',str(root),'commit','-m','synthetic'],stdout=subprocess.DEVNULL)
            with self.assertRaisesRegex(ValueError,'FEATURE_BRANCH_REQUIRED'):gate.source(root)

class RealPrepareTests(unittest.TestCase):
    def test_real_prepare_review_rejection_and_single_use_launch_wiring(self):
        import subprocess
        import review_fixtures
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory).resolve();workspace=base/'worker';workspace.mkdir();runtime=base/'owner';runtime.mkdir(mode=0o700)
            def git(*args):return subprocess.check_output(['/usr/bin/git','-C',str(workspace),*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init','-b','feature/test');git('config','user.email','synthetic@example.invalid');git('config','user.name','Synthetic');git('remote','add','origin','https://github.com/example/repo.git')
            (workspace/'test_code.py').write_text('before\n');(workspace/'spec.md').write_text('SYNTHETIC: bounded scope and acceptance criteria; no real project approval.\n');git('add','.');git('commit','-m','synthetic reviewed scope');head=git('rev-parse','HEAD')
            adapter=json.loads((gate.ROOT/'adapters/my-ea.json').read_text());adapter['repository']='example/repo';adapter_file=base/'adapter.json';adapter_file.write_text(json.dumps(adapter))
            expected=review_fixtures.subject(head=head,base=head);expected.update(repository='example/repo',change_id='SYNTHETIC')
            reviews=base/'reviews.json';reviews.write_text(json.dumps(review_fixtures.bundle(expected)))
            executable=Path(gate.sys.executable).resolve();receipt={'contract':gate.CONTRACT,'executable_sha256':gate.executable_digest(executable),'controller_sha256':gate.code_digest(),'frontend_and_child_behavior_verified':True}
            receipt_file=runtime/'client-capability.json';receipt_file.write_text(json.dumps(receipt));receipt_file.chmod(0o600)
            args=[runtime,workspace,adapter_file,'spec.md',reviews,'SYNTHETIC','feature','builder-agent-1','synthetic-builder-session',head,['test_code.py'],'example-model','openai']
            bad=review_fixtures.bundle(expected);bad['records']=[];reviews.write_text(json.dumps(bad))
            with patch.object(gate,'launch') as spawn:
                with self.assertRaisesRegex(ValueError,'REQUIRED_REVIEW'):gate.prepare(*args)
                spawn.assert_not_called()
            reviews.write_text(json.dumps(review_fixtures.bundle(expected)));packet=gate.prepare(*args)
            self.assertEqual(packet['risk'],'high');self.assertEqual(packet['triggers'],['assurance'])
            gate.approve(runtime,packet['id'],gate.digest(packet))
            with patch('activity.source_paths',return_value=[]),patch.object(gate,'source',return_value=packet['source']),patch.object(gate.subprocess,'Popen') as spawn:
                spawn.return_value.returncode=0
                self.assertEqual(gate.execute(runtime,packet['id'],executable),'completed')
                self.assertTrue(spawn.call_args.kwargs['close_fds']);self.assertEqual(set(spawn.call_args.kwargs['env']),{'PATH','HOME','CODEX_HOME'})
            with self.assertRaisesRegex(ValueError,'APPROVAL'):gate.execute(runtime,packet['id'],executable)
            self.assertEqual(gate.observations(runtime)[0]['state'],'completed')
            packet=gate.prepare(*args);gate.approve(runtime,packet['id'],gate.digest(packet));receipt_file.write_text('{}')
            with patch.object(gate,'source',return_value=packet['source']),patch.object(gate.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(ValueError,'CLIENT_CAPABILITY'):gate.execute(runtime,packet['id'],executable)
                spawn.assert_not_called()
            self.assertEqual(gate.observations(runtime)[0]['state'],'launch_blocked')
            receipt_file.write_text(json.dumps(receipt));packet=gate.prepare(*args);gate.approve(runtime,packet['id'],gate.digest(packet))
            with patch('activity.snapshot',side_effect=OSError('synthetic missing telemetry')),patch.object(gate,'source',return_value=packet['source']),patch.object(gate.subprocess,'Popen') as spawn:
                spawn.return_value.returncode=0
                self.assertEqual(gate.execute(runtime,packet['id'],executable),'completed__usage_unavailable')
            self.assertEqual(gate.observations(runtime)[0]['state'],'completed__usage_unavailable')
    def test_both_executable_mode_changes_and_custom_default_are_blocked(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            def git(*args):return subprocess.check_output(['/usr/bin/git','-C',str(root),*args],stderr=subprocess.DEVNULL)
            git('init','-b','feature/test');git('config','user.email','synthetic@example.invalid');git('config','user.name','Synthetic')
            file=root/'script.sh';file.write_text('echo synthetic\n');file.chmod(0o644);git('add','.');git('commit','-m','synthetic')
            file.chmod(0o755)
            with self.assertRaisesRegex(ValueError,'EXECUTABLE_MODE'):gate.source(root)
            git('add','.');git('commit','-m','synthetic executable');file.chmod(0o644)
            with self.assertRaisesRegex(ValueError,'EXECUTABLE_MODE'):gate.source(root)
            file.chmod(0o755);git('branch','-m','trunk')
            with self.assertRaisesRegex(ValueError,'FEATURE_BRANCH'):gate.source(root,'trunk')

class BundleControllerTests(unittest.TestCase):
    def test_bundled_controller_has_transitive_code_inputs(self):
        import subprocess
        from build_release import build
        with tempfile.TemporaryDirectory() as directory:
            bundle=Path(directory)/'bundle';build(bundle)
            env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(bundle/'tooling'),'PYTHONDONTWRITEBYTECODE':'1'}
            output=subprocess.check_output([gate.sys.executable,'-B','-c','from guarded_task import code_digest;print(code_digest())'],cwd=directory,env=env,text=True)
            self.assertEqual(output.strip(),gate.code_digest())
    def test_exact_new_file_scope_never_grants_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();packet={'source':{'root':str(root),'files':{}},'writable':['module/new.py'],'new_files':['module/new.py']}
            fs=gate.permissions(packet)['filesystem']
            self.assertEqual(fs[str(root/'module/new.py')],'write');self.assertNotIn(str(root/'module'),fs)
