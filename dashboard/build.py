"""Provision standard Grafana panels; no secret is embedded in dashboard JSON."""
import json
from pathlib import Path

UID = "agentic-engineering-evidence"
DS = {"type": "yesoreyeram-infinity-datasource", "uid": "governance-evidence"}
COLUMNS = {
    'execution':['Task','Gate','Required action'],
    'activities':['Task','Phase','Round','Agent role','Model','State','Total tokens','Marker elapsed seconds','Measurement','Agent scope','Gaps','Findings','Activity'],
    'activity-tasks':['Task','Observed token subtotal','Eligible activities','Recorded activities','Excluded or open','Marker seconds (sum)','Marker seconds (union)','Coverage'],
    'activity-rounds':['Task','Phase','Round','Observed token subtotal','Eligible activities','Recorded activities','Excluded or open','Marker seconds (sum)','Marker seconds (union)'],
    'workspaces':['Workspace','Branch','Effective approved policy','Local files','Issues','Inventory status','Freshness'],
    "summary": ["Measure", "Observation"],
    "changes": ["Change", "State", "Profile", "Risk", "Planning metadata", "Checks", "PR evidence"],
    "rules": ["Rule", "Requirement", "Applicability", "Automation", "Semantic assurance", "Evidence limit"],
    "decisions": ["Change", "Current approvals", "Exception", "Independent review", "Device evidence", "Release evidence", "Outcome evidence", "Evidence"],
    "sessions": ["Agent role", "Model", "Session", "Total tokens", "Cached input (subset)", "Output tokens", "Reported turn seconds", "Open turns", "Accounting", "Repository scope"],
    "health": ["Source", "Status", "Freshness", "Age seconds", "Error code", "Last success", "Last attempt"],
}


def query(view, port):
    return {"refId": "A", "type": "json", "source": "url", "format": "table", "parser": "backend", "root_selector": "", "url": f"http://127.0.0.1:{port}/api/{view}?repo=${{repo:percentencode}}", "url_options": {"method": "GET"}, "columns": []}


