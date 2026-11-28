"""Local phase usage recorder. No model client, inference or HTTP writes.

Task/phase labels are declared. Counter snapshots are observations, not exact
semantic phase costs or governance clearance. Closed captures never refresh.
"""
import argparse
import contextlib
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import time
import uuid

from common import UTC, REPO, SHA, canonical, fingerprint, identifier, integer, now, seconds, timestamp
from usage import FIELDS, MAX_LINE, MAX_FILE, interval_union, normalise, agent_source

ROOT = Path(__file__).resolve().parent.parent
PHASES = ('initial_work', 'review', 'remediation', 're_review')
OUTCOMES = ('completed', 'findings', 'blocked', 'aborted')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z')
AGENT = re.compile(r'/root(?:/[a-z0-9_]+)+\Z')
MAX_RUNS = 2048
MAX_BYTES = 512 * 1024 * 1024


class ActivityError(ValueError): pass


def uid(value):
    try: return str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError): return False


def safe_ancestors(path):
    path = Path(path).absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink(): raise ActivityError('UNSAFE_ACTIVITY_PATH')
    return path


@contextlib.contextmanager
def source_file(path, root):
    """Open beneath a fixed root using non-following descriptors at each level."""
    root = safe_ancestors(root)
    relative = Path(path).relative_to(root)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        child = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        info = os.fstat(child)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE or info.st_uid != os.getuid():
            os.close(child); raise ActivityError('UNSAFE_USAGE_SOURCE')
        with os.fdopen(child, 'rb') as handle: yield handle
    finally: os.close(fd)


def source_paths(root):
    root = safe_ancestors(root); count = 0; deadline = time.monotonic() + 10
    def walk(folder, depth):
        nonlocal count
        if depth > 8: raise ActivityError('ACTIVITY_DISCOVERY_LIMIT')
        with os.scandir(folder) as entries:
            for entry in entries:
                count += 1
                if count > 20000 or time.monotonic() > deadline: raise ActivityError('ACTIVITY_DISCOVERY_LIMIT')
                if entry.is_symlink(): raise ActivityError('UNSAFE_USAGE_SOURCE')
                if entry.is_dir(follow_symlinks=False): yield from walk(Path(entry.path), depth + 1)
                elif entry.name.endswith('.jsonl'): yield Path(entry.path)
    yield from walk(root, 0)


