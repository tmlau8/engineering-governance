import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import guard_runtime as guard


class GuardRuntimeTests(unittest.TestCase):
    def test_aliases_and_special_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; source.write_text('synthetic')
            self.assertEqual(guard.safe_tree(root), 1)
            alias = root / 'alias'; alias.symlink_to(source)
            with self.assertRaisesRegex(ValueError, 'WORKSPACE_SYMLINK'): guard.safe_tree(root)
            alias.unlink(); os.link(source, alias)
            with self.assertRaisesRegex(ValueError, 'WORKSPACE_HARDLINK'): guard.safe_tree(root)
            alias.unlink(); os.mkfifo(alias)
            with self.assertRaisesRegex(ValueError, 'WORKSPACE_SPECIAL_FILE'): guard.safe_tree(root)

    def test_workspace_entry_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'file').touch()
            with patch.object(guard, 'MAX_ENTRIES', 0):
                with self.assertRaisesRegex(ValueError, 'WORKSPACE_ENTRY_LIMIT'): guard.safe_tree(directory)

    def test_profile_cannot_grant_control_paths_or_parent_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'file').write_text('synthetic')
            for path in ['../outside', '/tmp/outside', '.git/config', '.codex/config.toml', '.governance/adoption.json']:
                with self.assertRaises(ValueError): guard.profile(root, [path])
            (root / 'alias').symlink_to(root / 'file')
            with self.assertRaises(ValueError): guard.profile(root, ['alias'])
            os.link(root / 'file', root / 'link')
            with self.assertRaises(ValueError): guard.profile(root, ['link'])

    def test_profile_has_explicit_denies_and_exact_file_grant(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); (root / 'file').touch()
            p = guard.profile(root, ['file']); fs = p['filesystem']
            self.assertEqual(fs[str(root / 'file')], 'write')
            self.assertEqual(fs[str(root)], 'read')
            for key in [':root', ':tmpdir', ':slash_tmp', str(root / '.git'), str(root / '.aws')]:
                self.assertEqual(fs[key], 'deny')
            self.assertFalse(p['network']['enabled'])

    def test_environment_drops_authority_and_injection(self):
        with patch.dict(os.environ, {'GH_TOKEN':'synthetic', 'SSH_AUTH_SOCK':'synthetic', 'DYLD_INSERT_LIBRARIES':'synthetic', 'CODEX_HOME':'synthetic'}):
            self.assertEqual(set(guard.clean_environment()), {'PATH','LANG','HOME'})

    def test_native_command_requires_explicit_named_profile(self):
        command = guard.native_command('/trusted/codex', '/workspace', {'network':{'enabled':False}}, ['/bin/true'])
        self.assertIn('--permission-profile', command)
        self.assertEqual(command[-2:], ['--', '/bin/true'])
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', command)

    def test_unsupported_platform_fails_closed(self):
        with patch.object(guard.sys, 'platform', 'linux'):
            with self.assertRaisesRegex(ValueError, 'UNVERIFIED_PLATFORM'): guard.verify('/unused')

class EscalationDenialTests(unittest.TestCase):
    def test_only_exact_expected_call_and_denial_count(self):
        from verify_guard_escalation import exact_denial
        expected='approval policy is Never; reject command — you cannot ask for escalated permissions if the approval policy is Never'
        good={'type':'function_call_output','call_id':'call_fixture','output':expected}
        self.assertTrue(exact_denial(good))
        for change in [{'output':'unrelated approval parser failure'},{'output':'unsupported tool; reject'},{'call_id':'different'},{'type':'custom_tool_call_output'},{'output':{'text':expected}}]:
            self.assertFalse(exact_denial(dict(good,**change)))
