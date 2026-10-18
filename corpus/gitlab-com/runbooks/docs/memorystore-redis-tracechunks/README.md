<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Memorystore Redis TraceChunks Service

* [Service Overview](https://dashboards.gitlab.net/d/memorystore-redis-tracechunks-main/memorystore-redis-tracechunks-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22memorystore-redis-tracechunks%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::MemorystoreRedisTraceChunks"

## Logging

* [system](https://log.gprd.gitlab.net/goto/a10c2cd2b710f9eb65b13b9a2a328d51)

<!-- END_MARKER -->

## Summary

`memorystore-redis-tracechunks` is the GCP-managed MemoryStore for Redis instance (`tracechunks-redis`) that stores CI job trace (log) output in chunks. Rails writes trace chunks here as CI jobs run and reads them back when rendering job logs. If this instance degrades, CI job output may be delayed in becoming visible, or in severe cases lost.

It is a managed MemoryStore instance, not a Sentinel-based Redis VM.

## Architecture

The instance runs in `us-east1` (gprd project `gitlab-production`, gstg project `gitlab-staging-1`). Rails reaches it through the `trace_chunks` storage selector; see the metrics-catalog definition [`metrics-catalog/services/memorystore-redis-tracechunks.jsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/memorystore-redis-tracechunks.jsonnet).

For connecting to the instance with `redis-cli`, see [connecting-to-memorystore-redis.md](connecting-to-memorystore-redis.md).

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

The service has two SLIs, each from a different metric source:

* **`primary_server`**: operations on the Redis primary, from the GCP Stackdriver exporter (`stackdriver_redis_instance_redis_googleapis_com_commands_calls`). Reflects server-side activity on the managed instance.
* **`rails_redis_client`**: all TraceChunks operations issued from the Rails codebase (`gitlab_redis_client_requests_total{storage="trace_chunks"}`). Reflects client-side activity.

Because the two SLIs have independent sources, comparing them is the fastest way to tell a real traffic stop from a metric-pipeline break: Rails traffic present while `primary_server` is absent points at the Stackdriver exporter, not Redis.

### Alerts

* [MemorystoreRedisTracechunksServicePrimaryServerTrafficAbsent](alerts/MemorystoreRedisTracechunksServicePrimaryServerTrafficAbsent.md)
* Generic traffic-signal background: [TrafficAbsent and TrafficCessation](../alerts/TrafficAbsent.md)

## Links to further Documentation

* [Connecting to the MemoryStore instance](connecting-to-memorystore-redis.md)
