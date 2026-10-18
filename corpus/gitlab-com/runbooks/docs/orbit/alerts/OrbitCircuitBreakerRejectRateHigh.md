# OrbitCircuitBreakerRejectRateHigh

A circuit is open and shedding significant traffic, above 10 rejected calls per minute. Severity s3, fires after `5m`.

## Overview

An open circuit breaker is rejecting more than 10 calls per minute, meaning
real traffic is being shed rather than served. Where `OrbitCircuitBreakerOpen`
signals that a breaker tripped at all, this alert quantifies sustained user
impact: the dependency has been down long enough for meaningful load to pile
into the open breaker.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_circuit_breaker_calls_rejected_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_circuit_breaker_calls_rejected_total[5m])) * 60 > 10
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- Rejections scale with incoming traffic, so this quantifies sustained user impact where OrbitCircuitBreakerOpen only marks the event.

## Severities

- s3, no paging. Real traffic is being shed; treat the incident at the underlying dependency's severity.

## Verification

```promql
sum by (service) (rate(gkg_circuit_breaker_calls_rejected_total[5m])) * 60
```

The `service` label names the dependency being shed. Correlate with the
error-rate alerts for that dependency and with
`gkg_circuit_breaker_state_transitions_total` to see whether the breaker is
stuck open or flapping.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Sustained rejects, dependency confirmed down | Ongoing dependency outage | Restore the dependency; the breaker closes on its own probes |
| Rejects continue after the dependency recovered | The breaker's probe never succeeds (bug) | File an issue with the breaker name; a pod restart is the stopgap |

## Possible Resolutions

Same paths as [OrbitCircuitBreakerOpen](OrbitCircuitBreakerOpen.md): restore the
dependency behind the named breaker. Because rejections here scale with
incoming traffic, consider whether the callers retrying into the open breaker
should back off; sustained high rejection with a recovered dependency means
the breaker's probe never succeeds, which is a bug worth filing with the
breaker name.

## Dependencies

- Whichever dependency the `service` label names.

## Escalation

Ask in `#f_orbit_dev` (`context_systems`). If user-facing error rates are
elevated at the same time, treat the incident at the dependency's severity,
not this alert's.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