def dashboard(api_port=8769, repositories=None):
    repositories=list(dict.fromkeys(['all',*(repositories or ['tmlau8/my-ea','tmlau8/engineering-governance'])]))
    panels = []
    def text(title, body, y, h=3):
        panels.append({"id": len(panels)+1, "type": "text", "title": title, "gridPos": {"x": 0, "y": y, "w": 24, "h": h}, "options": {"mode": "markdown", "content": body}})
    def table(title, view, y, h=9, description="", detailed=False):
        panels.append({"id": len(panels)+1, "type": "table", "title": title, "description": description, "datasource": DS, "gridPos": {"x": 0, "y": y, "w": 24, "h": h}, "targets": [query(view, api_port)], "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
            "fieldConfig": {"defaults": {"custom": {"align": "auto", "filterable": True, "cellOptions": {"type": "auto"}}, "noValue": "Unknown / not collected"}, "overrides": [
                {"matcher": {"id": "byName", "options": name}, "properties": [{"id": "links", "value": [{"title": "Open source evidence", "url": "${__value.raw}", "targetBlank": True}]}]} for name in ["PR evidence", "Exact revision", "Evidence"]]}})
        if view in COLUMNS and not detailed:
            names = COLUMNS[view]
            panels[-1]["transformations"] = [{"id": "filterFieldsByName", "options": {"include": {"names": names}}}, {"id": "organize", "options": {"indexByName": {name: i for i, name in enumerate(names)}}}]
        panels[-1]["fieldConfig"]["defaults"]["custom"]["minWidth"] = 110
        if view == "summary":
            panels[-1]["fieldConfig"]["overrides"].append({"matcher": {"id": "byName", "options": "Measure"}, "properties": [{"id": "custom.width", "value": 290}]})
    text("Engineering governance · local pilot", "**Observed evidence and visible gaps.** All applicable policy remains mandatory; **0 requirements are claimed fully enforced**. Native Desktop startup and GitHub merge boundaries are not established. Guarded CLI task permissions use a separate explicit route shown below. ¹ Unevaluated planning is Unknown, not a retrospective violation. ² Session repository attribution uses registered Git identity; activity task/phase links are **explicitly declared**. Activity subtotals and cumulative session totals are separate measures. Scope errors retain last-known snapshots. Tokens are not billing or pure compute.", 0, 4)
    table("Overview · adopted policy, changes and usage coverage", "summary", 4, 10)
    table("Changes · planning, risk, checks and revision links", "changes", 14, 10, "Approved policy data supports path-risk observation only; action gates are not evaluated. Historical merges do not prove pre-merge readiness. Full evidence includes observation policy version and scope.")
    table("Candidate requirements · automation coverage and evidence limits", "rules", 24, 12, "Candidate catalogue is distinct from My EA’s adopted pin. New candidate rules are not adopted automatically. Guidance-only is not optional after adoption. Metadata presence and semantic/independent review are separate.")
    table("Decisions and follow-through · review, exceptions, device, release and outcome gaps", "decisions", 36, 10)
    text("Agent usage · how to read it", "**Input includes cached input; output includes reasoning. Do not add subsets again.** Totals are cumulative per retained session, not a time-window bill. Turn time includes tools/waiting; it is not pure compute or human effort. Parallel parent/child turn times overlap. Broad-directory sessions are excluded; unlinked sessions are not attributed to a PR. Reset/fork/malformed data is marked partial and excluded from the exact sum. The session may still be running. Collection polls every 5 minutes; views refresh every 30 seconds.", 46, 4)
    table("Agent sessions · token usage and time", "sessions", 50, 13, "Scoped to configured working folders, not linked to individual PRs. Cached input is already included in total. Full input/uncached/reasoning/observed-time fields remain available from the read-only sessions endpoint.")
    table("Collection health · attempts, last success, age and explicit errors", "health", 63, 7)
    table("Observation history · changed source snapshots", "history", 70, 7)
    table("Collection attempt history", "attempts", 77, 7)
    for panel in panels:
        if panel["gridPos"]["y"] >= 4:
            panel["gridPos"]["y"] += 6
    for panel in panels:
        if panel['gridPos']['y']>=10:panel['gridPos']['y']+=10
    table('Repository coverage · all registered worktrees, including missing adoption','workspaces',10,10,
        'Effective policy comes from the external approved pin, not the branch files. Local gaps remain visible. Inventory does not prove instructions were loaded or create a mandatory startup/merge boundary.')
    for x, field, title, unit, color in [
        (0, "Open changes", "Open PRs observed", "none", "blue"),
        (6, "Missing planning metadata", "Planning metadata gaps¹", "none", "orange"),
        (12, "Reported token sum (eligible sessions)", "Tokens · scoped sessions²", "short", "purple"),
        (18, "Reported turn seconds (sum; overlaps)", "Turn time · incl. overlaps²", "s", "blue")]:
        panels.append({"id": len(panels)+1, "type": "stat", "title": title, "datasource": DS, "gridPos": {"x": x, "y": 4, "w": 6, "h": 5},
            "targets": [query("overview", api_port)], "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "/^"+field.replace("(", r"\(").replace(")", r"\)")+"$/", "values": False}, "textMode": "value", "colorMode": "value", "graphMode": "none"},
            "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "fixed", "fixedColor": color}, "noValue": "Unknown"}, "overrides": []}})
    details = []
    table("Full session accounting · input, cache, output, reasoning and time", "sessions", 102, 12, "Expand for all source fields, including model, subsets, reported/observed/union/elapsed time and incomplete turns. Horizontal scrolling preserves the complete accounting view.", detailed=True)
    details.append(panels.pop())
    table("Full change evidence · exact revisions and assurance limits", "changes", 114, 12, "Exact revision and PR evidence are clickable. Account/check metadata does not prove independent review or historic readiness.", detailed=True)
    details.append(panels.pop())
    for index, panel in enumerate(details):
        panel["id"] = 101 + index
    panels.append({"id": 100, "type": "row", "title": "Detailed evidence · expand for complete token/time fields and exact revision links", "collapsed": True, "gridPos": {"x": 0, "y": 101, "w": 24, "h": 1}, "panels": details})
    for panel in panels:
        if panel['gridPos']['y']>=10:panel['gridPos']['y']+=29
        for child in panel.get('panels',[]):child['gridPos']['y']+=29
    table('Task usage · recorded work, review and remediation','activity-tasks',10,8,
        'Observed activity subtotals, never added to cumulative session totals. Eligible/all counts expose missing measurements. Historic uninstrumented work is unknown; marker time includes waiting.')
    table('Phase and review round · initial work, reviewers, fixes and re-review','activity-rounds',18,8,
        'Phases and task links are declared. Distinct reviewer activities remain available below; repeated context processing counts as usage. Sum and union of marker intervals are separate.')
    table('Activity detail · each agent and review iteration','activities',26,13,
        'No LLM calls for capture. Observed boundary-counter deltas have source timestamp lag, not exact semantic phase costs. Open, reset, fork, shared-prefix and overlapping windows are excluded. Rows are recorded work, not synthetic examples.')
    table('Full activity accounting · boundaries, findings and attribution','activities',155,13,
        'Complete input/cache/output/reasoning fields, frozen snapshots, boundary lags, findings, revision links and measurement basis. Role labels do not establish reviewer independence.',detailed=True)
    # The existing collapsed detail row occupies y130 with children through y155.
    panels[-1]['gridPos']['y']=168
    for panel in panels:
        if panel['gridPos']['y']>=10:panel['gridPos']['y']+=12
        for child in panel.get('panels',[]):child['gridPos']['y']+=12
    table('Guarded task gates · decisions, review records and execution boundary','execution',10,12,
        'Only tasks launched through the owner controller are in scope. Operator decisions are not authenticated human identity. Completed means client exit, not acceptance. Empty means no recorded task; no enforcement inferred.')
    for field,width in [('Task',210),('Gate',190)]:
        panels[-1]['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':field},'properties':[{'id':'custom.width','value':width}]})
    table('Full guarded task evidence · revisions, review records and limits','execution',193,12,
        'Complete raw decisions and declared identity/evidence limits; completed means client exit, not acceptance.',detailed=True)
    return {"uid": UID, "title": "Agentic Engineering · Evidence & Usage", "schemaVersion": 41, "version": 1, "timezone": "browser", "refresh": "30s", "time": {"from": "now-30d", "to": "now"},
        "editable": False, "timepicker": {"hidden": True}, "tags": ["engineering-governance", "local-pilot"], "panels": panels,
        "templating": {"list": [{"name": "repo", "label": "Repository", "type": "custom", "query": ','.join(repositories), "current": {"text": "all", "value": "all"}, "options": [{"text": v, "value": v, "selected": v == "all"} for v in repositories], "hide": 0}]}}


