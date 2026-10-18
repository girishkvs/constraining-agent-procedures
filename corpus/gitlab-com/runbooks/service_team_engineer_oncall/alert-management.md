# Alert Management for the Service Team Engineer On-Call (STEOC)

What you can expect to be paged for once your service is opted into
`pager: pagerduty` routing, and how to work each category. The categories below
apply to any service whose SLIs and thresholds are defined under
`metrics-catalog/services/<service>.jsonnet`

Alerts in this repo are auto-generated from that file. You do not write PromQL
by hand for these — you edit the metric definitions and thresholds, and
`make generate` produces the Mimir alert rules under
`mimir-rules/<tenant>/<service>/`.

## How to read an alert page

Every alert reaching PagerDuty carries the same shape. When you open the
incident, look for:

- **Alertname** — Composed as `<Service><SliName><AlertType><Aggregation>`. Parse it — the
  name tells you the SLI and the failure mode before you open anything.
- **Labels** (the routing/grouping key set):
  - `type` — service identifier (e.g. `gitaly`, `ai-gateway`, `ci-runners`).
    This is what STEOC opt-in routes on.
  - `stage` — `main` or `cny` (canary).
  - `tier` — service tier (e.g. `sv`, `db`, `stor`, `runners`).
  - `shard` — populated on shard-level alerts (e.g. a Gitaly storage shard or
    a runners shard).
  - `component` — the SLI name (e.g. `gitaly`, `completions`, `polling`).
  - `sli_type` — `apdex`, `error`, or `ops`.
  - `alert_class` — `slo_violation`, `traffic_cessation`, or unset (custom / saturation).
  - `alert_type` — `symptom` (user-impacting) vs `cause` (leading indicator).
  - `severity` — `s1`..`s4`. `s1/s2` page; `s3/s4` typically Slack-only.
  - `pager: pagerduty` — the flag that put this in your rotation.
  - `feature_category` — e.g. `source_code_management`, `ai_abstraction_layer`.
  - `window` — burn-rate window (`1h` or `6h`).
- **Annotations**:
  - `title` — human-readable summary with `stage`/`shard` interpolated.
  - `description` — what the SLI monitors and current value.
  - `grafana_dashboard_link` — pre-filtered dashboard for this alert.
  - `runbook` — a path like `<service>/#alerts` or
    `<service>/troubleshooting-guide/`. Alertmanager expands this into a
    `docs/<runbook>` URL in this repo. Named per-alert runbooks live at
    `docs/<service>/alerts/<AlertName>.md` when present.
  - `promql_template_1` — copy-paste-able PromQL with labels already
    substituted, for pasting into Thanos/Grafana Explore.

Rule of thumb: read the title, look at the linked dashboard first, then the
linked runbook. Only crack open the PromQL if the dashboard is ambiguous.

## Category 1 — SLI apdex / latency degradation

- **Alertname pattern**: `<Service>Service<Sli>ApdexSLOViolation[SingleShard|SingleNode|Regional]`
- **Labels**: `alert_class=slo_violation`, `sli_type=apdex`, `alert_type=symptom`,
  `slo_alert=yes`, `severity=s2`, `pager=pagerduty`.
- **Triggers when**: the SLI's apdex ratio breaches its multi-window,
  multi-burn-rate threshold — both a long window (1h or 6h) and a short window
  (5m or 30m) must exceed the burn-rate budget simultaneously, with the SLI
  above its minimum ops rate. Thresholds come from
  `monitoringThresholds.apdexScore` (and any per-shard overrides) in
  `metrics-catalog/services/<service>.jsonnet`.
- **Usually means**: real latency degradation for a component — a class of
  requests is slower than the SLO allows. Common causes vary by service, but
  cluster into:
  - Capacity: fleet undersized / autoscaler stuck / cloud quota hit /
    storage under-provisioned.
  - Upstream slowness: a dependency (Postgres, Redis, Gitaly, an LLM
    provider) is answering slowly.
  - Bad deploy or config change on the service itself.
  - Traffic spike concentrated on one shard/node.