def snapshot(root, binding, cutoff, window_start=None):
    """Read selected structured metadata only; discard every free-text field."""
    selected = []; identities = {}; bytes_read = 0; timing_flags=[]
    for path in source_paths(root):
        with source_file(path, root) as handle:
            header = handle.readline(262145); bytes_read += len(header)
            if bytes_read > MAX_BYTES: raise ActivityError('ACTIVITY_SCAN_LIMIT')
            try: meta = json.loads(header).get('payload', {})
            except (ValueError, AttributeError): continue
            if not isinstance(meta,dict): continue
            if not uid(meta.get('id')): continue
            _, spawn = agent_source(meta.get('source'))
            if binding.get('session'):
                match = meta['id'] == binding['session']
            elif binding.get('cli_cwd'):
                match = (meta.get('source') == 'exec' and isinstance(meta.get('cwd'),str) and
                         str(Path(meta['cwd']).resolve()) == binding['cli_cwd'] and
                         (timestamp(meta.get('timestamp')) or '') >= binding['began_at'] and
                         (timestamp(meta.get('timestamp')) or 'z') <= cutoff)
            else:
                match = (spawn.get('agent_path') == binding['agent_path'] and
                         spawn.get('parent_thread_id') == binding['parent_session'] and
                         (timestamp(meta.get('timestamp')) or '') >= binding['began_at'] and
                         (timestamp(meta.get('timestamp')) or 'z') <= cutoff)
            if not match: continue
            identity = {k: meta.get(k) for k in ('id','timestamp','forked_from_id')}
            if binding.get('cli_cwd'):identity['cli_cwd']=binding['cli_cwd']
            identity.update(parent=spawn.get('parent_thread_id'), agent=spawn.get('agent_path'))
            if meta['id'] in identities and identities[meta['id']] != identity:
                raise ActivityError('ACTIVITY_SESSION_IDENTITY_CONFLICT')
            identities[meta['id']] = identity
            records = []
            while True:
                raw = handle.readline(MAX_LINE + 1)
                if not raw: break
                bytes_read += len(raw)
                if bytes_read > MAX_BYTES or len(raw) > MAX_LINE: raise ActivityError('ACTIVITY_SCAN_LIMIT')
                if not raw.endswith(b'\n'): raise ActivityError('ACTIVITY_SOURCE_INCOMPLETE')
                try: r = json.loads(raw)
                except ValueError: raise ActivityError('ACTIVITY_SOURCE_INVALID') from None
                if not isinstance(r,dict): raise ActivityError('ACTIVITY_SOURCE_INVALID')
                at = timestamp(r.get('timestamp'))
                p = r.get('payload'); kind = r.get('type')
                if not at:
                    if kind=='turn_context' or (kind=='event_msg' and isinstance(p,dict) and p.get('type') in ('token_count','task_started','task_complete','turn_aborted')):
                        timing_flags.append('invalid_source_time')
                    continue
                if at > cutoff: continue
                if not isinstance(p, dict): continue
                if kind == 'turn_context':
                    records.append({'type':kind,'timestamp':at,'payload':{'model':identifier(p.get('model'))}})
                elif kind == 'event_msg' and p.get('type') in ('token_count','task_started','task_complete','turn_aborted'):
                    q = {k:p.get(k) for k in ('type','turn_id','started_at','completed_at','duration_ms')}
                    if p['type'] == 'token_count':
                        info = p.get('info'); usage = info.get('total_token_usage') if isinstance(info,dict) else None
                        q['info'] = {'total_token_usage':{k:integer(usage.get(k)) for k in FIELDS} if isinstance(usage,dict) else None}
                    records.append({'type':kind,'timestamp':at,'payload':q})
                if len(records) > 50000: raise ActivityError('ACTIVITY_EVENT_LIMIT')
            selected.append((identity, records))
    if not selected: return {'session':binding.get('session'),'captured_at':timestamp(now()),'event_at':None,'tokens':None,'flags':['usage_unavailable'],'signals':[]}
    if len(identities) != 1: raise ActivityError('AMBIGUOUS_ACTIVITY_BINDING')
    identity = selected[0][0]; unique = {}
    for _, records in selected:
        for r in records: unique[fingerprint(r)] = r
    records = sorted(unique.values(), key=lambda r:r['timestamp'])
    points = []; flags = list(timing_flags)
    for r in records:
        if r['type'] != 'event_msg' or r['payload']['type'] != 'token_count': continue
        if window_start and r['timestamp'] < window_start: continue
        u = r['payload']['info']['total_token_usage']
        valid = bool(u) and all(u[k] is not None for k in FIELDS)
        valid = valid and u['cached_input_tokens'] <= u['input_tokens'] and u['reasoning_output_tokens'] <= u['output_tokens'] and u['total_tokens'] == u['input_tokens'] + u['output_tokens']
        if not valid: flags.append('invalid_counter'); continue
        if points and any(u[k] < points[-1]['tokens'][k] for k in FIELDS): flags.append('counter_reset')
        points.append({'event_at':r['timestamp'],'tokens':u})
    if identity.get('forked_from_id'): flags.append('fork_ambiguity')
    if len(points) > 256: flags.append('counter_window_limit')
    latest = points[-1] if points else {'event_at':None,'tokens':None}
    model_records=records
    if window_start:
        previous=[r for r in records if r['type']=='turn_context' and r['timestamp']<window_start]
        model_records=previous[-1:]+[r for r in records if r['timestamp']>=window_start]
    model = normalise(model_records, {'id':identity['id'],'timestamp':identity['timestamp'],'source':{}}, 'declared')
    if not binding.get('session'):
        starts={};ends={};created=timestamp(identity['timestamp'])
        if not created or any(p['event_at']<max(created,binding['began_at']) for p in points):
            flags.append('invalid_source_time')
        for r in records:
            if r['type']!='event_msg' or r['payload']['type']=='token_count':continue
            p=r['payload'];turn=identifier(p.get('turn_id'))
            if turn=='unknown' or not created or not created<=r['timestamp']<=cutoff:
                flags.append('invalid_lifecycle');continue
            for field in ('started_at','completed_at'):
                if p.get(field) is not None and (not timestamp(p[field]) or not created<=timestamp(p[field])<=cutoff):flags.append('invalid_lifecycle')
            if p.get('started_at') and p.get('completed_at') and timestamp(p['started_at']) and timestamp(p['completed_at']) and timestamp(p['started_at'])>timestamp(p['completed_at']):flags.append('invalid_lifecycle')
            target=starts if p['type']=='task_started' else ends
            if turn in target and target[turn]!=r['timestamp']:flags.append('invalid_lifecycle')
            target[turn]=r['timestamp']
        if not starts or set(starts)!=set(ends) or any(ends[t]<starts[t] for t in set(starts)&set(ends)):
            flags.append('invalid_lifecycle')
    observed_at=timestamp(now())
    return {'session':identity['id'],'identity_digest':fingerprint(identity),'created_at':timestamp(identity['timestamp']), 'captured_at':observed_at,
            **latest, 'lag_seconds':seconds(latest['event_at'],observed_at), 'flags':sorted(set(flags)),
            'model':model['model'],'completed_turns':model['completed_turns'],'open_turns':model['open_turns'],
            'signals':[fingerprint(p) for p in points[:256]]}


