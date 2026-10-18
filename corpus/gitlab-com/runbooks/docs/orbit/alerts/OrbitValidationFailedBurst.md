# OrbitValidationFailedBurst

Sustained burst of structural validation failures, above 10 per minute; a broken client or someone probing the API. Severity s3, fires after `5m`.

## Overview

The compiler is rejecting queries for structural problems (`parse`, `schema`,
`reference`, `pagination`) at more than 10 per minute for 5 minutes. These
rejections are the validation layer working as designed; the alert exists
because a sustained burst means either a client is systematically sending
broken queries or someone is probing the endpoint.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_engine_compiler_rejected_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_query_engine_compiler_rejected_total{failure_reason=~"parse|schema|reference|pagination"}[5m])) * 60 > 10
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- Occasional low-volume rejections are normal client noise; the 10/min threshold marks a sustained burst.

## Severities

- s3, no paging. Not user-impacting by itself: the rejected queries were invalid.

## Verification

```promql
sum by (failure_reason) (rate(gkg_query_engine_compiler_rejected_total{failure_reason=~"parse|schema|reference|pagination"}[5m])) * 60
```

Pull the rejection logs and group by caller: one correlation-id cluster or
user means a broken client, a spread across callers after a release means a
query-producing integration (for example the Duo agent tooling) regressed.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| One correlation-id cluster or user | A broken client | File an issue against the calling feature with a sample rejected query |
| Spread across callers after a release | Ontology or schema change invalidated previously valid queries | Check release notes; roll back if unintended |
| Unknown external caller | Probing | Rails owns rate limiting; capture the caller identity |

## Possible Resolutions

- Broken internal client: file an issue against the calling feature with a
  sample rejected query from the logs.
- After a GKG release: a schema or ontology change may have invalidated
  previously valid queries; check the release notes for ontology changes and
  roll back if unintended.
- External probing: rate-limiting happens in Rails (`orbit_query` rate
  limit); no GKG-side action.

## Dependencies

- Query-producing clients: glab, Duo agent tooling, direct API users.

## Escalation

Ask in `#f_orbit_dev` (`context_systems`). This alert alone is not
user-impacting; escalate only if it accompanies error-rate alerts.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
