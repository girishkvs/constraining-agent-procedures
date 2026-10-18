<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Duo Workflow Service

* [Service Overview](https://dashboards.gitlab.net/d/duo-workflow-svc-main/duo-workflow-svc-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22duo-workflow-svc%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::DuoWorkflow"

## Logging

* [gitlab.com](https://cloudlogging.app.goo.gl/5zAqZnsS2pdrgn4S8)
* [staging.gitlab.com](https://cloudlogging.app.goo.gl/76p7VVzJr4aLSGua8)

<!-- END_MARKER -->

### Log Filtering Tips

#### Service Logs

* In `gitlab-runway-production` or `gitlab-runway-staging` projects
* Use filter: `resource.labels.service_name="duo-workflow-svc"`

#### Billing Events (Staging)

* Successful workflows in staging send billing events with token consumption data to:
  * Endpoint: `https://billing.stgsub.gitlab.net`
* To check billing-related logs:
  * Filter: `jsonPayload.logger="workflow_checkpointer"`
  * Staging logs URL: [Workflow Checkpointer Logs](https://console.cloud.google.com/logs/query;query=resource.labels.service_name%3D%22duo-workflow-svc%22%0AjsonPayload.logger%3D%22workflow_checkpointer%22?project=gitlab-runway-staging)

## Quick Links

* [Logs](https://cloudlogging.app.goo.gl/5zAqZnsS2pdrgn4S8)
* [Langsmith traces](https://smith.langchain.com/o/477de7ad-583e-47b6-a1c4-c4a0300e7aca/projects/p/a4e68128-258a-41eb-b766-9414684ce34d?timeModel=%7B%22duration%22%3A%227d%22%7D)
* [Sentry error tracking](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=36&referrer=sidebar)
* [Grafana Service Overview](https://dashboards.gitlab.net/d/duo-workflow-svc-main/duo-workflow-svc-overview)
* [Grafana Error Breakdown Dashboard](https://dashboards.gitlab.net/d/duo-workflow-svc-errors-breakdown)
* [Log based dashboard](https://dashboards.gitlab.net/d/3d9c7954-2669-4782-9206-b714c8a589fa/dws-log-based-dashboard)

## Before starting the investigation

NOTE: Do **NOT** expose customer's RED data in public issues. Redact them or make a confidential issue if you're unsure.

Before starting the investigation, please collect the following information:

* GitLab username for the user that encountered the bug (e.g. `@johndoe`)
* What happened (e.g. User asked a question in Flows tab in VSCode extension and the agent platform did not respond)
* When it happened (e.g. Around 2024/09/16 01:00 UTC)
* Is it happening in .com, self-managed or dedicated instances? If self-managed or dedicated, what GitLab version they're using?
* GitLab Workflow VS Code extension version (e.g. v.6.26.1) if applicable.
* If using VSCode extension, ask whether they use gRPC connection or webhooks to communicate.
* Are there executor logs?
  * For VSCode -> Command + P -> Show Extension Logs -> Choose GitLab Language Server from dropdown
  * For flows running in CI -> CI job logs
* What is the flow type (chat for agentic chat, software_development if it's Flows tab, issue to MR, or a custom flow etc.)
* How often it happens (e.g. It happens everytime)
* Steps to reproduce (e.g. 1. Ask a question "xxx" 2. Click ...)
* AI Gateway or self-managed AI Gateway (If they use custom models, it's likely latter.)
* A link to a Slack discussion, if any.

## Workflows fail to start (startup connection failures)

WARNING: **Quiet dashboards do not rule this out.** Startup failures can happen on the
runner/executor side, before requests are visible in normal
[Duo Workflow Service dashboards](https://dashboards.gitlab.net/d/duo-workflow-svc-main/duo-workflow-svc-overview)
— which may look normal even during widespread startup failures. With multiple "fails to start"
reports, check logs before trusting the dashboards.

**Where to look:**

* **CI job logs** — primary source; open them directly from a failing session/pipeline link.
* **Executor logs** (local IDE flows) — the EOC can't pull these; ask the reporter to capture
  them (see the intake checklist above).

**Common fingerprints:** `WebSocketWorkflowClient`, `1006`, `Failed to connect`, `WebSocket error`.
These are examples, not an exhaustive list.

**Default vs. custom config:** if only default setups are affected while projects with custom
`agent-config.yml` or custom images still work, suspect the startup/connection path rather than a
broad service failure.

**Escalate** to the `tier2 - AI` on-call rotation: use `/inc escalate` in Slack and select
`tier2 - AI` from the "Oncall team" dropdown (see
[How to Escalate](https://gitlab.com/gitlab-com/runbooks/-/tree/master/on-call#how-to-escalate)).
Include failing session links and CI/executor logs.

## Summary

The Duo Workflow Service is a Python service that manages and executes Duo Agent Platform sessions using
LangGraph. Within AI-Gateway, it handles communication between the user interface, the LLM provider, and the executors,
while maintaining workflow state through periodic checkpoints saved to GitLab. This service
provides the intelligence layer that interprets user goals, plans execution steps, processes LLM responses,
and orchestrates the necessary commands to complete tasks, all while maintaining a secure boundary
between untrusted code execution and the core GitLab infrastructure. .

## Architecture

See design document at <https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/duo_workflow/>

<!-- ## Performance -->

## Scalability

Duo Workflow Service will autoscale with traffic. To manually scale, update [`runway-production.yml`](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/main/.runway/duo-workflow-svc/runway-production.yml) based on [documentation](../runway/README.md#scalability).

It is also possible to directly edit the tunables for the `duo-workflow-svc` service via the [Cloud Run console's Edit YAML interface](https://console.cloud.google.com/run/detail/us-east1/duo-workflow-svc/yaml/view?project=gitlab-runway-production).  This takes effect faster, but be sure to make the equivalent updates to the `runway-production.yml` as described above; otherwise the next deploy will revert your manual changes to the service YAML.

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Deployment

Duo Workflow Service is deployed through Runway from the same monorepo — and the same
`model-gateway` image — as AI Gateway (built from
[`ai-assist`](https://gitlab.com/gitlab-org/security/modelops/applied-ml/code-suggestions/ai-assist),
private; the image entrypoint runs Duo Workflow Service when `ENABLE_DUO_WORKFLOW_SERVICE=true`),
via its own Runway deployment project:

* [Runway Deployment project](https://gitlab.com/gitlab-com/gl-infra/platform/runway/deployments/duo-workflow-svc)

For more details on the Runway deployment model, refer to the [Runway runbook](../runway/README.md).

### Monitoring Deploys

To quickly find out **when the last deploy went out and what changes it included**, use
the [`ai-gateway-deploys` Claude skill](../../.agents/skills/ai-gateway-deploys/SKILL.md).

The skill covers both AI Gateway and Duo Workflow Service — just ask about DWS and it
will use the correct deployment project automatically.

**Typical questions it answers:**

* *"What's currently deployed to Duo Workflow Service?"*
* *"What changed in the last DWS deploy?"*

The skill requires the GitLab MCP connector to be enabled. The output leads with the
deploy time and a diff URL so they're easy to spot at a glance.

For a deterministic check of the **live** running revision per region — and whether a
specific MR/commit is deployed — use the [`scripts/ai-gateway-deployed-revisions`](../../scripts/ai-gateway-deployed-revisions)
script (`--service duo-workflow-svc`), which reads Cloud Run state directly (requires
`gcloud` access to `gitlab-runway-production`).

**Key pipeline project:**

| Pipeline | Project |
| --- | --- |
| Regular production | [`duo-workflow-svc`](https://gitlab.com/gitlab-com/gl-infra/platform/runway/deployments/duo-workflow-svc) |

**Source repo for diffs:** [`ai-assist`](https://gitlab.com/gitlab-org/security/modelops/applied-ml/code-suggestions/ai-assist) (private)

## Monitoring/Alerting

Duo Workflow Service uses both [custom metrics](../../metrics-catalog/services/duo-workflow-svc.jsonnet) scraped from application and default metrics provided by [Runway](../runway/README.md#monitoringalerting). These alerts are routed to `g_agent-execution` in Slack. To route to different channel, refer to [documentation](../uncategorized/alert-routing.md).

Currently, error logs from Sentry also trigger alerts. These alerts are directed to `g_duo_workflow_alerts` in Slack.

## Determining What Is Currently Deployed

Duo Workflow Service is deployed from the same repository and pipeline as AI Gateway, so the procedure for finding the live revision per region — and for checking whether a given MR or commit is included in it — is documented once in [AI Gateway: Determining What Is Currently Deployed](../ai-gateway/README.md#determining-what-is-currently-deployed). Pass `--service duo-workflow-svc` to query this service instead of AI Gateway.

<!-- ## Links to further Documentation -->
