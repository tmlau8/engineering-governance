# GUARD-005 verification — 27 November 2026

**Senior Concierge implementation is not cleared.** This change supplies a
repeatable native command-boundary verifier, not a production task launcher.
Neither a policy reference nor successful synthetic tests establish that an
existing Desktop chat is governed.

## Completed evidence

`tooling/guard_runtime.py` passed all 28 checks against Codex CLI
`0.171.0-alpha.13.2`, executable SHA256
`e1c3d034b7fd295d160d6ab412357f9c54241c8ed7a2a861f4730b8a4dd88ddb`.
Run it explicitly on the supported macOS/Xcode installation:

```sh
.venv/bin/python -B tooling/guard_runtime.py
```

It uses disposable synthetic files and no model requests. Positive read, write,
sandboxed Python/import/subprocess/file-recreation and live loopback controls
succeeded. Read-only writes, adjacent/foreign writes, outside and nested-secret
reads, symlink writes, dynamic hardlink creation, local/external socket connects,
same-user foreign-process signals and detached-child writes were denied. Existing
hardlinks are rejected before use. Exact socket-operation PermissionError output
is required, independent of external connectivity. The final effect of operations
is checked outside the sandbox. The report always says implementation_authorized
is false. This is a platform-specific observation, not a portable certificate.

Independent Quality review identified a false-pass risk if sandboxed Python could
not initialize. The additional in-profile runtime positive control now proves
imports, subprocess execution, removal/recreation and verified writes. It passed
on the final run. The scanner is a point-in-time check, not a concurrent-owner lock.

Three bounded actual-client experiments used temporary files. Shell and patch
changed the allowed file; protected content stayed unchanged and synthetic secret
content did not appear in captured host output. Host tool reflection found image
and image-preview tools still present in the first configuration. Supported
image_generation/view_image disabling removed them in the final experiment.
MCP resource/template results were empty in that experiment.

The actual client still allowed child-agent creation with agents.max_depth=0.
The child's recorded permission profile matched its parent's restricted filesystem,
network and never-approve settings. That metadata is not a behavioral escape test.
Do not claim delegation is disabled, or count this as a cleared frontend boundary.
No real credential files were probed. No Senior source or adoption was changed.

## Regression verification

All 146 tests passed on Python 3.9 and Python 3.12 with the hash-locked
validator dependencies. The sandbox-only initial run could not bind loopback
listeners or inspect processes; the authorised runtime runs passed. Bundle
construction and exact-byte verification also passed. Linux CI runs the source
regressions; it does not run or certify the macOS native verifier.

## Outstanding controls, in execution order

1. Verify the entire enabled client/tool surface, including actual child behavior
   and alternate permission/approval requests, against the fixed launch contract.
   The native-command verifier cannot clear this requirement.
2. Implement and independently test an owner-side controller: exact source/spec/
   review binding, scope, expiry, atomic single-use permission, timeout and private
   audit record. It must reject changes before launching; an optional CLI check
   alone is insufficient. This controller has **not** been implemented here.
3. Reconcile and explicitly approve Senior's draft adoption. Preserve its current
   uncommitted architecture work and bind the reviewed final revision. Feature
   profile certification is not available from the fix-only pilot evaluator.
4. Collect the actual platform/phone feasibility and independent review evidence
   required by the Senior feature. Code/configuration success is not that evidence.
5. Activate only the reviewed execution route, then test denial of a missing review,
   stale source, expired/reused grant and out-of-scope write before real coding.
   Show those records in the dashboard; no such execution records exist today.

GitHub merge/release remains an explicit human control on the current private-repo
plan. No plan purchase, repository visibility change, global client installation,
merge or release was performed. Existing unmanaged Desktop chats are outside this
candidate control. Read-only feasibility investigation can proceed within its
existing authority; dependent implementation remains blocked.

## Independent contribution record

Independent Quality review identified the sandboxed-Python false-pass risk and
verified the correction against the final harness and seven focused tests. The
reviewer inspected the account for readiness overclaims and retained its blocked
production status. Actual native and full-matrix execution was performed by the
builder, separately from that static review. Final Security/adversarial review is
still pending; this is a draft checkpoint, not a cleared activation or release.
Review declarations do not authenticate reviewer origin or separate credentials.
