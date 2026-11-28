"""Resolve registered repository policy independently of a candidate working tree.

This is discovery/detection, not a protected launch or merge boundary.
"""
import argparse
import hashlib
import functools
import contextlib
import errno
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
GIT = '/usr/bin/git'
MAX_OBJECT = 4 * 1024 * 1024
MAX_FILES = 256
MAX_WORKSPACES = 64


class ResolutionError(ValueError): pass


@functools.lru_cache(maxsize=1)
def git_executable():
    if sys.platform!='darwin':return GIT
    # Avoid the protected macOS shim; locate the system-selected developer binary.
    result=subprocess.run(['/usr/bin/xcrun','--find','git'],env={'PATH':'/usr/bin:/bin'},
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=5,check=True)
    if len(result.stdout)>4096:raise ResolutionError('TRUSTED_GIT_UNAVAILABLE')
    path=Path(result.stdout.decode().strip()).resolve()
    if not path.is_file() or not any(path.is_relative_to(p) for p in [Path('/Applications'),Path('/Library/Developer')]):
        raise ResolutionError('TRUSTED_GIT_UNAVAILABLE')
    return str(path)


def strict_json(raw):
    if len(raw) > MAX_OBJECT: raise ResolutionError('JSON_LIMIT')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ResolutionError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    try: return json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError): raise ResolutionError('INVALID_JSON') from None


def git(cwd, *args, limit=262144):
    # A clean child environment prevents inherited Git config/object overrides.
    env = {'PATH':'/usr/bin:/bin', 'LANG':'C', 'GIT_CONFIG_NOSYSTEM':'1',
        'GIT_CONFIG_GLOBAL':'/dev/null', 'GIT_NO_REPLACE_OBJECTS':'1',
        'GIT_NO_LAZY_FETCH':'1', 'GIT_TERMINAL_PROMPT':'0', 'GIT_ALLOW_PROTOCOL':'',
        'GIT_OPTIONAL_LOCKS':'0'}
    command = [git_executable(),'--no-pager','--no-replace-objects','-c','core.fsmonitor=false',
        '-c','core.hooksPath=/dev/null','-c','protocol.allow=never','-C',str(cwd),*args]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env=env, start_new_session=True)
    selector = selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
    output = bytearray(); deadline = time.monotonic()+10
    try:
        while selector.get_map():
            remaining = deadline-time.monotonic()
            if remaining <= 0: raise ResolutionError('GIT_READ_TIMEOUT')
            for key, _ in selector.select(remaining):
                data = os.read(key.fileobj.fileno(),min(65536,limit-len(output)+1))
                if not data: selector.unregister(key.fileobj); break
                output.extend(data)
                if len(output)>limit: raise ResolutionError('GIT_OUTPUT_LIMIT')
        if process.wait(timeout=max(.01,deadline-time.monotonic())):
            raise ResolutionError('GIT_READ_UNAVAILABLE')
        return bytes(output)
    finally:
        selector.close(); process.stdout.close()
        if process.poll() is None:
            try:process.wait(timeout=.2) # Closing the pipe normally terminates a capped reader.
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except (ProcessLookupError,PermissionError):
                    try:process.kill()
                    except ProcessLookupError:pass
                process.wait(timeout=2)


def identity(cwd):
    cwd = Path(cwd).resolve(strict=True)
    top = Path(git(cwd,'rev-parse','--show-toplevel').decode().strip()).resolve(strict=True)
    common = Path(git(cwd,'rev-parse','--git-common-dir').decode().strip())
    common = (cwd/common).resolve(strict=True) if not common.is_absolute() else common.resolve(strict=True)
    return top, common


def remote_repository(root):
    value = git(root,'remote','get-url','origin',limit=8192).decode().strip()
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?',value)
    if not match: raise ResolutionError('REMOTE_BINDING_UNAVAILABLE')
    return match[1].lower()


