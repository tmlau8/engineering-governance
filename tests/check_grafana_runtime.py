"""Optional real-Grafana integration checks; temporary fixtures never enter real evidence."""
import argparse
import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "evidence"), str(ROOT / "dashboard")]
from build import dashboard
from store import Store
from views import health, overview

FIXTURE_UID = "governance-runtime-fixtures"


def main(action):
    credentials = json.loads((ROOT / ".runtime/secrets/credentials.json").read_text())
    basic = base64.b64encode((credentials["grafana_user"] + ":" + credentials["grafana_password"]).encode()).decode()
    def api(path, payload=None, method=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request("http://localhost:3001/" + path, data=data, headers={"Authorization": "Basic " + basic, "Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            assert all(value.encode() not in raw for key, value in credentials.items() if key != "grafana_user"), "CREDENTIAL_DISCLOSURE"
            return json.loads(raw)
    if action == "cleanup":
        api("api/dashboards/uid/" + FIXTURE_UID, method="DELETE")
        print("Temporary fixture dashboard removed.")
        return
    for endpoint in ["api/datasources", "api/dashboards/uid/agentic-engineering-evidence"]:
        api(endpoint)
    live = dashboard()
    panels = [p for p in live["panels"] if "targets" in p]
    panels += [p for row in live["panels"] if row["type"] == "row" for p in row["panels"]]
    for repo in ["all", "tmlau8/my-ea", "tmlau8/engineering-governance"]:
        for panel in panels:
            target = copy.deepcopy(panel["targets"][0]); target["datasource"] = panel["datasource"]
            target["url"] = target["url"].replace("${repo:percentencode}", urllib.parse.quote(repo, safe=""))
            result = api("api/ds/query", {"queries": [target], "from": "now-30d", "to": "now"})["results"]["A"]
            assert result.get("status") == 200 and not result.get("error"), "DATASOURCE_QUERY_FAILED"
    with tempfile.TemporaryDirectory() as temporary:
        store = Store(Path(temporary) / "fixture.sqlite")
        empty = health(store, "all"); unknown = overview(store, "all")
        store.snapshot("github:tmlau8/my-ea", {}, at="2020-01-01T00:00:00Z")
        store.failure("github:tmlau8/my-ea", "GITHUB_429")
        stale = health(store, "all"); store.close()
    def inline(panel, value):
        result = copy.deepcopy(panel)
        target = result["targets"][0]
        target.pop("url", None); target["source"] = "inline"; target["data"] = json.dumps(value)
        result.pop("transformations", None)
        return result
    health_panel = next(p for p in panels if p["title"].startswith("Collection health"))
    stat_panel = next(p for p in panels if p["title"] == "Open PRs observed")
    fixtures = [inline(health_panel, empty), inline(health_panel, stale), inline(stat_panel, unknown)]
    titles = ["TEST ONLY · no successful collection", "TEST ONLY · stale last-good data and failed attempt", "TEST ONLY · unknown open PRs, not zero"]
    for index, panel in enumerate(fixtures):
        panel["id"] = index + 1; panel["title"] = titles[index]
        panel["gridPos"] = {"x": 0, "y": index * 8, "w": 24, "h": 8}
        target = copy.deepcopy(panel["targets"][0]); target["datasource"] = panel["datasource"]
        result = api("api/ds/query", {"queries": [target], "from": "now-30d", "to": "now"})["results"]["A"]
        assert result.get("status") == 200 and not result.get("error"), "FIXTURE_QUERY_FAILED"
    fixture = {"uid": FIXTURE_UID, "title": "TEST ONLY · Governance missing/stale/error fixtures", "schemaVersion": 41, "panels": fixtures, "editable": False, "timepicker": {"hidden": True}}
    api("api/dashboards/db", {"dashboard": fixture, "overwrite": True})
    print("All live panel/filter queries passed; inspected API responses contained no generated credential values.")
    print("Fixture preview: http://localhost:3001/d/" + FIXTURE_UID)
    print("After browser inspection, run this script with cleanup.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "cleanup"], default="check", nargs="?")
    main(parser.parse_args().action)
