# OrbitPipelineLatencyP95High

p95 end-to-end query pipeline latency is above 5 seconds for 10 minutes. Severity s3, fires after `10m`.

## Overview

The 95th percentile of end-to-end pipeline latency (compile, authorize,
execute, redact) exceeds 5 seconds. Normal query latency is 2-5s, so this
threshold marks the top of the healthy range. ClickHouse execution time
dominates the distribution; compilation and redaction are normally
milliseconds.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_pipeline_duration_seconds_bucket` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
histogram_quantile(0.95, sum by (env, environment, stage, le) (rate(gkg_query_pipeline_duration_seconds_bucket[5m]))) > 5
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- 10 minute `for` rides out short bursts; sustained contention is what fires it.

## Severities

- s3, no paging. Users see slow Orbit API responses; 5s is the top of the healthy 2-5s range.

## Verification

```promql
histogram_quantile(0.95, sum by (env, environment, stage, le) (rate(gkg_query_pipeline_duration_seconds_bucket[5m])))
```

Compare against the execution failure rate and indexer write volume for the
same window. Latency rising while indexer throughput rises means read/write
contention on the shared graph ClickHouse. Latency rising with a flat write
rate points at query mix (heavier queries) or ClickHouse Cloud replica
pressure.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Latency tracks indexer throughput | Read/write contention on the shared graph ClickHouse | Pause or scale down the indexer pools; queries recover immediately |
| Flat write rate, heavier query mix | Query weight or replica pressure | ClickHouse Cloud vertical autoscaling maximum is a config-mgmt terraform change |
| First slow queries after a quiet period | ClickHouse Cloud `idle_scaling` wake-up | Self-resolves in minutes; do not scale for it |

## Possible Resolutions

- Read/write contention: pause or scale down the indexer pools; queries
  recover immediately, indexing resumes later without loss.
- Sustained heavier query mix: ClickHouse Cloud vertical autoscaling has a
  configured maximum; raising it is a terraform change in config-mgmt
  (`environments/orbit-prd/clickhouse-cloud.tf`).
- After an idle period: `idle_scaling` wake-up latency self-resolves in
  minutes; do not scale for it.

## Dependencies

- Graph ClickHouse (ClickHouse Cloud), shared between webserver reads and indexer writes.

## Escalation

Ask in `#f_orbit_dev` (`context_systems`).

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
