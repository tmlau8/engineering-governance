"""Start/stop the local evidence/Grafana pilot. No global installation or config."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".runtime"
GRAFANA = RUNTIME / "software/grafana-13.3.0"


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".private-")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps(value, indent=2) + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def lifecycle(code):
    """No vendor/process output is retained; only fixed local lifecycle codes."""
    from common import now
    path = RUNTIME / "logs/lifecycle.log"
    for old in path.parent.glob("*.log*"):
        if old.stat().st_mtime < time.time() - 30 * 86400:
            old.unlink()
    if path.exists() and path.stat().st_size >= 1024 * 1024:
        path.replace(path.with_suffix(".log.1"))
    with path.open("a") as log:
        log.write(now() + " " + code + "\n")
    path.chmod(0o600)


def prepare(my_ea, workspace):
    os.umask(0o077)
    if RUNTIME.is_symlink():
        raise ValueError("RUNTIME_SYMLINK_FORBIDDEN")
    RUNTIME.mkdir(exist_ok=True, mode=0o700)
    RUNTIME.chmod(0o700)
    for folder in ["data", "logs", "secrets", "grafana/data", "software/plugins"]:
        (RUNTIME / folder).mkdir(parents=True, exist_ok=True, mode=0o700)
    credentials_file = RUNTIME / "secrets/credentials.json"
    if not credentials_file.exists():
        write_private(credentials_file, {"grafana_user": "albert", "grafana_password": secrets.token_urlsafe(24), "api_token": secrets.token_urlsafe(40), "grafana_secret_key": secrets.token_urlsafe(40)})
    credentials = json.loads(credentials_file.read_text())
    settings = {"repositories": ["tmlau8/my-ea", "tmlau8/engineering-governance"], "api_port": 8769, "grafana_port": 3001,
        'repository_registry':str(RUNTIME/'repositories.json'),
        "sessions_root": str(Path.home() / ".codex/sessions"),
        "usage_scopes": [{"cwd": str(Path(my_ea).resolve()), "repository": "tmlau8/my-ea"}, {"cwd": str(Path(workspace).resolve()), "repository": "tmlau8/engineering-governance"}]}
    write_private(RUNTIME / "settings.json", settings)
    spec = importlib.util.spec_from_file_location("dashboard_build", ROOT / "dashboard/build.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.provision(RUNTIME, credentials, settings["api_port"], settings["grafana_port"])
    from store import Store
    store = Store(RUNTIME / "data/evidence.sqlite"); store.close()
    write_private(RUNTIME / ".owned-runtime.json", {"project": str(ROOT), "schema_version": 1})
    return settings


def stop_children(children):
    for label, pid in children.items():
        if type(pid) is not int:
            raise ValueError("INVALID_OWNED_PID")
        snapshot = subprocess.run(["ps", "-ww", "-p", str(pid), "-o", "stat=", "-o", "command="], capture_output=True, text=True).stdout.strip()
        if not snapshot:
            continue
        state, _, command = snapshot.partition(' ')
        # Exited/unreaped children have lost their command path. Do not mistake
        # them for an unowned live process or try to signal an unrelated PID.
        if state.startswith('Z'):
            continue
        if str(ROOT) not in command or label not in ("api", "grafana", "collector"):
            raise ValueError("PID_OWNERSHIP_UNCONFIRMED")
        if os.getpgid(pid) != pid:
            raise ValueError("PROCESS_GROUP_OWNERSHIP_UNCONFIRMED")
        os.killpg(pid, signal.SIGTERM)
        for _ in range(30):
            state = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True).stdout.strip()
            if not state or state.startswith("Z"):
                break
            time.sleep(0.1)
        else:
            raise ValueError("OWNED_PROCESS_STILL_RUNNING")


def stop():
    path = RUNTIME / "processes.json"
    if not path.exists():
        return
    stop_children(json.loads(path.read_text()))
    path.unlink()
    lifecycle("SERVICES_STOPPED")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def service_ports(settings):
    ports=[settings.get('api_port'),settings.get('grafana_port')]
    if any(type(port) is not int or not 1<=port<=65535 for port in ports) or ports[0]==ports[1]:
        raise ValueError('INVALID_LOCAL_SERVICE_PORTS')
    return ports


def require_free_ports(settings):
    # Reject an existing listener before spawning or sending any credentials.
    for port in service_ports(settings):
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                probe.bind(('127.0.0.1',port));probe.listen(1)
        except OSError:raise ValueError('LOCAL_SERVICE_PORT_UNAVAILABLE') from None


def services_ready(settings, credentials, deadline=None):
    """Check actual loopback service readiness without leaking auth to proxies."""
    ports=service_ports(settings)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    basic=base64.b64encode((credentials['grafana_user']+':'+credentials['grafana_password']).encode()).decode()
    def read(port,path,authorization=None):
        remaining=1 if deadline is None else min(1,deadline-time.monotonic())
        if remaining<=0:return None
        headers={'Authorization':authorization} if authorization else {}
        # Grafana enforces its configured localhost domain. Keep the transport
        # pinned to 127.0.0.1, and supply the expected Host without following redirects.
        if port==ports[1]:headers['Host']='localhost:'+str(port)
        request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,headers=headers)
        with opener.open(request,timeout=remaining) as response:
            raw=bytearray()
            while len(raw)<=1024*1024:
                if deadline is not None and time.monotonic()>=deadline:return None
                chunk=response.read1(min(65536,1024*1024-len(raw)+1))
                if not chunk:break
                raw.extend(chunk)
            if response.status!=200 or len(raw)>1024*1024:return None
            return json.loads(raw)
    try:
        health=read(ports[1],'/api/health')
        if not isinstance(health,dict) or health.get('database')!='ok':return False
        overview=read(ports[0],'/api/overview','Bearer '+credentials['api_token'])
        if not isinstance(overview,list) or not overview or not isinstance(overview[0],dict) or 'Snapshot' not in overview[0]:return False
        dashboard=read(ports[1],'/api/dashboards/uid/agentic-engineering-evidence','Basic '+basic)
        return isinstance(dashboard,dict) and isinstance(dashboard.get('dashboard'),dict) and dashboard['dashboard'].get('uid')=='agentic-engineering-evidence'
    except (OSError,ValueError,urllib.error.URLError):
        # Never put response bodies, auth headers or raw vendor errors in logs.
        return False


def wait_ready(settings, processes, credentials, timeout=45):
    deadline=time.monotonic()+timeout
    while True:
        if any(child.poll() is not None for child in processes):
            raise ValueError('SERVICE_EXITED_BEFORE_READY')
        if services_ready(settings,credentials,deadline=deadline):
            if any(child.poll() is not None for child in processes):
                raise ValueError('SERVICE_EXITED_BEFORE_READY')
            return
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ValueError('SERVICE_START_TIMEOUT')
        time.sleep(min(.25,remaining))


def start():
    os.umask(0o077)
    if (RUNTIME / "processes.json").exists():
        raise ValueError("ALREADY_STARTED_USE_STOP_FIRST")
    if not (GRAFANA / "bin/grafana").is_file():
        raise ValueError("INSTALL_PINNED_GRAFANA_FIRST")
    settings = json.loads((RUNTIME / "settings.json").read_text())
    require_free_ports(settings)
    # Only allowlisted subprocesses receive authentication context; Grafana gets no GH token.
    grafana_env = {k: v for k, v in os.environ.items() if not any(x in k.upper() for x in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))}
    api_env = dict(grafana_env, PYTHONDONTWRITEBYTECODE="1")
    collector_env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    children = {}
    write_private(RUNTIME / "processes.json", children)
    try:
        commands = [
            ("collector", "collector.log", [sys.executable, "-B", str(ROOT / "evidence/collect.py"), "--runtime", str(RUNTIME), "--loop"], collector_env),
            ("api", "evidence.log", [sys.executable, "-B", str(ROOT / "evidence/server.py"), "--runtime", str(RUNTIME)], api_env),
            ("grafana", "grafana-process.log", [str(GRAFANA / "bin/grafana"), "server", "--homepath", str(GRAFANA), "--config", str(RUNTIME / "grafana.ini")], grafana_env),
        ]
        processes = []
        for label, logfile, command, env in commands:
            child = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, start_new_session=True)
            children[label] = child.pid
            processes.append(child)
            write_private(RUNTIME / "processes.json", children)
        credentials=json.loads((RUNTIME/'secrets/credentials.json').read_text())
        wait_ready(settings,processes,credentials)
    except BaseException:
        # In-memory ownership includes a child even if its journal write failed.
        try:
            stop_children(children)
        except BaseException:
            write_private(RUNTIME / "processes.json", children)
            raise
        (RUNTIME / "processes.json").unlink(missing_ok=True)
        raise
    lifecycle("SERVICES_STARTED")
    print(f"Dashboard: http://localhost:{settings['grafana_port']}/d/agentic-engineering-evidence")
    print("Login credentials are in the owner-only .runtime/secrets/credentials.json; not printed or published.")


def purge(full=False):
    marker = RUNTIME / ".owned-runtime.json"
    if RUNTIME.is_symlink() or not marker.exists() or json.loads(marker.read_text()).get("project") != str(ROOT):
        raise ValueError("RUNTIME_OWNERSHIP_UNCONFIRMED")
    stop()
    time.sleep(1)
    targets = ["data", "logs", "grafana", "provisioning", "dashboards", "secrets", "settings.json", "grafana.ini", "processes.json", ".owned-runtime.json", "software/grafana-13.3.0/data",'repositories.json','approved-policy']
    if full:
        targets.append("software")
    for name in targets:
        path = RUNTIME / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
    if any((RUNTIME / name).exists() for name in targets):
        raise ValueError("OWNED_DATA_REMAINS")
    print("Owned evidence, sidecars, logs, Grafana state/config and credentials removed. Upstream records are unchanged; physical erasure is not asserted.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "start", "stop", "purge"])
    p.add_argument("--my-ea", type=Path)
    p.add_argument("--workspace", type=Path)
    p.add_argument("--full", action="store_true")
    args = p.parse_args()
    if args.action == "prepare":
        if args.my_ea is None or args.workspace is None:
            p.error("prepare needs explicit --my-ea and --workspace scopes")
        prepare(args.my_ea, args.workspace)
    elif args.action == "start": start()
    elif args.action == "stop": stop()
    elif args.action == "purge": purge(args.full)
