# EVIDENCE-001 — Local evidence and Grafana dashboard

Status: implemented local pilot; independent reviews completed. Human PR merge
remains separate; no new policy release implied. See the
[verification record](../verification/EVIDENCE-001.md).
Owner: Albert; implementation: engineering-governance feature branch.

## Contract

Provide a private local end-to-end My EA engineering view: adopted policy/revision,
change profile and derived risk, gate observations and evidence links, all 38 rule
coverage/gaps, review/acceptance/exception/release/outcome debt, collection health,
and agent token/time usage. Existing policy remains mandatory; unknown evidence
must never become a green compliance assertion. New telemetry does not retrospectively
prove old work complied. Do not change My EA app code or personal client config.

Use Grafana OSS 13.3.0 with Grafana-maintained Infinity 4.1.5, versions verified
from official download/plugin pages on 4 November 2026. Grafana renders approved
read-only JSON views from a small local evidence API; SQLite holds local event
history and projections. Code remains outside the immutable policy bundle.

## Evidence contract and privacy

Collect only authorised repositories (initially tmlau8/my-ea and the governance
repo), GitHub read-only API observations and allowlisted local structured usage
metadata. Never persist raw messages/prompts, PR/review/comment bodies, tool
arguments/output, auth files or tokens. GitHub handles and session IDs are limited
identifying provenance metadata. Runtime DB/config/logs/credentials stay outside
Git under an owner-only .runtime directory. Supply a retention/delete operation.

Credentials stay server-side. gh authentication may have broader authority than
GET-only collection; do not call it a read-only token. The collector performs no
GitHub writes, never checks out/executes PR code, and stores bounded safe errors.
SQLite app usage state, if inspected, is opened read-only and never modified.

Use append-only local observations with deduplicated fingerprints plus current
projections; append-only here is a software convention, not WORM/tamper-proof
custody. Source errors preserve the last good data, record last-attempt and
last-success separately and make freshness/partial coverage visible.

The HTTP API binds 127.0.0.1 only, requires an unguessable bearer token, validates
Host/Origin, accepts fixed read-only endpoints, and makes no arbitrary URL/SQL/file
requests. Grafana binds loopback with authenticated access and server-side API
credentials. Disable analytics/update checks and external sharing. Render metadata
as text and allow only canonical GitHub evidence links.

## Usage measurement

Preferred future interface is documented Codex OpenTelemetry, without prompt/body
logging. This machine has no existing exporter; do not edit global config silently.
For historical pilot data, use an explicitly labelled local structured-event adapter
reading only session_meta, turn_context metadata, token_count and lifecycle fields.
This internal format is not a stable public API; failures/unknowns stay visible.

Deduplicate physical rollout fragments by logical session/event identity; do not
sum cumulative counters per event or file. Cached input is a subset of input and
reasoning is a subset of output: never add them again to totals. Handle resets,
missing usage, incomplete turns and forks without inventing zeros. Show tool/model,
input/cached/uncached/output/reasoning/total tokens, session elapsed span and observed
turn duration. Turn duration includes waiting/tools and is not pure compute or
human effort. Parallel agent durations are not a single elapsed duration. No billed
cost is inferred from subscription tokens. Repo/session/PR associations have explicit
provenance; do not infer My EA attribution from a broad parent directory.

## Views

Overview/changes; per-rule evidence gaps; reviews/exceptions/release/outcome;
agent usage by session/tool/model and association; collector health/history.
Include source links, policy/subject SHA, measured versus declared versus derived
fields, unsupported controls and known native-protection restriction. Fixture and
real datasets remain separate. No leaderboard or generated-code productivity claim.

## Acceptance

- Real read-only GitHub records render, including adopted release and PR73 merge.
- All 38 requirements remain visible with applicability and unknown evidence;
  only supported observations may satisfy a detector. Metadata presence, independent
  semantic review and enforced boundaries remain distinct.
- Missing/withdrawn/stale review or changed PR/check data changes the projection;
  failed collection cannot produce an empty green dashboard.
- Local usage handles duplicate snapshots/fragments, counter resets, null counters,
  cache/reasoning subset semantics, aborted/unfinished/overlapping turns and unlinked
  sessions. Ambiguous session attribution stays unassigned; no billed cost fabricated.
- API rejects missing auth, hostile Host/Origin, writes, arbitrary paths and unsafe
  URLs. No sensitive sentinel content is stored or returned.
- Grafana provisioned panels use real endpoints, render correctly, and link to exact
  GitHub revisions/evidence. Test both ordinary and gap/error fixture states.
- Existing 31 policy tests remain green; new meaningful collector/usage/API tests pass.
- Independent security and quality review, browser inspection and a reviewable PR
  precede handoff. Human merge remains required; earlier two-PR exception is consumed.

## Deciding sources

- https://developers.openai.com/codex/config-advanced/ — OTel usage/duration support;
  enabling telemetry is user-level and local state is not a complete audit interface.
- https://grafana.com/grafana/download?edition=oss&platform=mac — ARM64 13.3.0 archive
  SHA256 8c640b5632c7336b2bebfa1b879b6e674631980fdf3b21ca0bc4337e7ef83457.
- https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/ — Grafana Labs
  maintains Infinity 4.1.5; JSON backend datasource supported on selected Grafana.

Independent design findings and actual verification are recorded before handoff.

## Persisted allowlist and source boundary (design-review closure)

Only these fields may cross the collection boundary; unknown fields are dropped:

