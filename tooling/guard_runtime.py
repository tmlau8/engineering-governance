"""Native command-boundary verification. This does not activate Desktop governance.

All test material is synthetic. No model request, project mutation, real secret
read, credential change or approval is performed by this command.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time

MAX_ENTRIES = 100000
DISABLED_FEATURES = (
    'apps', 'browser_use', 'browser_use_external', 'computer_use', 'plugins',
    'remote_plugin', 'hooks', 'shell_snapshot', 'image_generation', 'view_image',
)


def toml(value):
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k) + '=' + toml(v) for k, v in value.items()) + '}'
    if type(value) is bool:
        return 'true' if value else 'false'
    if isinstance(value, (str, int)):
        return json.dumps(value)
    raise ValueError('UNSUPPORTED_PROFILE_VALUE')


def safe_tree(root):
    """Reject pre-existing inode aliases, not merely path traversal.

    This is an entry-time check, not a lock against concurrent owner changes.
    Git metadata is excluded from source traversal and denied in the profile.
    """
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('UNSAFE_WORKSPACE_ROOT')
    count = 0
    for folder, directories, files in os.walk(root, followlinks=False):
        if Path(folder) == root:
            directories[:] = [n for n in directories if n != '.git']
            files = [n for n in files if n != '.git']
        for name in directories + files:
            count += 1
            if count > MAX_ENTRIES:
                raise ValueError('WORKSPACE_ENTRY_LIMIT')
            info = (Path(folder) / name).lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ValueError('WORKSPACE_SYMLINK')
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError('WORKSPACE_SPECIAL_FILE')
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise ValueError('WORKSPACE_HARDLINK')
    return count


def profile(workspace, writable=(), runtime_reads=()):
    root = Path(workspace).resolve(strict=True)
    fs = {':root': 'deny', ':minimal': 'read', ':tmpdir': 'deny', ':slash_tmp': 'deny',
          ':workspace_roots': {'.': 'read'}, str(root): 'read'}
    for path in runtime_reads:
        fs[str(Path(path).resolve(strict=True))] = 'read'
    for relative in writable:
        candidate = Path(relative)
        if candidate.is_absolute() or not candidate.parts or any(p in ('.', '..') for p in candidate.parts):
            raise ValueError('INVALID_WRITE_PATH')
        if candidate.parts[0] in ('.git', '.codex', '.agents', '.aws', '.governance', '.github'):
            raise ValueError('PROTECTED_WRITE_PATH')
        destination = root / candidate
        if destination.is_symlink() or not destination.is_file() or destination.stat().st_nlink != 1:
            raise ValueError('WRITE_PATH_NOT_SINGLE_REGULAR_FILE')
        fs[str(destination)] = 'write'
    # These more-specific entries override the target's general read access.
    for name in ('.git', '.codex', '.agents', '.aws', '.governance', '.env', '.env.local'):
        fs[str(root / name)] = 'deny'
    return {'extends': ':read-only', 'filesystem': fs, 'network': {'enabled': False}}


def clean_environment():
    # Never inherit GH/GITHUB tokens, proxy configuration, SSH agent sockets,
    # shell startup controls, DYLD/LD variables or Git overrides.
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'HOME': '/var/empty'}


def native_command(executable, workspace, permissions, command):
    return [str(executable), 'sandbox', '-C', str(workspace),
            '-c', 'permissions=' + toml({'governance-probe': permissions}),
            '--permission-profile', 'governance-probe', '--', *map(str, command)]


def run(command, timeout=8):
    # Child output is bounded by a file-size cap, discarded after inspection,
    # and never written to a governance report. No owner descriptors are inherited.
    import resource
    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (65536, 65536))
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        child = subprocess.Popen(command, stdout=out, stderr=err,
            stdin=subprocess.DEVNULL, env=clean_environment(), close_fds=True,
            start_new_session=True, preexec_fn=limits)
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL); child.wait()
            raise ValueError('NATIVE_PROBE_TIMEOUT') from None
        out.seek(0); err.seek(0)
        return code, out.read(65536), err.read(65536)


def verify(executable):
    if sys.platform != 'darwin':
        raise ValueError('UNVERIFIED_PLATFORM')
    executable = Path(executable).resolve(strict=True)
    if not executable.is_file():
        raise ValueError('CODEX_EXECUTABLE_UNAVAILABLE')
    version = run([str(executable), '--version'])[1].decode().strip()
    before = hashlib.sha256(executable.read_bytes()).hexdigest()
    checks = {}
    with tempfile.TemporaryDirectory(prefix='governance-boundary-') as temporary:
        base = Path(temporary).resolve(); worker = base / 'worker'; worker.mkdir()
        allowed = worker / 'allowed'; allowed.write_text('before')
        readonly = worker / 'readonly'; readonly.write_text('unchanged')
        foreign = base / 'foreign'; foreign.write_text('SYNTHETIC_CANARY')
        (worker / '.aws').mkdir(); secret = worker / '.aws' / 'canary'; secret.write_text('SYNTHETIC_NESTED')
        xcode = Path('/Applications/Xcode.app/Contents/Developer')
        python = xcode / 'usr/bin/python3'
        if not python.is_file():
            raise ValueError('VERIFIED_PROBE_RUNTIME_UNAVAILABLE')
        read = profile(worker, runtime_reads=[xcode])
        write = profile(worker, ['allowed'], [xcode])
        def probe(name, permissions, command, expected=0, forbidden=None):
            code, out, err = run(native_command(executable, worker, permissions, command))
            checks[name] = code == expected if expected == 0 else code != 0
            if forbidden is not None:
                checks[name] &= forbidden not in out + err
            return code, out, err
        probe('positive_read', read, ['/bin/cat', readonly])
        probe('read_mode_write_denied', read, ['/bin/sh', '-c', 'echo BAD > allowed'], 1)
        checks['read_mode_unchanged'] = allowed.read_text() == 'before'
        probe('foreign_read_denied', write, ['/bin/cat', foreign], 1, b'SYNTHETIC_CANARY')
        probe('nested_secret_denied', write, ['/bin/cat', secret], 1, b'SYNTHETIC_NESTED')
        probe('positive_scoped_write', write, ['/bin/sh', '-c', 'echo PERMITTED > allowed'])
        new_file=worker/'new-planned-file';new_permissions=profile(worker,runtime_reads=[xcode]);new_permissions['filesystem'][str(new_file)]='write'
        probe('new_exact_file_creation',new_permissions,['/bin/sh','-c','echo NEW > new-planned-file'])
        checks['new_file_effect']=new_file.exists() and new_file.read_text().strip()=='NEW'
        probe('unplanned_new_file_denied',new_permissions,['/bin/sh','-c','echo BAD > unplanned-file'],1)
        checks['unplanned_file_absent']=not (worker/'unplanned-file').exists()
        checks['scoped_write_effect'] = allowed.read_text().strip() == 'PERMITTED'
        script = ('import os,socket,subprocess,sys;'
                  'p=sys.argv[1];os.unlink(p);open(p,"w").write("PYTHON_READY");'
                  'assert open(p).read()=="PYTHON_READY";'
                  'assert subprocess.run(["/usr/bin/true"]).returncode==0')
        probe('positive_sandboxed_python_runtime', write, [python, '-c', script, allowed])
        checks['sandboxed_python_effect'] = allowed.read_text() == 'PYTHON_READY'
        probe('adjacent_write_denied', write, ['/bin/sh', '-c', 'echo BAD > readonly'], 1)
        checks['adjacent_unchanged'] = readonly.read_text() == 'unchanged'
        probe('foreign_write_denied', write, ['/usr/bin/touch', foreign], 1)
        allowed.unlink(); allowed.symlink_to(foreign)
        probe('symlink_write_denied', write, ['/bin/sh', '-c', 'echo BAD > allowed'], 1)
        allowed.unlink(); allowed.write_text('PERMITTED')
        # A pre-existing hardlink is a known bypass: the scanner must reject it.
        alias = worker / 'preexisting-link'; os.link(foreign, alias)
        try: safe_tree(worker); checks['hardlink_preflight_rejected'] = False
        except ValueError as error: checks['hardlink_preflight_rejected'] = str(error) == 'WORKSPACE_HARDLINK'
        alias.unlink()
        # Verify both link creation and subsequent reads/writes, using exact paths
        # in a synthetic subprocess, without touching any real credential.
        for name, source in [('foreign', foreign), ('readonly', readonly)]:
            script = 'import os,sys;os.unlink(sys.argv[2]);os.link(sys.argv[1],sys.argv[2]);open(sys.argv[2],"w").write("BAD")'
            probe('dynamic_' + name + '_hardlink_denied', write,
                  [python, '-c', script, source, allowed], 1)
            checks[name + '_source_unchanged'] = source.read_text() == ('SYNTHETIC_CANARY' if name == 'foreign' else 'unchanged')
            if not allowed.exists(): allowed.write_text('PERMITTED')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen(1)
            port = listener.getsockname()[1]
            script = ('import socket,sys\ntry: socket.create_connection(("127.0.0.1",'+str(port)+'),timeout=2)'
                      '\nexcept PermissionError as e: print("CONNECT_DENIED",e.errno);sys.exit(1)')
            # Positive control uses exactly the same transport and live listener.
            checks['positive_loopback'] = run([python, '-c', script])[0] == 0
            code, out, err = probe('loopback_denied', write, [python, '-c', script], 1)
            checks['loopback_permission_denial'] = out.strip() in (b'CONNECT_DENIED 1', b'CONNECT_DENIED 13')
        # PermissionError establishes a kernel denial, independent of internet availability.
        script = ('import socket,sys;s=socket.socket();s.settimeout(2)\n'
                  'try: s.connect(("1.1.1.1",443))\n'
                  'except PermissionError as e: print("CONNECT_DENIED",e.errno);sys.exit(1)')
        code, out, err = probe('external_network_denied', write, [python, '-c', script], 1)
        checks['external_permission_denial'] = out.strip() in (b'CONNECT_DENIED 1', b'CONNECT_DENIED 13')
        sleeper = subprocess.Popen(['/bin/sleep', '20'], env=clean_environment(), close_fds=True)
        try: probe('foreign_signal_denied', write, ['/bin/kill', '-STOP', str(sleeper.pid)], 1)
        finally:
            sleeper.send_signal(signal.SIGCONT); sleeper.terminate(); sleeper.wait(timeout=5)
        script = 'import subprocess,sys;p=subprocess.Popen(["/usr/bin/touch",sys.argv[1]],start_new_session=True);sys.exit(p.wait())'
        target = base / 'detached-target'
        probe('detached_child_write_denied', write, [python, '-c', script, target], 1)
        checks['detached_target_absent'] = not target.exists()
        checks['foreign_content_preserved'] = foreign.read_text() == 'SYNTHETIC_CANARY'
    checks['executable_unchanged'] = before == hashlib.sha256(executable.read_bytes()).hexdigest()
    return {'schema_version': 1, 'kind': 'synthetic_native_command_boundary',
            'codex_version': version, 'executable_sha256': before,
            'result': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
            'implementation_authorized': False,
            'limitations': ['not_a_client_tool_inventory_or_frontend_certificate',
                            'not_a_task_approval_or_project_adoption',
                            'unmanaged_desktop_and_github_owner_actions_uncovered']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', default=shutil.which('codex'))
    args = parser.parse_args()
    try: result = verify(args.codex)
    except (OSError, ValueError, subprocess.SubprocessError, TypeError):
        result = {'result': 'failed', 'error': 'NATIVE_BOUNDARY_VERIFICATION_UNAVAILABLE',
                  'implementation_authorized': False}
    print(json.dumps(result, indent=2))
    return 0 if result['result'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
