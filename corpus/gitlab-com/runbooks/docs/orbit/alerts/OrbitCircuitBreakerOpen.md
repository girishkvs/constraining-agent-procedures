# OrbitCircuitBreakerOpen

A circuit breaker opened; an external dependency is unreachable and calls to it are being shed. Severity s3, fires after `1m`.

## Overview

A circuit breaker transitioned to open, meaning repeated failures against an
external dependency (ClickHouse, the GitLab internal API, NATS) crossed the
breaker's threshold and GKG is now failing calls fast instead of waiting on
timeouts. This protects the rest of the service, but whatever sits behind
the open breaker is effectively down for GKG.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_circuit_breaker_state_transitions_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_circuit_breaker_state_transitions_total{to="open"}[5m])) > 0
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- This alert fires on the *transition* to open, not on the state of being open: the rate window drains roughly 5 minutes after the last transition, so the alert self-resolves even if the breaker is still open. Sustained shedding is covered by [OrbitCircuitBreakerRejectRateHigh](OrbitCircuitBreakerRejectRateHigh.md) above 10 rejected calls/min; a persistently open breaker in a low-traffic environment can sit below that. A state gauge to alert on is a known gap in the service metrics.

## Severities

- s3, no paging. Whatever sits behind the open breaker is effectively down for GKG; calls fail fast instead of hanging.

## Verification

```promql
sum by (service) (rate(gkg_circuit_breaker_state_transitions_total{to="open"}[5m]))
```

The `service` label names the dependency. Check that dependency's own health
directly (ClickHouse Cloud console, GitLab webservice status, NATS pods) and
watch for `half_open` transitions, which mean the breaker is probing for
recovery.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| `service` names ClickHouse | Graph ClickHouse unreachable or failing | Follow [OrbitExecutionFailureRate](OrbitExecutionFailureRate.md) resolution paths |
| `service` names the GitLab internal API | Rails degraded | Follow [OrbitAuthorizationFailureRate](OrbitAuthorizationFailureRate.md) |
| Breaker flaps open/half-open repeatedly | Threshold tuned too tight, or an unstable dependency | File an issue with the breaker name and the window |

## Possible Resolutions

The breaker itself needs no intervention: it closes automatically once the
dependency answers its probes. Fix or wait out the underlying dependency:

- ClickHouse breaker: see [OrbitExecutionFailureRate](OrbitExecutionFailureRate.md)
  resolution paths.
- GitLab internal API breaker: see
  [OrbitAuthorizationFailureRate](OrbitAuthorizationFailureRate.md).
- A breaker flapping open/closed repeatedly without a clear dependency
  outage suggests a threshold tuned too tight; file an issue with the
  breaker name and the window.

## Dependencies

- Whichever dependency the `service` label names: ClickHouse, the GitLab internal API, or NATS.

## Escalation

Ask in `#f_orbit_dev` (`context_systems`), naming the dependency (`service` label) from the
verification query.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
