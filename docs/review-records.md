# Review records: candidate contract and use

This is the 1.1.0-rc.1 candidate. Publishing a version and upgrading an adopter
remain separate actions. Current My EA stays pinned to 1.0.0-rc.1. The original
38 requirements are preserved; CODE-039–050 add the agentic baseline.

Use one JSON record per bounded review, following
`policy/schemas/review-record.schema.json`. Record the external subject revision,
builder/reviewer identities and sessions, provenance, shared context, credential
separation, inspected evidence, claims, counterexamples, findings and limitations.
Principal review also hashes the exact drafted account. If tool/model information
is unavailable, state `unavailable`; never invent provenance. Same-model review is
permitted with shared-blind-spot risk disclosed. Context supplied for challenge
is distinct from treating builder conclusions as premises.

## Storage and input boundary

Store real records and approved evidence outside the source commit, for example
in the ignored owner-only `.runtime/reviews/` directory or an approved external
store. Putting a head-bound record into the source commit changes its head.
Do not copy raw prompts, confidential payloads, credentials or classified evidence
into Git or into review bundles. Redact approved artifacts before review and hash
the exact redacted bytes that the reviewer inspected.

The initial transport is an **explicit operator-supplied local JSON bundle**:
`records` is an array and `artifacts` maps references to base64-encoded approved
bytes. References never cause network requests or filesystem reads. Limits are
64 records, 256 artifacts and 16 MiB decoded evidence; JSON input is also bounded.
Hashes prove that supplied bytes match the recorded digest, not who reviewed them
or whether the evidence proves a claim. Signatures/platform origin are not verified.
PR-comment record collection and external immutable custody are deferred; the
candidate does not claim those transports exist.

## Validation

Install dependencies as in README, then try the deliberately synthetic full set:

```sh
.venv/bin/python -B tooling/review_records.py \
  --bundle templates/review-bundle.example.json \
  --subject templates/review-subject.example.json
```

The **trusted caller** supplies subject JSON independently: repository, change ID,
policy version, head SHA, base SHA, trigger IDs, builder ID and builder session ID.
Never derive the expected values by trusting candidate review records themselves.
Principal validation additionally requires the caller's `account_sha256` for the
actual drafted account; a record cannot select a different account and certify
it by hashing its own replacement. This field can also be supplied in gate facts.
Only `cleared` counts. Conditional work requires a new cleared record after the
conditions are resolved. A deferred high/critical concern cannot clear through an
agent decision; human exceptions stay distinct from evidence that a rule passed.
Unavailable reviews remain representable without manufactured findings.

The set checker requires adversarial and quality records for a triggered change,
and specialist coverage for every detected trigger. One qualified specialist may
cover several explicitly named triggers. Duplicate/forked/cyclic/dangling
supersession is rejected. A superseding non-clear record removes its old clearance;
old well-formed superseded records remain visible but do not count.

Gate CLI input can include the bundle in trusted `facts.review_bundle`, plus
`head_sha`, `base_sha`, `builder_id` and `builder_session_id`. The GitHub adapter
accepts the same explicit operator input:

```sh
.venv/bin/python -B tooling/github_gate.py --repo OWNER/REPO --pr NUMBER \
  --project /trusted/project.json --stage before_merge \
  --review-bundle /approved/review-bundle.json \
  --builder-id BUILDER --builder-session-id SESSION
```

The operator path is never taken from PR content. GitHub checks/account metadata
and supplied review metadata retain distinct provenance. Without the required
bundle, triggered merge/release evaluation fails closed. The fix-only automation
scope remains unchanged; other profiles retain their standing full review obligations.

## Interpret the result correctly

`metadata_conforming` means the bounded declarations, revision fields, supplied
bytes and role counts conform. It does **not** certify reviewer authenticity,
credential isolation, actual semantic review, physical-human acceptance, enforcement
or permission to merge/release. Reports carry these gaps explicitly.

Self-acceptance is labelled as account self-acceptance, never independent review.
An agent using a human account cannot be distinguished through that account's
GitHub metadata. Separate task identities and constrained credentials remain an
unmet operational control in the present shared-account setup. No new identity,
token scope, sandbox or network policy is installed merely by adding these rules.

The candidate dashboard derives catalogue counts and labels its candidate version
separately from the recorded adopter pin. Candidate-only requirements do not
silently become My EA obligations before an adoption update.