def provision(runtime, credentials, api_port=8769, grafana_port=3001):
    runtime = Path(runtime).resolve()
    provisioning = runtime / "provisioning"
    for directory in [provisioning / "datasources", provisioning / "dashboards", runtime / "dashboards"]:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # JSON is valid YAML and avoids a new configuration parser dependency.
    datasource = {"apiVersion": 1, "datasources": [{"name": "Governance evidence", "type": DS["type"], "uid": DS["uid"], "access": "proxy", "isDefault": True, "editable": False,
        "jsonData": {"allowedHosts": [f"http://127.0.0.1:{api_port}"], "auth_method": "none", "httpHeaderName1": "Authorization"},
        "secureJsonData": {"httpHeaderValue1": "Bearer " + credentials["api_token"]}}]}
    path = provisioning / "datasources/evidence.yaml"; path.write_text(json.dumps(datasource, indent=2)); path.chmod(0o600)
    provider = {"apiVersion": 1, "providers": [{"name": "Engineering governance", "type": "file", "disableDeletion": True, "allowUiUpdates": False, "updateIntervalSeconds": 10, "options": {"path": str(runtime / "dashboards")}}]}
    path = provisioning / "dashboards/evidence.yaml"; path.write_text(json.dumps(provider, indent=2)); path.chmod(0o600)
    settings=json.loads((runtime/'settings.json').read_text()) if (runtime/'settings.json').is_file() else {}
    path = runtime / "dashboards/engineering.json"; path.write_text(json.dumps(dashboard(api_port,settings.get('repositories')), indent=2)); path.chmod(0o600)
    config = f"""[paths]
data = {runtime / 'grafana/data'}
logs = {runtime / 'logs'}
plugins = {runtime / 'software/plugins'}
provisioning = {provisioning}
[server]
http_addr = 127.0.0.1
http_port = {grafana_port}
domain = localhost
root_url = http://localhost:{grafana_port}/
enforce_domain = true
[security]
admin_user = albert
admin_password = {credentials['grafana_password']}
secret_key = {credentials['grafana_secret_key']}
disable_gravatar = true
allow_embedding = false
[auth.anonymous]
enabled = false
[users]
allow_sign_up = false
allow_org_create = false
[analytics]
reporting_enabled = false
check_for_updates = false
check_for_plugin_updates = false
[plugins]
preinstall_disabled = true
[log]
mode = console
level = error
[snapshots]
external_enabled = false
"""
    path = runtime / "grafana.ini"; path.write_text(config); path.chmod(0o600)
