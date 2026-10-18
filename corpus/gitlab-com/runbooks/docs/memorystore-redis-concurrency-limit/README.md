<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Memorystore Redis Concurrency Limit Service

* [Service Overview](https://dashboards.gitlab.net/d/memorystore-redis-concurrency-limit-main/memorystore-redis-concurrency-limit-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22memorystore-redis-concurrency-limit%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::MemorystoreRedisConcurrencyLimit"


<!-- END_MARKER -->

## Summary

`memorystore-redis-concurrency-limit` is the GCP-managed MemoryStore for Redis instance (`concurrency-limit-redis`) that holds Sidekiq concurrency-limit deferred jobs. When a worker exceeds its concurrency limit, `Gitlab::SidekiqMiddleware::ConcurrencyLimit::QueueManager` pushes the serialized job onto a Redis LIST here instead of running it. `ConcurrencyLimit::ResumeWorker` drains those LISTs as capacity frees up.

Queue depth on this instance tracks worker throttling, not user traffic. It is idle whenever no worker is being throttled.

It is a managed MemoryStore instance, not a Sentinel-based Redis VM.

## Why this instance exists

Deferred jobs previously lived on `redis-cluster-shared-state`. A throttled high-volume worker such as `AuditEvents::AuditEventStreamingWorker` can accumulate millions of serialized payloads, and that growth drove shared-state memory past 90%. Shared-state also holds distributed locks, MR diffs, and CI pipeline state, so an OOM there has a wide blast radius. Isolating this workload removes that vector.

See the epic: <https://gitlab.com/groups/gitlab-com/gl-infra/tenant-scale/tenant-services/-/epics/72>.

## Architecture

Rails reaches the instance through the `concurrency_limit` storage selector, wired by `Gitlab::Redis::ConcurrencyLimit`. The metrics-catalog definition is [`metrics-catalog/services/memorystore-redis-concurrency-limit.jsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/memorystore-redis-concurrency-limit.jsonnet).

Provisioning and sizing live in [`environments/gstg/memorystore.tf`](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gstg/memorystore.tf). The instance is `STANDARD_HA` with one replica, `maxmemory-policy=noeviction`, and persistence disabled.

Keys are per worker, sharded by worker name:

* `sidekiq:concurrency_limit:throttled_jobs:{worker_name}` — the deferred-job LIST.
* `sidekiq:concurrency_limit:resume_meta:{worker_name}` — resume metadata.
* `sidekiq:concurrency_limit:drop_requested:{worker_name}` — admin purge flag.

`Gitlab::ExclusiveLease` still uses `Gitlab::Redis::SharedState`, so the `concurrency_limit:queue_manager:{worker}` lease keys remain on shared-state and are expected there.

For connecting with `redis-cli`, see [connecting-to-memorystore-redis.md](../memorystore-redis-tracechunks/connecting-to-memorystore-redis.md).

## `noeviction` is deliberate

Under `noeviction` Redis rejects writes once memory is full rather than discarding keys. A deferred job is the only copy of that job, so eviction would lose work silently. Rejected writes surface as errors in the `rails_redis_client` SLI instead, which is the intended failure mode.

This is why the memory saturation alert is s2 at soft 0.40 / hard 0.50, defined by `memorystore_redis_memory_tracechunks` in [`libsonnet/saturation-monitoring/memorystore_redis_memory.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/saturation-monitoring/memorystore_redis_memory.libsonnet). The default `memorystore_redis_memory` point is s4 and does not page, which would be wrong for a workload where saturation means rejected writes.

At `maxmemory`, the instance behaves as follows:

* Writes are rejected. `RPUSH` of a new deferred job fails with an `OOM` error.
* Reads and trims keep working. `LRANGE`, `LLEN` and `LTRIM` succeed, so `ConcurrencyLimit::ResumeWorker` can still drain the LISTs and free memory.

Draining is therefore the recovery path. Follow [sidekiq/sidekiq-concurrency-limit.md](../sidekiq/sidekiq-concurrency-limit.md) to stop new deferrals and let `ResumeWorker` catch up.

The s2 saturation alert depends on the Stackdriver exporter relabeling `concurrency-limit-redis` to
`memorystore-redis-concurrency-limit`. The relabel lives in
[`services/stackdriver-exporter-memorystore/values.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/stackdriver-exporter-memorystore/values.yaml).
If the saturation panel is empty while `rails_redis_client` shows traffic, check that relabel first.

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

The service has two SLIs, each from a different metric source:

* **`primary_server`**: operations on the Redis primary, from the GCP Stackdriver exporter (`stackdriver_redis_instance_redis_googleapis_com_commands_calls`). Reflects server-side activity on the managed instance.
* **`rails_redis_client`**: all concurrency-limit operations issued from the Rails codebase (`gitlab_redis_client_requests_total{storage="concurrency_limit"}`). Reflects client-side activity.

Because the two SLIs have independent sources, comparing them distinguishes a real traffic stop from a metric-pipeline break: Rails traffic present while `primary_server` is absent points at the Stackdriver exporter, not Redis.

An absent traffic signal is benign here whenever no worker is throttled, in a way it is not for other Redis instances.

`SidekiqConcurrencyLimitQueueBacklogged` fires on `sidekiq_queue_size` and is instance-agnostic, so it is unaffected by this migration. See [sidekiq/sidekiq-concurrency-limit.md](../sidekiq/sidekiq-concurrency-limit.md) for how to respond to a backlog.

## Links to further Documentation

* [Sidekiq concurrency limit](../sidekiq/sidekiq-concurrency-limit.md)
* [Connecting to a MemoryStore instance](../memorystore-redis-tracechunks/connecting-to-memorystore-redis.md)
* [Redis survival guide for SREs](../redis/redis-survival-guide-for-sres.md)