| Record | Allowed scalar fields / limits |
|---|---|
| GitHub change | repo (one configured owner/name), PR positive integer, subject SHA 40 hex, base SHA 40 hex, state enum, merged/draft booleans, created/updated/merged timestamps, profile enum or unknown, risk enum, configured policy version/commit/digest, canonical GitHub URLs generated locally; no title/body text |
| Check/review observation | allowlisted check/workflow name <=120, provider <=80, status/conclusion enum, actor login <=80, review state enum, subject SHA, source ID integer and timestamp, canonical source URL |
| Gate/rule result | CODE ID or named gate enum, result enum, bounded predefined reason code, evidence-kind enum, source link; no arbitrary declaration text |
| Usage session | validated UUID-like session/parent/fork IDs <=80, tool enum, model/version <=100 matching identifier grammar, source kind, timestamps, integer token counters, completed/aborted/open turn counts, reported duration and observed interval sums/union, coverage/reset/invalid-count flags, configured repo association and association-source enum |
| Collector attempt | source enum, receipt time, last-success time, success/partial/error enum, predefined safe error code, row count; no raw exception or response text |

PR governance JSON is processed transiently only for bounded metadata and the
existing detector; its free-text fields never enter the event store. Reviewer
identity/state is observed, not proof of independent or physical-human judgment.
Merged changes have a historical observation path: the existing open-PR gate is
not reused to manufacture retrospective readiness. Unknown policy-at-change stays
unknown; current-policy gap analysis is labelled as such.

Local discovery reads only regular non-symlink .jsonl files beneath the canonical
`~/.codex/sessions` root (max256MiB/file, max8MiB/record). First select sessions by
explicit configured cwd scopes for My EA and the governance workspace; parse only
needed metadata/event fields after selection. Cwd is used transiently and never
persisted. Broad parent/unrelated sessions are not imported. Explicit operator
registration may include a named session, labelled declared and never silently
assigned to a PR. No auth.json, logs database or user-message content is a source.
The optional app-state index is deferred; no SQLite state file is needed.

Event identity is session+timestamp+record kind+allowlisted counter/turn identity.
Physical fragments are deduplicated. Cumulative counter decreases flag ambiguity;
without an explicit verified epoch/baseline, retain a labelled observed lower bound
and exclude that session from exact usage rollups. Forks lacking an own-usage
baseline are similarly excluded. Null/invalid usage stays null, never zero. Model
changes keep the session marked mixed; cumulative totals are not split across models.
Per-turn reported duration, observed start/end interval and incomplete-turn count
are distinct. Neither is labelled pure compute. Sum and union of overlapping
intervals are distinct; human waiting and cost remain unmeasured.

Owned runtime storage is exactly `.runtime/` below this checkout: DB/WAL/SHM,
collector/API logs, Grafana config/data/provisioning/plugins and credentials.
Downloads are in its separate software subdirectory. Default metadata retention
is30 days; prune events and expired projections on collection. Logs are bounded
and contain fixed lifecycle/error codes only, no request/response content.
Deletion stops owned processes, removes DB/sidecars/logs, Grafana data/config and
credentials, and verifies those locations are absent; binaries may remain unless
full cleanup is requested. No backups/exports are created. Do not claim secure
physical erasure or deletion of upstream GitHub/Codex records. Recollection creates
new history only for the configured retained source window, not a hidden backup.

Runtime files/directories use0600/0700. API binding refuses nonloopback, enforces
exact Host/Origin, rejects writes/arbitrary paths and constant-time checks a bearer
secret. Grafana authentication stays enabled; datasource API secret is server-side.
No metrics/logs/usage leave this machine. Dependencies are checksum/version pinned.

## Facts ledger and before-build dispositions

| Claim | Deciding evidence | Connection / disposition |
|---|---|---|
| Maintained dashboard/data source exists | Official Grafana OSS download and Infinity plugin pages above | The selected ARM64 archive has a published hash; Infinity is maintained by Grafana Labs and supports backend JSON. Installed checksum-verified; actual panel queries and browser rendering verified in the linked record |
| Codex can expose usage/duration | Official advanced-config page: turn.token_usage and turn.e2e_duration_ms; sse completion token counts | Supports a future OTel adapter; does not establish historical export or current desktop hook coverage. Cleared with explicit limitations |
| This local format has usable scalar fields | Bounded metadata-only spike in the authorised governance session: task_started/task_complete/turn_aborted include turn_id; completion has duration_ms/started_at/completed_at; token_count.info has total_token_usage | Use only these fields. No message fields retained. Internal format fallback, not a stable audit API |
| Historical PR73 can be collected as a gate pass | Existing github_gate.collect rejects non-open PRs | Ruled out; implement separate historical observation, no retrospective pass |

Data/schema/migration: cleared for a new owner-only metadata SQLite database;
no My EA data migration. Privacy/authority/permissions: constrained by exact
allowlist, source roots and loopback/auth boundary above; independent recheck
required. OS/host feasibility: verify real local server and Grafana startup before
handoff; no iOS surface change. Shared state/concurrency: single collector writer,
transactional snapshots and append-only observations; fixed API reads only.
Resource budget: bounded API pages/records, 5-minute collection interval, 30-day
retention. UX: use existing Grafana panels with visible unknown/freshness/source
labels. Proven dependency: Grafana/Infinity selected from official maintained
components; SQLite/HTTP adapters use standard library for this bounded local pilot.
Recovery: stop local processes and rebuild projections from retained observations;
source failures preserve last good data. Observability: source attempt/success/error
and stale age exposed. No blocked load-bearing concern may be marked cleared by
fixture tests alone; real runtime validation and independent final review remain.
