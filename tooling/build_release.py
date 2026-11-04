"""Build a portable bundle and its manifest; never publishes or merges."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from load_policy import ROOT


def build(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Release destination must be new")
    destination.mkdir(parents=True)
    for name in ["policy", "tooling", "templates"]:
        shutil.copytree(ROOT / name, destination / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    files = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(destination.rglob("*")) if p.is_file()}
    version = json.loads((ROOT / "policy/gates.yaml").read_text())["version"]
    manifest = {"schema_version": 1, "version": version, "python_minimum": "3.9", "files": files}
    raw = (json.dumps(manifest, indent=2) + "\n").encode()
    (destination / "manifest.json").write_bytes(raw)
    return {"version": version, "manifest_sha256": hashlib.sha256(raw).hexdigest(), "files": len(files)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
