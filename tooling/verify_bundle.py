"""Verify a local bundle against a separately trusted manifest digest.

The expected digest must come from the approved adoption/configuration, not the
candidate's own manifest. No manifest-provided script is ever executed.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def verify(root, expected_manifest_sha256):
    root = Path(root).resolve()
    manifest_file = root / "manifest.json"
    raw = manifest_file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_manifest_sha256:
        raise ValueError("Manifest differs from trusted adoption pin")
    manifest = json.loads(raw)
    if manifest["schema_version"] != 1 or not manifest["files"]:
        raise ValueError("Unsupported or empty release manifest")
    for name, expected in manifest["files"].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Unsafe manifest path")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Symlinks/outside paths are forbidden")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Bundle file differs: " + name)
    inventory = list(root.rglob("*"))
    if any(p.is_symlink() for p in inventory):
        raise ValueError("Bundle symlinks are forbidden")
    # Bytecode caches can execute before source; they cannot be ignored here.
    # Only the root manifest is outside its own file inventory.
    actual = {str(p.relative_to(root)) for p in inventory if p.is_file() and p != manifest_file}
    if actual != set(manifest["files"]):
        raise ValueError("Bundle has unexpected or missing files")
    return {"result": "satisfied", "policy_version": manifest["version"], "files_verified": len(actual)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", required=True)
    p.add_argument("--expected-manifest-sha256", required=True)
    args = p.parse_args()
    try:
        report = verify(args.bundle, args.expected_manifest_sha256)
    except (ValueError, KeyError, OSError) as error:
        print(json.dumps({"result": "failed", "errors": [str(error)]}))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