def validate(meta):
    keys = {'repository','task','pr','revision','role','phase','round','findings','review_record','session','agent_path','parent_session'}
    if not isinstance(meta,dict) or set(meta) not in (keys,keys|{'cli_cwd'}) or any(not isinstance(meta[k],str) for k in ('repository','task','role')) or len(meta['repository'])>200 or not REPO.fullmatch(meta['repository']) or not ID.fullmatch(meta['task']) or not ID.fullmatch(meta['role']): raise ActivityError('INVALID_ACTIVITY_METADATA')
    if meta['phase'] not in PHASES or type(meta['round']) is not int or not 1 <= meta['round'] <= 1000: raise ActivityError('INVALID_ACTIVITY_METADATA')
    if meta['pr'] is not None and (type(meta['pr']) is not int or not 1 <= meta['pr'] <= 10**9): raise ActivityError('INVALID_ACTIVITY_METADATA')
    if meta['revision'] is not None and (not isinstance(meta['revision'],str) or not SHA.fullmatch(meta['revision'])): raise ActivityError('INVALID_ACTIVITY_METADATA')
    if meta['review_record'] is not None and (not isinstance(meta['review_record'],str) or not ID.fullmatch(meta['review_record'])): raise ActivityError('INVALID_ACTIVITY_METADATA')
    if not isinstance(meta['findings'],list) or len(meta['findings']) > 16 or any(not isinstance(f,str) or not ID.fullmatch(f) for f in meta['findings']): raise ActivityError('INVALID_ACTIVITY_METADATA')
    if meta.get('cli_cwd'):
        cwd=meta['cli_cwd']
        if not isinstance(cwd,str) or len(cwd)>1024 or not Path(cwd).is_absolute() or str(Path(cwd).resolve())!=cwd or any(meta[k] for k in ['session','agent_path','parent_session']):raise ActivityError('INVALID_ACTIVITY_BINDING')
    elif meta['session']:
        if not uid(meta['session']) or meta['agent_path'] or meta['parent_session']: raise ActivityError('INVALID_ACTIVITY_BINDING')
    elif not isinstance(meta['agent_path'],str) or len(meta['agent_path']) > 160 or not AGENT.fullmatch(meta['agent_path']) or not uid(meta['parent_session']): raise ActivityError('INVALID_ACTIVITY_BINDING')


@contextlib.contextmanager
def ledger(runtime, readonly=False):
    runtime=safe_ancestors(runtime)
    if not runtime.exists():runtime.mkdir(parents=True,mode=0o700)
    for part in [runtime,*runtime.parents]:
        info=part.stat()
        if not stat.S_ISDIR(info.st_mode) or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):raise ActivityError('UNSAFE_ACTIVITY_LEDGER')
    info=runtime.stat()
    if info.st_uid!=os.getuid() or info.st_mode & 0o077:raise ActivityError('UNSAFE_ACTIVITY_LEDGER')
    folder = safe_ancestors(runtime/'data')
    if not folder.exists(): folder.mkdir(parents=True,mode=0o700)
    info = folder.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077: raise ActivityError('UNSAFE_ACTIVITY_LEDGER')
    path = safe_ancestors(folder/'activity.sqlite')
    for file in [path,Path(str(path)+'-journal'),Path(str(path)+'-wal'),Path(str(path)+'-shm')]:
        safe_ancestors(file)
        if file.exists():
            info = file.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 64*1024*1024: raise ActivityError('UNSAFE_ACTIVITY_LEDGER')
    if not readonly and not path.exists():
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10) if readonly else sqlite3.connect(path,timeout=10)
    try:
        if not readonly:
            db.execute('PRAGMA journal_mode=DELETE')
            db.executescript('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, run TEXT, at TEXT, kind TEXT);')
        yield db
    finally: db.close()


