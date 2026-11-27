# USAGE-004 — Activity and review-round usage

Implement before further governance enforcement changes. Change profile: feature,
high risk (private telemetry persistence, collector/API and assurance changes).

## Acceptance and scope

Record initial work, each reviewer, remediation and repeat reviews with immutable
activity ID, declared task/repository/optional PR, session or exact parent/agent
binding, role, phase, round, finding IDs, reviewed revision and outcome. Show each
activity, phase/round subtotals and task totals in Grafana. Repeated rounds and
concurrent reviewers remain separate. Repository/task/role attribution is declared
metadata, never governance clearance or proof of reviewer independence.

Explicit phase markers are necessary; do not classify old conversations with a
model or pretend missing phases were captured. A local CLI and command wrapper
capture boundaries without making model requests; the wrapper executes the supplied
work command once. Existing orchestrator commands can include markers. Native
desktop and other clients require this explicit adapter integration; no global
client hook is installed or claimed. No added LLM calls solely for telemetry.

## Measurement contract

Capture available cumulative counters and source event timestamps at begin/end,
retain marker timestamps and both boundary lags. Deltas are **observed boundary
counter deltas**, not exact semantic phase consumption. Validate the entire
counter window, including interior decreases/invalid values. Missing counters,
forks, conflicts, overlapping same-session windows and unfinished activities are
excluded from additive subtotals; no movement at an unchanged snapshot is unknown.
Never silently attribute later source events to a closed activity.

A binding declared before dispatch may select exactly one session created within
the activity with matching full agent path and parent UUID. A completed fresh
session entirely within the activity may report its observed cumulative counter
directly (not subtraction from an invented zero), with explicit whole-session
basis, no fork and all observed turns complete at capture (at least one completed
turn and no open observed turns). Turn completion does not terminate a session.
Freeze selected counters and validating records at end; later resumes cannot
rewrite closed activity. A failed close capture remains unknown even on retry;
backdated source events arriving later are not boundary observations. Resumed
sessions use measured snapshots and must retain their original baseline point.

Physical duplicate telemetry is deduplicated. Context processed again in a
different model call remains usage. Input includes cached input; output includes
reasoning. Session totals and activity subtotals are separate and never added.
Show eligible/all counts, excluded/open activities and unknown historic coverage.
Marker elapsed includes waiting/tools. Report sum and interval union separately;
neither is compute, billed cost or complete historical task effort.

## Trust, storage and lifecycle

Owner-only `.runtime/data/activity.sqlite` stores bounded metadata-only activity
state/events, separate from the collector's evidence database. Transactional begin
and end, immutable run IDs, idempotent retries and conflicting-retry rejection.
Reject unsafe ancestor/leaf symlinks and ledger permissions; source reads use
verified regular descriptors. Bound discovery entries/depth/time, bytes, rows and
IDs. No prompts, messages, tool arguments/output, credentials or arbitrary URLs
enter storage. Evidence links are generated from repository/PR/revision.

Read-only activity collection runs independently before policy-resolution failure
can return from the collector. Failures preserve prior activity projections with
separate health. Thirty-day metadata retention and the existing purge cover the
ledger. Keep open runs visible; crashes do not fabricate an ending.

## Before-build dispositions and validation

No application/schema migration; new local metadata database only. Privacy and
counter correctness need independent specialist/adversarial/Quality review.
Concurrency: SQLite immediate transactions, one active activity per known session
or exact pending binding; projection also detects binding overlap. Recovery:
stop local preview, retain prior code and private data; no policy pins or agent
permissions change. Dependency: standard library only. Observability: explicit
activity source health and quality flags. UX: task summary followed by per-agent
phase/round rows and complete accounting details.

Test all four phases, repeated rounds, concurrent reviewers, same-session reuse,
interior resets, delayed/missing snapshots, forks, duplicate fragments, malformed
values, binding ambiguity, unsafe files, crash/retry behavior, retention, privacy
sentinels and registry rejection independent collection. Verify real capture,
all Grafana panel/filter queries and browser rendering. Fixtures must never be
presented as real work. Final independent review, Python 3.9/3.12 and CI precede
handoff. Human merge/release remain separate.
