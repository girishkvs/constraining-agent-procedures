<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Memorystore Redis Sidekiq Quarantine Service

* [Service Overview](https://dashboards.gitlab.net/d/memorystore-redis-sk-quarantine-main/memorystore-redis-sk-quarantine-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22memorystore-redis-sk-quarantine%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::MemorystoreRedisSidekiqQuarantine"


<!-- END_MARKER -->

## Summary

`memorystore-redis-sk-quarantine` is the dedicated GCP MemoryStore Redis instance backing the Sidekiq quarantine shard. Only the quarantine shard uses it.

Jobs reach it via the `queues_shard_quarantine` Redis shard. For the routing rules and the workers currently sent to quarantine, see [sidekiq/sharding.md](../sidekiq/sharding.md). Instance provisioning and sizing are defined in [`environments/gprd/memorystore.tf`](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/memorystore.tf) and [`environments/gstg/memorystore.tf`](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gstg/memorystore.tf).

## Architecture

The instance is a GCP MemoryStore for Redis (`STANDARD_HA`, `noeviction`), not a Sentinel-based Redis VM. It backs only the `queues_shard_quarantine` Sidekiq Redis shard.

MemoryStore has no VM to co-locate an exporter on, so the Sidekiq metrics probe runs as a standalone `gitlab-exporter` Kubernetes Deployment pointed at the remote endpoint. It is the ArgoCD service [`services/gitlab-exporter-sk-quarantine/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/gitlab-exporter-sk-quarantine), deployed to the `gitlab` namespace ([gprd values](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/gitlab-exporter-sk-quarantine/env/gprd/clusters/gprd-gitlab-gke/values.yaml), [gstg values](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/gitlab-exporter-sk-quarantine/env/gstg/clusters/gstg-gitlab-gke/values.yaml)). It scrapes `type=memorystore-redis-sk-quarantine` metrics from the MemoryStore endpoint. The probe's config gotchas (`redis_enable_client`, `/sidekiq` scrape path) are documented as comments in that service's `values.yaml`. For why the instance is MemoryStore rather than Sentinel and why the shard runs 8 threads per pod, see [sidekiq/quarantine-shard.md](../sidekiq/quarantine-shard.md). The operational entry point for a broken metric pipeline is [Metrics panels show `No data`](#metrics-panels-show-no-data).

<!-- ## Performance -->

<!-- ## Scalability -->

## Availability

The instance is `STANDARD_HA`, so a zonal failure triggers an automatic failover that promotes the replica. During failover there is a short (~10.7s) window where writes raise `READONLY You can't write against a read only replica`. The window is retryable and Sidekiq retries the enqueue; see [Brief `READONLY` errors during failover](#brief-readonly-errors-during-failover).

## Durability

The instance runs with `noeviction`, so a full instance rejects new enqueues (`OOM command not allowed`) rather than dropping keys. Reads and job processing continue while the instance is at `maxmemory`.

<!-- ## Security/Compliance -->

## Monitoring/Alerting

Metrics come from two sources:

* **GCP-side metrics** (memory, ops/sec, connected clients, evictions): the `stackdriver-exporter-memorystore` ArgoCD service, which queries the GCP Monitoring API. One deployment covers all MemoryStore instances; the `type` label is derived per `instance_id`.
* **Sidekiq queue-depth and job-state metrics** (`sidekiq_queue_size`, `sidekiq_jobs_*`, retry/schedule set backlogs): the standalone `gitlab-exporter` Sidekiq probe described under [Architecture](#architecture).

### Alerts

* [MemorystoreRedisSkQuarantineServicePrimaryServerTrafficAbsent](alerts/MemorystoreRedisSkQuarantineServicePrimaryServerTrafficAbsent.md) — the `primary_server` SLI stopped reporting. Note this shard is idle by design when no worker is routed to quarantine.
* Generic traffic-signal background: [TrafficAbsent and TrafficCessation](../alerts/TrafficAbsent.md)

Alerts on this service carry a `runbook: memorystore-redis-sk-quarantine/#alerts` annotation, which resolves to this section.

### Checking queue depth

* Dashboard: the queue-depth panel on the [service overview](https://dashboards.gitlab.net/d/memorystore-redis-sk-quarantine-main/memorystore-redis-sk-quarantine-overview) reads `sidekiq_queue_size{type="memorystore-redis-sk-quarantine"}` from this exporter. Confirm the source is the dedicated MemoryStore, not the shared `redis-sidekiq`.
* Direct: `redis-cli -h <endpoint> -a <auth> llen queue:quarantine`.

The `<endpoint>` IP is not hardcoded here because GCP assigns a new private IP if the instance is recreated. Retrieve the current endpoint from the `redis_url` in the ArgoCD values file for the environment ([gprd](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/gitlab-exporter-sk-quarantine/env/gprd/clusters/gprd-gitlab-gke/values.yaml), [gstg](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/gitlab-exporter-sk-quarantine/env/gstg/clusters/gstg-gitlab-gke/values.yaml)) or from the MemoryStore instance in the GCP Console. Read `<auth>` from Vault at `env/{gstg,gprd}/ns/gitlab/memorystore-redis-sidekiq-quarantine`.

If queue-depth panels show `No data`:

1. Check the exporter pod: `kubectl -n gitlab get pods -l app.kubernetes.io/name=gitlab-exporter-sk-quarantine`, and its logs for `CLIENT` errors.
2. Confirm the pod serves metrics on `/sidekiq` (HTTP 200) and that the ServiceMonitor scrapes `/sidekiq`, not `/metrics`. A `/metrics` 404 in the pod's access log means the scrape path is wrong.
3. Confirm `sidekiq_queue_size{type="memorystore-redis-sk-quarantine"}` is present in Mimir for the environment.

### Checking memory usage

Memory metrics come from the GCP Monitoring API via `stackdriver-exporter-memorystore`, not the Sidekiq probe.

* Dashboard: the memory panels on the [service overview](https://dashboards.gitlab.net/d/memorystore-redis-sk-quarantine-main/memorystore-redis-sk-quarantine-overview) show used and peak memory for this instance.
* Alerts: memory saturation pages at 75% (warning) and 90% (critical), routed to Sidekiq on-call. See the [alerts view](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22memorystore-redis-sk-quarantine%22%2C%20tier%3D%22db%22%7D).
* Direct: `redis-cli -h <endpoint> -a <auth> info memory` reports `used_memory` and `maxmemory`.

A rising `used_memory` with a growing `queue:quarantine` length means a routed worker is flooding the shard. Because the instance is `noeviction`, enqueues fail once `maxmemory` is reached — new jobs raise `OOM command not allowed`, while reads and job processing continue.

### Relieving memory pressure

When a routed worker floods `queue:quarantine` and memory approaches `maxmemory`, use the standard Sidekiq worker controls rather than touching Redis directly:

1. Defer or drop the flooding worker via feature flags — see [disabling a worker](../sidekiq/disabling-a-worker.md). This is the first tool to reach for.
2. If jobs landed on the wrong instance (for example after a routing revert), migrate them per [sidekiq/sharding.md](../sidekiq/sharding.md#troubleshooting).

Deleting the queue directly (`del queue:quarantine`) drops jobs and is a genuine last resort; confirm the jobs are safe to lose first. Never run `FLUSHALL` or `FLUSHDB` — that clears the whole instance.

### Troubleshooting

Common failure modes, most to least frequent.

#### Queue backlog and memory saturation from a flooding worker

**Symptom**: `queue:quarantine` length and `used_memory` both climbing; memory-saturation alert firing.

**Cause**: a routed worker is enqueuing faster than the quarantine pods drain. This is the expected failure mode for this shard — it holds bursty, badly-behaved workers.

**Action**: identify the worker on the [sidekiq: Shard Detail](https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq-shard-detail) dashboard, then defer or drop it via feature flags per [disabling a worker](../sidekiq/disabling-a-worker.md). See [Relieving memory pressure](#relieving-memory-pressure) for the full order.

#### Enqueues failing with `OOM command not allowed`

**Symptom**: clients raise `OOM command not allowed when used memory > 'maxmemory'`; reads and job processing still work.

**Cause**: the instance hit `maxmemory`. It runs `noeviction`, so it rejects writes rather than dropping keys.

**Action**: relieve memory pressure by deferring or dropping the flooding worker (see [Relieving memory pressure](#relieving-memory-pressure)), or revert routing to stop the inflow.

#### Queueing apdex paging on a healthy backlog

**Symptom**: `sidekiq_queueing` apdex alert pages while the shard is absorbing an expected burst.

**Cause**: the quarantine shard's apdex target is held to `0.95` (below the service default of `0.995`) because it holds bursty workers; the strict default produced repeated low-value pages (INC-12509, INC-12576). The override is in `metrics-catalog/services/sidekiq.jsonnet` under `monitoring.shard.overrides.sidekiq_queueing.thresholds`. A backlog alone is not an incident here: the shard is pinned at its HPA ceiling (so there is no headroom to absorb a burst faster) and runs a single worker (so one worker's burst is the whole shard's apdex).

**Action**: confirm jobs are still being consumed (queue depth falling) — a drain-after-burst is expected and needs no action. Investigate only if jobs stop being picked up altogether (queue depth flat or climbing with no worker progress), which is what `0.95` still catches.

#### Throughput stalls despite spare replicas

**Symptom**: backlog grows while pods show spare CPU and threads; throughput plateaus.

**Cause**: a CPU-bound worker (for example `AuditEvents::AuditEventStreamingWorker`) contends on the Ruby GVL when too many threads share a pod (INC-12023 / INC-12026).

**Action**: lower per-pod `concurrency` (threads) and raise replica count rather than adding threads.

#### Brief `READONLY` errors during failover

**Symptom**: short burst of `READONLY You can't write against a read only replica` errors.

**Cause**: MemoryStore `STANDARD_HA` failover promotes the replica. The write window is ~10.7s and retryable.

**Action**: none — Sidekiq retries. Investigate only if the window exceeds ~30s or jobs are lost.

#### Metrics panels show `No data`

See [Checking queue depth](#checking-queue-depth) for the probe-side checklist (`CLIENT` errors, `/sidekiq` scrape path, metric presence in Mimir). Memory panels come from a different source — if only memory is missing, check `stackdriver-exporter-memorystore`, not this probe.

### Escalation

* Page the Sidekiq on-call via the memory-saturation alert routing (Incident.io for gprd).
* Owning team: Tenant Services, `#g_tenant_services` in Slack.
* Escalate to the team when a drain does not recover memory, when routing changes are needed to stop the flood, or when resizing the instance is required. Resize is a slow control-plane operation (~21 min under load) and is not an incident-time lever; prefer draining or a routing revert.
* Context: epic [tenant-services#56](https://gitlab.com/groups/gitlab-com/gl-infra/tenant-scale/tenant-services/-/work_items/56), provisioning [team#440](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/440).

## Links to further Documentation

* [The Sidekiq quarantine shard and its dedicated MemoryStore Redis](../sidekiq/quarantine-shard.md) — why MemoryStore over Sentinel, the concurrency tuning behind INC-12023/INC-12026, and the shard's operational constraints.
* [Sidekiq sharding](../sidekiq/sharding.md) — routing rules and the generic sharding process.
* [Redis survival guide for SREs](../redis/redis-survival-guide-for-sres.md) — Redis at GitLab generally.
