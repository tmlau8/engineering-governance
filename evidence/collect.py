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
from load_policy import load_observation_policy
from repository_policy import registry, inspect, ResolutionError


def workspace_context(runtime, config, store):
    """No fallback to whichever adapter happens to be in the current branch."""
    if config.get('repository_registry')!=str((runtime/'repositories.json').resolve()):raise ValueError('REGISTRY_CONFIGURATION_MISMATCH')
    entries=registry(runtime/'repositories.json');scopes=[];adapters={};missing=False;pending=[]
    for entry in entries:
        source='workspace:'+entry['repository']
        try:
            records,found,approved=inspect(entry,runtime/'approved-policy')
            scopes.extend(found)
            adapters[entry['repository']] = load_observation_policy(
                approved/'baseline/policy/gates.yaml', approved/'project.json')
            adapters[entry['repository']]['approved_source_revision'] = entry['policy_source_revision']
            pending.append((source,records))
            missing|=any('WORKSPACE_UNAVAILABLE' in r['issues'] for r in records.values())
        except ResolutionError as error:
            # Resolver exceptions carry fixed, bounded codes, never source text.
            store.failure(source,str(error));raise
        except Exception:
            store.failure(source,'WORKSPACE_DISCOVERY_UNAVAILABLE');raise
    if not adapters:raise ValueError('NO_APPROVED_REPOSITORIES')
    for source,records in pending:store.snapshot(source,records)
    store.snapshot('workspace:registry',{})
    registered={e['repository'] for e in entries}
    # Legacy workspace labels cannot establish repository identity. Keep their
    # old snapshots, visibly stale, until the operator explicitly registers them.
    if any(s['repository'] not in registered for s in config.get('usage_scopes', [])):
        store.failure('usage:scope-migration', 'UNVERIFIED_LEGACY_SCOPES_NOT_ATTRIBUTED')
    else:
        store.snapshot('usage:scope-migration', {})
    return adapters,scopes,missing


def run_once(runtime):
    runtime = Path(runtime)
    config = json.loads((runtime / "settings.json").read_text())
    store = Store(runtime / "data/evidence.sqlite")
    try:
        adapters,scopes,missing=workspace_context(runtime,config,store)
    except Exception:
        store.failure('workspace:registry','REPOSITORY_CONTEXT_UNAVAILABLE')
        store.failure('usage:codex','WORKSPACE_DISCOVERY_UNAVAILABLE')
        result=store.health();store.close();return result
    for repo in config["repositories"]:
        policy=adapters.get(repo)
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
        if missing:raise ValueError('WORKSPACE_UNAVAILABLE')
        usage = usage_collect(config["sessions_root"], scopes)
        if any(s['repository'] not in adapters for s in config.get('usage_scopes', [])):
            # Do not silently delete or relabel historical cumulative sessions.
            store.failure('usage:codex', 'USAGE_SCOPE_MIGRATION_REQUIRES_REVIEW')
        else:
            store.snapshot("usage:codex", usage)
    except (ValueError, TypeError, KeyError, OSError) as error:
        safe = {"USAGE_FILE_LIMIT", "USAGE_SCAN_LIMIT", "USAGE_EVENT_LIMIT", "USAGE_HEADER_INVALID", "USAGE_DISCOVERY_INCOMPLETE",'WORKSPACE_UNAVAILABLE','USAGE_SESSION_IDENTITY_CONFLICT'}
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
