# Orbit webserver SLO alerts

Covers `OrbitServiceGkgWebserverApdexSLOViolation`, `OrbitServiceGkgWebserverErrorSLOViolation`,
`OrbitServiceGkgWebserverTrafficCessation` and `OrbitServiceGkgWebserverTrafficAbsent`.

## Overview

The webserver serves the graph over gRPC (`KnowledgeGraphService`). Every Orbit query a
user runs through `/api/v4/orbit/*` ends up here.

These alerts are severity s3 and do not page. They post to `#f_orbit_alerts`.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Alerts

### OrbitServiceGkgWebserverApdexSLOViolation

gRPC queries are slower than the 5s (satisfied) / 10s (tolerated) thresholds. Users see
slow Orbit API responses.

### OrbitServiceGkgWebserverErrorSLOViolation

The rate of non-OK gRPC status codes is rising. Users see failed queries.

### OrbitServiceGkgWebserverTrafficCessation / TrafficAbsent

The webserver stopped receiving queries. Either nobody can reach it (Workhorse, LB, or
the pods) or the alert fired on a real usage gap. `TrafficCessation` means traffic
recently dropped to zero, `TrafficAbsent` means it has been missing for longer.

## Metrics

The `gkg_webserver` SLI in
[`metrics-catalog/services/orbit.jsonnet`](../../../metrics-catalog/services/orbit.jsonnet)
measures `rpc_server_duration_seconds` on the webserver pods. Errors are responses with a
non-OK gRPC status code. Normal query latency is 2-5s, so the 5s/10s apdex thresholds sit
just above the healthy range.

Under normal conditions the apdex stays above 0.99 and the error ratio below 5%.

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D)
  filtered on the alertname.
- Expected to be rare. The most common real trigger is ClickHouse load, not the pods.

## Severities

- s3, no paging. Impact is degraded or failed Orbit API queries for gitlab.com users.
- If the whole query path is down (all queries fail), consider raising an incident at
  higher severity per the
  [incident severity guide](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/#incident-severity).

## Verification

The alerts fire on these recording rules in the `mimir-analytics-eventsdot` datasource
([Grafana Explore](https://dashboards.gitlab.net/explore)):

```promql
# Apdex (1 means all requests were fast enough)
gitlab_component_apdex:ratio_1h{type="orbit", component="gkg_webserver", monitor="global"}

# Error ratio
gitlab_component_errors:ratio_1h{type="orbit", component="gkg_webserver", monitor="global"}

# Request rate (traffic cessation fires when this drops to zero)
gitlab_component_ops:rate_1h{type="orbit", component="gkg_webserver", monitor="global"}
```

- [Orbit Overview dashboard](https://dashboards.gitlab.net/d/orbit-main/orbit3a-overview?orgId=1&var-environment=orbit-prd),
  `gkg_webserver` row: apdex, error rate, RPS.
- [Webserver dashboard](https://dashboards.gitlab.net/d/orbit-orbit-gkg-webserver) for per-RPC
  latency and error breakdown.
- Test from outside: `glab orbit remote status`, then a real query
  (see [Quick commands](../README.md#quick-commands)). A broken webserver can still show
  `Running` pods, always test a query.
- Logs: [Kibana, orbit index](https://log.gprd.gitlab.net/app/r/s/DhOL5), filter
  `json.mode: webserver`.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged)
  touching `services/gkg` (a merge is a deploy). Check whether a fresh ReplicaSet lines up
  with the alert, see [Recent changes and rollback](../README.md#recent-changes-and-rollback).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

Work through [Order of checks](../README.md#order-of-checks). Webserver-specific
signatures from [Common signatures](../README.md#common-signatures):

| Symptom | Cause | Action |
| --- | --- | --- |
| All `query` calls return HTTP 502 after ~15s, `status` and `schema` still work, logs show `LazyLock instance has previously been poisoned` | Bad image (missing analytics config), one panic poisons all queries | Roll back the image tag |
| Queries fail with `Code: 159 ... TIMEOUT_EXCEEDED` | Heavy query hits the ClickHouse 30s execution timeout | Check ClickHouse load and query weight, not the pods |
| First queries after a quiet period are slow, then recover | ClickHouse Cloud `idle_scaling` waking up | No action, expected |
| Latency rises together with indexer write volume | Shared graph ClickHouse, indexing burst degrades reads | Pause indexing pools ([Pause and resume indexing](../README.md#pause-and-resume-indexing)) |

## Possible Resolutions

- Bad deploy: revert `image.tag` in argocd-apps (see
  [Recent changes and rollback](../README.md#recent-changes-and-rollback)).
- ClickHouse write pressure: pause the indexer pools, queries keep working while data
  goes stale.
- Webserver OOM: scale memory as a stopgap, then report the unoptimized query to
  `context_systems`.

## Dependencies

- Graph ClickHouse (ClickHouse Cloud) dominates query performance.
- Workhorse and GitLab Rails sit in front: if they are down, traffic ceases here even
  though Orbit is healthy. See [Query flow](../README.md#query-flow).

## Escalation

- Ask in `#f_orbit_dev` (team channel for `context_systems`).
- Generic SLO playbooks: [ApdexSLOViolation](../../alerts/ApdexSLOViolation.md),
  [ErrorSLOViolation](../../alerts/ErrorSLOViolation.md),
  [TrafficAbsent](../../alerts/TrafficAbsent.md).

## Definitions

- [Alert rules](../../../mimir-rules/analytics-eventsdot/orbit/autogenerated-analytics-eventsdot-orbit-service-level-alerts.yml)
  (generated, do not edit).
- [Tune the SLI](../../../metrics-catalog/services/orbit.jsonnet), then run `make generate`.

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
