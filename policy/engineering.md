# Engineering policy 1.0.0-rc.1

Authoritative portable coding baseline for trial use. All applicable requirements are mandatory now. Guidance/detected/enforced describes implemented assurance, not whether a rule is optional.

This document is generated from `requirements.json`, the maintained requirement source. Update that source and regenerate this view together. The six-row gate table in `gates.yaml` defines minimum pilot routing; it never waives a requirement below.

## Applicability and precedence

Common requirements apply across adopting coding repositories. UI, iOS, role-based, classified-data and documentation profiles apply when that work is present; My EA-specific requirements remain in its project profile. Existing project additions remain binding. Resolve conflicts explicitly; a local adapter cannot silently relax a shared requirement. Agent runtime permissions remain separate controls.

The compact-spec amendment is a format change after impact analysis, not a waiver of specialist reviews or tests. The original before-build checklist language could be read as permitting work with blocked items: this edition makes explicit that blocked load-bearing concerns prohibit dependent work. No global personal instruction file is rewritten by adoption.

## CODE-001 — Verify changing external facts from primary sources before relying on them

Applicability: `engineering_baseline`.

Verify changing external facts against current primary documentation, headers or an actual test before relying on them. Cite the deciding source. Label unverified claims explicitly.

## CODE-002 — Perform verification available to the agent before asking the user

Applicability: `engineering_baseline`.

Perform verification available through documentation, code, supported interfaces or your build before asking the owner to test. Ask for private account/device checks only when that is the necessary source, stating why.

## CODE-003 — Resolve load-bearing facts before dependent work

Applicability: `engineering_baseline`.

Resolve load-bearing facts before dependent implementation. If the deciding fact is unknown, mark the dependent work BLOCKED pending a specific investigation. A caveat does not clear it.

## CODE-004 — Facts-ledger evidence must directly support a cleared claim

Applicability: `engineering_baseline`.

A cleared facts-ledger row needs the primary-source quote column and an explicit connecting-line explanation showing how that quotation decides the actual claim. If either is missing or does not support the claim, the row is BLOCKED.

## CODE-005 — Verify the actual success requirement, not an adjacent proxy

Applicability: `engineering_baseline`.

Phrase the deciding claim as the actual acceptance requirement. Test that requirement rather than an adjacent or convenient proxy.

## CODE-006 — Unvalidated status changes only on new supporting evidence

Applicability: `engineering_baseline`.

Distinguish confirmed facts, hypotheses and ruled-out claims. An unvalidated claim becomes cleared only on new supporting evidence, not repetition or reinterpretation without new evidence.

## CODE-007 — Use the smallest feasibility spike before building on unresolved assumptions

Applicability: `engineering_baseline`.

When a load-bearing assumption cannot be resolved from documentation, run the smallest authorised disposable feasibility experiment and record its result before building on it.

## CODE-008 — Validate real platform/integration behaviour beyond configuration/build success

Applicability: `engineering_baseline`.

Validate platform/host activation, coexistence, eligibility and lifecycle rules before integration work. Build success and correct configuration do not prove real platform reachability; retain applicable runtime checks.

## CODE-009 — Escalate scope-narrowing discoveries and confirm real entry points

Applicability: `engineering_baseline`.

Escalate discoveries that narrow intended scope. Name real entry points, content types and constraints and obtain the owner’s decision before implementing a narrower requirement.

## CODE-010 — Complete a before-build concern checklist with explicit dispositions

Applicability: `engineering_baseline`.

Before triggered implementation, record the concern checklist in the specification: data/migration, shared-state concurrency, platform feasibility, permissions/capabilities, lifecycle/entry points, main-thread hazards, resource budgets, privacy/data flow, requirement scope, UX, dependencies, reversibility and observability. Mark every line cleared, not applicable with reason, or blocked, citing evidence. Blocked load-bearing concerns prohibit dependent implementation.

## CODE-011 — Perform proportionate design review before and code review after

Applicability: `engineering_baseline`.

Perform proportionate design examination before implementation and diff/code review afterwards, including real triggers, lifecycle, concurrency and the actual request. Required project review skills and independent gates remain binding even for a small diff.

## CODE-012 — Separate automated checks from real-runtime regression evidence

Applicability: `engineering_baseline`.

