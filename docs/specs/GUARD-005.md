# GUARD-005 — Guarded execution pilot

Feature, high risk: agent authority, security, assurance and deployment controls.
The immediate target is Senior Concierge. No paid plan, public repository,
project cleanup, merge, release or global client setting is authorised.

## Contract

An owner-controlled launcher makes task permission checks mandatory for the CLI
runs it starts. Native Desktop chats and GitHub owner actions remain outside this
boundary. The owner approves an exact task after inspecting specification and
independent review evidence; a schema-conforming record alone cannot grant access.
The existing review-record format remains canonical. Unknown feasibility or an
unavailable required review blocks dependent implementation.

A task binds canonical repository root/common-dir, a clean feature-branch HEAD,
specification and review-bundle byte digests, explicit writable files, approved
model/provider boundary, launch expiry and wall-clock budget. Source/spec/review
changes require a new decision. Each implementation permit is consumed atomically
before launch, including failed launches. Expiry limits launch; it is not a promise
of instant revocation. Wall timeout terminates the owned process group; detached
children retain kernel restrictions. Owner merge and release remain manual.

Use supported named Codex permission profiles with root-deny, minimal runtime
reads, read-only target and exact write exceptions. Deny Git/control/credential
paths and all worker network access. Reject workspace symlinks, hardlinks and
special files before a grant; a demonstrated pre-existing hardlink bypass makes
this a load-bearing prerequisite. Do not load candidate hooks, project configs,
MCP or plugins. Launch from a trusted non-Git driver directory with a scrubbed
environment and closed inherited descriptors. Model transport is a trusted client
function; model auth must not imply access to GitHub or human acceptance authority.

## Before-build concerns

Data: private metadata only, no app migration. Concurrency: atomic single-use
claim and source revalidation immediately before spawn. Feasibility: supported
configuration plus actual kernel and complete enabled-tool probes are required;
command-only probes cannot certify the Codex frontend. Privacy: no real secret
reads in tests; synthetic canaries only. Budget: bounded process time, output,
workspace entries and bytes. UX: show blocked reasons and precise coverage;
never translate registration or a green detector into enforced governance.
Recovery: no source writes before authorization; retain previous source and
owner-controlled publication. Tests may not change private project data.

## Verification and activation

Positive controls must succeed before negative results count. Probe read-only
and scoped-write modes, protected files, symlink/hardlink aliases, local/external
network, same-UID signals, inherited environment and detached descendants. Prove
actual shell and patch tools and absence of alternate integration/approval paths
in the launched client. Fail closed on unsupported versions/configuration/tools.
Independent Security/adversarial and Quality review precede readiness. Runtime
verification uses synthetic repositories first, then read-only Senior assessment.

Senior's current adoption is draft and its architecture file has unrelated local
work; preserve both. A candidate launcher is not permission to clear its platform
feasibility concerns. Do not activate an unverified runner to meet a deadline.
