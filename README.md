# Engineering governance

Shared coding and agentic-engineering policy, release **1.0.0-rc.1**. This private
trial baseline preserves 38 existing coding requirements and the accepted compact
workflow. It is independent of Codex or Claude Code.

Start with [the policy](policy/engineering.md), [workflow rules](policy/workflow.md)
and [the adoption guide](docs/adoption.md). The maintained requirement source is
`policy/requirements.json`; the Markdown policy is its readable view. Each
requirement has a stable CODE identifier and applicability. Project additions
remain binding. Presentation requirements and personal source snapshots are excluded.

**All applicable rules are mandatory.** Automation coverage is a separate fact:
metadata checks detect only stated conditions and do not certify the meaning of
evidence, specialist independence, physical-device behaviour or human identity.
[Control coverage](policy/control-coverage.json) records that boundary. No merge
or release enforcement is claimed by publishing this repository.

## Quick start

Python 3.9+ is sufficient for policy evaluation and bundle verification.

```sh
PYTHONPATH=tooling python3 -m unittest discover -s tests
python3 tooling/check_gate.py --project adapters/my-ea.json \
  --change templates/change.example.json --paths templates/paths.example.json \
  --stage before_delegation
python3 tooling/build_release.py --output /tmp/engineering-governance-rc1
```

The change example is explicitly synthetic. Replace it with a real specification
and impact analysis. Adding a regression test routes the fix high under the
accepted rule; use a focused full spec and the required review evidence.

## Adoption and trust

An adopting repository records an immutable source commit, version and manifest
digest, vendors the exact release bundle and supplies a reviewed project adapter.
Agents explicitly read that local policy through `AGENTS.md`; a Claude entry point
can point to the same contract. A URL alone does not load or enforce policy.

The trusted evaluator/configuration is selected outside the candidate PR. Never
execute a candidate's verifier, policy scripts or workflow as trusted code. A PR
cannot approve itself by editing its adoption pin and manifest together. Required
merge checks need an eligible GitHub plan and actual configured protection; release
authorisation needs a separate release boundary.

This initial private release may point to the independently reviewed bootstrap
candidate while its source PR awaits human merge. The release records the exact
commit. Publication authorisation is not a merge or deployment authorisation.
Future policy changes and My EA adoption follow branch, PR and human merge.

## Evidence and dashboard

The evidence/dashboard work follows the policy publication. It must preserve the
distinction between missing, declared, independently reviewed and automatically
verified evidence, and show collector freshness and unavailable controls. No
confidential collected evidence belongs in this repository. Runtime state is
excluded by `.gitignore`. See [implementation contract](docs/implementation-contract.md).
