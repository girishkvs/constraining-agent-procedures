<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Siphon Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22siphon%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Siphon"


<!-- END_MARKER -->

## Summary

[Siphon](https://gitlab.com/gitlab-org/analytics-section/siphon) is a high-throughput data replication tool that captures changes from PostgreSQL via logical replication (CDC - change data capture) and replicates them to other data stores. The primary target is ClickHouse.

## Architecture

Siphon has two independent components communicating via NATS JetStream:

* **Producer**: Connects to PostgreSQL, reads the WAL stream via a logical replication slot, buffers events in memory, and publishes them to a NATS stream.
* **Consumer**: Subscribes to the NATS stream and writes events to the target store (e.g. ClickHouse).

Initial snapshots are handled separately: existing rows are extracted in a `REPEATABLE READ` transaction and sent to a snapshot NATS stream, which is then merged into the main stream before CDC resumes.

## Deployments

| Environment | GCP Project | Status |
| --- | --- | --- |
| Staging | `orbit-stg` | Live |
| Production | `orbit-prd` | Rollout in progress |


## Escalation Path

Primary contact: `#g_analytics_platform_insights` Slack channel ([team handbook](https://handbook.gitlab.com/handbook/engineering/data-engineering/analytics/platform-insights/)).

Individuals with the most context: `@ahegyi`, `@arun.sori` and `@ankitbhatnagar`

For immediate emergencies or if there is no response from the primary contacts, escalate to `#database_operations`.

## Monitoring

Siphon metrics are available in the [Siphon Grafana folder](https://dashboards.gitlab.net/dashboards/f/cfj21k0em8cn4c/siphon) (sandbox dashboards, select the `prd` env).

Key signal for debugging: **logical replication lag**. An increasing lag indicates the producer is falling behind or has stopped consuming from the WAL. This can have serious effect on the database health if not mitigated in a timely manner (<1 day).

Kibana logs:

* Staging: [nonprod-log.gitlab.net](https://nonprod-log.gitlab.net/app/r/s/qLnJb)
* Production: [log.gprd.gitlab.net](https://log.gprd.gitlab.net/app/r/s/6LMBY)

### PostgreSQL Replication lag

On the Siphon Producers Grafana dashboard [Siphon Grafana folder](https://dashboards.gitlab.net/dashboards/f/cfj21k0em8cn4c/siphon) the lag on the logical replication slot is tracked. The chart lists multiple slots because the slot sync (setting name: `sync_replication_slots`) feature is enabled. Slot data is periodically synchronized to replicas which ensures that when the primary is down, the slot will survive.

When determining the actual replication lag, you must look at the series that belongs to the primary (prefixed with `PRIMARY`).

When the replicas synchronize the slot from the primary, intermittently high logical replication lag might be visible on the replica nodes. This may happen when a long vacuum or transaction is running on the primary, there is nothing to do in this case, the issue will resolve itself automatically.

### Kubectl Setup

Both `orbit-stg` and `orbit-prd` environments are available via `glsh` wrapper in runbooks. It is possible to access `orbit-stg` and `orbit-prd` clusters via following the steps in the [k8s oncall setup](https://runbooks.gitlab.com/kube/k8s-oncall-setup/).

```shell
glsh kube use-cluster orbit-prd --no-proxy
```

To inspect, stop, or get logs from pods, use `kubectl`:

```shell
kubectl get pods -A -o wide
```

**Important pods**

|pod name|description|
|-|-|
|`postgres-producer-$DB_NAME*`|Siphon producer process consuming the logical replication stream|
|`clickhouse-consumer-*`|Siphon consumer process ingesting data into ClickHouse|

The `$DB_NAME` indicates which database the producer connects to. Siphon always connects to the primary for logical replication. The initial data snapshot (one-time process) usually involves the DB archive node (except on Staging where snapshot is running from a replica node), which is not part of the Patroni cluster.

## On-call Onboarding

This section aims to provide enough context to triage a page without knowing the codebase.

### Important note

Siphon is not user-facing. A Siphon outage delays analytics data and it does not break
GitLab.com. The only reason siphon can page is **the replication slot.** An unconsumed logical
replication slot makes PostgreSQL retain WAL forever, and unbounded WAL retention
eventually fills the disk on a GitLab.com Patroni primary — which is a
customer-wide outage.

The on-call priority order should be:

1. Start monitoring the slot immediately, and keep watching it throughout. Track
   `pg_replication_slots_confirmed_flush_lsn_bytes` for the affected slot and disk
   utilisation on the Patroni primary from the first minute.
2. Recover the producer (NATS health, pod restarts, see [First 15 minutes](#first-15-minutes)).
   A producer that is running again advances the slot and releases WAL with no data loss.
3. Escalate early if lag keeps growing while you work on the producer: bring in
   `#g_analytics_platform_insights` and `#database_operations`. If primary disk
   utilisation is above 70% and trending upward, escalate severity.
4. Slot mitigation (stop Siphon and drop the slot) is the **last resort**, only when disk
   exhaustion on the primary is imminent. On production it forces a full re-snapshot with
   a recovery period of *at least a week* of degraded analytics data. Note that stopping
   the producer alone does *not* release WAL; only dropping the slot does.
5. Data freshness in ClickHouse comes last.

See [High logical replication lag / producer not running](#high-logical-replication-lag--producer-not-running)
for the full steps.

### Mental model

```
PostgreSQL ──WAL──> Producer ──> NATS JetStream ──> Consumer ──> ClickHouse
                       │                              │
                    (buffers in memory;          (distributed lock:
                     LSN acked to PG only         one active consumer
                     after the batch is           per stream and
                     flushed to NATS)             application id)
```

Three NATS streams per producer, and knowing which is which explains most confusing
dashboards:

| Stream | Contents |
| --- | --- |
| **Main** | Normal CDC events. This is what consumers read. |
| **Snapshot** | Initial table rows from a snapshot in progress. |
| **Temporary** | CDC events that arrived *during* a snapshot, held back to preserve ordering. |

When a snapshot finishes, the producer _pauses replication_, merges Snapshot + Temporary
into Main in LSN order, then resumes.
In rare cases **a stuck merge can stall CDC entirely for that producer**, and it looks like "the producer
stopped" rather than "a snapshot is slow." While a merge runs, the producer pod reports NotReady
(`/health/ready` returns 503 `merge in progress; replication is paused`).

### First 15 minutes

1. **Which producer?** The slot name encodes it: `prd_main_siphon_slot_1` → `main` on
   production. Producers are per-database (`main`, `ci`, `sec`).
2. **Is NATS healthy?** If NATS is down, everything downstream is down and the producer
   is likely in [failover mode](#producer-in-failover-mode-nats-unavailable). See the [NATS runbook](../nats/README.md).
3. **Is the producer running and progressing?**

   ```shell
   glsh kube use-cluster orbit-prd --no-proxy
   kubectl get pods -n siphon -o wide
   kubectl logs -n siphon -l app=postgres-producer-<db> --tail=200
   ```

4. **Check the admin API** on the producer pod — this answers "is it paused or
   snapshotting?" in one call:

   ```shell
   kubectl port-forward -n siphon deploy/postgres-producer-<db> 8081:8081
   curl -s localhost:8081/v1/status | jq
   # => {"app_id": "...", "snapshot_paused": false, "snapshot_running": false}
   ```

   `8081` is the default HTTP port (`http.port`). If the connection is refused, check the
   container ports on the deployment. In failover mode this endpoint returns `503`
   (`no producer is currently registered to accept snapshots`), which is itself a useful signal.

5. **Bouncing the producer is safe and often sufficient.** Siphon always resumes from the
   PostgreSQL replication slot (`confirmed_flush_lsn`), never from a cached position, so a
   restart cannot skip WAL. Re-delivered events are deduplicated in ClickHouse by primary
   key (`ReplacingMergeTree` versioned on `_siphon_replicated_at`).

   ```shell
   kubectl rollout restart deployment/postgres-producer-<db> -n siphon
   ```

### Critical Signals

| Signal | Description |
| --- | --- |
| `pg_replication_slots_confirmed_flush_lsn_bytes` | WAL the primary is retaining for Siphon. **The paging signal.** |
| `siphon_data_lag_ms{source="data"}` | True end-to-end lag, producer → ClickHouse. Staleness signal. |
| `siphon_data_lag_ms{source="heartbeat"}` | Pipeline liveness only. On an idle table only heartbeats arrive, so `source="data"` looking frozen is *normal*. |
| `siphon_failover_mode_active` | 1 = producer is buffering CDC to durable storage because NATS is unreachable. |
| `siphon_snapshot_paused` | 1 = someone paused via the admin API. **Nothing auto-resumes this.** |
| `siphon_operations_total` | Producer throughput. Flat = not replicating. |
| `siphon_clickhouse_consumer_number_of_events` | Consumer throughput. Flat while main stream grows = consumer stalled. |

A gauge caveat that can mislead: `siphon_data_lag_ms` is a **gauge that is only
written after a message is successfully processed**, so a *frozen* value means "nothing
processed recently," not "no lag."

### Restart semantics

Producers and consumers behave differently on persistent failure, which changes what a
crash-looping pod means:

* **Producers** first restart in-process (`siphon producer failed, restarting...`) with
  exponential backoff. After roughly 15 minutes of consecutive failures the process exits
  and Kubernetes restarts the pod. The budget resets after any run lasting more than 3
  minutes, so a `CrashLoopBackOff` producer means a persistent error that fails fast
  (config, credentials, grants, unusable failover storage).

* **Consumers** retry **indefinitely** with a 3-second backoff and log
  `consumer failed - restarting`. Only startup errors (bad config, handler build failure)
  exit non-zero. Once running, a permanently broken consumer looks like a *running* pod
  with flat throughput, not a crash loop.

### Admin API reference

Served on the producer's HTTP port (default `8081`, `http.port`; `/v1` routes can be moved
to a separate `api.port`). The `/v1` routes are only meaningful on producers.

| Method + Path | Purpose |
| --- | --- |
| `GET /health` | Producer: 503 when the last status update is stale. |
| `GET /health/ready` | Producer: 503 while a merge is in progress. Consumer: 503 when this replica does not hold the consumer lock (standby). |
| `GET /health/live` | Consumer: 503 when the fetch loop has not cycled for ~2 minutes. |
| `GET /v1/status` | `snapshot_paused` / `snapshot_running`. Accepts `?app_id=`. |
| `POST /v1/snapshot` | Trigger a snapshot for one or more tables. `app_id` goes in the JSON body. |
| `GET /v1/snapshot-status/{schema}/{table}` | `in_progress` / `complete` / `failed`. Accepts `?filters_hash=`. |
| `POST /v1/snapshot/pause` | Pause snapshotting **and partition monitoring**. |
| `POST /v1/snapshot/resume` | Resume both. |

When several producers share a pod, an `app_id` query parameter selects one; omitting it
with multiple producers registered returns `409` listing the valid ids. While a producer is
in failover mode it does not register for the `/v1` routes, so they return `503`.

There is **no endpoint to abort a running snapshot or merge**, and no way to force a
failover drain. The only control over in-flight work is a process restart.

## Failure Modes

The sections below are ordered roughly by how often they are expected to occur. Each
lists the detection signal, the risk, and the steps.

### High logical replication lag / producer not running

**Detection:** An automated alert monitors the Siphon producer process. If the process loses expected traffic, an alert is triggered. Additionally, logical replication lag metrics; WAL retention metrics on PostgreSQL might be triggered.

The slot name encodes the affected DB and environment, e.g. `stg_main_siphon_slot_1`, `prd_ci_siphon_slot_1`.

**Risk:** An inactive replication slot causes PostgreSQL to retain WAL indefinitely. If lag grows without bound, WAL accumulation will eventually exhaust disk on the PostgreSQL host. Dropping the replication slot is the last resort. Only do this when disk exhaustion is imminent. Siphon will recreate the slot on next start, but a full re-snapshot will be required.

**Steps:**

Work through these in order. Keep watching slot lag and primary disk utilisation the
whole time: they decide whether and when you move on to the slot mitigation steps.

1. **Determine which DB is affected**: the slot name (or the application name on the
   producer dashboard) contains the DB name: `main`, `ci`, or `sec`.
1. **Start monitoring slot lag and primary disk now.** Keep the [Siphon overview](https://dashboards.gitlab.net/d/ahfvxhn/siphon-producers) and the
   [Patroni overview](https://dashboards.gitlab.net/d/patroni-main/patroni-overview) open.
   Note the growth rate: it tells you how much time you have.
1. **Check if NATS is up and running.** If the NATS service is down, Siphon is down. See the [NATS runbook](../nats/README.md).
1. **Try to recover the producer.** Check the pods and logs, then restart it. This is
   safe: the producer always resumes from the slot, so no data is lost.

   ```shell
   kubectl get pods -n siphon -o wide
   kubectl logs -n siphon -l app=postgres-producer-<db> --tail=200
   kubectl rollout restart deployment/postgres-producer-<db> -n siphon
   ```

   A recovering producer shows `siphon_operations_total` rising and slot lag falling.
1. **Escalate if lag keeps growing.** Post in `#g_analytics_platform_insights` and
   `#database_operations`. If primary disk utilisation is above 70% and trending upward,
   raise incident severity.

**Slot mitigation (last resort).** Only continue past this point when disk exhaustion on
the primary is imminent. Dropping the slot forces a full re-snapshot: on production that
means a recovery period of at least a week. Stopping the producer on its own does not
release any WAL; the steps below only matter as a lead-up to dropping the slot.

1. **Stop Siphon** by scaling down the relevant producer deployment (adjust `postgres-producer` to the affected instance: `main`, `ci`, or `sec`):

   ```shell
   kubectl scale deployment postgres-producer-<db> --replicas=0 -n siphon
   ```

   Alternatively, prevent reconnection by disabling the database role (this is only needed when `kubectl` is not set up or extra permission is needed for accessing the `orbit` cluster):

   ```sql
   ALTER ROLE siphon_replicator NOLOGIN;
   ```

1. **Disconnect any active session** still holding the replication slot. The slot will contain the `siphon` substring. Find the PID:

   ```sql
   SELECT
     slot_name,
     active_pid,
     pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) AS lag_bytes
   FROM pg_replication_slots
   WHERE
   slot_type = 'logical' AND slot_name ILIKE '%siphon%';
   ```

   Then terminate the `active_pid` if present:

   ```sql
   SELECT pg_terminate_backend(<active_pid>);
   ```

1. **Drop the replication slot** (last resort, breaks consistency and requires re-snapshot):

   ```sql
   SELECT pg_drop_replication_slot('stg_main_siphon_slot_1');
   ```

   Siphon has a built-in retry mechanism and will recreate the slot on next startup, unless
   the producer is configured with `replication.slot_priority_list`, in which case it never
   creates slots and must be re-provisioned by the team.

### Consumer stalled (data lag climbing, producer healthy)

**Detection:** `siphon_data_lag_ms{source="data"}` climbing steadily while
`siphon_operations_total` on the producer is healthy. The main NATS stream grows but
`siphon_clickhouse_consumer_number_of_events` is flat. PostgreSQL replication lag is
normal — this failure does not threaten the primary.

**Risk:** ClickHouse data goes stale. This is a lower-urgency
failure, but a consumer that stays stalled long enough
can be outrun by [retention](#retention-manager-misbehaving). Further downstream systems
like Orbit will be operating on stale data.

Note that a stalled consumer _is still a running pod_ — it retries forever rather
than crash-looping.

### Snapshot or stream merge stuck

**Detection:** `siphon_snapshot_operations_total` flat while a snapshot is in progress, or
CDC throughput (`siphon_operations_total`) has stopped entirely with
`Merging table, pausing replication` in the logs and no subsequent
`All pending merges finished, resuming replication`.

**Risk:** High. A merge **pauses CDC replication for the whole producer**, so the
replication slot stops advancing and WAL accumulates on the primary. A stuck merge
escalates into the replication-lag failure mode above. Merges have a hard **30-minute
deadline** after which they fail and the producer core restarts in-process (not a pod
restart). Every in-process restart re-runs the snapshot/merge cycle, so a merge that keeps
timing out shows up as a repeating log pattern

**Steps:**

1. **Confirm what the producer thinks it is doing:**

   ```shell
   curl -s localhost:8081/v1/status | jq
   curl -s "localhost:8081/v1/snapshot-status/public/<table>" | jq
   ```

2. **Look for the phase in the logs.** Useful strings, in order of the lifecycle:

   ```shell
   kubectl logs -n siphon -l app=postgres-producer-<db> --tail=500 \
     | grep -E "snapshot slice progress|snapshot complete|Merging table|merge in progress|merge complete|snapshot failed"
   ```

   `merge in progress` with a rising `messages_merged` means it is working — let it finish.
   A repeated `snapshot failed` means the snapshot is being retried in a loop.

3. **Common benign cause on replica snapshots:**
   `snapshot database is behind the publication LSN` means the snapshot source replica
   has not caught up. This is transient and self-healing via retry.

4. **If the merge is genuinely wedged, restart the producer.** Recovery is idempotent:
   the merge consumer is always recreated from the start of the stream, orphaned merge
   consumers are cleaned up on every (re)start, and re-merging is safe because ClickHouse
   deduplicates by primary key.

   ```shell
   kubectl rollout restart deployment/postgres-producer-<db> -n siphon
   ```

   There is no way to abort a merge without restarting the process.

### Producer in failover mode (NATS unavailable)

**Detection:** `siphon_failover_mode_active{app_id} == 1` (alert:
[SiphonEmergencyModeActive](alerts/SiphonEmergencyModeActive.md)). Log:
`entering failover mode: NATS unreachable, buffering CDC to durable storage`.
`siphon_failover_writes_total` climbing.

**Description:** Failover is enabled purely by configuration (`queueing.failover_storage`
with a `gcs`, `s3` or `file` backend; `nats` is rejected, since NATS being down is the
premise). Each time the producer core starts, it checks NATS health. If NATS is unhealthy
and failover storage is configured, the producer keeps consuming WAL and buffers CDC events
to durable storage instead of NATS. This keeps the replication slot advancing.

* There is **no operator toggle**. Failover cannot be switched on while NATS is healthy, and
  it cannot be switched off while NATS is unhealthy (short of removing `failover_storage`
  from the config).
* It is not only a boot-time decision. If NATS fails mid-run, publish errors restart the
  producer core in-process, and the next iteration enters failover. No pod restart needed.
* **Exit is automatic.** In failover the producer polls NATS every `recovery_poll_seconds`
  (default 30). Once healthy it logs
  `NATS recovered; exiting failover mode and restarting siphon core`, then *drains the
  failover store into NATS before resuming replication*. The slot does not advance while
  the drain runs.
* Snapshotting, partition monitoring and the `/v1` admin API are disabled while in
  failover mode. New partitions are picked up after returning to normal mode.

**Risk:** Moderate and mostly deferred. Data is safe but not in NATS, so consumers see no
new data and lag grows. A drain that keeps failing (`drain failover store: ...` in the
logs) counts towards the producer's retry budget and eventually crash-loops the pod, at
which point the slot stops advancing. That escalates to the replication-lag failure mode.

**Steps:**

1. **Fix NATS first**. See the [NATS runbook](../nats/README.md).
2. Watch the automatic recovery and drain. A restart is not required; it only skips
   the up-to-30s recovery poll. The in-flight backlog is
   `siphon_failover_writes_total - siphon_failover_drain_published_total`, and it should
   fall to zero. `siphon_failover_drain_errors_total` rising means drain runs are aborting
   and will retry.
3. If the producer will not start at all, check for
   `failover storage not usable:` in the logs. On every start the producer round-trips a
   test object through the failover store and refuses to continue if that fails. Check
   bucket access and workload identity.

### Partition detection restart loop

**Detection:** Repeated `new table or partition found, restarting to pick it up` /
`restarting Siphon producer due to partition change` in the producer logs. These are
in-process restarts, so the pod restart count does not move.

**Description:** The partition monitor (every 300s by default) restarts the producer core
whenever it detects a new table or partition, so the new relation is picked up with a correct table mapping.
A few restarts around partition rollover are expected and correct as this is by design, not a
fault. Adding the table without a restart would make PostgreSQL stream a relation the
producer cannot route, silently dropping events while the LSN advances past them.

**Risk:** Low if it converges within a few cycles. If it does **not** converge, the
producer is not replicating and the slot is not advancing — escalating to the
replication-lag failure mode.

**Steps:**

1. Check whether it is converging. If restarts stop after a few cycles, no action.
2. If it loops indefinitely, the publication `ADD TABLE` is failing. Look for:

   ```shell
   kubectl logs -n siphon -l app=postgres-producer-<db> --tail=300 \
     | grep -i "failed to add table to publication"
   ```

   `... due to lock timeout, retrying` means `ALTER PUBLICATION` could not get its lock,
   typically because of long-running transactions on the table. Otherwise it is usually a
   **grants problem on the primary**: the Siphon role needs ownership/permission to alter
   the publication. Escalate to `#database_operations` with
   the table name.

3. Note the interaction with pause: partition monitoring is skipped entirely while
   snapshots are paused. A forgotten `POST /v1/snapshot/pause` silently disables partition
   handling — check `siphon_snapshot_paused`.

### Snapshot paused and forgotten

**Detection:** `siphon_snapshot_paused{app_id} == 1` for an extended period.

**Risk:** Snapshots do not run **and partition monitoring is disabled**, so new partitions
are not picked up. CDC for already-mapped tables continues normally, which is what makes
this easy to miss.

**Nothing auto-resumes a paused producer.** The pause is in-process only, so any restart
clears it — meaning the gauge can also be cleared accidentally by an unrelated restart.

**Steps:**

```shell
curl -s localhost:8081/v1/status | jq          # confirm snapshot_paused
curl -sX POST localhost:8081/v1/snapshot/resume | jq
```

Pausing does not stop an in-flight snapshot; it only prevents new ones from starting.

### ClickHouse write failures

**Detection:** `siphon_clickhouse_consumer_batch_retry_total` rising.
`siphon_clickhouse_consumer_adaptive_batch_size` (a histogram of successful batch sizes)
trending down. Logs:
`Batch failed, retrying with smaller size`.

**Description:** It is self-healing. On size-related ClickHouse errors (memory limits,
timeouts, "too many parts", query or AST too large, read limits) the consumer halves the batch size and
retries, down to a single row, and caches the reduced size for 5 minutes. Steady
low-level retries with data still flowing are normal backpressure, not an incident.

**Escalation:** `Batch failed with non-retriable error` (also logged when a
size error persists at batch size 1). Connection drops and schema mismatches are
deliberately *not* retried by halving, because halving cannot fix them. These become
handler failures, and the message is NAKed and redelivered forever (`MaxDeliver: -1`, no
dead-letter queue): a poison message that stalls the consumer. The signature is repeated
`message NAKed, error handling the message` at the same `stream_sequence`, followed by
`consumer failed - restarting`.

**Steps:**

1. Check ClickHouse health first — see the [ClickHouse runbook](../clickhouse/README.md).
2. `Too many parts` usually means ClickHouse merges are behind, not a Siphon fault.
3. A schema mismatch (a column present in PostgreSQL but missing in the ClickHouse target
   table) will stall permanently. Escalate to the team; it needs a target-table migration.

### Retention manager misbehaving

**Detection:** Two opposite failures, with different signals.

**Aggresive retention: data loss that has already happened:**
`siphon_retention_floor_below_first_seq_total > 0`, with the log line
`slowest consumer ack floor is below stream first sequence with pending data`.
This means stream retention evicted messages a live consumer had not yet acked. Any
non-zero value warrants investigation of the named consumer - it has a permanent gap.
`min_days` (default 7) is the floor the retention window can never go below; a consumer
lagging by more than that is at risk.

**Stalled — unbounded disk growth:** NATS stream storage growing while
`siphon_retention_maxage_seconds` does not change. Streams are created with unlimited
`MaxBytes`/`MaxMsgs`, so `MaxAge` is the only limit; a retention loop that never
updates lets the NATS disk grow without bound.

The trap: `siphon_retention_maxage_updates_total` staying flat is *normal* in steady state,
because updates within 24h of the current value are skipped. The skip reasons
(`no consumers on stream`, `lowest ack floor is 0 (nothing acked)`, and
`MaxAge within no-op threshold`) emit **no error metric at all**, so an alert built only on
`siphon_retention_claim_errors_total` will miss a permanently stalled loop. Read the skip
reason from the logs.

**Steps:**

1. Check which case you are in:

   ```shell
   kubectl logs -n siphon -l app=retention-manager --tail=200 \
     | grep -E "retention cycle failed|retention manager failed|skipping( retention)? update|clamping to first sequence"
   ```

2. For hard failures, `siphon_retention_claim_errors_total` carries a `phase` label
   (`connect`, `stream_info`, `list_consumers`, `message_time`, `update_maxage`) that
   localises the problem. `phase="update_maxage"` means NATS rejected the write.
3. `siphon_retention_maxage_seconds` reports the current window; **0 means unlimited**.
4. Retention is configured **one manager per NATS stream**, not per producer. Duplicate
   entries for the same stream are a misconfiguration.

### Oversize events / object storage unavailable

**Detection:** Producer restart loop with `put object to store` or `writing GCS object`
in the logs. Consumers logging `failed to fetch referenced event` with data lag climbing.

**Description:** Events larger than the NATS payload limit and **all snapshot events,
regardless of size** - are written to object storage, with only a reference published to
NATS. `siphon_oversized_events_total` counts all of these, snapshot events included.

`siphon_object_storage_put_failures_total` and the put/get duration metrics are reliable for
the `gcs`, `s3` and `file` backends. With the `nats` object-store backend, producer Puts are
**not** instrumented (consumer Gets are), so detect producer-side failures from logs.

**Risk:** On the producer, a failed Put aborts the flush and restarts the producer, so the
slot stops advancing — this escalates to the replication-lag failure mode. On the
consumer, a missing object is a permanent poison message (NAKed and redelivered forever,
see [ClickHouse write failures](#clickhouse-write-failures)).

**Steps:**

1. Check the bucket is reachable and the workload identity / credentials are valid.
   GCS and S3 buckets are **managed externally** — Siphon does not create them. Only the
   `nats` object-store backend is auto-created.
2. For consumers that cannot fetch a referenced object, check whether it **expired**.
   GCS/S3 log `object ... not found in bucket`; the NATS backend logs `getting object ...`.
   If the bucket TTL (NATS object-store TTL, or the GCS/S3 lifecycle policy) is shorter
   than the stream's `MaxAge`, a consumer that falls behind will hit permanently-missing
   objects. This is a
   configuration bug worth escalating, not a transient fault.
3. Multiple producers sharing a bucket must have distinct `application_identifier` values;
   objects are namespaced by it.
