# OrbitPipelinePostCompileErrorRateHigh

Post-compile failure rate is above 1%, isolating server-side reliability from client-input quality. Severity s3, fires after `5m`.

## Overview

The failure rate of queries that passed compilation exceeds 1%. Excluding
`compile_error` filters out bad client input, so what remains (execution,
authorization, security, internal) is the server's own reliability. This
mirrors the "Pipeline success rate (1h), post-compile" gauge on the overview
dashboard. When `OrbitQueryingErrorRateHigh` fires but this one does not, the
problem is client input, not the service.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_pipeline_queries_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_queries_total{status!~"ok|compile_error"}[5m]))
  / sum by (env, environment, stage) (rate(gkg_query_pipeline_queries_total{status!="compile_error"}[5m])) > 0.01
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- Fires without OrbitQueryingErrorRateHigh when the server is failing but total volume dilutes the aggregate rate.

## Severities

- s3, no paging. Excludes client input errors, so this is server-side reliability degrading.

## Verification

```promql
sum by (status) (rate(gkg_query_pipeline_queries_total{status!~"ok|compile_error"}[5m]))
```

- `execution`: ClickHouse failing queries, cross-check
  `OrbitExecutionFailureRate`.
- `authorization`: the Rails redaction/authorization exchange failing,
  cross-check `OrbitAuthorizationFailureRate`.
- `security`: cross-check `OrbitSecurityRejected`.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| `execution` dominates | ClickHouse failing queries | Follow [OrbitExecutionFailureRate](OrbitExecutionFailureRate.md) |
| `authorization` dominates | Rails redaction exchange failing | Follow [OrbitAuthorizationFailureRate](OrbitAuthorizationFailureRate.md) |
| No single mode dominates, rose with a deploy | Release regression | Roll back the image tag and investigate offline |

## Possible Resolutions

Follow the dominant failure mode's own playbook (linked above). If no single
mode dominates and the rate rose with a deploy, roll back the image tag and
investigate offline.

## Dependencies

- Graph ClickHouse (ClickHouse Cloud)
- GitLab Rails (JWT minting, internal Orbit API)

## Escalation

Ask in `#f_orbit_dev` (`context_systems`).

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
