"""Generate the readable policy from its maintained requirement catalogue."""
import argparse
import json
from pathlib import Path
from load_policy import ROOT


def render():
    rules = json.loads((ROOT / "policy/requirements.json").read_text())["rules"]
    version = json.loads((ROOT / "policy/gates.yaml").read_text())["version"]
    existing = (ROOT / "policy/engineering.md").read_text()
    header = existing.split("## CODE-001", 1)[0]
    header = "# Engineering policy " + version + "\n" + header.split("\n", 1)[1]
    return header + "".join(f"## {r['id']} — {r['title']}\n\nApplicability: `{r['applicability']}`.\n\n{r['requirement']}\n\n" for r in rules).rstrip() + "\n"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--check", action="store_true"); args = p.parse_args()
    value = render(); path = ROOT / "policy/engineering.md"
    if args.check: raise SystemExit(0 if path.read_text() == value else 1)
    path.write_text(value)
