# Moving to Tier-1: Service Team Engineer On-Call (STEOC)

For service teams **transitioning from a Tier-2 SME rotation to a Tier-1
Service Team Engineer On-Call (STEOC) rotation**. If your team is picking up
automated pages for its own service for the first time.

Source of truth for the program:
[Tier-1 for Service teams (STEOC)](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/on-call/tier-1/#tier-1-for-service-teams-steoc)
in the GitLab handbook (introduced in
[handbook!20736](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/20736);
epic [gl-infra&2067](https://gitlab.com/groups/gitlab-com/gl-infra/-/work_items/2067)).

This provides additional information around the program , to start onboarding , use the onboarding checklist template and create an issue to track your progress in [Production Engineering](https://gitlab.com/gitlab-com/gl-infra/production-engineering/)

---

## STEOC responsibilities

Service teams on Tier-1 rotations are responsible for:

1. Responding to pages for alerts configured to page their owned service within the defined SLO ( usually 15 minutes )
2. Investigating and resolving incidents related to their owned services.
3. Escalating to EOC or other Tier 2 and Tier 1 teams when the issue is
   outside the scope of their service or requires additional support.
4. Updating alert configurations to reduce noise and improve signal quality.
5. Updating alert playbooks for their team
5. Documenting findings and resolutions in the post-incident review.
6. Participating in [post-incident reviews](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-review/)
   and creating corrective actions to improve processes and prevent recurrence.

---

## How pages actually reach you

### Pages originating from Alerts

Three things must be true for an alert to page your team as STEOC:

1. The alert rule has `pager: pagerduty` (severity `s1` or `s2`).
2. The alert carries the `Service` label your team owns
3. These alerts are matched by an [Alert route defined in incident.io to page you](https://app.incident.io/gitlab/on-call/alert-routes/overview)

### Pages originating from humans

Like Tier-2 , teams will continue to remain pageable in case their insights are required during
an active incident.
Members belonging to the Tier-1 rotation will continue to fulfill all responsibilities of a Tier-2 rotation.

[Tier-2](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/on-call/tier-2/)

---

## During a page — quick reference

1. **Acknowledge** in incident.io (see [Acknowledging a page](#acknowledging-a-page)
   below). You have 15 minutes before it auto-escalates to EOC
2. **Open the runbook** linked from the alert to check for any existing alert playbooks
   (`docs/<service>/alerts/<AlertName>.md`).
3. **Check dashboards** — service dashboard first, then the SLI dashboard for
   the failing component.
4. **Decide**: silence (noise, file a tuning follow-up) → fix (in your
   control) → escalate to EOC (see [Escalating to EOC](#escalating-to-eoc)).
5. **Post-incident**: write up the resolution and file
   [corrective actions](#corrective-actions)

---

## Working the incident in incident.io

Full mechanics live in the runbooks' incident.io docs:

- [`docs/incident-io/oncall.md`](../docs/incident-io/oncall.md) —
  responder quick-start, alert-handling process, manual escalation.
- [`docs/incident-io/incident-management.md`](../docs/incident-io/incident-management.md)
  — declaring, retros, dashboard, Slack channel navigation.
- [`docs/incident-io/workflow-quick-reference.md`](../docs/incident-io/workflow-quick-reference.md)
  — end-to-end diagram.

The distilled path for STEOC:

### Acknowledging a page

- Install the [incident.io mobile app](https://help.incident.io/articles/3472064049-get-started-as-an-on-call-responder)
  (SAML via Okta). Without the app, you still get SMS + call, but the app is
  the fast path
  ([`docs/incident-io/oncall.md`](../docs/incident-io/oncall.md) lines 8–14).
- Acknowledge via the app or Slack; that stops the escalation timer and
  drops you into the incident's Slack channel.
- If a **triage** incident fired from your alert, join
  `#incidents-dotcom-triage` and **Accept** it (or **Merge**/**Decline**)
  ([`docs/incident-io/incident-management.md`](../docs/incident-io/incident-management.md) lines 9–11).

### Declaring an incident yourself

If the page is real user-facing impact and there's no incident yet, declare
one — don't wait.

- In any Slack channel: `/incident declare` → type `Gitlab.com`
  ([`docs/incident-io/incident-management.md`](../docs/incident-io/incident-management.md) lines 13–19).
- EOC is auto-assigned lead for S3/S4; IMOC for S1/S2 — you don't have to
  page them separately
  ([`docs/incident-io/oncall.md`](../docs/incident-io/oncall.md) line 45).
- Toggle **Block Deployments** / **Feature Flags** / **Confidential** via
  `/incident field` if needed.

If in doubt about severity, err high. It can be downgraded.

### While you're working the incident

- Investigate in the incident's Slack channel. Everything worth keeping
  should end up there.
- **Pin evidence** with `:pushpin:` (public → posts to the GitLab incident
  issue) or `:star:` (internal comment)
- **Use absolute time ranges** in every screenshot / dashboard link. In
  Grafana: `Share > Copy` (not "Shorten URL"). In Kibana:
  `Share > Get Links > Short URL`
- **Assign an action item** during investigation: react `:boom:` to a Slack
  message. Note: `:boom:` does **not** create a GitLab issue — it's just an
  in-incident action
- **Status updates**: react with `:mega:` on a Slack message, or use
  `/incident update` — either syncs to the public issue.

### Corrective actions

A task to do after the incident closes. Creates a GitLab
issue automatically. Use for the whole spectrum — revert a workaround,
add a runbook, tune an alert.

- Slash command: `/incident follow-up` in the incident channel, fill the
  form, assign owner
- Or react `:fast_forward:` on any Slack message — same result

If the incident was your service's fault, **expect to own the corrective
actions** , We have an automation to route Corrective actions automatically to teams that owns them but it can be wrong sometimes.

### Closing out

- Move the incident to **Monitoring** once mitigated (may auto-clear when
  alerts clear).
- Move to **Closed** when fully resolved; the Post-Incident workflow prompts
  for review + follow-ups [`docs/incident-io/oncall.md`](../docs/incident-io/oncall.md).
- Incident reviews are typically required for all S1/S2 incidents, or when
  triggered by the [incident review criteria](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-review/#the-criteria-which-triggers-a-review).

---

## Escalating to EOC

EOC is the primary responder for `GitLab Production` and owns platform-wide
incident coordination. You are the domain expert for your service. Escalate
when the problem crosses that line or you need an extra pair of eyes if your team is lost.

### Who does what

- **STEOC**: subject-matter expert for a specific service. Handles the
  service's own alerts, tunes noise, drives investigation for issues scoped
  to the service.
- **EOC**: primary GitLab.com on-call; holds production-change privileges,
  declares/leads incidents, coordinates cross-team response. Response SLA
  15 minutes [`on-call/checklists/eoc.md`](../on-call/checklists/eoc.md).
- **IMOC**: incident coordination for S1/S2. Auto-paged if EOC does not
  acknowledge within 15 minutes.
  [`on-call/checklists/eoc.md`](../on-call/checklists/imoc.md).
- **CMOC**: external comms (status.io, tweets)[`on-call/checklists/cmoc.md`](../on-call/checklists/imoc.md).
- **Other Tier 2/Tier 1 teams** : Domain experts for
  their areas. See [handbook for Tier-2 rotations](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/on-call/tier-2/#active-tier-2-rotations) and [for Tier-1 rotations](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/on-call/tier-1/#tier-1-for-service-teams-steoc) for the full list and when each is the right target.

### When to escalate to EOC

Escalate when any of these are true:

- **Impact is broader than your service** — multiple services degraded, or
  you suspect a shared dependency
- **You need production-change privileges you don't have** — for example Firewall access to make Cloudflare WAF changes
- **You are lost** and the alert is still paging /
  impact is unclear. Escalate to EOC.

### When NOT to escalate

- Alerts scoped to your service with a known runbook.
- Noisy or non-actionable alerts — tune or silence them
  ([`docs/monitoring/alert_tuning.md`](../docs/monitoring/alert_tuning.md),
  [`docs/monitoring/deleting-alerts.md`](../docs/monitoring/deleting-alerts.md)).
- Non-paging Slack-only notifications (S3/S4) with no ongoing symptom —
  investigate async, file a follow-up.
- Alerts you can silence via chatops on your own service.

If it's borderline, ping `@sre-oncall` in `#production` first for a read.
That alias notifies the current EOC **without paging** them[`on-call/checklists/eoc.md`](../on-call/checklists/eoc.md)

## Related Docs

| # | Doc | What it covers |
| --- | --- | --- |
| 1 | [`common-alerts.md`](./common-alerts.md) | The categories of alert you'll actually see (SLI apdex/error, traffic absent, saturation, custom, anomaly) and how to work each. |

---

## Feedback

This directory is meant to be edited by teams as they onboard. If something
is wrong, missing, or outdated for your service, open an MR.
