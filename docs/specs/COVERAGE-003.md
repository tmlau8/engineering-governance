# COVERAGE-003 — Repository identity, policy resolution and workspace coverage

This corrects the folder-based My EA adoption/usage assumption. One approved
repository policy applies across its registered clones and all linked worktrees,
including older branches without governance files. No My EA source, worktree,
branch or adopted version is changed. No new GitHub identity, merge permission,
release or global Codex configuration is authorised by this implementation.

## Acceptance and boundaries

- Register trusted repository identity, clone root, immutable adoption commit,
  policy source commit and approved manifest digest outside candidate branches.
  Read the approved Git objects, never candidate scripts, for effective policy.
- Discover every linked worktree with Git metadata, independent of folder names.
  Show effective policy separately from missing/diverged local installation and
  instruction references. Missing context is blocked/unknown, never exempt.
- A startup preflight resolves any registered checkout/subdirectory to the same
  approved baseline and project adapter. Unknown clones, missing pins, corrupt
  bundles and ambiguous roots fail visibly; no implicit remote trust or fetching.
- Usage scopes derive from discovered worktrees. Broad parent-directory sessions
  stay unassigned; nested foreign repositories are excluded. Registration is not
  retrospective proof that a session followed policy or worked on one PR.
- Dashboard reports discovered workspaces, local adoption/instruction gaps,
  effective baseline, supported profile, and startup/merge enforcement limits.
  A successful inventory is not proof that the agent loaded instructions.
- Test actual four My EA worktrees plus real disposable Git fixtures for spaces,
  moved paths, old branches, absent/stale/tampered files, nested repositories,
  unregistered clones, Git replacement objects and unavailable pins/discovery.
  Preserve all pre-existing local work and baseline pins.

## Trust and privacy

Runtime registry/cache remain owner-only and outside Git. Their operator-controlled
custody is not protected from an agent with the same user's write access; reports
must say so. GitHub account role metadata is not token-scope evidence. Startup
preflight is detection unless an independently controlled runner makes it mandatory.
Hard merge/release enforcement remains absent and must not be claimed repaired.

Git reads use bounded plumbing commands, no candidate checkout/status/hook/script
execution, replacement objects or lazy network fetch. Materialised policy bytes
are checked against the externally pinned manifest and exact inventory. Reject
symlinks/traversal and oversize inputs. Absolute paths live only in private runtime
configuration/cache; persisted dashboard observations use labels/opaque IDs.
Authenticate the commit, every traversed tree and each read blob by recomputing
its Git object hash before trusting its content. `git cat-file` alone does not
prove local object integrity. Scrub inherited Git variables; disable hooks,
fsmonitor, pager and every network protocol in the plumbing subprocess environment.
Bound stdout incrementally with a deadline; never first capture an unbounded Git
response. Match both canonical common-dir and top-level root for cwd association,
including nested same-common-dir pointers. Cache publication is staged/atomic;
reuse checks reject all extra files, symlinks and nonregular entries. Association
describes current identity observed at collection, not historical path ownership.

Official Codex guidance confirms project-root-to-cwd instruction discovery and
global-home instructions, built once per run:
https://learn.chatgpt.com/docs/agent-configuration/agents-md . A file above Git root
cannot be assumed to bootstrap every checkout. Any global bootstrap installation
requires a separately reviewable change; do not quietly rewrite personal settings.

## Before-build dispositions

Identity/source authority: fixed external pins; root/remote changes block rather
than silently re-register. Privacy: metadata allowlist only. Persisted state:
new source records, no application migration. Concurrency: one collector writer,
read-only API; failed discovery preserves last-good evidence. Resource bounds:
command/byte/file/worktree caps. Recovery: stop preview and return to prior branch;
owned cache can be removed, upstream source untouched. UX: expose coverage before
general PR/usage summaries. Feasibility: real Git plumbing and actual repo audit
precede Ready. Dependencies: standard library/Git, no additional package.

Required independent design and final specialist/adversarial review, cross-version
suite, actual workspace audit and Grafana inspection remain acceptance gates.

## Implementation checks

Approved gates and adapter are composed only by a data-only observation loader.
It supports the 1.0/1.1 data formats without importing candidate review contracts
or running any adopted scripts. Observation policy cannot clear an action gate;
PR records name the observation version and scope. Unsupported versions preserve
last-good observations. Explicitly draft approved sources are rejected.

The frozen 1.0 gate fixture comes from policy commit
`30de3e055ed2189d53cd8f4ef1e60cb12a92bb70`; SHA256 is
`811531eab756e35cc0b7f02816f8dfbf2d076e96fbccf309fb7d2a4868604c51`.
Fixture bundles exercise data-version compatibility; the real My EA audit checks
the complete published bundle against its externally selected manifest digest.

Registry validation rejects case-insensitive slug, canonical clone-root and
common-directory ownership collisions across repositories. A bounded advisory
lock serializes registry read/validation/atomic publication. The lock is not
protection against another process with the same user's write privileges.
Exact local/cache inventories count directories as well as files, reject extra
empty directories and impose entry, depth, byte and time bounds.

All registered contexts validate before workspace snapshots are published.
Unverified legacy folder scopes cannot attribute new usage. Incomplete scope
migration preserves the entire prior usage snapshot with an explicit error;
an operator must review the scope changes rather than silently rewriting history.
Planning that was not evaluated is unknown, not missing or conforming.
