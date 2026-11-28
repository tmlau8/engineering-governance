# Guarded task pilot

This controller governs only the Codex CLI sessions it launches. Existing Desktop
chats, owner GitHub actions and other tools remain outside it. Keep normal human
merge and separate release decisions. No paid GitHub feature is needed for this
local execution boundary. The read-only dashboard cannot approve a task.

## Owner and agent responsibilities

Install/use the reviewed governance checkout outside the coding repository. Its
code, policy, trusted external adapter and `.runtime/guard` must stay outside the
worker's writable scope. Do not run controller code copied from the candidate
project. The initial supported runtime is the independently tested macOS Codex
binary; changed code or binary invalidates capability/permissions.

The agent prepares a scope/specification and independent review bundle conforming
to `policy/schemas/review-record.schema.json`. Reviews refer to the clean feature
HEAD; adversarial/Quality and each triggered specialist are checked. Review origin,
credential separation and semantic quality require owner inspection: schema
validation alone does not establish them. User and provider data classification
must permit the selected OpenAI model. No human GitHub credential is provided to
the worker.

A repository explicitly marked draft adoption is blocked. Preserve dirty work;
the controller never stashes, commits or cleans it. Confirm the repository's real
default branch in the request. Worktrees resolve through Git identity, not names;
root/common-dir/HEAD/index/working bytes and executable modes bind each task.

## Prepare, inspect and approve

From the governance checkout, the orchestrator prepares the request. Replace the
example fields with inspected real evidence; the example grants no approval.

```sh
.venv/bin/python -B tooling/guarded_task.py prepare \
  --workspace '/absolute/path/to/project' \
  --adapter adapters/senior-concierge.json \
  --spec docs/03-specs/FEATURE.md --bundle '/owner/private/reviews.json' \
  --task FEATURE-ID --profile feature --default-branch main \
  --builder builder-id --session declared-builder-session \
  --base-sha REVIEWED-BASE-SHA --model APPROVED-MODEL --provider openai \
  --write path/to/file.swift --write path/to/new/module.swift \
  --expires 3600 --timeout 900
```

Existing scope files must be tracked; new files receive exact path grants, not
parent-directory write grants. The specification and control/credential paths
cannot be writable. The controller creates approved parent directories itself.
Changing scope, source, policy, adapter, review bytes or client requires a fresh
request. A remediation request uses `--phase remediation --round 2 --finding ID`.
Independent reviewer sessions retain their separate review/re-review activity
markers; they are not reclassified as builder work.

Preparation prints a permit UUID and confirmation digest. The owner inspects the
packet, actual specification and review artifacts, then explicitly approves from
an owner-controlled terminal:

```sh
.venv/bin/python -B tooling/guarded_task.py inspect PERMIT-UUID
.venv/bin/python -B tooling/guarded_task.py approve PERMIT-UUID --confirm EXACT-DIGEST
.venv/bin/python -B tooling/guarded_task.py run PERMIT-UUID
```

Do not ask the worker to approve itself. Operator approval is a manual control,
not authenticated proof of a physical human. A permit is consumed before launch
validation, including rejected or failed launches; never retry it as reusable.
Client capability must have been reviewed and installed separately by the owner.
The task tool does not manufacture that receipt or turn a native probe into one.

## Evidence and limits

The dashboard's guarded-task table records preparation blocks, operator decisions,
claims and client outcome, with exact revision and review-record references.
`completed` means client exit, never acceptance, successful tests, merge or release.
Collection proceeds even when repository adoption discovery fails.

CLI root activity is declared before launch against a unique temporary non-Git
working directory. Only a fresh `exec` root, observed complete within the markers,
can contribute its observed cumulative tokens. Children are excluded unless
separately instrumented; the activity and task coverage labels state this current
run gap. No model requests are made for capture, and recorded subtotals are not
complete task cost or billing. Missing/ambiguous/incomplete telemetry stays unknown.

Expiry limits launch. Wall timeout kills the owned process group; detached children
retain the kernel's scope restrictions, and immediate revocation of detached
access is not claimed. Source checks are point-in-time; concurrent owner changes,
malicious privileged host processes and deliberate owner bypass are outside this
pilot. Production task review and actual device/platform feasibility remain
required. A green synthetic test never clears a Senior feature's feasibility.

## Reproduce the boundary tests

```sh
.venv/bin/python -B tooling/guard_runtime.py
.venv/bin/python -B tooling/verify_guard_escalation.py
```

The second test uses a local fixture provider and synthetic key to force the exact
native tool request; it makes no real model call and reads no owner authentication.
Live parent/child shell/patch tests are separate evidence, not inferred from it.
