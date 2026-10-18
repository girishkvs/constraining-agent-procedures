<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Duo Agent Platform Service

* [Service Overview](https://dashboards.gitlab.net/d/duo-agent-platform-main/duo-agent-platform-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22duo-agent-platform%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::DuoAgentPlatform"


<!-- END_MARKER -->

## Summary

`duo-agent-platform` serves two purposes:

1. **Incident reporting umbrella.** It is used in incident.io so that all incidents affecting Duo
   Agent Platform in any way are properly tagged and recorded, regardless of which underlying
   component failed.
2. **Monitored virtual service.** It carries the SLIs for the GitLab **monolith** side of the Duo
   Agent Platform — signals emitted by Workhorse, and in future Rails and Sidekiq. It has no
   infrastructure of its own.

Note the asymmetry: the incident.io umbrella is broader than the error budget. An incident tagged
`Service::DuoAgentPlatform` may originate in `gitlab-lsp` or `duo-workflow-svc`, which are not
covered by this service's SLIs.

Duo Agent Platform spans multiple components, each with its own observability surface:

* **[gitlab-lsp](https://gitlab.com/gitlab-org/editor-extensions/gitlab-lsp)** — Language Server Protocol client running in the IDE and in CI jobs
* **GitLab (Rails)** — handles API requests, authorization, orchestration, and checkpoint storage
* **GitLab (Workhorse)** — proxies WebSocket connections to the Duo Workflow Service
* **Duo Workflow Service** — the gRPC backend that executes workflows (<https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist>), monitored separately as [`duo-workflow-svc`](../duo-workflow-svc/README.md)

### Relationship to `duo-workflow-svc`

| Service | Covers | Emitted by | Mimir tenant |
| --- | --- | --- | --- |
| [`duo-workflow-svc`](../duo-workflow-svc/README.md) | The Duo Workflow Service itself (gRPC server, LLM calls, tool use, checkpoints) | Cloud Run / Runway | `runway` |
| `duo-agent-platform` | The GitLab monolith side (Workhorse WebSocket handler; Rails/Sidekiq signals in future) | `ai-assisted` fleet, `sidekiq`, `web` | `gitlab-gprd`, `gitlab-gstg` |

The split is not cosmetic. The two halves are scraped into **different, isolated Mimir tenants**;
a recording rule evaluated in the `runway` tenant cannot read monolith series, and vice versa —
see [mimir-rules-jsonnet/README.md](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules-jsonnet/README.md).
Tenant selection is per-service (`tenants:` in the service definition), not per-SLI, so
monolith-emitted Duo Agent Platform SLIs need their own service definition.

## Monitoring/Alerting

### SLIs

| SLI | Request rate | Error rate | Apdex | Emitted by |
| --- | --- | --- | --- | --- |
| `workhorse_dws_sessions` | `gitlab_workhorse_duo_workflow_sessions_total` | `gitlab_workhorse_duo_workflow_session_errors_total` | — | `ai-assisted` |
| `workhorse_dws_http_actions` | `gitlab_workhorse_duo_workflow_http_actions_total` | `gitlab_workhorse_duo_workflow_http_action_errors_total` | `gitlab_workhorse_duo_workflow_http_action_duration_seconds_bucket` | `ai-assisted` |
| `sidekiq_stuck_workflow_cleanups` | `gitlab_duo_workflow_stuck_workflows_cleaned_total` | — (ops-rate only) | - | `sidekiq` |

### Stuck workflow cleanups

`sidekiq_stuck_workflow_cleanups` counts workflows that were found stuck and force-failed by
`Ai::DuoWorkflows::FailStuckWorkflowsWorker`. Every increment is a workflow that died silently and
had to be reaped, so a rise means users are losing workflows.

It is an **ops-rate-only SLI** — request rate with no error ratio and no apdex. The counter has no
denominator: the natural one would be "workflows started", which is not instrumented on the
monolith side today. The Workhorse session counter cannot substitute for it, because it lives on a
different fleet, counts gRPC streams rather than workflows, and the cleanup cron reaps workflows
that started hours earlier — there is no common time base. The framework also forbids it outright:
`emittedBy` is per-SLI rather than per-metric, and `validateTypeSelector` asserts the type selector
matches it, so a `type="sidekiq"` numerator over a `type="ai-assisted"` denominator fails to build.

Two consequences worth knowing:

* **It generates no alerts at all.** Ops-rate-only SLIs only ever produce `TrafficCessation` and
  `TrafficAbsent`, and both are disabled here — zero cleanups is the healthy state, so a cessation
  alert would fire on exactly the outcome we want. Watch it on the dashboard, not via a page.
* **Do not add `monitoringThresholds` to it.** Setting `errorRatio` or `apdexScore` on an SLI with
  no error rate or apdex metric is a silent no-op — the alert generator gates on
  `hasErrorRateSLO() && hasErrorRate()`, so a threshold with no matching metric produces nothing,
  with no warning. The service-level `errorRatio: 0.95` is inherited but equally inert here.

`serviceAggregation: false` keeps these background repair events out of the service ops rate so
they do not dilute the Workhorse SLIs.

### Workhorse metrics

Workhorse exposes six Prometheus counters and one histogram for the `duoworkflow` package,
declared in
[`workhorse/internal/ai_assist/duoworkflow/metrics.go`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/workhorse/internal/ai_assist/duoworkflow/metrics.go).
See the [duoworkflow package README](https://gitlab.com/gitlab-org/gitlab/-/blob/master/workhorse/internal/ai_assist/duoworkflow/README.md#metrics)
for full documentation including example PromQL queries. Five of the seven back the SLIs above: the
two session counters, and the three `http_action` metrics covering HTTP requests Workhorse issues
on behalf of a running workflow.

They are emitted by the Workhorse process on the **`ai-assisted` fleet**. The Duo Agent Platform
WebSocket handler is registered on the `/api/v4/ai/duo_workflows/ws` route (`duo_workflow_ws` in
`workhorse/internal/upstream/routes.go`), which is an API-pattern route in Workhorse's own routing
table — but HAProxy routes the request to `ai-assisted`, so that is the fleet whose counters move.
Hence the `type="ai-assisted"` selector and `emittedBy: ['ai-assisted']` in the service definition.
On that fleet the scrape job is plain `gitlab-workhorse`, not a fleet-suffixed variant like
`gitlab-workhorse-api`.

**Do not infer the fleet from the route table.** These counters are package-level `promauto`
counters registered at process init, so *every* Workhorse fleet exports all four of them with a
permanent value of `0`. Selecting the wrong `type` therefore produces a recorded series that reads
`0` rather than returning no data, which is indistinguishable from a genuinely idle feature.
Confirm the fleet empirically:

```promql
sum by (type) (increase(gitlab_workhorse_duo_workflow_sessions_total{env="gprd"}[24h]))
```

### Alerts

| Alert | SLI | Type | Severity |
| --- | --- | --- | --- |
| `DuoAgentPlatformServiceWorkhorseDwsSessionsErrorSLOViolation` | `workhorse_dws_sessions` | Error | `s2` |
| `DuoAgentPlatformServiceWorkhorseDwsHttpActionsErrorSLOViolation` | `workhorse_dws_http_actions` | Error | `s3` |
| `DuoAgentPlatformServiceWorkhorseDwsHttpActionsApdexSLOViolation` | `workhorse_dws_http_actions` | Apdex | `s3` |

`workhorse_dws_http_actions` is deliberately `s3` so that it does not page while its thresholds
are still guesses. Promote it to `s2` once a baseline has been measured and the thresholds
adjusted — see [Known gaps](#known-gaps).

`sidekiq_stuck_workflow_cleanups` produces no alerts — see [Stuck workflow
cleanups](#stuck-workflow-cleanups).

Traffic cessation and traffic absent alerts are **intentionally disabled**
(`trafficCessationAlertConfig: false`) on every SLI here. Duo Agent Platform WebSocket traffic can
legitimately fall to zero when the feature is idle, and these SLIs have no established baseline
ops rate yet — see [Known gaps](#known-gaps). Enable them once real volume is visible.

## Troubleshooting

Because this is a virtual service, triage usually means following the signal to the component that
emits it:

1. **Check the service overview dashboard** to see which SLI is degraded.
2. **`workhorse_dws_sessions` errors** are failures on the gRPC `ExecuteWorkflow` stream between
   Workhorse and the Duo Workflow Service. The `grpc_code` label points at the cause:
   `ResourceExhausted` and `DeadlineExceeded` usually indicate DWS-side pressure, `Unavailable` a
   connectivity or deployment issue. Cross-check
   [`duo-workflow-svc`](../duo-workflow-svc/README.md) before suspecting the monolith —
   `duo-workflow-svc` is a declared dependency, so its alerts may already explain the failure.
3. **`workhorse_dws_http_actions` errors** are transport-level failures on HTTP requests Workhorse
   makes on behalf of a running workflow. The `error_type` label distinguishes `timeout`,
   `aborted`, and size-limit failures. Remember that HTTP 4xx/5xx responses are **not** counted
   here — if the workflow is failing but this SLI is clean, break the request rate down by
   `status_code` to see whether the remote endpoint is returning errors. A degraded apdex with a
   clean error rate usually means a slow remote endpoint rather than a Workhorse problem.
4. **`sidekiq_stuck_workflow_cleanups` rising** means workflows are dying without reporting a
   failure, and the cron is reaping them. Because it is ops-rate only there is no alert and no
   error budget, so it has to be read against the other SLIs: a rise here with a clean
   `workhorse_dws_sessions` points at the workflow dying after the gRPC stream closed cleanly —
   look at `duo-workflow-svc` and the Rails side rather than Workhorse. Because the cron batches,
   expect a step change on its schedule rather than a smooth curve, and read it over hours:

   ```promql
   sum by (status) (increase(gitlab_duo_workflow_stuck_workflows_cleaned_total{env="gprd"}[24h]))
   ```

## Known gaps

* **No observed baseline.** These SLIs have never recorded real data. They first lived on
  `duo-workflow-svc`, selecting `type="duo-workflow-svc"` in the `runway` tenant, where neither the
  tenant nor the `type` label ever matched. Moving them here fixed the tenant but selected
  `type="api"`, which recorded a flat zero. Only the correction to `type="ai-assisted"` produces
  real numbers, and recording rules do not backfill — expect an empty history before that change
  was deployed. The `errorRatio: 0.95` thresholds have been carried through all three revisions
  unchanged and have never been checked against observed data. The same applies to the
  `workhorse_dws_http_actions` thresholds (`apdexScore: 0.9`, `errorRatio: 0.95`) and its 1s/5s
  apdex buckets, which were chosen from `prometheus.DefBuckets` without a baseline. That SLI is
  held at `s3` for this reason; promote it to `s2` once the thresholds are grounded in observed
  data.
* **No denominator for stuck workflow cleanups.** `gitlab_duo_workflow_stuck_workflows_cleaned_total`
  is now covered by the `sidekiq_stuck_workflow_cleanups` SLI, but only as an ops rate — there is
  still no workflows-created counter to divide it by, so there is no error ratio and no error
  budget. Once one exists, convert this into a proper ratio SLI and give it an SLO.
* The broader Rails-side instrumentation gap is catalogued in
  [GitLab Duo Agent Platform observability (Rails)](https://docs.gitlab.com/development/ai_features/duo_agent_platform_observability/),
  which lists ~14 planned `gitlab_duo_agent_platform_*` metrics. Those should land here as they
  ship.

## Service Changes

* [SLI definitions](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/duo-agent-platform.jsonnet)
* [Dashboard source](https://gitlab.com/gitlab-com/runbooks/-/blob/master/dashboards/duo-agent-platform/)

## Links to further Documentation

* [Duo Agent Platform user documentation](https://docs.gitlab.com/user/duo_agent_platform/)
* [Duo Agent Platform observability (Rails)](https://docs.gitlab.com/development/ai_features/duo_agent_platform_observability/)
* [Duo Workflow architecture design document](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/duo_workflow/)
* [SLO alerting howto](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/)
