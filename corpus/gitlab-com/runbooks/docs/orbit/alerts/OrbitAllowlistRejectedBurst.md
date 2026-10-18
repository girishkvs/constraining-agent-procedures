# OrbitAllowlistRejectedBurst

Sustained ontology-allowlist violations, above 5 per minute; schema drift or an enumeration attempt. Severity s3, fires after `5m`.

## Overview

Queries are referencing entities, properties or relationships outside the
ontology allowlist at more than 5 per minute. Two very different causes share
this signature: a client built against a newer or older graph schema than the
server exposes (drift), or a caller enumerating the schema surface to see
what exists (probing).

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Metrics

The firing expression, on `gkg_query_engine_compiler_rejected_total` (emitted by the service, see the
[metrics catalog](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/crates/gkg-observability/orbit-dashboards/gkg-metrics.json)):

```promql
sum by (env, environment, stage) (rate(gkg_query_engine_compiler_rejected_total{failure_reason=~"ontology|ontology_internal"}[5m])) * 60 > 5
```

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D) filtered on the alertname.
- Drift rejects a small stable set of names repeatedly; enumeration walks many names once.

## Severities

- s3, no paging. `ontology_internal` rejections deserve the most attention: no legitimate client references internal-only schema elements.

## Verification

```promql
sum by (failure_reason) (rate(gkg_query_engine_compiler_rejected_total{failure_reason=~"ontology|ontology_internal"}[5m])) * 60
```

Pull the rejected names from the compiler rejection logs. Real schema drift
rejects a small stable set of names repeatedly; enumeration walks many names
once. `ontology_internal` rejections mean the query referenced internal-only
schema elements, which no legitimate client does.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) touching `services/gkg` (a merge is a deploy).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Small stable set of names rejected repeatedly | Schema drift between client and server | Check for a recent SCHEMA_VERSION or ontology change; update or roll back; `glab orbit remote schema` shows what the server exposes |
| Many names each rejected once | Enumeration of the schema surface | Capture the caller identity; follow the security process |
| `ontology_internal` rejections present | Caller referencing internal-only elements | Treat as probing |

## Possible Resolutions

- Schema drift: check whether a `SCHEMA_VERSION` bump or ontology change
  shipped recently and whether the caller (`glab`, Duo tooling) needs a
  release to match; `glab orbit remote schema` shows what the server exposes.
- Enumeration: rate-limiting lives in Rails; capture the caller identity from
  the logs before it stops.

## Dependencies

- The ontology allowlist shipped with the running GKG version.
- Clients built against the graph schema (glab, Duo tooling).

## Escalation

Ask in `#f_orbit_dev` (`context_systems`). For suspected enumeration of
internal schema, follow the security process.

## Definitions

- [Alert rule](../../../mimir-rules/analytics-eventsdot/orbit/orbit-cause-alerts.yml) (hand-maintained; keep the expr above in sync when tuning it).

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
