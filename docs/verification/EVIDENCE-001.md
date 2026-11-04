# EVIDENCE-001 verification and review record

Verified 4 November 2026 on macOS ARM64, ordinary branch
`feature/evidence-dashboard`. This record contains verification outcomes rather
than private repository snapshots, usage records, credentials or screenshots.

## Automated and runtime evidence

- **61 tests passed** with
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tooling:evidence python3 -B -m unittest discover -s tests`.
  Includes the existing 31 policy tests, usage arithmetic/lifecycle boundaries,
  historical/racing GitHub observations, fixed-host requests, real loopback API
  rejection cases, real owned-child termination after failed startup, journal
  failure rollback, retention/purge and preservation of full dashboard details.
- Pinned Grafana archive checksum verified; Grafana OSS 13.3.0 and Infinity 4.1.5
  installed locally. No global client configuration was modified.
- Real authenticated Grafana datasource queries succeeded for every table/stat/
  detailed panel across all three repository filters. The reproducible optional
  check is `python3 -B tests/check_grafana_runtime.py check`.
- gstack browse authenticated normally, rendered real evidence, expanded the
  detailed row and exposed session accounting fields and exact GitHub commit
  links, including the My EA adoption change. Builder inspected screenshots.
- A separately labelled synthetic dashboard rendered never-collected, stale plus
  failed-attempt, and unknown-stat states. The unknown count displayed **Unknown**,
  not zero. Synthetic records used a temporary SQLite store and inline fixture
  queries, never the real evidence database. The fixture dashboard was deleted
  using `python3 -B tests/check_grafana_runtime.py cleanup`.
- Inspected authenticated datasource/dashboard responses contained none of the
  generated credential values. Dashboard JSON has no embedded secret. This is
  bounded verification of these responses, not proof about every Grafana API.
- Local source health recovered after an adoption-root lookup defect was fixed;
  adoption content is pinned to one fetched branch revision. Native protection
  remains unavailable; observing this fact does not claim enforcement.
- A fresh policy bundle verified **13 files**, with manifest SHA256
  `d7fc97eaca106a990e2f9a4114d473441d5a54dc2b30a90cf3a5c996b1b6e0f8`,
  unchanged from the published 1.0.0-rc.1 release. My EA app source was not edited.

## Independent privacy/security review

Reviewer: dispatched `evidence_privacy`, independent of the builder.
Four substantive challenges were accepted and resolved:

1. Failed startup could leave untracked processes: immediate atomic ownership
   journals and in-memory rollback now cover spawn/journal failures.
2. Malformed nested agent metadata could crash collection: nested container types
   are validated before selection.
3. Per-file bounds did not bound aggregate memory/work: scan file/byte/event caps
   now fail visibly, preserving last-good data; old files skip parsing by mtime.
4. Unbounded vendor output contradicted the log contract: process output is
   discarded; fixed lifecycle logs are bounded. Legacy local vendor logs were
   removed during a stopped-runtime transition.

Reviewer independently reran 15 targeted tests successfully and found no remaining
blocking security issue within the reviewed scope. Socket and actual process
termination checks were performed by the builder in the authorised runtime;
the reviewer did not inspect credentials or raw usage/session content.

## Independent adversarial/Quality review

Reviewer: dispatched `evidence_quality`, independent of the builder.
Six substantive challenges were accepted and resolved:

1. Ten-PR historical truncation: closed PR pagination continues through the cutoff;
   pagination/scope limits fail visibly.
2. Fractional timestamp ordering: canonical fixed-precision UTC timestamps preserve
   chronological ordering and turn intervals.
3. Unknown duration becoming zero: null is preserved and duration coverage shown.
4. Cumulative component decreases: ambiguous sessions are excluded from exact sums.
5. Skipped oversized/invalid files appearing complete: incomplete discovery fails
   the source and preserves last-good projections.
6. Readability filters hiding required details: a discoverable collapsed row
   retains full session fields and exact-revision source links.

Final Quality verdict: ready for handoff within review scope, no remaining blocker.
Reviewer independently reran 25 focused tests successfully. Browser execution and
the complete suite remain the builder's evidence rather than reviewer execution.

Quality's reviewed implementation snapshot SHA256 was
`febc33654762a455ed500253eca584c980b84e6152586987d0ac702227a03872`,
computed over sorted relative path, NUL, bytes, NUL for `evidence/*.py`,
`dashboard/build.py`, both evidence/runtime test files and EVIDENCE-001. The
subsequent spec status/reference and this verification record add documentation
of those results; implementation bytes remain unchanged.

## Principal review and remaining boundaries

### Essential flow impact / Test SME mapping

This change adds a single-user Grafana surface. My EA's iOS essential flows,
app/extension source and device-test contract are unaffected; no My EA UI change
or device verification is claimed. Independent Quality is the dispatched test
specialist for this dashboard's CODE-027 testability and negative/lifecycle gates.

| Dashboard flow | Evidence at the final implementation snapshot |
|---|---|
| Sign in and open evidence | Real gstack login, authenticated dashboard/API checks, inspected overview screenshot |
| Separate repository evidence | All actual panel queries exercised for all/My EA/governance filters |
| Inspect source and full accounting | Expanded detailed row, session fields, rendered exact commit/PR links; full-detail regression |
| Recognise missing/error/stale evidence | Isolated labelled fixture dashboard and inspected screenshots; failed-source/last-good regressions |
| Keep local access private | Real loopback API auth/Host/Origin/write rejection tests; inspected credential-free browser responses |
| Stop/restart/delete/recreate safely | Real runtime restarts, actual owned-child failure cleanup, journal failure and isolated purge/fresh-store regressions |

Independent Quality's final verdict above covers test design and the inspectable
results. Builder performed the real browser interactions; neither another role
nor an inline reviewer persona substitutes for those recorded executions.

Independent `evidence_principal` reviewed substantive status drafts. Valid
challenges narrowed “collection completed” to a partial first pass, avoided stale
session counts and limited the credential claim to inspected API responses.
Subsequent progress drafts received no substantive challenge; none was invented.

This is an observation pilot. Review independence, human acceptance, exceptions,
device, release and outcome artifacts are not inferred from CI/GitHub account
metadata. Historical policy-at-decision is unknown. Usage is experimental local
structured data, scoped to folders and unlinked to PRs; cost and pure compute are
unmeasured. Claude Code and supported OTel ingestion are not implemented. Native
merge protection is unavailable on the current plan. Runtime custody is local
and owner-editable. Human merge of this new PR remains required.
