# OrbitSecurityRejected

The query pipeline is rejecting requests for invalid or missing security context. Severity s3, fires after `5m`.

## Overview

Requests are failing the pipeline's security check: the JWT is missing,
expired, unverifiable, or lacks the claims the pipeline needs. Unlike
`OrbitAuthFilterMissing` (a compiler-level invariant breach), this is the
expected rejection path doing its job; the alert exists because a sustained
rate means some caller is systematically broken, most often after a JWT key
rotation that only landed on one side.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_pipeline_failed_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_failed_total{failure_reason="security"}[10m])) > 0
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- A short burst can lag the alert by a few minutes: the 10m rate window holds the signal long enough for the 5m `for` to complete.

## Severities

- s3, no paging. Requests are being rejected safely; impact is failed queries for the affected callers.

## Verification

```promql
sum by (env, environment, stage) (rate(gkg_query_pipeline_failed_total{failure_reason="security"}[10m]))
```

Check the webserver logs for the JWT verification errors around the window.
JWTs are HS256 with a 5 minute lifetime and a single shared key: if Rails and
GKG disagree on the key version, every request fails until both match.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Every request failing | JWT key rotation half-done, sides disagree on the key version | Align the pinned Vault secret versions and redeploy both sides |
| Failures pinned to one caller | Broken token handling in that client | Identify the caller in the logs and fix it |
| Sporadic failures across callers | Clock skew against the 5-minute JWT lifetime | Compare pod clocks on Rails and GKG |

## Possible Resolutions

- Key rotation in progress: finish it. Bump the pinned Vault secret version on
  whichever side still runs the old key and redeploy; the two sides cannot
  overlap keys, so the failure window closes only when both match.
- Clock skew between Rails and GKG pods can invalidate the short-lived
  tokens; compare pod clocks if rotation is ruled out.
- A single misbehaving internal caller: identify it in the logs and fix its
  token handling.

## Dependencies

- GitLab Rails (JWT minting, internal Orbit API)
- The shared HS256 JWT key in Vault, pinned on both sides.

## Escalation

Ask in `#f_orbit_dev` (`context_systems`). If the requests come from an
unknown caller rather than Rails, treat it as probing and follow the security
process.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
