<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# PMDB distribution service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22pmdb-dist-svc%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::pmdb-dist-svc"

## Logging

* [pmdb-dist-svc asia-northeast1](https://console.cloud.google.com/run/detail/asia-northeast1/pmdb-dist-svc/observability/logs?project=gitlab-runway-production)
* [pmdb-dist-svc us-east1](https://console.cloud.google.com/run/detail/us-east1/pmdb-dist-svc/observability/logs?project=gitlab-runway-production)
* [pmdb-dist-svc europe-west1](https://console.cloud.google.com/run/detail/europe-west1/pmdb-dist-svc/observability/logs?project=gitlab-runway-production)

<!-- END_MARKER -->

## Summary

[pmdb-dist-svc](https://gitlab.com/gitlab-org/security-products/license-db/pmdb-distribution-service), aka PDS, is responsible for providing PMDB data to GitLab instances. It serves three datasets: `malware` (malware advisories), `advisories` (security advisories from GLAD and Trivy-db) and `licenses` (package licenses).
The malware and advisories datasets live in private buckets. GitLab instances need to be authenticated before PDS provides them with signed URLs to download the data. The licenses bucket is public, so PDS serves plain download URLs for it.

## Architecture

You can find the overall architecture in the dedicated [ADD document](https://internal.gitlab.com/handbook/engineering/architecture/design-documents/malware-advisories/).

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

The service exposes [custom application metrics](https://gitlab.com/gitlab-org/security-products/license-db/pmdb-distribution-service/-/blob/main/docs/metrics.md)
scraped by Runway into the `mimir-runway` datasource (use it in
[Grafana Explore](https://dashboards.gitlab.net/explore) for all queries below).
Custom alerts are defined in
[`mimir-rules/runway/pmdb-dist-svc.yml`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/runway/pmdb-dist-svc.yml),
are scoped to production (`env="gprd"`), and route to
`#g_ast-composition-analysis-alerts` (team `composition_analysis`).

The dataset-scoped alerts aggregate `by (dataset)` and fire independently per
dataset (malware, licenses, advisories) with the dataset named in the alert
title; a new dataset is covered automatically once it emits metrics. The JWKS
and instance-cap alerts have no dataset dimension.

| Alert | Meaning | Severity |
| --- | --- | --- |
| `PmdbDistSvcManifestRefreshErrorRateHigh` | >50% of a dataset's manifest refresh checks failed over 1h | s3 |
| `PmdbDistSvcManifestStale2h` / `Stale4h` | An instance has had no successful refresh of a dataset's manifest for 2h / 4h | s4 / s3 |
| `PmdbDistSvcManifestNotUpdated12h` / `24h` | Refreshes succeed but a dataset's manifest content unchanged for 12h / 24h | s4 / s3 |
| `PmdbDistSvcAllCacheMissRateHigh` / `DeltaCacheMissRateHigh` | >50% signed-URL cache misses on a dataset's `/all` / `/delta` over 1h | s4 |
| `PmdbDistSvcSignedUrlQuotaExhausted` | Any signed-URL generation hit the IAM SignBlob quota in the last 10m | s4 |
| `PmdbDistSvcSignedUrlErrors` | Signed-URL generation failing (non-quota errors) continuously for 15m+ | s4 |
| `PmdbDistSvcDeltaUnsupportedPurlTypesRequests` | `/delta` continuously called with purl types missing from the dataset's manifest (1h) | s4 |
| `PmdbDistSvcJwksRefreshErrors` | OIDC signing-key (JWKS) fetches failing for 30m+ | s3 |
| `PmdbDistSvcRegionInstancesAtMax` | A region pegged at the Cloud Run max-instances cap (10) for 30m | s4 |
| `PmdbDistSvcSustained503Responses` | A dataset served `dataset_not_ready` 503s continuously for 10m+ (API group failed initialization) | s3 |

### Manifest refresh failing or stale

Alerts: `ManifestRefreshErrorRateHigh`, `ManifestStale2h/4h` (per dataset).

Each instance refreshes every dataset's manifest from GCS every ~5 minutes. The
error-rate alert means refresh attempts are actively failing; the staleness
alerts mean an instance hasn't completed a successful refresh in hours (this
also catches a silently stalled refresh loop that produces no errors). Either
way, affected instances serve an increasingly outdated manifest.

* Check [Cloud Run logs](https://console.cloud.google.com/run/detail/us-east1/pmdb-dist-svc/observability/logs?project=gitlab-runway-production)
  for refresh errors (GCS access, timeouts).
* Check GCS availability and the service account's permissions on the manifest
  bucket. GCS-side errors by operation:

  ```promql
  sum by (operation) (rate(gitlab_object_storage_operations_total{env="gprd", result="error"}[5m]))
  ```

* Worst-instance staleness (healthy: ~300s):

  ```promql
  max by (dataset) ((time() - gitlab_manifest_cache_last_refresh_success_timestamp_seconds{env="gprd"})
    and (gitlab_manifest_cache_last_refresh_success_timestamp_seconds{env="gprd"} > 0))
  ```

### Manifest not updated (12h/24h)

Alerts: `ManifestNotUpdated12h/24h` (per dataset).

The service is healthy — refresh checks succeed — but the manifest content
never changes. This means the **upstream publishing pipeline** (PMDB) has stopped
producing new manifests; investigate there, not in this service. Publish count
over the last 12h (each bump above 0 is a publish):

```promql
max by (dataset) (increase(gitlab_manifest_cache_refresh_total{env="gprd", result="changed"}[12h]))
```

### Signed-URL cache miss rate high

Alerts: `AllCacheMissRateHigh`, `DeltaCacheMissRateHigh` (per dataset).

A background loop pre-signs object-storage URLs so requests are served from
cache; a miss signs on demand inside the request, adding latency. Sustained
misses mean the pre-signing loop isn't keeping up or isn't running.

* Check logs for signing errors and IAM `SignBlob` failures.
* Signing quota exhaustion (should be 0) and p95 signing latency:

  ```promql
  sum(rate(gitlab_signed_url_generation_duration_seconds_count{env="gprd", result="quota_exhausted"}[5m]))

  histogram_quantile(0.95, sum by (le) (rate(gitlab_signed_url_generation_duration_seconds_bucket{env="gprd", result="success"}[5m])))
  ```

* Note: during very-low-traffic hours a handful of lookups can inflate the
  miss ratio; sanity-check volume before digging deeper:

  ```promql
  sum by (endpoint) (increase(gitlab_signed_url_cache_operations_total{env="gprd"}[1h]))
  ```

### Signed-URL generation failing

Alerts: `SignedUrlQuotaExhausted`, `SignedUrlErrors` (per dataset).

Signing calls IAM `SignBlob` for every pre-signed URL (background) and every
cache miss (on demand, inside the request). A background re-sign retries 3
times within ~300ms and then drops the path from the cache; an on-demand
failure makes the whole `/all` or `/delta` response a 500.

* `SignedUrlQuotaExhausted` fires on any `ResourceExhausted`. The per-minute
  quota is shared by every Runway service in `gitlab-runway-production`, and
  the retries are too quick to wait it out, so even a short burst can drop
  paths. If it recurs, ask the Runway team to raise the quota.
* `SignedUrlErrors` fires only when other errors keep recurring for 15m+.
  Short bursts that the retries recover from (e.g. `Unauthenticated` /
  `ACCESS_TOKEN_EXPIRED` on one instance) can't fire it. Check the logs for
  `failed to sign a URL` to get the gRPC code, and for
  `dropping path from cache after exhausting sign retries` to see whether
  paths were lost.
* Failures per dataset, result and region:

  ```promql
  sum by (dataset, result, region) (increase(gitlab_signed_url_generation_duration_seconds_count{env="gprd", result!="success"}[10m]))
  ```

### Unsupported purl types on /delta

Alert: `DeltaUnsupportedPurlTypesRequests` (per dataset).

Some client is persistently calling `/delta` with purl types that aren't in
the dataset's manifest; the service skips them and reports them in the
response's `not_supported` array. The offending registry names are
deliberately **not** a metric label (unbounded cardinality) — find them in the
request logs under `skipping unsupported purl_types in /delta request`, then
track down and fix the client.

### JWKS refresh errors

Alert: `PmdbDistSvcJwksRefreshErrors`.

The service can't fetch OIDC signing keys. **Not yet user-visible**: cached
keys keep validating tokens for up to 7 days, after which all clients get
401s indistinguishable from bad tokens — fix before the cache expires.
One fetch attempt covers every issuer in `PMDB_OIDC_PROVIDERS`; any single
issuer failing counts as an error for the whole attempt.

* Check service logs for which issuer is failing.
* Verify the issuer's `.well-known/openid-configuration` and JWKS endpoints
  are reachable from the service.

### Region at max instances

Alert: `PmdbDistSvcRegionInstancesAtMax`.

The region has run at the Cloud Run max-instances cap (10; baseline 5) for
30+ minutes — autoscaling is saturated and additional load can't scale out.
Investigate whether the traffic is legitimate; if sustained, raise
max-instances in the Runway config **and update the alert threshold to
match** (it's hardcoded in the alert expression).

### Sustained 503 responses

Alert: `PmdbDistSvcSustained503Responses`.

The dataset named in the alert has served `dataset_not_ready` 503s
continuously for 10+ minutes, counted per dataset and `reason` by
`gitlab_service_unavailable_responses_total`. The expected cause is that
dataset's API group failing initialization: every request to that group
returns 503 until its init retry succeeds, which rarely happens without
intervention. Short 503 bursts from deploys or scaling age out of the alert's
5m window before its 10m timer completes, so a firing alert means an ongoing
problem, not a blip. `/all` 503s for a registry whose snapshot hasn't been
published yet (`snapshot_not_yet_published`) wait on upstream, not on PDS, and
don't fire this alert.

* Gauge the blast radius on the
  [regional overview dashboard](https://dashboards.gitlab.net/d/pmdb-dist-svc-regional-overview/)
  — the "Request count by status" panel plots each status code separately,
  per region.
* Check [Cloud Run logs](https://console.cloud.google.com/run/detail/us-east1/pmdb-dist-svc/observability/logs?project=gitlab-runway-production)
  for initialization errors to see which dataset is failing and why.
* 503 volume by region:

  ```promql
  sum by (location) (stackdriver_cloud_run_revision_run_googleapis_com_request_count{job="runway-exporter", env="gprd", type="pmdb-dist-svc", response_code="503"}) / 60
  ```

* 503 rate per dataset and reason (the alert only counts `dataset_not_ready`):

  ```promql
  sum by (dataset, reason) (rate(gitlab_service_unavailable_responses_total{env="gprd"}[5m]))
  ```

* Instances on which each dataset hasn't finished its initial load.
  Instances warming up after a deploy or scale-up appear briefly; the
  alerting dataset should stay listed:

  ```promql
  count by (dataset) (gitlab_dataset_ready{env="gprd"} == 0)
  ```

<!-- ## Links to further Documentation -->