- **First response**:
  1. Open the `grafana_dashboard_link` from the alert. Locked time range.
  2. Check whether it's one shard/node or many — the `shard` label narrows it.
  3. Cross-check: saturation dashboard, recent deploys, cloud/quota panel.
  4. Pivot into logs via the SLI's `toolingLinks` (Kibana / logs.gitlab.net)
     filtered by the affected shard.
- **Silence vs fix vs escalate**:
  - **Silence** only for known, tracked capacity events (link the CR or issue).
    Use `alert_tuning.md` if you're doing this often — it means the threshold
    is wrong.
  - **Fix** if you own the lever (scale up, unblock autoscaler, revert, fail
    over a node).
  - **Escalate to EOC** if the apdex drop correlates with a Rails/Postgres
    signal or spans multiple services
- **Runbook**: `docs/<service>/alerts/<AlertName>.md` when a per-alert file
  exists; otherwise the `runbook` annotation resolves to
  `docs/<service>/README.md#alerts`.
- **Examples**: `GitalyServiceGitalyApdexSLOViolation`,
`AiGatewayServiceCompletionsApdexSLOViolation`,`CiRunnersServiceCiRunnerJobsApdexSLOViolationSingleShard`.

## Category 2 — SLI error rate

- **Alertname pattern**: `<Service>Service<Sli>ErrorSLOViolation[SingleShard|...]`.
- **Labels**: `alert_class=slo_violation`, `sli_type=error`, same severity/pager
  as apdex above.
- **Triggers when**: error ratio breaches the multi-window burn-rate threshold
  from `monitoringThresholds.errorRatio`. The error definition comes from the
  SLI's `errorRate` selector — e.g. gRPC non-OK codes for a Gitaly RPC,
  upstream 5xx for an AI completion, HTTP 5xx on `/api/v4/jobs/request` for a
  runners polling SLI.
- **Usually means**: a real error spike on the SLI. Root causes cluster into:
  - Downstream failure — Postgres, Redis, object storage, upstream RPC, an
    external provider.
  - Fleet health — a node/pod unhealthy, TLS cert expired, upstream
    connectivity broken.
  - Bad deploy — check `#production` and config-mgmt merges in the last hour.
- **First response**:
  1. Grafana link in the alert → error ratio panel, filter by `stage`/`shard`.
  2. Logs via the SLI's `toolingLinks` (Kibana / logs.gitlab.net on the
     relevant index) — pre-built into the jsonnet.
  3. Correlate with any current EOC investigation in `#production` — a
     platform-wide issue often looks like your error rate.
- **Silence vs fix vs escalate**:
  - **Fix** if the cause is on your service (roll a pod/node, revert config).
  - **Escalate to EOC** for anything database-adjacent or cross-service. Do not
    burn 30 minutes trying to diagnose Postgres slowness yourself.
- **Runbook**: per-alert `.md` files under `docs/<service>/alerts/` when
  present; otherwise the `runbook` annotation resolves to
  `docs/<service>/README.md#alerts`.
- Examples: `GitalyServiceGitalyErrorSLOViolation`,
    `AiGatewayServiceCompletionsErrorSLOViolation`,
    `CiRunnersServicePollingErrorSLOViolation`.

## Category 3 — Traffic cessation / traffic absent

- **Alertname pattern**:
  - `<Service>Service<Sli>TrafficCessation[SingleShard|...]` — SLI is present
    but reads zero.
  - `<Service>Service<Sli>TrafficAbsent[SingleShard|...]` — series has
    disappeared entirely.
- **Labels**: `alert_class=traffic_cessation`, `alert_type=cause`,
  `slo_alert=no`, `severity=s2`, `pager=pagerduty`.