Separate automated/build evidence from real-runtime verification. At every handoff identify affected existing behaviours, coverage and what must be physically retested and why. Avoid blocking or WebKit-backed work on UI/render/on-appear paths where prohibited by the platform profile.

## CODE-013 — Scale review depth to the cost of reversing the mistake

Applicability: `engineering_baseline`.

Scale review depth to the cost of reversal. Resolve hard-to-undo data, authority and platform pillars early; avoid unnecessary heavyweight design for cheap-to-change work. Ambiguity about a load-bearing concern triggers investigation/review.

## CODE-014 — Prefer native/proven interaction patterns and visible primary actions

Applicability: `frontend_ux_profile`.

For user interfaces, prefer native/proven platform controls, navigation, integration and sharing patterns. Make primary actions and state visible. Explain material deviations proactively.

## CODE-015 — Demonstrate primary-action discoverability with a mock or walkthrough

Applicability: `frontend_ux_profile`.

For a new or changed primary action, demonstrate discoverability before implementation using a mock or explicit hardest-case walkthrough, including zero/one-item states. Include “found unaided” as an acceptance criterion. A component-level prose review alone is insufficient.

## CODE-016 — Research proven packages, APIs and standards before hand-rolling

Applicability: `engineering_baseline`.

Research official SDKs, maintained/adopted libraries and open standards before hand-rolling a non-trivial capability. Record what was checked and the concrete reasons for a custom implementation.

## CODE-017 — State a viable undo before destructive or data-changing work

Applicability: `engineering_baseline`.

Before a destructive or data-changing operation, state and prepare a viable recovery action, such as a verified snapshot restore or safe feature switch. Prefer small reversible steps. Do not execute without a safe recovery/containment route; reverting code alone may not recover data or be security-safe.

## CODE-018 — Define how failures become observable without manual discovery

Applicability: `engineering_baseline`.

The specification identifies how failure becomes visible without relying on manual discovery: appropriate errors, logs, counters or explicit failed/queued state. Verify relevant instrumentation without exposing sensitive content.

## CODE-019 — Spec and acceptance criteria before code

Applicability: `engineering_baseline`.

Create or update a specification with scope, acceptance criteria and impact analysis before implementation. Eligible low-risk fixes may use the adopted compact specification; high risk uses a focused full specification. Preserve each project’s specified contract location until its adoption change explicitly reconciles the format.

## CODE-020 — Implement on branches and PRs; human controls merge/distribution

Applicability: `engineering_baseline`.

Implement on an ordinary feature branch and submit a PR. Agents never commit or merge directly to master/main/default branches, regardless of whether native branch protection is available, or distribute/deploy without explicit authority. The authorised human controls merge and separately authorises release. Preserve parent/child feature scope across PRs.

## CODE-021 — Independent specialist review triggered by unproven correctness properties

Applicability: `agent_workflow_baseline`.

Independent specialist review is mandatory when correctness depends on facts a compile/unit test cannot prove, including external systems, runtime/platform behaviour, persisted data, a new dependency or the user environment. Uncertainty triggers the gate. Map the concern to the project’s specialist and require its evidence before dependent work.

## CODE-022 — Review requires inspectable evidence, not verbal clearance

Applicability: `engineering_baseline`.

A review is an inspectable, retained artifact tied to the reviewed revision and supported by specific sources, tests or attempted counterexamples. A verbal approval or empty checked box does not clear the gate.

## CODE-023 — Builder cannot self-certify triggered work through an inline persona

Applicability: `agent_workflow_baseline`.

For triggered work, the builder cannot certify its own change by adopting an inline reviewer persona. Use an independent dispatched reviewer with a bounded assignment and the required evidence. Inline checklists are only for untriggered work and are not independent reviews.

## CODE-024 — Adversarial challenge for triggered assumptions and evidence

Applicability: `agent_workflow_baseline`.

Every triggered change receives independent adversarial challenge of its load-bearing assumptions and cleared evidence. The challenge must test whether evidence decides the actual requirement and record attempts/findings and their dispositions.

## CODE-025 — Independent review of every substantive user-facing update and honest contribution record

Applicability: `agent_workflow_baseline`.

Before every substantive user-facing update, an independent principal reviewer inspects the artifacts and drafted account for ambiguity, overclaims, logic, completeness and suitability. Append an honest Principal review record identifying valid challenges and dispositions or no substantive challenge. Do not manufacture a contribution.

