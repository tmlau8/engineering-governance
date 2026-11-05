# Engineering governance

Shared coding and agentic-engineering policy, **unreleased candidate 1.1.0-rc.1**.
It preserves the original 38 requirements and adds 12 agentic requirements.
Published 1.0.0-rc.1 and existing adopter pins remain unchanged. The candidate is
tool-neutral; current shared-account credentials do not satisfy its identity target.

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

Python 3.9+ is supported. Review validation adds hash-locked dependencies;
bundle byte verification remains standard-library-only.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r tooling/requirements-review.lock
PYTHONPATH=tooling:evidence .venv/bin/python -B -m unittest discover -s tests
python3 tooling/check_gate.py --project adapters/my-ea.json \
  --change templates/change.example.json --paths templates/paths.example.json \
  --stage before_delegation
python3 -B tooling/check_package.py
```

The change and [review examples](docs/review-records.md) are explicitly synthetic.
The evaluator reports **metadata_conforming**, never semantic clearance or verified
human identity. Triggered merge/release checks fail closed without a complete
revision-bound review bundle. Replace examples with a real specification
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

The published initial release records an exact immutable source commit. Candidate
changes do not replace it. Publication authorisation is separate from merge or
deployment authority. Future policy and My EA adoption changes use ordinary PRs.

## Evidence and dashboard

The local Grafana pilot is described in [the dashboard quick start](docs/dashboard.md).
It preserves the
distinction between missing, declared, independently reviewed and automatically
verified evidence, and shows collector freshness and unavailable controls. No
confidential collected evidence belongs in this repository. Runtime state is
excluded by `.gitignore`. See [implementation contract](docs/implementation-contract.md).