- **Triggers when**:
  - Cessation: `rate_30m == 0` now, but `>= 0.16667 ops/s` an hour ago.
  - Absent: series existed 1h ago (`offset 1h`) but no longer exists.
  - Only fires on the `main` stage for component-level alerts; shard-level
    fires on all stages.
- **Usually means** — this is the most-misread category:
  - **Real outage** — nothing is reaching your service. Rare but urgent.
  - **Metric plumbing broken** — a scrape config change, an exporter down, a
    label rename, or an SLI's selector no longer matching. This is the common
    case, and it looks scary.
  - **Legitimate quiet period** — a low-traffic shard emptied. The
    `minimumSamplesForTrafficCessation` guard (300 samples in 30m, see
    `libsonnet/alerts/service-component-alerts.libsonnet` line 13) makes this
    rarer, but not impossible on off-hours shards.
- **First response**:
  1. Check the linked Grafana panel over a 24h window — is the drop cliff-edge
     or gradual?
  2. Check the raw source metric (from `promql_template_1`) — does it exist
     at all? If not, the selector or exporter is the problem, not the service.
  3. Check for recent MRs to the SLI definition or to
     `mimir-rules-jsonnet/`.
  4. If real user traffic is missing, treat as an SLI error / apdex event and
     escalate.
- **Silence vs fix vs escalate**:
  - **Silence** only after you've confirmed it's a metric-plumbing issue and
    filed a fix. Silences without a linked issue rot.
  - **Escalate** immediately if real traffic is gone.
- **Runbook**: same anchor as SLI alerts — `docs/<service>/README.md#alerts`.
- **Examples**: `GitalyServiceGitalyTrafficCessation`,
    `AiGatewayServiceCompletionsTrafficAbsent`,
    `CiRunnersServiceLoadbalancerTrafficCessation`.

## Category 4 — Saturation

- **Alertname pattern**:
  - `component_saturation_slo_out_of_bounds:<component>` — a resource is at or
    over its saturation SLO right now.
  - `ComponentResourceRunningOut_<component>` — linear prediction says it will
    breach within 3h or 6h.
- **Labels**: `alert_type=cause`, `severity=s3` (default), typically **no**
  `pager: pagerduty` — most saturation alerts land in Slack, not PagerDuty.
  Check `severity`; if you see `s2` on one, it's been explicitly promoted.
- **Triggers when**:
  `gitlab_component_saturation:ratio{component=…, type=…} > slo:max:hard:...`.
  Components come from `capacityPlanning.components` in the service jsonnet
  plus the shared saturation library.
- **Usually means**: leading indicator — user impact hasn't happened yet, but
  the resource is about to hit a wall. Service-specific saturation
  components measure headroom against a configured max (e.g. Gitaly disk on a
  storage node, runner-shard capacity vs. its cap, LLM-provider rate-limit
  budget).
- **First response**:
  1. Open the linked saturation dashboard
     (`alerts-sat_<component>` — e.g. `alerts-sat_cpu`).
  2. Determine whether it's a single node/shard or the whole fleet.
  3. For `RunningOut_*`, look at the trend, not the instantaneous value —
     the alert is predicting the future.
- **Silence vs fix vs escalate**:
  - **Fix** — scale, tune, or increase the saturation SLO if it's been
    calibrated to the wrong number. `docs/monitoring/alert_tuning.md`.
  - **Silence** only during a planned capacity event, with a linked CR.
  - **Escalate** only if you cannot scale in time — most saturation alerts
    are a STEOC-owned fix, not an EOC problem.
- **Runbook**: `docs/{{ $labels.type }}/README.md`, plus the linked
  saturation dashboard.
- **Examples**: `component_saturation_slo_out_of_bounds:cpu`,
    `component_saturation_slo_out_of_bounds:memory`,
    `component_saturation_slo_out_of_bounds:disk_space`,
    `component_saturation_slo_out_of_bounds:open_fds`,
    `ComponentResourceRunningOut_disk_space`. Services can also register
    service-specific components (e.g. per-shard fleet headroom for runners,
    per-storage disk usage for Gitaly).