def saved(db):
    data=db.execute('SELECT data FROM runs LIMIT ?', (MAX_RUNS+1,)).fetchall()
    if len(data)>MAX_RUNS: raise ActivityError('ACTIVITY_ROW_LIMIT')
    result=[]
    for encoded, in data:
        if len(encoded)>262144:raise ActivityError('ACTIVITY_ROW_LIMIT')
        row=json.loads(encoded)
        if set(row)!={'schema_version','id','metadata','began_at','ended_at','outcome','outcome_findings','command_claimed','begin','end'} or row['schema_version']!=1 or not uid(row['id']): raise ActivityError('INVALID_ACTIVITY_RECORD')
        validate(row['metadata'])
        if not timestamp(row['began_at']) or (row['ended_at'] is not None and (not timestamp(row['ended_at']) or row['ended_at']<row['began_at'])):raise ActivityError('INVALID_ACTIVITY_RECORD')
        if row['outcome'] not in (None,*OUTCOMES) or type(row['command_claimed']) is not bool:raise ActivityError('INVALID_ACTIVITY_RECORD')
        if not isinstance(row['outcome_findings'],list) or len(row['outcome_findings'])>16 or any(not isinstance(f,str) or not ID.fullmatch(f) for f in row['outcome_findings']):raise ActivityError('INVALID_ACTIVITY_RECORD')
        for point in [row['begin'],row['end']]:
            if point is None:continue
            allowed={'session','identity_digest','created_at','captured_at','event_at','tokens','lag_seconds','flags','model','completed_turns','open_turns','signals'}
            if not isinstance(point,dict) or set(point)-allowed:raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            if point.get('session') is not None and not uid(point['session']):raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            if point.get('identity_digest') is not None and not re.fullmatch('[0-9a-f]{64}',point['identity_digest']):raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            for field in ['created_at','captured_at','event_at']:
                if point.get(field) is not None and not timestamp(point[field]):raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            if point.get('model') is not None and identifier(point['model'])!=point['model']:raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            if point.get('lag_seconds') is not None and (type(point['lag_seconds']) not in (int,float) or not math.isfinite(point['lag_seconds']) or point['lag_seconds']<0):raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            for key in ['completed_turns','open_turns']:
                if key in point and integer(point[key]) is None:raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            known={'usage_unavailable','invalid_counter','counter_reset','fork_ambiguity','counter_window_limit','invalid_source_time','invalid_lifecycle','baseline_missing_or_changed','session_identity_changed'}
            if not isinstance(point.get('flags'),list) or any(f not in known for f in point['flags']):raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            if not isinstance(point.get('signals'),list) or len(point['signals'])>256 or any(not isinstance(s,str) or not re.fullmatch('[0-9a-f]{64}',s) for s in point['signals']):raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
            if point.get('tokens') is not None and (not isinstance(point['tokens'],dict) or set(point['tokens'])!=set(FIELDS) or any(integer(v) is None for v in point['tokens'].values())):raise ActivityError('INVALID_ACTIVITY_SNAPSHOT')
        result.append(row)
    return result


def begin(runtime, sessions, meta, run_id=None):
    validate(meta); run_id=run_id or str(uuid.uuid4())
    if not uid(run_id): raise ActivityError('INVALID_ACTIVITY_ID')
    with ledger(runtime) as db:
        db.execute('BEGIN IMMEDIATE')
        records=saved(db)
        for old in records:
            if old['id']==run_id:
                if old['metadata']!=meta: raise ActivityError('CONFLICTING_ACTIVITY_RETRY')
                return old
            if old['ended_at'] is None and ((meta.get('cli_cwd') and old['metadata'].get('cli_cwd')==meta['cli_cwd']) or (not meta.get('cli_cwd') and not old['metadata'].get('cli_cwd') and ((meta['session'] and old['metadata']['session']==meta['session']) or (not meta['session'] and (old['metadata']['agent_path'],old['metadata']['parent_session'])==(meta['agent_path'],meta['parent_session']))))):
                raise ActivityError('ACTIVE_ACTIVITY_OVERLAP')
        if len(records)>=MAX_RUNS: raise ActivityError('ACTIVITY_ROW_LIMIT')
        at=timestamp(now()); binding={**meta,'began_at':at}
        capture=snapshot(sessions,binding,at) if meta['session'] else None
        row={'schema_version':1,'id':run_id,'metadata':meta,'began_at':at,'ended_at':None,'outcome':None,'outcome_findings':[], 'command_claimed':False,'begin':capture,'end':None}
        db.execute('INSERT INTO runs VALUES (?,?)',(run_id,canonical(row)))
        db.execute('INSERT INTO events(run,at,kind) VALUES (?,?,?)',(run_id,at,'begin'));db.commit();return row


