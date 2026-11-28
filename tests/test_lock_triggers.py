import unittest
from pathlib import Path
from load_policy import load_policy,ROOT
from check_gate import matches


class LockTriggerTests(unittest.TestCase):
    def test_common_lock_formats_are_mandatory_without_clock_false_positives(self):
        for adapter in ['my-ea.json','senior-concierge.json']:
            policy=load_policy(project_path=ROOT/'adapters'/adapter)
            paths=next(t['paths'] for t in policy['triggers'] if t['id']=='dependency_tool_permission')
            for name in ['gradle.lockfile','android/gradle.lockfile','bun.lockb','.terraform.lock.hcl','Brewfile.lock.json','package-lock.json','Package.resolved','yarn.lock','lockfile']:
                self.assertTrue(any(matches(name,p) for p in paths),(adapter,name))
            for name in ['ClockView.swift','BlockedStateView.swift']:
                self.assertFalse(any(matches(name,p) for p in paths),(adapter,name))
