# OrbitExecutionFailureRate

ClickHouse query execution is failing, above 1 failure per minute. Severity s3, fires after `5m`.

## Overview

Compiled queries are failing at execution against the graph ClickHouse.
ClickHouse dominates query performance and shares its capacity between
webserver reads and indexer writes, so the usual cause is load: a heavy
indexing burst, a very heavy query, or the ClickHouse Cloud service itself
being degraded. Timeouts (`Code: 159 TIMEOUT_EXCEEDED`, the 30s execution
cap) land here too.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_pipeline_failed_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_failed_total{failure_reason="execution"}[5m])) * 60 > 1
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- The first queries after a quiet period can fail or crawl while ClickHouse Cloud wakes from idle; that self-resolves in minutes.

## Severities

- s3, no paging. Users see failed queries; indexing is unaffected unless ClickHouse itself is down.

## Verification

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_failed_total{failure_reason="execution"}[5m])) * 60
```

The webserver logs carry the ClickHouse error codes. Check the graph
ClickHouse service health and current load in the ClickHouse Cloud console
(Service Read Only role suffices), and whether indexer write volume rose at
the same time.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Failures rise with indexer write volume | Read/write contention on the shared graph ClickHouse | Pause the indexer pools ([Pause and resume indexing](../README.md#pause-and-resume-indexing)) |
| Same query fails repeatedly with `TIMEOUT_EXCEEDED` | One pathological query against the 30s execution cap | Identify it in the logs; the fix is query optimization, not scaling |
| Broad failures, ClickHouse console shows degradation | ClickHouse Cloud incident | Open a support case with ClickHouse Cloud |

## Possible Resolutions

- Indexing burst degrading reads: pause the indexer pools
  (`indexer.enabled: false` in the ArgoCD values); queries keep working while
  data goes stale.
- One pathological query timing out repeatedly: identify it in the logs; the
  fix is application-side query optimization, not scaling.
- ClickHouse Cloud degraded or waking from idle: `idle_scaling` makes the
  first queries after a quiet period slow; sustained failure is a support
  case with ClickHouse Cloud.

## Dependencies

- Graph ClickHouse (ClickHouse Cloud) dominates query performance and is shared with indexer writes.

## Escalation

Ask in `#f_orbit_dev` (`context_systems`). For a ClickHouse Cloud platform
problem, escalate through the ClickHouse Cloud support channel.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
