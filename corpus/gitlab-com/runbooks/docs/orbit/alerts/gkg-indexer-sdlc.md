# Orbit SDLC indexer SLO alerts

Covers `OrbitServiceGkgIndexerSdlcApdexSLOViolation`, `OrbitServiceGkgIndexerSdlcErrorSLOViolation`,
`OrbitServiceGkgIndexerSdlcTrafficCessation` and `OrbitServiceGkgIndexerSdlcTrafficAbsent`.

## Overview

The SDLC indexer pool consumes entity events (users, projects, MRs, pipelines, ...) from
NATS and writes graph data to the graph ClickHouse.

No user-facing errors: queries keep working, data goes stale. These alerts are severity
s3 and do not page. They post to `#f_orbit_alerts`.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Alerts

### OrbitServiceGkgIndexerSdlcApdexSLOViolation

ETL handlers are slower than 2.5s (satisfied) / 5s (tolerated).

### OrbitServiceGkgIndexerSdlcErrorSLOViolation

Handlers are failing. Failed messages are redelivered by JetStream, so errors also show
up as `nats_jetstream` redeliveries.

### OrbitServiceGkgIndexerSdlcTrafficCessation / TrafficAbsent

The pool stopped consuming messages. Either the pods are down, the NATS consumer is
stuck, or nothing upstream (Siphon, dispatcher) is producing. `TrafficCessation` means
traffic recently dropped to zero, `TrafficAbsent` means it has been missing for longer.

## Metrics

The `gkg_indexer_sdlc` SLI in
[`metrics-catalog/services/orbit.jsonnet`](../../../metrics-catalog/services/orbit.jsonnet)
measures `gkg_etl_handler_duration_seconds` for the `entity.*` handlers. SDLC handlers are
light; their latency is bound by ClickHouse insert latency and NATS fetch rate, not pod
resources.

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D)
  filtered on the alertname.
- A short error burst during a deploy or a ClickHouse hiccup self-heals through JetStream
  redelivery. Sustained violation means something is actually stuck.

## Severities

- s3, no paging. User impact is stale SDLC data in Orbit query results, not errors.

## Verification

The alerts fire on these recording rules in the `mimir-analytics-eventsdot` datasource
([Grafana Explore](https://dashboards.gitlab.net/explore)):

```promql
# Apdex (1 means all requests were fast enough)
gitlab_component_apdex:ratio_1h{type="orbit", component="gkg_indexer_sdlc", monitor="global"}

# Error ratio
gitlab_component_errors:ratio_1h{type="orbit", component="gkg_indexer_sdlc", monitor="global"}

# Request rate (traffic cessation fires when this drops to zero)
gitlab_component_ops:rate_1h{type="orbit", component="gkg_indexer_sdlc", monitor="global"}
```

- [Orbit Overview dashboard](https://dashboards.gitlab.net/d/orbit-main/orbit3a-overview?orgId=1&var-environment=orbit-prd),
  `gkg_indexer_sdlc` row.
- [Indexer dashboard](https://dashboards.gitlab.net/d/orbit-orbit-gkg-indexer) for per-handler
  duration and error split.
- Indexing progress for a namespace: `glab orbit remote graph-status --full-path gitlab-org`.
- Logs: [Kibana, orbit index](https://log.gprd.gitlab.net/app/r/s/DhOL5), filter
  `json.mode: indexer`.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged)
  touching `services/gkg`.
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

The detailed procedures live in the KG repo's
[SDLC indexing runbook](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/sdlc_indexing.md):
checkpoint inspection, force reindex, purging stuck subjects.

| Symptom | Cause | Action |
| --- | --- | --- |
| Errors on the ClickHouse write | Graph ClickHouse slow or unreachable | Check ClickHouse Cloud status and load first |
| Traffic ceased, pods healthy | Upstream dry: Siphon CDC or the dispatcher stopped producing | Check the [Siphon dashboard](https://dashboards.gitlab.net/d/orbit-orbit-siphon) and the [dispatcher alerts page](gkg-dispatcher.md) |
| One namespace never finishes | Checkpoint stuck or corrupted cursor | [Inspect checkpoints](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/sdlc_indexing.md#inspect-checkpoints) |
| Same batch fails repeatedly | Poison message in redelivery loop | [Remove stuck messages from NATS](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/sdlc_indexing.md#remove-stuck-messages-from-nats) |
| Consumer lag grows, no errors | Throughput bound | Scale the pool: `indexer.pools.sdlc.replicas` in the ArgoCD values ([Scale or restart](../README.md#scale-or-restart-a-component)) |

NATS state can be inspected from a nats-box pod, see
[Troubleshoot NATS with nats-box](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/server_configuration.md#troubleshoot-nats-with-nats-box).

## Possible Resolutions

- Scale the SDLC pool horizontally, it has no ephemeral-storage constraint.
- Purge a stuck subject and force a reindex of the affected namespace (KG runbook above).
  Jobs queued during a pause are redelivered, nothing is lost, only delayed.

## Dependencies

- Graph ClickHouse (writes), NATS JetStream (queue), datalake ClickHouse via the
  dispatcher (job source). See [What degrades if X fails](../README.md#what-degrades-if-x-fails).

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
