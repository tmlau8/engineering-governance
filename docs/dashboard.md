# Local evidence and dashboard pilot

This adds a local Grafana dashboard alongside the published policy; it does not
change the policy release or My EA app. GitHub and local usage are read-only
sources. Runtime evidence and credentials never belong in a commit.

## Start on this Mac

Run from this repository. GitHub CLI must already be authenticated with read
access to the two private repositories. The pinned installer supports macOS ARM64
and needs Python 3.12+ for safe archive extraction; the application needs 3.9+.

```sh
python3.12 -B evidence/install.py
python3 -B evidence/manage.py prepare \
  --my-ea '/Users/albert/Projects/My EA' \
  --workspace '/Users/albert/Claude/Projects/Grow in AI Governance'
```

Before starting collection, register each repository using an adoption commit,
policy source revision and bundle digest approved outside the candidate checkout:

```sh
python3 -B tooling/repository_policy.py --register \
  --registry .runtime/repositories.json --cache .runtime/approved-policy \
  --workspace '/absolute/path/to/approved/clone' \
  --repository OWNER/REPOSITORY --repository-id NUMERIC_GITHUB_REPOSITORY_ID \
  --adoption-revision APPROVED_ADOPTION_COMMIT \
  --policy-source-revision APPROVED_POLICY_COMMIT \
  --manifest-sha256 APPROVED_MANIFEST_SHA256 --policy-version APPROVED_VERSION
python3 -B evidence/manage.py start
```

Replace the placeholders with independently selected approved values. A remote
URL alone cannot register a clone. Explicitly register additional clones; linked
worktrees are discovered automatically, including old branches missing policy
files. Registration is an operator declaration in owner-writable storage, not a
protected approval service. An explicitly draft adoption cannot be registered as
approved. The external pins remain authoritative over candidate branch files.

The initial `prepare` command retains legacy folder declarations for migration;
they do not authorize repository attribution. Unregistered declarations produce a
visible migration error and preserve prior usage snapshots without refreshing,
deleting or relabelling their counters. Register each intended repository, then
explicitly review/remove obsolete `usage_scopes` declarations in the private
settings. Do not treat broad-parent sessions as belonging to a repository.

Open [the local dashboard](http://localhost:3001/d/agentic-engineering-evidence).
Username and generated password are in `.runtime/secrets/credentials.json`, an
owner-only local file. Keep it private. Grafana remains authenticated and binds
only to localhost. The evidence API uses a separate bearer secret on port 8769;
Grafana stores that datasource secret server-side.

The first collection can take a few minutes. It repeats every five minutes;
Grafana refreshes every 30 seconds. Health shows last attempt, last success,
errors and stale evidence. Failed or incomplete collection preserves the last
good snapshot. It does not turn missing evidence green.

```sh
python3 -B evidence/manage.py stop
# Refresh once while stopped, without starting the dashboard:
python3 -B evidence/collect.py
# Remove collected data, credentials, Grafana state and local lifecycle logs:
python3 -B evidence/manage.py purge
# Also remove the downloaded software:
python3 -B evidence/manage.py purge --full
```

Choose one purge command; a second purge needs a newly prepared ownership marker.
Purge does not delete upstream GitHub/Codex records or claim physical secure erase.
Processes run while the Mac is awake; this is not an always-on hosted service.
Do not run a manual collection concurrently with the background collector.

## Views and their limits

- **Overview and changes:** open PRs plus closed PRs updated in the last 30 days,
  derived path risk, check/review metadata and PR
  links. More than 60 selected changes or incomplete pagination fails visibly.
  Risk observations use approved gate data and its approved project adapter,
  never the development branch's policy. Published 1.0 and candidate 1.1 data
  formats are supported for observation only; action gates are not evaluated.
  Planning is unknown where unevaluated. Historical authorisation is not inferred.
- **Repository coverage:** discovered worktrees, approved baseline, missing or
  diverged local installation, inventory freshness and explicit startup/merge
  enforcement gaps. Inventory does not establish instruction loading.
- **Candidate requirements:** shared automation coverage, observed subsets and explicit
  semantic gaps. All applicable rules remain mandatory. Zero controls are
  claimed natively enforced. Native protection is not established by collection.
- **Decisions:** account-level review/merge observations; independent review,
  exceptions, device, release and outcome evidence remain unknown/uncollected
  unless a future adapter supplies inspectable evidence.
- **Agent usage:** Codex input/cache/output/reasoning/total tokens, model, role,
  completed/aborted/open turns, reported duration and observed interval sum/union.
  Input includes cache and output includes reasoning. Totals are cumulative per
  retained session, not tokens consumed within a selectable date window or a bill.
  Turn duration includes tools/waiting and concurrent agents overlap.
- **Health/history:** successful snapshots, collection attempts and changes in
  retained observations. Local history is editable by its owner, not tamper-proof.

Usage import is an **experimental local structured-event adapter**, not an
official complete audit/billing API. Duplicate physical fragments are deduplicated;
counter decreases, shared prefixes, forks and malformed records are excluded
from exact token sums. Null counters/durations remain unknown. Folder association
does not establish a PR association. Earlier My EA sessions started in a broad
parent directory are excluded rather than assigned speculatively. No PR-level
cost or complete engineer/agent effort measurement is claimed.

New repository attribution requires the registered Git root and common-directory
identity to match. Nested foreign repositories are excluded. This observes current
identity, not historical ownership of a folder or proof that policy was followed.
Prompt/message/tool text,
source code, PR titles/bodies and credentials are not evidence fields. Retention
is 30 days of local observations; session counters may include older cumulative
usage. Scans have file/byte/event caps and fail visibly if incomplete. Vendor
process output is discarded; fixed lifecycle logs rotate at 1 MiB with one backup
and old files are removed on lifecycle operations after 30 days. Source errors
are fixed codes in the evidence store. No global Codex configuration is changed.

## Extension and validation

Source adapters emit bounded records into the SQLite observation store; the
read-only API and provisioned Grafana panels consume those records. Claude Code,
supported OpenTelemetry ingestion, explicit task/PR linking and release/outcome
artifacts are future adapters, **not implemented in this pilot**. Other projects
need reviewed repository/path/configuration adapters; onboarding is not automatic.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tooling:evidence \
  python3 -B -m unittest discover -s tests
```

Dependencies: [Grafana OSS](https://grafana.com/grafana/download?edition=oss&platform=mac)
13.3.0 with the official archive SHA256 pinned in `evidence/install.py`, and
[Grafana Labs Infinity](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/)
4.1.5. Plugin signatures remain checked by Grafana. This reuses maintained
dashboard/provisioning components; only the bounded source adapters and views
are custom code.