def end(runtime, sessions, run_id, outcome, findings=None):
    findings=findings or []
    if len(findings)>16 or any(not isinstance(f,str) or not ID.fullmatch(f) for f in findings): raise ActivityError('INVALID_ACTIVITY_METADATA')
    if not uid(run_id) or outcome not in OUTCOMES: raise ActivityError('INVALID_ACTIVITY_END')
    with ledger(runtime) as db:
        db.execute('BEGIN IMMEDIATE')
        found=db.execute('SELECT data FROM runs WHERE id=?',(run_id,)).fetchone()
        if not found: raise ActivityError('ACTIVITY_NOT_FOUND')
        row=next(r for r in saved(db) if r['id']==run_id)
        if row['ended_at']:
            if row['outcome']!=outcome or row['outcome_findings']!=findings: raise ActivityError('CONFLICTING_ACTIVITY_RETRY')
            # A failed capture was not observed at the boundary. It stays unknown;
            # late-arriving backdated records cannot repair it retrospectively.
            return row
        else:
            at=timestamp(now())
            if at < row['began_at']: raise ActivityError('ACTIVITY_CLOCK_REGRESSION')
            # Preserve the intended boundary even if capture fails. A retry
            # returns unknown and never reconstructs an unobserved boundary.
            row.update(ended_at=at,outcome=outcome,outcome_findings=findings)
            db.execute('UPDATE runs SET data=? WHERE id=?',(canonical(row),run_id));db.commit()
            db.execute('BEGIN IMMEDIATE')
        binding={**row['metadata'],'began_at':row['began_at']}
        row['end']=snapshot(sessions,binding,row['ended_at'],(row['begin'] or {}).get('event_at'))
        start=row['begin'] or {}
        if start.get('tokens'):
            baseline=fingerprint({k:start[k] for k in ['event_at','tokens']})
            if baseline not in row['end']['signals']:row['end']['flags'].append('baseline_missing_or_changed')
            if start.get('identity_digest')!=row['end'].get('identity_digest'):row['end']['flags'].append('session_identity_changed')
        db.execute('UPDATE runs SET data=? WHERE id=?',(canonical(row),run_id))
        db.execute('INSERT INTO events(run,at,kind) VALUES (?,?,?)',(run_id,row['ended_at'],'end'));db.commit();return row


def claim_command(runtime,run_id):
    with ledger(runtime) as db:
        db.execute('BEGIN IMMEDIATE')
        row=next((r for r in saved(db) if r['id']==run_id),None)
        if row is None:raise ActivityError('ACTIVITY_NOT_FOUND')
        if row['command_claimed'] or row['ended_at']: raise ActivityError('ACTIVITY_COMMAND_ALREADY_CLAIMED')
        row['command_claimed']=True
        db.execute('UPDATE runs SET data=? WHERE id=?',(canonical(row),run_id));db.commit()


def project(row):
    m=row['metadata']; start=row['begin'] or {}; stop=row['end'] or {}
    flags=list(stop.get('flags',[])); tokens=None; basis='unavailable'
    if not row['ended_at']: flags.append('activity_open')
    elif stop.get('tokens') and not flags:
        if m['session'] and start.get('tokens') and start.get('event_at')!=stop.get('event_at'):
            delta={k:stop['tokens'][k]-start['tokens'][k] for k in FIELDS}
            if any(v<0 for v in delta.values()): flags.append('counter_reset')
            elif delta['total_tokens']==0: flags.append('no_counter_movement')
            elif delta['cached_input_tokens']>delta['input_tokens'] or delta['reasoning_output_tokens']>delta['output_tokens']: flags.append('invalid_counter_delta')
            else: tokens=delta;basis='observed_boundary_counter_delta'
        elif not m['session'] and stop.get('created_at') and row['began_at']<=stop['created_at']<=row['ended_at'] and stop.get('completed_turns',0)>0 and stop.get('open_turns')==0:
            tokens=stop['tokens'];basis='fresh_session_observed_cumulative'
        else: flags.append('missing_boundary_or_lifecycle')
    if not tokens and not flags: flags.append('usage_unavailable')
    return {**row,'repository':m['repository'],'session':stop.get('session') or start.get('session'),
            'model':stop.get('model') or start.get('model') or 'unknown','measurement_basis':basis,
            'tokens':tokens,'eligible':tokens is not None and not flags,'flags':sorted(set(flags)),
            'elapsed_seconds':seconds(row['began_at'],row['ended_at']),
            'association':'operator_declared_task_phase_not_independent_authority',
            'instrumentation_model_calls':0,'measurement_scope':'CLI root session only; child sessions excluded unless separately instrumented' if m.get('cli_cwd') else 'Explicitly bound individual session'}


