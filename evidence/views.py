"""Read-only dashboard projections. Missing evidence never becomes compliance."""
import datetime as dt
import json
import collections
from pathlib import Path
from common import UTC, now, seconds
from common import github_url
from usage import interval_union, FIELDS

ROOT = Path(__file__).resolve().parent.parent


def rows(store, kind, repo="all"):
    return [r["data"] for r in store.records(kind) if repo == "all" or r["data"].get("repository") == repo]


def changes(store, repo):
    result = []
    for r in rows(store, "github:", repo):
        checks = r["checks"]
        result.append({"Repository": r["repository"], "Change": r["id"], "State": r["state"],
            "Profile": r["profile"], "Risk": r["risk"], "Triggers": ", ".join(r["triggers"]) or "No path trigger; semantic risk unverified",
            "Planning metadata": r["metadata_gate"], "Successful checks": sum(c["conclusion"] == "success" for c in checks),
            "Failed checks": sum(c["conclusion"] not in ("success", "pending", "neutral", "skipped") for c in checks),
            "Pending checks": sum(c["conclusion"] == "pending" for c in checks), "Current approvals": r["current_approvals"],
            "Checks": f"{sum(c['conclusion'] == 'success' for c in checks)} success / {sum(c['conclusion'] == 'pending' for c in checks)} pending / {sum(c['conclusion'] not in ('success', 'pending', 'neutral', 'skipped') for c in checks)} failed",
            "Independent review": r["independent_review"], "Policy at original decision": r["policy_at_change"],
            "Revision": r["head_sha"][:12], "PR evidence": r["url"], "Exact revision": r["revision_url"], "Updated": r["updated_at"]})
        result[-1]['Detector adapter scope']=r.get('detector_adapter_repository','unknown')
        result[-1]['Observation policy']=r.get('evaluated_policy_version','unknown')
        result[-1]['Evaluation scope']=r.get('policy_evaluation_scope','unknown')
    return result


def rule_coverage(store, repo):
    catalogue = json.loads((ROOT / "policy/requirements.json").read_text())["rules"]
    coverage = {r["id"]: r for r in json.loads((ROOT / "policy/control-coverage.json").read_text())["requirements"]}
    records = rows(store, "github:", repo)
    adopted = rows(store, "adoption:", repo)
    result = []
    for rule in catalogue:
        code = rule["id"]
        observed = 0
        note = "No semantic evidence collected; requirement remains mandatory when applicable"
        if code == "CODE-019":
            observed = sum(r["metadata_gate"] == "metadata_conforming" for r in records)
            note = "Planning metadata only; does not prove spec preceded implementation or is adequate"
        elif code == "CODE-020":
            observed = sum(r["state"] == "merged" for r in records)
            note = "GitHub merge observed; chat authorisation, physical human and independent review not inferred"
        elif code == "CODE-031":
            observed = sum(any(c["name"] == "reference-integrity" and c["conclusion"] == "success" for c in r["checks"]) for r in records)
            note = "CI check metadata only; no protected-producer or whole-document semantic certification"
        applicability = "conditional" if rule["applicability"] not in ("engineering_baseline", "agent_workflow_baseline") else "applicable"
        if code == "CODE-035":
            applicability = "N/A for single-user My EA; conditional for role-based projects"
        if adopted:
            applicability = adopted[0].get("applicability", {}).get(code, "not_in_recorded_adoption")
        result.append({"Rule": code, "Requirement": rule["title"], "Applicability": applicability,
            "Automation": coverage[code]["status"], "Observed subset": observed,
            "Changes inspected": len(records), "Semantic assurance": "unknown", "Enforced": "not demonstrated", "Evidence limit": note,
            "Project mechanism map": adopted[0].get("mechanism_map_url") if adopted else None})
    return result


def sessions(store, repo):
    result = []
    for r in rows(store, "usage:", repo):
        result.append({"Repository scope": r["repository"], "Session": r["session"], "Parent session": r["parent_session"] or "main",
            "Tool": r["tool"], "Agent role": r.get("agent_role", "unknown"), "Model": r["model"], "PR link": "unlinked",
            "Input tokens": r["input_tokens"], "Cached input (subset)": r["cached_input_tokens"], "Uncached input": r["uncached_input_tokens"],
            "Output tokens": r["output_tokens"], "Reasoning (subset)": r["reasoning_output_tokens"], "Total tokens": r["total_tokens"],
            "Accounting": r["usage_quality"], "Exact rollup eligible": r["included_in_exact_rollup"],
            "Reported turn seconds": r["reported_turn_seconds"], "Observed turn seconds (sum)": r["observed_turn_seconds"],
            "Turn interval seconds (union)": r["turn_interval_union_seconds"], "Session elapsed seconds": r["session_elapsed_seconds"],
            "Complete turns": r["completed_turns"], "Aborted turns": r["aborted_turns"], "Open turns": r["open_turns"],
            "Last source event": r["last_event_at"], "Association": r["association"], "Coverage": "local structured fallback; not billing or complete audit"})
    return result


