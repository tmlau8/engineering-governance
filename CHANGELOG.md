# Changelog

## 1.1.0-rc.1 — unreleased candidate

- Preserve CODE-001–038 and add CODE-039–050 for agent identity, least privilege,
  authority envelopes, untrusted input, provenance, egress, stop conditions and review records.
- Add JSON Schema 2020-12 and bounded subject/identity/artifact/supersession/set
  validation. Conditional or unavailable records cannot satisfy review completeness.
- Replace presence-only `satisfied` gate results with `metadata_conforming`; expose
  self-acceptance/identity limits and active dissent. Tighten security/lock path fixtures.
- Add a policy generator, hash-locked validator dependencies, Python 3.9/3.12 CI
  and reproducible bundle checks. No signed release or adoption-pin update is implied.

## 1.0.0-rc.1

- Portable, scoped restatement of 38 existing coding requirements with stable IDs.
- Accepted fix/enhancement/feature, derived low/high risk and three gate points;
  fix automation enabled first while every applicable standing rule remains binding.
- Compact specification after impact analysis; full specification for high risk.
- Shared policy separated from reviewed project paths, authorities and checks.
- Dependency-free evaluator, read-only GitHub adapter, bundle manifest and verifier.
- Explicit limits: metadata is not semantic review, self-acceptance is not independent
  review, publication is not adoption, and detection is not merge/release enforcement.
