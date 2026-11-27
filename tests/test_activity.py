import contextlib
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import activity as a
from common import UTC
from store import Store
from views import activities, activity_totals

SID='11111111-1111-1111-1111-111111111111'
PARENT='22222222-2222-2222-2222-222222222222'
T=dt.datetime.now(UTC).replace(microsecond=0)-dt.timedelta(hours=1)


def at(n):return (T+dt.timedelta(seconds=n)).isoformat(timespec='microseconds').replace('+00:00','Z')
def tokens(n,value):return {'timestamp':at(n),'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':value,'cached_input_tokens':value//2,'output_tokens':0,'reasoning_output_tokens':0,'total_tokens':value}},'private':'PRIVATE_SENTINEL'}}
def event(n,kind):return {'timestamp':at(n),'type':'event_msg','payload':{'type':kind,'turn_id':'turn1'}}


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.runtime=self.root/'runtime';self.runtime.mkdir(mode=0o700)
        (self.runtime/'data').mkdir(parents=True,mode=0o700)
        self.sessions=self.root/'sessions';self.sessions.mkdir(mode=0o700)
        self.meta={'repository':'fixture/repo','task':'TASK-1','pr':1,'revision':'a'*40,'role':'builder',
            'phase':'initial_work','round':1,'findings':[],'review_record':None,'session':SID,'agent_path':None,'parent_session':None}
        self.write([tokens(9,100)])

    def write(self,records,sid=SID,agent=None,created=0,fork=None,name=None):
        meta={'id':sid,'timestamp':at(created),'forked_from_id':fork,'private':'PRIVATE_SENTINEL'}
        if agent:meta['source']={'subagent':{'thread_spawn':{'parent_thread_id':PARENT,'agent_path':agent}}}
        path=self.sessions/(name or sid+'.jsonl')
        path.write_text('\n'.join(json.dumps(r) for r in [{'type':'session_meta','payload':meta},*records])+'\n');return path

    def begin(self,n=10,meta=None,id=None):
        with patch('activity.now',return_value=at(n)):return a.begin(self.runtime,self.sessions,meta or self.meta,id)

    def end(self,row,n=20,outcome='completed',findings=None):
        with patch('activity.now',return_value=at(n)):return a.end(self.runtime,self.sessions,row['id'],outcome,findings)

    def test_observed_delta_freezes_and_drops_private_fields(self):
        row=self.begin();self.write([tokens(9,100),tokens(19,150)])
        self.end(row);value=a.collect(self.runtime)[row['id']]
        self.assertEqual(value['tokens']['total_tokens'],50)
        self.assertEqual(value['measurement_basis'],'observed_boundary_counter_delta')
        self.assertEqual(value['begin']['lag_seconds'],1)
        self.assertEqual(value['end']['lag_seconds'],1)
        self.write([tokens(9,100),tokens(19,150),tokens(25,900)])
        self.assertEqual(a.collect(self.runtime)[row['id']]['tokens']['total_tokens'],50)
        self.assertNotIn('PRIVATE_SENTINEL',(self.runtime/'data/activity.sqlite').read_bytes().decode(errors='ignore'))

    def test_four_phases_and_additional_round_reconcile(self):
        values=[100,150,180,225,240,260,275]
        self.write([tokens(9,values[0]),*[tokens(19+20*i,v) for i,v in enumerate(values[1:])]])
        for i,phase in enumerate(['initial_work','review','remediation','re_review','remediation','re_review']):
            meta={**self.meta,'phase':phase,'round':1 if i<3 else 2 if i<5 else 3,
                  'role':'quality' if 'review' in phase else 'builder','findings':['Q-001'] if i else []}
            row=self.begin(10+20*i,meta);self.end(row,20+20*i,'findings' if phase=='review' else 'completed',['Q-002'] if phase=='review' else [])
        store=Store(self.runtime/'data/evidence.sqlite');store.snapshot('activity:local',a.collect(self.runtime))
        totals=activity_totals(store,'all')[0]
        self.assertEqual(totals['Observed token subtotal'],175);self.assertEqual(totals['Eligible activities'],6)
        self.assertEqual(len(activities(store,'all')),6);self.assertEqual(len(activity_totals(store,'all',True)),6)
        self.assertEqual(totals['Marker seconds (sum)'],60);self.assertEqual(totals['Telemetry model calls'],0);store.close()

    def test_fresh_reviewers_and_concurrent_wall_union(self):
        rows=[]
        for i in [1,2]:
            meta={**self.meta,'phase':'review','role':'security' if i==1 else 'quality','session':None,
                  'agent_path':'/root/reviewer_'+str(i),'parent_session':PARENT}
            row=self.begin(meta=meta);rows.append(row)
            sid=f'{i+2:08d}-1111-1111-1111-111111111111'
            self.write([event(12,'task_started'),tokens(18,80+i),event(19,'task_complete')],sid,meta['agent_path'],created=11)
            self.end(row,30)
        result=a.collect(self.runtime)
        self.assertEqual({r['measurement_basis'] for r in result.values()},{'fresh_session_observed_cumulative'})
        store=Store(self.runtime/'data/evidence.sqlite');store.snapshot('activity:local',result)
        totals=activity_totals(store,'all')[0]
        self.assertEqual(totals['Observed token subtotal'],163);self.assertEqual(totals['Marker seconds (sum)'],40)
        self.assertEqual(totals['Marker seconds (union)'],20);store.close()

    def test_interior_reset_invalid_counter_fork_and_missing_are_excluded(self):
        for case in ['reset','invalid','fork','missing']:
            with self.subTest(case=case):
                row=self.begin(10)
                records=[tokens(9,100),tokens(15,200),tokens(16,50),tokens(19,250)] if case=='reset' else [tokens(9,100),tokens(19,150)]
                if case=='invalid':
                    bad=tokens(15,120);bad['payload']['info']['total_token_usage']['cached_input_tokens']=999;records.insert(1,bad)
                if case=='missing':records=[tokens(9,100)]
                self.write(records,fork=PARENT if case=='fork' else None);self.end(row)
                value=a.collect(self.runtime)[row['id']];self.assertFalse(value['eligible']);self.assertIsNone(value['tokens'])
                self.write([tokens(9,100)])

    def test_open_overlap_retry_and_command_claim(self):
        row=self.begin(id=SID);self.assertEqual(self.begin(id=SID),row)
        with self.assertRaisesRegex(a.ActivityError,'ACTIVE_ACTIVITY_OVERLAP'):self.begin()
        with self.assertRaisesRegex(a.ActivityError,'CONFLICTING_ACTIVITY_RETRY'):self.begin(meta={**self.meta,'round':2},id=SID)
        self.assertIn('activity_open',a.collect(self.runtime)[row['id']]['flags'])
        a.claim_command(self.runtime,row['id'])
        with self.assertRaisesRegex(a.ActivityError,'ALREADY_CLAIMED'):a.claim_command(self.runtime,row['id'])
        self.write([tokens(9,100),tokens(19,150)]);first=self.end(row)
        self.assertEqual(first,self.end(row,100))
        with self.assertRaisesRegex(a.ActivityError,'CONFLICTING'):self.end(row,100,'aborted')

    def test_failed_close_retry_never_fabricates_boundary_observation(self):
        row=self.begin();self.write([tokens(9,100),tokens(19,150)])
        with patch('activity.snapshot',side_effect=a.ActivityError('INJECTED')):
            with self.assertRaises(a.ActivityError):self.end(row,20)
        self.assertIsNone(a.collect(self.runtime)[row['id']]['tokens'])
        self.write([tokens(9,100),tokens(19,150),tokens(18,140),tokens(30,900)])
        result=self.end(row,50)
        self.assertEqual(result['ended_at'],at(20));self.assertIsNone(a.collect(self.runtime)[row['id']]['tokens'])

    def test_invalid_source_time_and_missing_baseline_are_not_hidden(self):
        for case in ['time','baseline','identity']:
            with self.subTest(case=case):
                row=self.begin();records=[tokens(9,100),tokens(19,150)]
                if case=='time':
                    bad=tokens(15,110);bad['timestamp']='invalid';records.insert(1,bad)
                elif case=='baseline':records=[tokens(15,50),tokens(19,150)]
                self.write(records,created=1 if case=='identity' else 0);self.end(row)
                self.assertFalse(a.collect(self.runtime)[row['id']]['eligible'])
                self.write([tokens(9,100)])

    def test_unmatched_or_out_of_bounds_fresh_lifecycle_is_unknown(self):
        for i,case in enumerate(['missing_start','future_payload','pre_creation_start','pre_creation_tokens']):
            meta={**self.meta,'session':None,'agent_path':'/root/reviewer_'+str(i),'parent_session':PARENT}
            row=self.begin(meta=meta);records=[event(12,'task_started'),tokens(18,80),event(19,'task_complete')]
            if case=='missing_start':records=records[1:]
            elif case=='future_payload':records[-1]['payload']['completed_at']=at(200)
            elif case=='pre_creation_start':records[0]['payload']['started_at']=at(0)
            else:
                records[1]=tokens(18,900)
                records.insert(0,tokens(5,900))
            self.write(records,f'{i+3:08d}-1111-1111-1111-111111111111',meta['agent_path'],created=11)
            self.end(row);result=a.collect(self.runtime)[row['id']]
            self.assertFalse(result['eligible'])
            if case=='pre_creation_tokens':self.assertIn('invalid_source_time',result['flags'])

    def test_binding_ambiguity_is_not_newest_match(self):
        meta={**self.meta,'session':None,'agent_path':'/root/reviewer','parent_session':PARENT}
        row=self.begin(meta=meta)
        for i in [3,4]:self.write([tokens(19,100),event(19,'task_complete')],f'{i:08d}-1111-1111-1111-111111111111',meta['agent_path'],created=11)
        with self.assertRaisesRegex(a.ActivityError,'AMBIGUOUS'):self.end(row)
        self.assertFalse(a.collect(self.runtime)[row['id']]['eligible'])

    def test_duplicate_fragments_and_shared_prefix_detection(self):
        self.write([tokens(9,100)],name='copy.jsonl')
        row=self.begin();self.write([tokens(9,100),tokens(19,150)]);self.write([tokens(9,100),tokens(19,150)],name='copy.jsonl');self.end(row)
        self.assertEqual(a.collect(self.runtime)[row['id']]['tokens']['total_tokens'],50)
        meta={**self.meta,'session':PARENT,'role':'quality'}
        self.write([tokens(9,100)],PARENT);second=self.begin(meta=meta)
        self.write([tokens(9,100),tokens(19,150)],PARENT);self.end(second)
        self.assertTrue(all(not r['eligible'] for r in a.collect(self.runtime).values()))

    def test_binding_overlap_with_explicit_session_excludes_both(self):
        bound={**self.meta,'session':None,'agent_path':'/root/reviewer','parent_session':PARENT}
        first=self.begin(meta=bound)
        self.write([tokens(12,50),tokens(19,100),event(19,'task_complete')],agent=bound['agent_path'],created=11)
        second=self.begin(13);self.end(second,20);self.end(first,21)
        self.assertTrue(all('overlap_or_shared_prefix' in r['flags'] for r in a.collect(self.runtime).values()))

    def test_metadata_privacy_paths_and_ledger_permissions(self):
        with self.assertRaises(a.ActivityError):self.begin(meta={**self.meta,'private':'PRIVATE_SENTINEL'})
        with self.assertRaises(a.ActivityError):self.begin(meta={**self.meta,'findings':['https://evil.invalid']})
        row=self.begin();db=self.runtime/'data/activity.sqlite';db.chmod(0o644)
        with self.assertRaises(a.ActivityError):a.collect(self.runtime)
        db.chmod(0o600);outside=self.root/'outside';outside.mkdir()
        (self.sessions/'link.jsonl').symlink_to(outside/'secret')
        with self.assertRaises(a.ActivityError):self.end(row)
        (self.sessions/'link.jsonl').unlink()
        data=json.loads(sqlite3.connect(db).execute('SELECT data FROM runs').fetchone()[0]);data['private']='PRIVATE_SENTINEL'
        with sqlite3.connect(db) as conn:conn.execute('UPDATE runs SET data=?',(json.dumps(data),))
        with self.assertRaises(a.ActivityError):a.collect(self.runtime)

    def test_policy_failure_does_not_block_activity_and_capture_failure_retains_it(self):
        from collect import run_once
        row=self.begin();self.write([tokens(9,100),tokens(19,150)]);self.end(row)
        (self.runtime/'settings.json').write_text(json.dumps({'repository_registry':str(self.runtime/'missing.json')}))
        run_once(self.runtime);store=Store(self.runtime/'data/evidence.sqlite');before=store.records('activity:')
        self.assertEqual(len(before),1)
        with patch('collect.activity_collect',side_effect=ValueError('PRIVATE_SENTINEL')):run_once(self.runtime)
        self.assertEqual(before,store.records('activity:'));self.assertTrue(any(h['source']=='activity:local' and h['status']=='error' for h in store.health()));store.close()

    def test_wrapper_executes_once_without_model_calls_and_does_not_store_command(self):
        marker=self.root/'marker';command=[sys.executable,'-c','from pathlib import Path;Path('+repr(str(marker))+').write_text("PRIVATE_SENTINEL")']
        args=['activity','--runtime',str(self.runtime),'--sessions',str(self.sessions),'run','--id',SID,
              '--repository','fixture/repo','--task','TASK-1','--role','builder','--phase','initial_work','--session',SID,'--',*command]
        with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()),patch('socket.socket',side_effect=AssertionError('telemetry network call')):
            self.assertEqual(a.main(),0);self.assertEqual(a.main(),1)
        self.assertTrue(marker.exists());self.assertNotIn(b'PRIVATE_SENTINEL',(self.runtime/'data/activity.sqlite').read_bytes())

    def test_retention_and_resource_caps(self):
        row=self.begin();self.write([tokens(9,100),tokens(19,150)]);self.end(row)
        with patch('activity.MAX_RUNS',0),self.assertRaises(a.ActivityError):a.collect(self.runtime)
        with patch('activity.MAX_BYTES',1),self.assertRaises(a.ActivityError):a.snapshot(self.sessions,{**self.meta,'began_at':at(10)},at(20))
        a.prune(self.runtime,days=0);self.assertEqual(a.collect(self.runtime),{})

    def test_nonregular_sources_and_nonprivate_runtime_are_rejected(self):
        os.mkfifo(self.sessions/'pipe.jsonl')
        with self.assertRaises(a.ActivityError):self.begin()
        (self.sessions/'pipe.jsonl').unlink();self.runtime.chmod(0o755)
        with self.assertRaises(a.ActivityError):self.begin()
        self.runtime.chmod(0o700)

    def test_new_read_only_routes_and_dashboard_contract_without_network(self):
        from server import make_handler
        import importlib.util
        row=self.begin();self.write([tokens(9,100),tokens(19,150)]);self.end(row)
        store=Store(self.runtime/'data/evidence.sqlite');store.snapshot('activity:local',a.collect(self.runtime));store.close()
        cls=make_handler(self.runtime,'test',8769,3001,['fixture/repo']);handler=cls.__new__(cls)
        handler.headers={'Host':'127.0.0.1:8769','Authorization':'Bearer test'}
        responses=[];handler.respond=lambda status,payload:responses.append((status,payload))
        for view in ['activities','activity-tasks','activity-rounds']:
            handler.path='/api/'+view+'?repo=fixture%2Frepo';handler.do_GET()
            self.assertEqual(responses[-1][0],200);self.assertEqual(len(responses[-1][1]),1)
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(responses[-1]))
        handler.do_POST();self.assertEqual(responses[-1][0],405)
        spec=importlib.util.spec_from_file_location('usage_dashboard',a.ROOT/'dashboard/build.py')
        build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
        doc=build.dashboard(repositories=['fixture/repo'])
        targets={p['targets'][0]['url'].split('/api/')[1].split('?')[0] for p in doc['panels'] if 'targets' in p}
        self.assertTrue({'activities','activity-tasks','activity-rounds'}<=targets)
        panels=doc['panels'];ids=[p['id'] for p in panels]
        self.assertEqual(len(ids),len(set(ids)))
        for p in panels:
            for q in panels:
                if p['id']>=q['id']:continue
                x,y=p['gridPos'],q['gridPos']
                intersects=x['x']<y['x']+y['w'] and y['x']<x['x']+x['w'] and x['y']<y['y']+y['h'] and y['y']<x['y']+x['h']
                self.assertFalse(intersects,(p['title'],q['title']))


if __name__=='__main__':unittest.main()