def decisions(store, repo):
    result = []
    for r in rows(store, "github:", repo):
        result.append({"Repository": r["repository"], "Change": r["id"], "State": r["state"],
            "Current approvals": r["current_approvals"], "Merge actor (account)": r["merge_actor"] or "not merged",
            "Exception": r["exception_state"], "Independent review": "unknown; inspect artifacts",
            "Device evidence": r["device_evidence"], "Release evidence": r["release_evidence"], "Outcome evidence": r["outcome_evidence"],
            "Evidence": r["url"], "Merge observation": r["merge_evidence"]})
    return result


def health(store, repo):
    result = []
    at = now()
    for r in store.health():
        if repo != "all" and ":" in r["source"] and r["source"].split(":", 1)[1] not in (repo, "codex",'registry','scope-migration','local'):
            continue
        age = seconds(r["succeeded_at"], at)
        freshness="never succeeded" if age is None else "stale" if age > 900 else "fresh snapshot"
        if r['status']=='error' and age is not None:
            freshness=('stale' if age>900 else 'recent')+' last-good; latest attempt failed'
        result.append({"Source": r["source"], "Status": r["status"], "Last attempt": r["attempted_at"], "Last success": r["succeeded_at"],
            "Age seconds": age, "Freshness": freshness,
            "Error code": r["error_code"] or "none", "Rows": r["row_count"]})
    return result or [{"Source": "collector", "Status": "not_collected", "Freshness": "unknown", "Error code": "NO_SUCCESSFUL_COLLECTION", "Rows": None}]


def workspaces(store,repo):
    source_health={r['Source']:r for r in health(store,repo)}
    registry_health=source_health.get('workspace:registry',{})
    result=[]
    for record in store.records('workspace:'):
        r=record['data']
        if repo!='all' and r['repository']!=repo:continue
        h=source_health.get(record['source'],{})
        failure=h if h.get('Status')=='error' else registry_health if registry_health.get('Status')=='error' else None
        issues=list(r['issues'])
        if failure:issues.append('Latest inventory rejected: '+failure.get('Error code','unknown'))
        result.append({'Repository':r['repository'],'Workspace':r['workspace'],'Branch':r['branch'],
            'Effective approved policy':'unknown_latest_inventory_failed' if failure else r['effective_policy_version'],
            'Last-known policy':r['effective_policy_version'],
            'Local files':'unknown_latest_inventory_failed' if failure else r['local_status'],
            'Last-known local files':r['local_status'],
            'Issues':', '.join(issues) or 'No local file mismatch observed',
            'Instructions actually loaded':r['instruction_loading'],'Mandatory startup boundary':r['startup_enforcement'],
            'Merge boundary':r['merge_enforcement'],'Registry custody':r['registry_custody'],
            'Inventory status':'error' if failure else h.get('Status','unknown'),
            'Freshness':failure.get('Freshness','last-good; latest attempt failed') if failure else h.get('Freshness','unknown'),
            'Last observed':record['last_seen'],'Workspace ID':r['workspace_id'],'Revision':r['head_sha']})
    return result


def overview(store, repo):
    changes_ = rows(store, "github:", repo)
    usage_ = rows(store, "usage:", repo)
    adoption = rows(store, "adoption:", repo)
    protection = rows(store, "protection:", repo)
    inventory=rows(store,'workspace:',repo)
    registry_error=any(r['Source']=='workspace:registry' and r['Status']=='error' for r in health(store,repo))
    inventory_health=[r for r in health(store,repo) if r['Source'].startswith('workspace:') and r['Source']!='workspace:registry']
    inventory_status='error' if registry_error else 'not_registered_or_not_collected' if not inventory_health else 'error' if any(r['Status']=='error' for r in inventory_health) else 'stale' if any(r['Freshness']=='stale' for r in inventory_health) else 'inventory_observed_not_launch_enforcement'
    exact = [r for r in usage_ if r["included_in_exact_rollup"]]
    reported_times = [r["reported_turn_seconds"] for r in usage_ if r["reported_turn_seconds"] is not None]
    github_observed = any(r["source"].startswith("github:") and r["succeeded_at"] and (repo == "all" or r["source"] == "github:" + repo) for r in store.health())
    planning_unknown = sum(r['metadata_gate'].startswith('not_evaluated') for r in changes_)
    return [{"Changes inspected": len(changes_) if github_observed else None, "Open changes": sum(r["state"] == "open" for r in changes_) if github_observed else None,
        "Missing planning metadata": sum(r["metadata_gate"] != "metadata_conforming" for r in changes_) if github_observed and not planning_unknown else None,
        "Planning metadata not evaluated": planning_unknown if github_observed else None,
        "Candidate catalogue version": json.loads((ROOT / "policy/gates.yaml").read_text())["version"],
        "Policy version": adoption[0]["policy_version"] if adoption else "not observed for selected repository",
        "Policy commit": adoption[0]["policy_commit"] if adoption else None,
        "Native merge boundary": protection[0]["status"] if protection else "not observed",
        "Enforced requirements": 0, "Requirements in catalogue": len(json.loads((ROOT / "policy/requirements.json").read_text())["rules"]),
        'Registered workspaces discovered':len(inventory) if inventory_health else None,
        'Workspaces with local policy gaps':sum(r['local_status']=='attention_required' for r in inventory) if inventory_health else None,
        'Workspace inventory status':inventory_status,'Mandatory startup enforcement':'not_installed',
        "Usage sessions": len(usage_), "Reported token sum (eligible sessions)": sum(r["total_tokens"] for r in exact) if exact else None,
        "Sessions with reported time": len(reported_times),
        "Sessions excluded from exact sum": len(usage_) - len(exact), "PR-linked usage sessions": 0,
        "Reported turn seconds (sum; overlaps)": sum(reported_times) if reported_times else None,
        "Cost": "not measured; subscription tokens are not a bill", "Snapshot": "observations and gaps; no whole-change compliance score"}]