def object_bytes(root, oid, kind):
    if not isinstance(oid,str) or not SHA.fullmatch(oid): raise ResolutionError('INVALID_OBJECT_ID')
    size = int(git(root,'cat-file','-s',oid,limit=32))
    if not 0 <= size <= MAX_OBJECT: raise ResolutionError('OBJECT_LIMIT')
    raw = git(root,'cat-file',kind,oid,limit=MAX_OBJECT)
    expected = hashlib.sha1(kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if len(raw)!=size or expected!=oid: raise ResolutionError('GIT_OBJECT_INTEGRITY_FAILURE')
    return raw


def tree(root, oid):
    raw = object_bytes(root,oid,'tree'); result = {}; offset = 0
    while offset<len(raw):
        end = raw.find(b'\0',offset)
        if end<0 or end+21>len(raw): raise ResolutionError('INVALID_TREE')
        mode, name = raw[offset:end].split(b' ',1); name = name.decode('utf-8')
        if name in result or name in ('.','..','.git') or '/' in name or '\\' in name or any(ord(c)<32 for c in name):
            raise ResolutionError('UNSAFE_TREE_PATH')
        result[name]=(mode.decode(),raw[end+1:end+21].hex()); offset=end+21
        if len(result)>MAX_FILES: raise ResolutionError('TREE_LIMIT')
    return result


def approved_sources(entry):
    root=Path(entry['clones'][0]['root']); top, common=identity(root)
    if top!=root.resolve() or str(common)!=entry['clones'][0]['common_dir'] or remote_repository(root)!=entry['repository'].lower():
        raise ResolutionError('REGISTERED_IDENTITY_CHANGED')
    commit=object_bytes(root,entry['adoption_revision'],'commit')
    roots=[line[5:].decode() for line in commit.split(b'\n\n',1)[0].splitlines() if line.startswith(b'tree ')]
    if len(roots)!=1: raise ResolutionError('INVALID_COMMIT_TREE')
    root_tree=tree(root,roots[0]); mode, gov_oid=root_tree['.governance']
    if mode!='40000': raise ResolutionError('UNSAFE_GOVERNANCE_TREE')
    governance=tree(root,gov_oid)
    def blob(name):
        mode, oid=governance[name]
        if mode not in ('100644','100755'): raise ResolutionError('NONREGULAR_APPROVED_SOURCE')
        return object_bytes(root,oid,'blob')
    adoption_raw, adapter_raw=blob('adoption.json'),blob('project.json')
    adoption=strict_json(adoption_raw); pin=adoption['policy_source']
    if str(adoption.get('status', '')).startswith('draft'):
        raise ResolutionError('APPROVED_ADOPTION_IS_DRAFT')
    if adoption['repository']!=entry['repository'] or pin['commit_sha']!=entry['policy_source_revision'] or pin['manifest_sha256']!=entry['manifest_sha256'] or pin['version']!=entry['policy_version']:
        raise ResolutionError('APPROVED_ADOPTION_MISMATCH')
    if strict_json(adapter_raw)['repository']!=entry['repository']:
        raise ResolutionError('APPROVED_ADAPTER_MISMATCH')
    mode, bundle_oid=governance['baseline']
    if mode!='40000': raise ResolutionError('UNSAFE_BUNDLE_TREE')
    files={};steps=0
    def walk(oid,prefix='',depth=0):
        nonlocal steps
        steps+=1
        if steps>MAX_FILES:raise ResolutionError('BUNDLE_TREE_LIMIT')
        if depth>12: raise ResolutionError('TREE_DEPTH_LIMIT')
        for name,(mode,child) in tree(root,oid).items():
            path=prefix+name
            if mode=='40000':walk(child,path+'/',depth+1)
            elif mode in ('100644','100755'):
                files[path]=child
                if len(files)>MAX_FILES:raise ResolutionError('BUNDLE_FILE_LIMIT')
            else:raise ResolutionError('NONREGULAR_BUNDLE_SOURCE')
    walk(bundle_oid)
    manifest_raw=object_bytes(root,files['manifest.json'],'blob')
    if hashlib.sha256(manifest_raw).hexdigest()!=entry['manifest_sha256']:
        raise ResolutionError('APPROVED_MANIFEST_MISMATCH')
    manifest=strict_json(manifest_raw)
    if set(files)!={'manifest.json',*manifest['files']} or manifest['version']!=entry['policy_version']:
        raise ResolutionError('APPROVED_INVENTORY_MISMATCH')
    return root,files,manifest_raw,adapter_raw,adoption_raw


def regular_read(path, root, limit=MAX_OBJECT):
    path=Path(path); root=Path(root)
    if any(p.is_symlink() for p in [path,*path.parents] if p.is_relative_to(root)):
        raise ResolutionError('UNSAFE_LOCAL_PATH')
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size>limit:
        raise ResolutionError('NONREGULAR_OR_OVERSIZE_FILE')
    return path.read_bytes()


def verify_inventory(folder, expected, error, containment=None):
    """Bound every entry, including directories; reject unexpected empty trees."""
    folder = Path(folder)
    if folder.is_symlink() or not stat.S_ISDIR(folder.lstat().st_mode):
        raise ResolutionError(error)
    allowed_dirs = {p.as_posix() for name in expected for p in PurePosixPath(name).parents
                    if p != PurePosixPath('.')}
    seen = set(); count = 0; deadline = time.monotonic() + 5
    def walk(directory, depth):
        nonlocal count
        if depth > 12: raise ResolutionError(error)
        with os.scandir(directory) as entries:
            for item in entries:
                count += 1
                if count > 2 * MAX_FILES or time.monotonic() > deadline:
                    raise ResolutionError(error)
                path = Path(item.path); name = path.relative_to(folder).as_posix()
                if item.is_symlink(): raise ResolutionError(error)
                if item.is_dir(follow_symlinks=False):
                    if name not in allowed_dirs: raise ResolutionError(error)
                    walk(path, depth + 1)
                else:
                    if name not in expected or not item.is_file(follow_symlinks=False):
                        raise ResolutionError(error)
                    if hashlib.sha256(regular_read(path, containment or folder)).hexdigest() != expected[name]:
                        raise ResolutionError(error)
                    seen.add(name)
    walk(folder, 0)
    if seen != set(expected): raise ResolutionError(error)


def materialize(entry, cache):
    validate_registry({'schema_version':1,'repositories':[entry]})
    root,files,manifest_raw,adapter_raw,adoption_raw=approved_sources(entry)
    manifest=strict_json(manifest_raw); cache=Path(cache)
    if cache.is_symlink() or cache.parent.is_symlink():raise ResolutionError('UNSAFE_CACHE_ROOT')
    cache=cache.resolve()
    destination=cache/(str(entry['repository_id'])+'-'+entry['adoption_revision'][:12]+'-'+entry['manifest_sha256'])
    cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    def verify(folder):
        expected={**{'baseline/'+k:v for k,v in manifest['files'].items()},
            'baseline/manifest.json':entry['manifest_sha256'],
            'project.json':hashlib.sha256(adapter_raw).hexdigest(),
            'adoption.json':hashlib.sha256(adoption_raw).hexdigest()}
        verify_inventory(folder, expected, 'CACHE_INTEGRITY_FAILURE')
    if destination.is_symlink():raise ResolutionError('CACHE_INTEGRITY_FAILURE')
    if destination.exists():
        verify(destination);return destination
    with tempfile.TemporaryDirectory(dir=cache,prefix='.staging-') as tmp:
        staging=Path(tmp)
        values={'adoption.json':adoption_raw,'project.json':adapter_raw,'baseline/manifest.json':manifest_raw}
        for name,oid in files.items():
            relative=PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts:raise ResolutionError('UNSAFE_BUNDLE_PATH')
            if name!='manifest.json':values['baseline/'+name]=object_bytes(root,oid,'blob')
        for name,raw in values.items():
            p=staging/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.write_bytes(raw);p.chmod(0o600)
        verify(staging)
        try: os.replace(staging,destination)
        except OSError as error:
            if error.errno not in (errno.EEXIST, errno.ENOTEMPTY): raise
            verify(destination) # Another complete, identical publication won.
    return destination


def validate_registry(value):
    if not isinstance(value,dict) or set(value)!={'schema_version','repositories'} or value['schema_version']!=1:
        raise ResolutionError('INVALID_REGISTRY')
    entries=value['repositories'];seen=set();seen_ids=set();common_dirs=set();clone_roots=set()
    if not isinstance(entries,list) or not 1<=len(entries)<=32:raise ResolutionError('INVALID_REGISTRY')
    required={'repository','repository_id','adoption_revision','policy_source_revision','policy_version','manifest_sha256','clones'}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!=required or not isinstance(entry['repository'],str) or not REPO.fullmatch(entry['repository']) or type(entry['repository_id']) is not int or entry['repository_id']<=0:
            raise ResolutionError('INVALID_REGISTRY')
        if entry['repository'].lower() in seen or entry['repository_id'] in seen_ids or not all(isinstance(entry[k],str) for k in ('adoption_revision','policy_source_revision','manifest_sha256')) or not SHA.fullmatch(entry['adoption_revision']) or not SHA.fullmatch(entry['policy_source_revision']) or not DIGEST.fullmatch(entry['manifest_sha256']) or not isinstance(entry['policy_version'],str) or not 1<=len(entry['policy_version'])<=64:
            raise ResolutionError('INVALID_REGISTRY')
        seen.add(entry['repository'].lower());seen_ids.add(entry['repository_id'])
        if not isinstance(entry['clones'],list) or not 1<=len(entry['clones'])<=16:raise ResolutionError('INVALID_REGISTRY')
        for clone in entry['clones']:
            if not isinstance(clone,dict) or set(clone)!={'root','common_dir'} or not all(isinstance(clone[k],str) and Path(clone[k]).is_absolute() for k in clone):raise ResolutionError('INVALID_REGISTRY')
            common = str(Path(clone['common_dir']).resolve()); root = str(Path(clone['root']).resolve())
            if common in common_dirs or root in clone_roots:raise ResolutionError('AMBIGUOUS_CLONE_REGISTRATION')
            common_dirs.add(common);clone_roots.add(root)
    return entries


def registry(path):
    return validate_registry(strict_json(regular_read(path,Path(path).parent)))


def worktrees(entry):
    result={}
    for clone in entry['clones']:
        root=Path(clone['root']);top,common=identity(root)
        if top!=root.resolve() or str(common)!=clone['common_dir'] or remote_repository(root)!=entry['repository'].lower():
            raise ResolutionError('REGISTERED_IDENTITY_CHANGED')
        raw=git(root,'worktree','list','--porcelain','-z')
        for group in raw.split(b'\0\0'):
            if not group:continue
            row={}
            for part in group.split(b'\0'):
                if part:
                    key,_,value=part.partition(b' ');row[key.decode()]=value.decode('utf-8')
            path=Path(row['worktree']).resolve()
            wid=hashlib.sha256((str(common)+'\0'+str(path)).encode()).hexdigest()[:16]
            if wid in result:raise ResolutionError('AMBIGUOUS_WORKSPACE')
            result[wid]={'id':wid,'root':path,'common_dir':common,'branch':row.get('branch','detached'),'head':row.get('HEAD'),'missing':not path.is_dir()}
            if len(result)>MAX_WORKSPACES:raise ResolutionError('WORKSPACE_LIMIT')
    return result


def inspect(entry, cache):
    started=time.monotonic();approved=materialize(entry,cache); inventory=worktrees(entry);observations={};scopes=[]
    for wid,w in inventory.items():
        if time.monotonic()-started>30:raise ResolutionError('AUDIT_TIME_LIMIT')
        root=w['root'];issues=[]
        if w['missing']:issues.append('WORKSPACE_UNAVAILABLE')
        else:
            try:
                if identity(root)!=(root,w['common_dir']):raise ResolutionError('WORKSPACE_IDENTITY_MISMATCH')
                local=root/'.governance'
                if regular_read(local/'adoption.json',root)!=regular_read(approved/'adoption.json',approved):issues.append('LOCAL_ADOPTION_DIFFERS')
                if regular_read(local/'project.json',root)!=regular_read(approved/'project.json',approved):issues.append('LOCAL_ADAPTER_DIFFERS')
                manifest_raw=regular_read(local/'baseline/manifest.json',root)
                if hashlib.sha256(manifest_raw).hexdigest()!=entry['manifest_sha256']:raise ResolutionError('LOCAL_MANIFEST_MISMATCH')
                expected={**strict_json(manifest_raw)['files'],'manifest.json':entry['manifest_sha256']}
                verify_inventory(local/'baseline', expected, 'LOCAL_BUNDLE_MISMATCH', root)
            except FileNotFoundError:issues.append('LOCAL_ADOPTION_MISSING')
            except (ValueError,OSError,KeyError):issues.append('LOCAL_POLICY_INVALID')
            try:
                file=root/'AGENTS.override.md' if (root/'AGENTS.override.md').exists() else root/'AGENTS.md'
                text=regular_read(file,root,131072).decode('utf-8')
                if '.governance/adoption.json' not in text:issues.append('POLICY_INSTRUCTION_REFERENCE_MISSING')
            except (OSError,ValueError):issues.append('POLICY_INSTRUCTION_REFERENCE_UNAVAILABLE')
            # Inventory includes nonconforming workspaces so they cannot disappear from evidence.
            scopes.append({'cwd':str(root),'repository':entry['repository'],'common_dir':str(w['common_dir']),'workspace_id':wid})
        label=re.sub(r'[^\w .()-]','_',root.name)[:120]
        observations[wid]={'repository':entry['repository'],'repository_id':entry['repository_id'],'workspace':label,'workspace_id':wid,
            'branch':w['branch'][:160],'head_sha':w['head'],'effective_policy_version':entry['policy_version'],
            'policy_source_revision':entry['policy_source_revision'],'approved_manifest_sha256':entry['manifest_sha256'],
            'local_status':'attention_required' if issues else 'local_metadata_matches','issues':sorted(set(issues)),
            'instruction_loading':'not_observed','startup_enforcement':'not_installed','merge_enforcement':'not_established',
            'registry_custody':'operator_configured_owner_writable_not_independently_protected'}
    if inventory!=worktrees(entry):raise ResolutionError('WORKSPACE_INVENTORY_CHANGED_RETRY')
    return observations,scopes,approved


@contextlib.contextmanager
def registry_lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=path.with_name(path.name+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            raise ResolutionError('UNSAFE_REGISTRY_LOCK')
        deadline=time.monotonic()+10
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>deadline:raise ResolutionError('REGISTRY_LOCK_UNAVAILABLE')
                time.sleep(.02)
        yield
    finally:
        os.close(fd)


def register(path, cache, cwd, repository, repository_id, adoption_revision, policy_source_revision, manifest_sha256, policy_version):
    with registry_lock(path):
        return register_locked(path,cache,cwd,repository,repository_id,adoption_revision,
                               policy_source_revision,manifest_sha256,policy_version)


def register_locked(path, cache, cwd, repository, repository_id, adoption_revision, policy_source_revision, manifest_sha256, policy_version):
    """Explicit operator registration; existing trust pins cannot silently change."""
    top,common=identity(cwd)
    entry={'repository':repository,'repository_id':repository_id,'adoption_revision':adoption_revision,
        'policy_source_revision':policy_source_revision,'manifest_sha256':manifest_sha256,'policy_version':policy_version,
        'clones':[{'root':str(top),'common_dir':str(common)}]}
    validate_registry({'schema_version':1,'repositories':[entry]})
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    entries=registry(path) if path.exists() else []
    existing=next((e for e in entries if e['repository'].lower()==repository.lower()),None)
    if existing:
        if any(existing[k]!=entry[k] for k in entry if k!='clones'):raise ResolutionError('REGISTRY_PIN_CHANGE_REQUIRES_REVIEW')
        if any(c['common_dir']==str(common) for c in existing['clones']):
            known=worktrees(existing)
            if not any(w['root']==top and w['common_dir']==common for w in known.values()):
                raise ResolutionError('WORKSPACE_IDENTITY_MISMATCH')
            return existing
    # Validate this clone's authenticated object chain, not just its remote string.
    materialize(entry,cache)
    if existing:existing['clones']+=entry['clones']
    else:entries.append(entry)
    fd,temporary=tempfile.mkstemp(dir=path.parent,prefix='.registry-')
    try:
        with os.fdopen(fd,'w') as handle:json.dump({'schema_version':1,'repositories':entries},handle,indent=2);handle.write('\n')
        registry(temporary);os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return existing or entry


def scope_for(cwd, scopes):
    try:
        value=Path(cwd).resolve(strict=True)
        candidates=[s for s in scopes if value.is_relative_to(Path(s['cwd']))]
        if not candidates:return None
        selected=max(candidates,key=lambda s:len(s['cwd']))
        top,common=identity(value)
        if str(top)!=selected['cwd'] or str(common)!=selected['common_dir']:return None
        return selected
    except (OSError,ValueError):return None


def preflight(path, cache, cwd, profile=None):
    for entry in registry(path):
        records,scopes,approved=inspect(entry,cache)
        selected=scope_for(cwd,scopes)
        if not selected:continue
        record=records[selected['workspace_id']]
        enabled=strict_json(regular_read(approved/'baseline/policy/gates.yaml',approved))['enabled_profiles']
        reasons=list(record['issues'])
        if profile and profile not in enabled:reasons.append('PROFILE_AUTOMATION_UNAVAILABLE')
        return {'result':'blocked' if reasons else 'resolution_available','reasons':reasons,'workspace':record,
            'effective_policy_path':str(approved/'baseline/policy/engineering.md'),'approved_project_adapter':str(approved/'project.json'),
            'enabled_profiles':enabled,'permission_to_execute':False,'limitation':'Resolution/detection only; no protected launcher or merge/release authority.'}
    raise ResolutionError('WORKSPACE_NOT_IN_APPROVED_REGISTRY')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--registry',required=True);p.add_argument('--cache',required=True);p.add_argument('--workspace',required=True);p.add_argument('--profile',choices=['fix','enhancement','feature']);p.add_argument('--register',action='store_true')
    for name in ['repository','adoption-revision','policy-source-revision','manifest-sha256','policy-version']:p.add_argument('--'+name)
    p.add_argument('--repository-id',type=int);a=p.parse_args()
    try:
        if a.register:
            if not all([a.repository,a.repository_id,a.adoption_revision,a.policy_source_revision,a.manifest_sha256,a.policy_version]):raise ResolutionError('EXPLICIT_APPROVED_PIN_REQUIRED')
            register(a.registry,a.cache,a.workspace,a.repository,a.repository_id,a.adoption_revision,a.policy_source_revision,a.manifest_sha256,a.policy_version)
            r={'result':'registration_recorded','permission_to_execute':False,'limitation':'Operator declaration; not protected from the same user or agent.'}
        else:r=preflight(a.registry,a.cache,a.workspace,a.profile)
    except Exception:r={'result':'blocked','reasons':['REPOSITORY_RESOLUTION_UNAVAILABLE'],'permission_to_execute':False}
    print(json.dumps(r,indent=2));return 0 if r['result'] in ('resolution_available','registration_recorded') else 1


if __name__=='__main__':raise SystemExit(main())