## Category 5 — Service-specific custom alerts

Manually-authored alerts under `mimir-rules/<tenant>/<service>/*.yml`. Not
derived from the metrics catalog — hand-written for behaviors that don't fit
an SLI. Every service tends to accumulate a handful of these; look for
files in your service's directory that aren't tagged `autogenerated-`.

Typical shapes you'll see:

- **Upstream / dependency signals** — a specific queue time, retry count, or
  provider error code that a plain error-ratio SLI would smear over. E.g. a
  Gitaly cache-miss rate, an AI-provider quota-exceeded rate, a CI workhorse
  queue-time p90.
- **Config / plumbing failures that are silent to the SLO** — a config reload
  error, a certificate expiry, an autoscaler that can't drain its queue. The
  service keeps serving, so error-ratio doesn't move; this alert is your
  only signal.
- **Anti-abuse / behavioral thresholds** — cumulative resource use that
  crosses a hand-tuned line (crypto-mining shape on runners, prompt-abuse
  patterns on AI, unusual repo-access shapes on Gitaly). Usually loops in
  Trust & Safety in addition to SEOC.
- **Component-internal indicators** — errors in a specific code path
  (trace-archive failures, replication lag, cache thrash) that predict
  user-visible failure by a few minutes.

## Category 6 — Service anomaly detection

- **Alertname**: `service_ops_out_of_bounds_upper_5m`,
  `service_ops_out_of_bounds_lower_5m`.
- **Source**: `libsonnet/alerts/service-anomaly-detection-alerts.libsonnet`,
  auto-generated per service.
- **Triggers when**: `gitlab_service_ops:rate_5m` diverges from its
  weekly-baseline prediction by more than a fixed number of standard
  deviations for 5m.
- **Usually means**: traffic level is unusual for this time-of-week. Upper
  bound is often abuse or a retry storm; lower bound is often a client
  outage or a broken deploy on the caller side.
- **First response**: check the dashboard (`general-service/service-platform-metrics`)
  linked from the alert. Correlate with error rate and apdex. Read
  `docs/monitoring/definition-service-ops-rate.md`.
- **Severity**: typically `s3` / cause. Don't wake anyone up for this alone
  — but do investigate before it turns into a symptom alert.

## Category 7 — Kube-cause alerts (K8s-based services only)

Fires for services deployed to Kubernetes (e.g. AI Gateway).

- **Source**: `libsonnet/alerts/kube-cause-alerts.libsonnet`,
  `libsonnet/alerts/kube-pods-unschedulable-alerts.libsonnet`.
- **Alertnames**: `KubeContainersWaitingInError`, `KubePodsUnschedulable`,
  HPA-maxed variants.
- **Means**: pods in `CrashLoopBackOff` / `ImagePullBackOff`, or HPA at
  ceiling. SLI apdex/error alerts usually follow within minutes.
- **First response**: `glsh kube use-cluster <env>`, then `kubectl get pods`,
  `describe pod`, `logs`. See `k8s-info` skill for the canonical flow.

## If Runbooks do not exist for your alerts

Add a runbook for a specific alert, by adding a Markdown file at:

```
docs/<service>/alerts/<AlertName>.md
```

## Related

- Service definition: `metrics-catalog/services/<service>.jsonnet`
- Alert generation library: `libsonnet/alerts/` (in particular
  `service-component-alerts.libsonnet`, `service-anomaly-detection-alerts.libsonnet`)
- Generated Mimir rules: `mimir-rules/<tenant>/<service>/`
- Per-alert runbooks: `docs/<service>/alerts/`
- Alerting model background: `docs/monitoring/alerts_manual.md`
- Metrics catalog concepts: `metrics-catalog/README.md`
- Escalation to EOC: `service_team_engineer_oncall/README.md` (see [Escalating to EOC](./README.md#escalating-to-eoc))
