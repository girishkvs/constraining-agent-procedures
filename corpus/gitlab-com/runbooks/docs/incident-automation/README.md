# Incident Automation (inc-automate)

GitLab webhook-driven service that pre-triages [incident.io](https://incident.io) Corrective Action follow-up issues so they land in GitLab ready for an engineer to act on — context, owner, and routing resolved automatically.

* **Repo**: <https://gitlab.com/gitlab-com/gl-infra/incident-automation>
* **Tracking issue**: <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28825>
* **Deployed via**: Runway on Cloud Run (staging + production)

## Summary

When a Corrective Action follow-up is created (or reopened) in GitLab, incident.io fires a GitLab Issue Hook to this service. The service:

1. Fetches the current GitLab issue and parses the parent `INC-XXXXX` reference.
2. Pulls incident details from the incident.io REST API.
3. Augments context via the incident.io MCP `ask_incident` responder-conversation search.
4. Asks Claude Sonnet 4.6 to synthesize a structured enrichment block (falls back to a deterministic minimal template when the MCP explicitly reports no linkage).
5. Rewrites the GitLab issue description between marker comments — **idempotent**; human edits outside the markers are preserved.
6. Uses Claude Haiku 4.5 + the runbooks service catalog + [`team_ownership/*.yaml`](https://gitlab.com/gitlab-com/gl-infra/incident-automation/-/tree/main/team_ownership) to pick `Service::` and `group::` labels, applies them, and `@`-mentions the team manager in a success comment.

Load-bearing failures (synthesis, description update) post a failure comment on the issue. Best-effort steps (MCP context, labels, manager mention) degrade silently.

## What the service checks before enriching a follow-up

Before doing any work on a webhook delivery, the service verifies:

* **`X-Gitlab-Token` header** matches the shared `GITLAB_WEBHOOK_SECRET` — unauthenticated deliveries are dropped.
* **Kill switch (`BOT_DISABLED`)** is off — when set, all actions halt for ops recovery. See [Operational Procedures for the inc-automate service](#operational-procedures-for-the-inc-automate-service).
* **Event type** is a GitLab Issue Hook for an `open` or `reopen` action — other actions are ignored.
* **Issue is a Corrective Action follow-up** created by the incident.io integration user — non-matching issues are skipped.
* **Parent `INC-XXXXX` reference** is present in the issue body — required to look up the parent incident.
* **Idempotency marker block** (`<!-- BEGIN/END inc-automate enrichment -->`) — re-runs replace only the block; human edits outside are preserved.

## Operational procedures for the inc-automate service

---

### Finding logs for a request id

Every enriched Corrective Action carries a `Request ID:` line in its
description footer and in the bot's success comment. The id correlates the
GitLab-visible action back to every log line the bot emitted while handling
that request — closing the audit trail Legal-Privacy required.

#### If the footer/comment has the id as a clickable link

Click it. The link lands you on the Cloud Logging query view filtered to
that request, in the GCP project this service runs in. No further steps.

#### If the id is not clickable (link template not configured)

The bot emits structured JSON logs to `stdout`, which Cloud Run forwards to
GCP Cloud Logging. In the Logs Explorer for the Runway-provisioned GCP
project, run:

```
resource.type = "cloud_run_revision"
resource.labels.service_name = "inc-automate"
jsonPayload.request_id = "<paste the request id here>"
```

Every log emitted while handling that webhook request will appear, in
order. Time range default is the last hour — extend if the issue is older.

If the bot has been deployed but the deeplink template hasn't been wired in
yet, set `LOGS_QUERY_URL_TEMPLATE` in
`.runway/inc-automate/env-production.yml` to the URL pattern in the
file's comments, and the next deploy will make all future ids clickable.

#### From Grafana / Loki (if shipping logs there too)

Use the Loki explore view with the equivalent filter:
`{service_name="inc-automate"} | json | request_id="<id>"`.

---

### Kill switch — halt all enrichment immediately

Use this when the bot is producing wrong or harmful output on real Corrective
Actions (e.g., posting confidential content, mis-routing labels, hitting an
API rate limit, or behaving unexpectedly after a deploy).

The kill switch is the `BOT_DISABLED` env var. When set to `true`, the handler
returns at the very top of `handle()` and **halts every action the bot would
take on the Corrective Action** — enrichment synthesis, GitLab description
update, `Service::` / `group::` label assignment, team-manager `@`-mention,
and the success comment are all skipped. The handler logs
`bot_killed_by_switch` and returns. The webhook receiver still returns 200 so
GitLab does NOT retry. Issues that arrive while the switch is on are dropped;
to retroactively enrich one after the switch is flipped back, re-trigger the
issue-creation event (e.g., close-and-reopen via the API, or recreate the
issue) so a fresh `action=open` webhook fires.

#### Emergency flip (fastest path — bypasses Runway / CI)

If you have `gcloud` access to the Runway project:

```sh
gcloud run services update inc-automate \
  --region us-central1 \
  --update-env-vars BOT_DISABLED=true \
  --project <runway-gcp-project>
```

The new revision rolls out in under a minute. Verify by checking the service's
revision env vars in the Cloud Run console.

#### Standard flip (preferred when not under time pressure)

1. Open an MR setting `BOT_DISABLED: 'true'` in
   `.runway/inc-automate/env-production.yml`.
2. Merge to `main`. The CI pipeline redeploys via the Runway template
   automatically. Expect ~5–10 minutes.

#### After flipping

1. Comment on the affected GitLab issue(s) explaining that enrichment was
   halted and pointing at the cause (incident channel, MR, etc.).
2. Open a follow-up issue in the [project tracker](https://gitlab.com/gitlab-com/gl-infra/inc-automate/-/issues)
   describing the trigger and the planned remediation. Label it
   `priority::1` so it's visible at the next standup.
3. SIRT notification: if the bot was leaking customer data, posting credentials,
   or otherwise touching the SIRT scope, file a SIRT ticket immediately per
   the [Security Incident Guide](https://handbook.gitlab.com/handbook/security/security-operations/sirt/engaging-security-on-call/).

#### Re-enabling

Reverse whichever flip you used (set `BOT_DISABLED=false` or delete the env
override). Verify a test Corrective Action enriches correctly before
considering the incident closed.

#### How to verify the switch is on

Watch the service logs in Grafana / Cloud Logging for the
`bot_killed_by_switch` event. If a webhook fires after the flip and you don't
see that event, the new revision hasn't rolled out yet.

---

## Claiming Corrective Actions for your team

The bot resolves the `group::` label and manager `@`-mention for each Corrective Action from files in [`team_ownership/`](https://gitlab.com/gitlab-com/gl-infra/incident-automation/-/tree/main/team_ownership) — one YAML per team. Adding or updating your team's file is how you tell the bot who owns what. By default it relies on the service catalog to assign ownership.

### When to add or edit a pattern

| Situation | Do you need a pattern? |
| --- | --- |
| Your team owns services in the runbooks [service catalog](https://gitlab.com/gitlab-com/runbooks/-/blob/master/services/service-catalog.yml) and the LLM lane is already routing correctly | **No.** Just create the file with `team_key` + `group_label` (+ `manager`) so the `owner → group::` map resolves. Leave `patterns: []`. |
| CAs about an internal tool, product name, or component that isn't in the catalog keep landing on other teams | **Yes.** Add a pattern for the name(s) so Lane 1 claims them deterministically. |
| A specific CA keeps getting mis-routed by the LLM (component name collides with another service) | **Yes.** Add a narrow pattern for that component, ideally with `service:` set so the correct `Service::` label lands too. |
| You want to grab everything mentioning your broad product area | **No — don't.** Broad patterns over-claim CAs that belong to other teams. Trust the LLM lane. |

### How to add or edit patterns

1. Find your team's file at `team_ownership/<team_key>.yaml`. If none exists, copy an existing one (e.g., [`team_ownership/observability.yaml`](team_ownership/observability.yaml)). The `team_key` MUST match the `owner` field in the service catalog for your services.
2. Add entries under `patterns:` using either shape:

   ```yaml
   patterns:
     # Plain string — only your group:: label is applied.
     - internal-tool-name
     # Mapped form (preferred) — also resolves a Service:: label from the catalog.
     - match: my-product-name
       service: my-catalog-service-name
   ```

   An example usecase from the Networking and Incident Management team

```yaml
   patterns:
  - match: haproxy
    service: frontend
  - match: gitlab-haproxy
    service: frontend
  - match: load balancer
    service: frontend
```

## Ownership

* **Team**: Networking and Incident Management

## Links

* [inc-automate repo](https://gitlab.com/gitlab-com/gl-infra/incident-automation)
* [Architecture doc](https://gitlab.com/gitlab-com/gl-infra/incident-automation/-/blob/main/docs/architecture.md) — flow, idempotency, cost model, security boundary
* [Deployment doc](https://gitlab.com/gitlab-com/gl-infra/incident-automation/-/blob/main/docs/deployment.md) — Runway provisioning + CI deploy pipeline
* [Runbook](https://gitlab.com/gitlab-com/gl-infra/incident-automation/-/blob/main/docs/runbook.md) — kill switch + ops procedures
* [Team ownership guide](https://gitlab.com/gitlab-com/gl-infra/incident-automation/-/blob/main/team_ownership/README.md) — how a team claims Corrective Actions
* [Tracking issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28825)