## CODE-026 — Missing independent review blocks dependent work

Applicability: `agent_workflow_baseline`.

If required independent review/dispatch is unavailable, disclose the missing gate and stop dependent work. Do not replace it with self-review or label it cleared.

## CODE-027 — Testability and negative/boundary/lifecycle/end-to-end evidence before Ready

Applicability: `engineering_baseline`.

Before Ready, establish testability, prerequisites and deterministic test-data paths. Define applicable negative, boundary, lifecycle and real end-to-end cases. Quality review verifies that the contract can actually be tested.

## CODE-028 — Project checks and explicit device-test debt

Applicability: `ios_project_profile`.

Run applicable project build/test commands and keep required suites green. For My EA app changes, preserve Debug and Release verification. Keep simulator, native UI, physical device and private-account evidence separate and state exact build identity, skips and device-test debt.

## CODE-029 — Preserve unrelated local work and stage only intentional changes

Applicability: `engineering_baseline`.

Preserve unrelated local work. Stage only intended files; do not silently clean, overwrite or include another change. Inspect branch/worktree state before mutation.

## CODE-030 — Codex uses explicit gstack preflight; Claude hooks are client-specific

Applicability: `tool_adapter_procedure`.

Use the project’s selected gstack browse installation for web browsing and perform the explicit installation preflight. A Claude-specific hook is not Codex enforcement. Tool adapters must use each client’s supported mechanisms and must not claim another client’s configuration is active.

## CODE-031 — Close affected canonical documentation and evidence within the feature change

Applicability: `engineering_baseline`.

Close affected canonical documentation and verification evidence within the same change. Record documentation impact, owners, update/not-applicable reasons and completion revision. Maintain the document register and affected catalogues, source/derivative relationships and shared references before handoff/merge.

## CODE-032 — Material workflow/tooling departures need prior agreement

Applicability: `personal_project_workflow`.

Use the established ordinary-branch, single-checkout workflow for an existing project. Explain and obtain the owner’s agreement before material departures such as additional worktrees, replacement tools or branch/release changes. Routine actions already authorised need no renewed permission.

## CODE-033 — Keep secrets out of version control

Applicability: `engineering_baseline`.

Keep secrets out of version control, evidence and logs. Use the project’s secure credential store, such as Keychain for My EA. Never publish tokens, keys or raw confidential payloads.

## CODE-034 — Essential-flow impact evidence tied to final snapshot

Applicability: `ios_project_profile`.

For My EA features and UI/app-flow redesigns, refresh the essential-flow impact matrix before Ready and against the final PR/integration snapshot. Independent Quality review covers real routes and deterministic data, negative/empty/lifecycle/overflow cases and automation gaps. Keep MyEA unit and MyEAUI native suites distinct; run applicable Debug/Release UI checks and disclose physical/private-account debt.

## CODE-035 — Verify end-to-end role operability without substituting another role

Applicability: `web_and_role_based_project_profile`.

In role-based systems, verify each role’s own real end-to-end workflow, permissions and actions. Do not substitute another role, impersonation or an administrative shortcut as proof of operability.

## CODE-036 — Keep classified project/member/source material outside repositories

Applicability: `project_data_handling_profile`.

Respect the project’s classified-data handling restrictions. Where material is prohibited from GitHub, keep member data, surveys, restricted third-party sources and other classified content out even when the repository is private. Publish only sanitised policy/evidence metadata permitted by the project.

## CODE-037 — Canonical source ownership and reproducible developer-reference derivatives

Applicability: `developer_documentation_profile`.

Maintain one canonical source per developer-reference artifact. Markdown owns prose; the declared diagram source owns diagrams; registries/maps own references/order. Renderers contain layout rather than parallel narrative. Regenerate, inspect and reconcile derivatives with their sources, recording hashes and audience/scope.

## CODE-038 — Project architecture, migration and extension source boundaries

Applicability: `ios_project_profile`.

For My EA, preserve module/registry composition and architecture boundaries. SwiftData has one store; non-additive changes require explicit versioned schema/migration design and regression evidence, while supported additive optional changes may use lightweight migration. Keep shared app/extension source paths and generated-project configuration consistent. Preserve privacy, Keychain and UI-thread rules.