def summary(store, repo):
    value = overview(store, repo)[0]
    fields = ["Candidate catalogue version", "Policy version", "Policy commit",'Registered workspaces discovered','Workspaces with local policy gaps','Workspace inventory status','Mandatory startup enforcement', "Native merge boundary", "Enforced requirements", "Changes inspected", "Usage sessions", "Sessions excluded from exact sum", "Sessions with reported time", "PR-linked usage sessions", "Cost"]
    return [{"Measure": key, "Observation": str(value[key]) if value[key] is not None else "Unknown / not collected"} for key in fields]


def activities(store,repo):
    result=[]
    for r in sorted(rows(store,'activity:',repo),key=lambda r:r['began_at']):
        m=r['metadata'];u=r['tokens'] or {};a=r['begin'] or {};b=r['end'] or {}
        result.append({'Repository':r['repository'],'Task':m['task'],'Activity':r['id'],
            'Phase':m['phase'],'Round':m['round'],'Agent role':m['role'],'Session':r['session'],
            'Model':r['model'],'State':'open' if not r['ended_at'] else r['outcome'],
            'Total tokens':u.get('total_tokens'),'Input tokens':u.get('input_tokens'),
            'Cached input (subset)':u.get('cached_input_tokens'),'Output tokens':u.get('output_tokens'),
            'Reasoning (subset)':u.get('reasoning_output_tokens'),
            'Marker elapsed seconds':r['elapsed_seconds'],'Measurement':r['measurement_basis'],
            'Eligible subtotal':r['eligible'],'Gaps':', '.join(r['flags']) or 'Boundary observations; semantic timing unverified',
            'Findings':', '.join(dict.fromkeys(m['findings']+r['outcome_findings'])),
            'Review record':m['review_record'],'Reviewed revision':m['revision'],
            'Evidence':github_url(r['repository'],('/pull/'+str(m['pr'])) if m['pr'] else ('/commit/'+m['revision']) if m['revision'] else ''),
            'Began':r['began_at'],'Ended':r['ended_at'],'Begin snapshot':a.get('event_at'),
            'Begin observation':a.get('captured_at'),'End observation':b.get('captured_at'),
            'End snapshot':b.get('event_at'),'Begin lag seconds':a.get('lag_seconds'),
            'End lag seconds':b.get('lag_seconds'),'Attribution':r['association'],
            'Telemetry model calls':r['instrumentation_model_calls']})
    return result


def activity_totals(store,repo,by_round=False):
    grouped=collections.defaultdict(list)
    for r in rows(store,'activity:',repo):
        m=r['metadata'];key=(r['repository'],m['task'],m['phase'],m['round']) if by_round else (r['repository'],m['task'])
        grouped[key].append(r)
    result=[]
    for key,group in sorted(grouped.items()):
        eligible=[r for r in group if r['eligible']]; intervals=[]
        for r in group:
            if r['ended_at']:
                intervals.append(tuple(dt.datetime.fromisoformat(r[k].replace('Z','+00:00')).timestamp() for k in ['began_at','ended_at']))
        result.append({'Repository':key[0],'Task':key[1],
            'Phase':key[2] if by_round else 'all recorded phases','Round':key[3] if by_round else 'all',
            'Eligible activities':len(eligible),'Recorded activities':len(group),
            'Excluded or open':len(group)-len(eligible),
            'Observed token subtotal':sum(r['tokens']['total_tokens'] for r in eligible) if eligible else None,
            'Marker seconds (sum)':sum(r['elapsed_seconds'] for r in group if r['elapsed_seconds'] is not None) if intervals else None,
            'Marker seconds (union)':interval_union(intervals) if intervals else None,
            'Coverage':'Recorded activities only; historical/uninstrumented work unknown; separate from session totals',
            'Telemetry model calls':0})
    return result


def dispatch(store, view, repo):
    handlers = {"overview": overview, "summary": summary,'workspaces':workspaces, "changes": changes, "rules": rule_coverage, "sessions": sessions, "decisions": decisions, "health": health,
        'activities':activities,'activity-tasks':activity_totals,'activity-rounds':lambda s,r:activity_totals(s,r,True)}
    if view == "history":
        return store.history()
    if view == "attempts":
        return store.attempts()
    return handlers[view](store, repo)
