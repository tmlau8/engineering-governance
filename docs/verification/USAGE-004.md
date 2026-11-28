# USAGE-004 verification

## Verified

- Full suite: 139 tests passed on Python 3.9 and Python 3.12 after the startup fix.
- All live Grafana panel queries passed for all configured repository filters,
  including task, phase/round and activity views. Responses were checked for
  generated credential values. This is telemetry validation, not governance clearance.
- Live task summary and per-agent activity table inspected in gstack browser.
  Initial work, separate Security/Quality reviews, remediation and round-two
  re-review render with explicit unknown/open values where applicable. The
  temporary TEST ONLY dashboard was removed after verification. The clarified
  attribution banner was provisioned into the running dashboard.
- Actual independent-reviewer sessions were recorded separately with observed
  boundary-counter deltas. Historical uninstrumented work remains unknown. One
  early capture missing the final identity digest was excluded rather than repaired.
- Source tests cover initial work, concurrent reviewers, remediation, repeated
  review rounds, unknown/open capture, reset/fork/shared-prefix, duplicate fragments,
  identity/baseline changes, delayed timestamps, failed-close retries, unsafe files,
  metadata privacy, task totals and interval union.
- Capture uses no model requests. The command wrapper executes its supplied work
  command once; task/phase labels are declared, not model-classified.

## Startup defect and correction

The operator's full verification command passed 133 tests on both versions and
bundle verification, then failed connecting to Grafana. A subsequent read-only
probe found the same recorded processes alive and Grafana healthy. The launcher
had reported success after two seconds of process liveness, before HTTP readiness.

Startup now rejects occupied ports before credential use, waits for Grafana's
healthy database, an authenticated evidence response and the provisioned dashboard,
and checks owned-child liveness before reporting success. Timeout/exit follows
the existing owned-process cleanup. Credentials, redirects and proxies are not
logged/followed. Requests use fixed loopback transport with Grafana's configured
localhost Host header. A live status-only probe reproduced default Host 301 versus
expected Host 200; this distinction has regression assertions.

Six startup regressions cover delayed readiness, exit/timeout, cleanup without
success output, occupied ports, invalid ports and authenticated endpoint/Host
selection. `--runtime-only --reload-preview` reruns only live preview verification;
it explicitly reports that suites/package checks are skipped.

## Independent reviews and limits

Independent Security and Quality reviewers found and resolved malformed timestamp,
fresh lifecycle/creation bound, lost baseline, private runtime and failed-close
reconstruction defects. Narrow startup and Host-binding reviews cleared the final
changes. Reviews were static/fixture based; actual full-suite and live-query
execution were performed separately by the implementing agent and operator.

No policy release, project adoption, human-merge authority or enforced execution
boundary is implied. Existing broad workspace/session evidence and activity
subtotals are distinct. Native desktop chats require explicit phase instrumentation;
no global client hooks were installed. PR #5 publishes this candidate; both Python matrix jobs passed. Final browser
inspection and fixture cleanup completed on 27 November 2026. These observations
do not establish project adoption or enforced execution controls.
