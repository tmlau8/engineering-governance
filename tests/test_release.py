import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from build_release import build
from load_policy import ROOT, load_policy
from verify_bundle import verify


class ReleaseTests(unittest.TestCase):
    def test_catalogue_preserves_38_unique_rules(self):
        rules = json.loads((ROOT / "policy/requirements.json").read_text())["rules"]
        self.assertEqual({r["id"] for r in rules}, {f"CODE-{n:03d}" for n in range(1, 39)})
        self.assertEqual(len(rules), 38)
        self.assertTrue(all(r["requirement"] and r["applicability"] and r["mandatory_when_applicable"] for r in rules))

    def test_manifest_and_file_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            built = build(root)
            self.assertEqual(verify(root, built["manifest_sha256"])["result"], "satisfied")
            target = root / "policy/engineering.md"
            original = target.read_bytes()
            target.write_bytes(original + b"changed")
            with self.assertRaises(ValueError): verify(root, built["manifest_sha256"])
            target.write_bytes(original)
            (root / "extra.py").write_text("untrusted")
            with self.assertRaises(ValueError): verify(root, built["manifest_sha256"])

    def test_manifest_cannot_self_authorise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"; built = build(root)
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["version"] = "forged"
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): verify(root, built["manifest_sha256"])

    def test_symlink_and_traversal_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"; built = build(root)
            target = root / "policy/engineering.md"; target.unlink()
            target.symlink_to(Path(tmp) / "outside")
            with self.assertRaises(ValueError): verify(root, built["manifest_sha256"])
            target.unlink()
            manifest = {"schema_version": 1, "files": {"../outside": "x"}}
            raw = json.dumps(manifest).encode(); (root / "manifest.json").write_bytes(raw)
            with self.assertRaises(ValueError): verify(root, hashlib.sha256(raw).hexdigest())

    def test_adapter_cannot_override_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = json.loads((ROOT / "adapters/my-ea.json").read_text())
            for key, value in [("enabled_profiles", ["feature"]), ("human_authorities", []), ("required_checks", [])]:
                adapter = dict(source); adapter[key] = value
                p = Path(tmp) / "project.json"; p.write_text(json.dumps(adapter))
                with self.assertRaises(ValueError): load_policy(project_path=p)

    def test_unlisted_cache_nested_manifest_and_symlink_directory_fail(self):
        for name in ["tooling/__pycache__/unverified.pyc", "tooling/manifest.json"]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "bundle"; built = build(root)
                extra = root / name; extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_bytes(b"not released")
                with self.assertRaises(ValueError): verify(root, built["manifest_sha256"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"; built = build(root)
            (root / "empty-link").symlink_to(tmp, target_is_directory=True)
            with self.assertRaises(ValueError): verify(root, built["manifest_sha256"])


if __name__ == "__main__": unittest.main()
