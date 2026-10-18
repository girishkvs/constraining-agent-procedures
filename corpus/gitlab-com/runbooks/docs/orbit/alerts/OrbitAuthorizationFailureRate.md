# OrbitAuthorizationFailureRate

The Rails authorization exchange is failing, above 1 failure per minute; redaction callbacks are not completing. Severity s3, fires after `5m`.

## Overview

Queries whose results need redaction are failing because the authorization
exchange with Rails is not completing. In the query flow, GKG sends resource
ids back over the Workhorse stream and Workhorse calls the Rails internal
redaction endpoint with the user's credentials; if Rails is slow, erroring,
or unreachable, the query fails rather than returning unredacted rows.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_pipeline_failed_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_failed_total{failure_reason="authorization"}[5m])) * 60 > 1
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- Only queries whose results need redaction take this path; queries without redaction keep working while it fires.

## Severities

- s3, no paging. Impact is failed queries for results needing redaction.

## Verification

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_failed_total{failure_reason="authorization"}[5m])) * 60
```

Check GitLab webservice health (this is the Rails internal API, so Rails
error rates and saturation apply) and the webserver logs for the redaction
call errors. If the GitLab side is healthy, check whether the failures
correlate with one user or namespace: an oversized authorization payload can
fail deterministically.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| GitLab webservice degraded overall | Rails-side incident | Resolves with the GitLab webservice; follow standard GitLab escalation |
| Failures pinned to one user or namespace | Oversized authorization payload failing deterministically | Capture the query shape from the logs and file an issue |
| Started with a GitLab deploy | Internal Orbit API regression in the monolith | Check recent changes to the Orbit internal API |

## Possible Resolutions

- Rails degraded: this resolves when the GitLab webservice recovers; nothing
  to do on the GKG side. Queries not needing redaction keep working.
- Failures pinned to one query shape or namespace: capture it from the logs
  and file an issue; the redaction batch size may need tuning.
- Started with a GitLab deploy: the internal endpoint may have regressed;
  check recent changes to the Orbit internal API in the monolith.

## Dependencies

- GitLab Rails (JWT minting, internal Orbit API) answers the redaction callbacks.
- Workhorse carries the redaction round-trip.

## Escalation

Ask in `#f_orbit_dev` (`context_systems`). If the Rails internal API itself
is down, follow the standard GitLab production escalation instead.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
