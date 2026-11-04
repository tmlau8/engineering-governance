# Workflow and supplemented routing rules

Profiles are **fix**, **enhancement**, **feature**. Routing inputs are profile and
derived **low/high risk**. Specification depth is an output. Agent authority is
execution configuration. Project commands, paths and authorities live in the
reviewed adapter. Scenarios test this structure; they do not define it.

| Profile / risk | Before delegation | Before merge | Before release |
|---|---|---|---|
| Fix / low | Compact spec, scope/criteria, impact analysis | Required checks, verification, human acceptance | Readiness, recovery, release authority |
| Fix / high | Full spec plus risk analysis and review plan | Same plus risk-review artifact | Same plus containment/follow-up |
| Enhancement / low | Compact spec plus design note | Checks, verification, acceptance | Readiness, recovery, authority |
| Enhancement / high | Full spec plus design/risk/review plan | Same plus risk review | Same plus containment/follow-up |
| Feature / low | Full spec, parent design and closure criteria | Checks, acceptance, child-to-parent scope | Readiness, recovery, authority, parent closure |
| Feature / high | Same plus risk/review plan | Same plus risk review | Same plus containment/follow-up |

`gates.yaml` is the executable table. Only fix automation is enabled in this trial.
Other profiles still obey the common policy and their existing project workflows;
the pilot checker refuses to certify unsupported profiles. Later gates recheck
earlier prerequisites. Merge, release and observed outcome are distinct events.

## High risk

High risk is derived from changed paths and identified effects:

1. Security boundary or sensitive data.
2. Data or schema migration.
3. Dependency, tool or agent-permission change.
4. Infrastructure or deployment change.
5. CI, test or policy change, always high.

All test changes, including an added regression test, are high under this accepted
rule. Additional declarations can raise risk, never suppress a detected trigger.
Path patterns do not find every semantic effect. Existing property-based specialist
triggers remain binding even if no pattern matches.

## Establish compact eligibility before implementation

Frame the defect and intended outcome, inspect affected consumers/contracts,
data/authority and side effects, identify verification/recovery and load-bearing
unknowns, and record the analysis with the proposed profile. A fix is compact only
when that analysis supports low risk, existing behaviour is bounded and criteria
are testable. The accountable owner confirms the route. A small diff alone is
insufficient. Unknown impact requires bounded investigation before dependent work.

Reassess when implementation discovers new paths/effects and against the actual
PR diff. A high trigger escalates to a focused full specification before dependent
implementation continues. Specification format never waives a standing review,
test, privacy, documentation or human-merge obligation.

## Handling

- **Urgent:** a named authorised person records reason, scope and follow-up. The
  person may expedite handling; evidence requirements and authority remain.
- **Blocked:** record the blocker, owner and bounded next investigation. No
  dependent readiness pass is possible.
- **Exception:** retain an explicit human decision, scope, expiry and follow-up
  separately from test results. An exception is not proof a requirement passed.
  This evaluator holds exceptions for human disposition; it cannot self-authorise one.

The project retains stricter local obligations until a reviewed adoption amendment
reconciles them. No agent silently removes an existing rule because it appears
duplicated or because automation does not inspect it.
