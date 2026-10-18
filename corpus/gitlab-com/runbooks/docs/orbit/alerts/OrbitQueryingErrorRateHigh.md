# OrbitQueryingErrorRateHigh

Aggregate query error rate across all failure modes is above 5% for 5 minutes (the availability SLI). Severity s3, fires after `5m`.

## Overview

The aggregate error rate across the whole query pipeline (compilation,
security, execution) exceeds 5%. This is the availability SLI for querying:
users are getting failed Orbit API responses. Compile errors caused by bad
client input count toward this rate, so a single broken client with enough
volume can trip it without any server-side fault.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_pipeline_queries_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_queries_total{status!="ok"}[5m]))
  / sum by (env, environment, stage) (rate(gkg_query_pipeline_queries_total[5m])) > 0.05
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- Client-caused compile errors count toward this rate, so a single broken high-volume client can trip it without a server fault.

## Severities

- s3, no paging. This is the availability SLI for querying: users are getting failed Orbit API responses.

## Verification

Break the rate down by failure mode to find what is actually failing:

```promql
sum by (status) (rate(gkg_query_pipeline_queries_total{status!="ok"}[5m]))
```

- `compile_error` dominating: likely a client problem, cross-check
  `OrbitValidationFailedBurst`.
- `execution` dominating: ClickHouse is failing queries, check the graph
  ClickHouse health and load.
- `security` dominating: cross-check `OrbitSecurityRejected` and
  `OrbitAuthFilterMissing`.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| `compile_error` dominates the breakdown | Broken client input | Identify the client; cross-check OrbitValidationFailedBurst |
| `execution` dominates | ClickHouse failing queries | Follow [OrbitExecutionFailureRate](OrbitExecutionFailureRate.md) |
| `authorization` dominates | Rails redaction exchange failing | Follow [OrbitAuthorizationFailureRate](OrbitAuthorizationFailureRate.md) |
| `security` dominates | JWT problems | Follow [OrbitSecurityRejected](OrbitSecurityRejected.md) |

## Possible Resolutions

- Execution failures: reduce ClickHouse pressure (pause indexing pools) or
  scale the ClickHouse service; a heavy indexing burst degrading reads is the
  most common cause.
- Compile-error bursts from one caller: identify the client in the logs and
  fix or rate-limit it; the server needs no change.
- A fresh deploy lining up with the alert: roll back the image tag.

## Dependencies

- Graph ClickHouse (ClickHouse Cloud)
- GitLab Rails (JWT minting, internal Orbit API)
- Workhorse (result streaming).

## Escalation

Ask in `#f_orbit_dev` (`context_systems`). If ClickHouse itself is unhealthy,
check the ClickHouse Cloud console before escalating further.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
