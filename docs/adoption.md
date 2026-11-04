# Adopt the shared policy

## 1. Select the release

Use the approved release's immutable source commit, version and bundle manifest
digest. Tags are readable labels, not the only trust reference. Review source and
release status, including whether the bootstrap PR is still awaiting human merge.
Never invent a commit or follow a moving branch automatically.

## 2. Add the local bundle and project adapter

```text
.governance/
  adoption.json
  baseline/                   # exact released policy/tooling/templates + manifest
  project.json                # reviewed repository, authorities, checks, trigger paths
  changes/                    # change metadata or references to maintained specs
```

Use the release asset or build the bundle from the exact release commit with
`python3 tooling/build_release.py --output <new-directory>`. Its output records the
manifest digest. Verify installed bytes with a trusted verifier and the digest
from the approved adoption record, never candidate-provided code/pins.

The project adapter has only `schema_version`, `repository`, `human_authorities`,
`required_checks`, `trigger_paths`. It cannot change common gates, delete mandatory
assurance paths, enable unsupported profiles or waive requirements. Authorities,
checks and semantic risk still need human review. The trusted evaluator reads the
approved adapter from outside the candidate change; modifying both adapter and
adoption.json in a PR cannot self-approve a weakening.

## 3. Wire the clients

Merge an explicit reading instruction into the existing AGENTS.md, preserving the
architecture/build/domain reading order:

> Read `.governance/adoption.json`, `.governance/baseline/policy/engineering.md`,
> `.governance/baseline/policy/workflow.md` and `.governance/project.json` before
> work. Record the adopted version and apply all relevant requirements. Reassess
> classification against the actual diff. Existing project-specific obligations
> remain binding. Policy changes use an ordinary reviewed adoption PR.

CLAUDE.md points to the same AGENTS.md contract. Keep runtime permissions/hooks
client-specific. A client acknowledging a version is discovery evidence, not
compliance proof. Verify reading from the root and relevant nested working dirs.

## 4. Reconcile duplicated requirements

Map every old shared rule to the corresponding CODE ID or accepted supplement
before replacing its duplicate text with the local package reference. Preserve
project-only architecture, build/test/device commands, role charters, documentation
register and stricter requirements. Record any conflict and its explicit decision.
For My EA, retain spec files but allow the adopted compact format for eligible
fixes only after its ways-of-working/template amendment is reviewed and merged.

## 5. Evaluate and collect evidence

```sh
python3 .governance/baseline/tooling/check_gate.py \
  --project .governance/project.json --change /path/to/change.json \
  --paths /path/to/planned-paths.json --stage before_delegation
```

Use the actual changed paths and authenticated GitHub records before merge. Put
one `governance` fenced JSON record in the PR body. The GitHub adapter's `--repo`,
`--pr`, `--project` and optional `--report` select the inspected PR. It performs
GET requests and never checks out PR code; that does not reduce the authority of
the credential supplied to it. Keep credentials server-side and narrowly scoped.

The adapter rejects mismatched check/run provenance and PR modifications to an
accepted check workflow or declared executable dependencies. Such governance changes
need explicit independent review and trusted producer evidence, not a trivial
replacement green check. Verify actual workflow/head/merge-revision behaviour on
a real PR before treating a configured CI input as available.

Required automated statuses and native protection are separate from the local
checker. A trusted default-branch/release evaluator must publish its status on the
actual inspected PR revision and re-evaluate after changes in source or evidence.
Do not use its own status as an input. A same-provider status is not, by itself,
proof of a separately protected producer. Protect control configuration and report
unavailable boundaries rather than claiming them enforced.

## 6. Review and human merge

Follow the target repository's specification, independent specialist/red-team/
quality/principal gates and documentation register. Test missing/stale/failed
evidence, modified baseline/adapter, workflow tampering and bypass attempts.
Preserve unrelated work. Humans merge; release remains a separate decision.

For upgrades, publish a new immutable release and submit a normal adoption PR.
Recovery is a reviewed adoption update/revert to an allowed release; do not remove
checks or silently drift to an old unsupported policy.