def collect(runtime):
    if not safe_ancestors(Path(runtime)/'data/activity.sqlite').exists(): return {}
    with ledger(runtime,readonly=True) as db: records=[project(r) for r in saved(db)]
    for index,row in enumerate(records):
        for other in records[index+1:]:
            if not row['session'] or not other['session']: continue
            overlap=row['began_at']<(other['ended_at'] or 'z') and other['began_at']<(row['ended_at'] or 'z')
            shared=set((row.get('end') or {}).get('signals',[])) & set((other.get('end') or {}).get('signals',[]))
            if (row['session']==other['session'] and overlap) or (row['session']!=other['session'] and shared):
                for affected in (row,other):
                    affected['eligible']=False;affected['tokens']=None
                    affected['flags']=sorted(set(affected['flags']+['overlap_or_shared_prefix']))
    return {r['id']:r for r in records}


def prune(runtime, days=30):
    if not safe_ancestors(Path(runtime)/'data/activity.sqlite').exists(): return
    cutoff=timestamp((dt.datetime.now(UTC)-dt.timedelta(days=days)).isoformat())
    with ledger(runtime) as db:
        for row in saved(db):
            if (row['ended_at'] or row['began_at']) < cutoff:
                db.execute('DELETE FROM events WHERE run=?',(row['id'],));db.execute('DELETE FROM runs WHERE id=?',(row['id'],))
        db.commit()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,default=ROOT/'.runtime');p.add_argument('--sessions',type=Path,default=Path.home()/'.codex/sessions')
    sub=p.add_subparsers(dest='action',required=True)
    for name in ['begin','run']:
        q=sub.add_parser(name);q.add_argument('--task',required=True);q.add_argument('--repository',required=True);q.add_argument('--role',required=True);q.add_argument('--phase',choices=PHASES,required=True);q.add_argument('--round',type=int,default=1);q.add_argument('--session');q.add_argument('--agent-path');q.add_argument('--parent-session');q.add_argument('--pr',type=int);q.add_argument('--revision');q.add_argument('--finding',action='append',default=[]);q.add_argument('--review-record');q.add_argument('--id')
        if name=='run':q.add_argument('command',nargs=argparse.REMAINDER)
    q=sub.add_parser('end');q.add_argument('--id',required=True);q.add_argument('--outcome',choices=OUTCOMES,required=True);q.add_argument('--finding',action='append',default=[])
    sub.add_parser('list');a=p.parse_args()
    try:
        if a.action=='list': result=list(collect(a.runtime).values())
        elif a.action=='end': result=end(a.runtime,a.sessions,a.id,a.outcome,a.finding)
        else:
            meta={k:getattr(a,k) for k in ['task','repository','role','phase','round','session','agent_path','parent_session','pr','revision','review_record']};meta['findings']=a.finding
            result=begin(a.runtime,a.sessions,meta,a.id)
            if a.action=='run':
                command=a.command[1:] if a.command[:1]==['--'] else a.command
                if not command:raise ActivityError('ACTIVITY_COMMAND_REQUIRED')
                claim_command(a.runtime,result['id'])
                try:code=subprocess.run(command).returncode
                except BaseException:
                    end(a.runtime,a.sessions,result['id'],'aborted');raise
                result=end(a.runtime,a.sessions,result['id'],'completed' if code==0 else 'aborted')
                print(json.dumps({'activity_id':result['id'],'command_exit_code':code}));return code
        print(json.dumps(result,indent=2));return 0
    except (ValueError,TypeError,KeyError,AttributeError,OSError,sqlite3.Error):
        print('{"error":"ACTIVITY_RECORDING_UNAVAILABLE"}');return 1


if __name__=='__main__':raise SystemExit(main())
