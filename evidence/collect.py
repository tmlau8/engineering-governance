"""Reconcile authorised GitHub and local usage sources without writing upstream."""
import argparse
import json
from pathlib import Path
import sys
import threading
import time
from common import now
from github import API, APIError, adoption, collect as github_collect
from store import Store
from usage import collect as usage_collect

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tooling"))
from load_policy import load_policy


def run_once(runtime):
    runtime = Path(runtime)
    config = json.loads((runtime / "settings.json").read_text())
    store = Store(runtime / "data/evidence.sqlite")
    policy = load_policy(project_path=config["project_adapter"])
    for repo in config["repositories"]:
        api = API(repo)
        source = "github:" + repo
        try:
            store.snapshot(source, github_collect(api, repo, policy))
        except APIError as error:
            store.failure(source, str(error))
        except (ValueError, KeyError, TypeError, OSError):
            store.failure(source, "SOURCE_SCHEMA_ERROR")
        if repo == "tmlau8/my-ea":
            try:
                store.snapshot("adoption:" + repo, {repo: adoption(api, repo)})
            except APIError as error:
                store.failure("adoption:" + repo, str(error))
            except (ValueError, KeyError, TypeError, OSError):
                store.failure("adoption:" + repo, "SOURCE_SCHEMA_ERROR")
            try:
                api.get(f"repos/{repo}/branches/master/protection")
                # Existing protection alone does not prove the right rule/check/bypass boundary.
                record = {"repository": repo, "status": "configuration_observed_not_validated", "enforced": False}
            except APIError as error:
                record = {"repository": repo, "status": "unavailable_403" if str(error) == "GITHUB_403" else "unavailable", "enforced": False}
            store.snapshot("protection:" + repo, {repo: record})
    try:
        usage = usage_collect(config["sessions_root"], config["usage_scopes"])
        store.snapshot("usage:codex", usage)
    except (ValueError, TypeError, KeyError, OSError) as error:
        safe = {"USAGE_FILE_LIMIT", "USAGE_SCAN_LIMIT", "USAGE_EVENT_LIMIT", "USAGE_HEADER_INVALID", "USAGE_DISCOVERY_INCOMPLETE"}
        store.failure("usage:codex", str(error) if str(error) in safe else "LOCAL_USAGE_UNAVAILABLE")
    store.prune()
    result = store.health()
    store.close()
    return result


def loop(runtime, stop):
    while not stop.is_set():
        try:
            run_once(runtime)
        except Exception:
            # Never expose raw source paths/arguments/error bodies in daemon logs.
            try:
                store = Store(Path(runtime) / "data/evidence.sqlite")
                store.failure("collector", "COLLECTOR_ERROR")
                store.close()
            except Exception:
                pass
        stop.wait(300)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime", type=Path, default=ROOT / ".runtime")
    p.add_argument("--loop", action="store_true")
    args = p.parse_args()
    if args.loop:
        loop(args.runtime, threading.Event())
    else:
        try:
            print(json.dumps(run_once(args.runtime), indent=2))
        except Exception:
            print('{"error":"COLLECTOR_ERROR"}')
            raise SystemExit(1)
