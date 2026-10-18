<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Secrets Manager GKE Database (Postgres) Service

* [Service Overview](https://dashboards.gitlab.net/d/runway-db-secrets-manager-gke-main/runway-db-secrets-manager-gke-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22runway-db-secrets-manager-gke%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RunwayDBSecretsManager"

## Logging

* [runway-db-secrets-manager-gke](https://console.cloud.google.com/logs/query;query=resource.type%3D%22cloudsql_database%22%0Aresource.labels.database_id%3D%22gitlab-runway-production:runway-db-secrets-manager-gke%22%0Alog_name%3D%22projects%2Fgitlab-runway-production%2Flogs%2Fcloudsql.googleapis.com%252Fpostgres.log%22?project=gitlab-runway-production)

<!-- END_MARKER -->

## Summary

`runway-db-secrets-manager-gke` is the Runway-managed Cloud SQL for PostgreSQL instance behind the `secrets-manager-gke` OpenBao service.
For the service itself, see the [`secrets-manager-gke` runbook](../secrets-manager-gke/README.md).

OpenBao owns two tables in the `openbao` database, `openbao_kv_store` and `openbao_ha_locks`.
The leadership lock lives in `openbao_ha_locks`, so this database is also OpenBao's leader election.

Instance and backup settings for both environments live in [`config/runtimes/gke/cloud-sql/managed.yml`](https://gitlab.com/gitlab-com/gl-infra/platform/runway/provisioner/-/blob/main/config/runtimes/gke/cloud-sql/managed.yml?ref_type=heads).

## Durability

Automated backups run daily at `11:00` UTC and the seven most recent are kept — a count, not a seven-day window.
Point-in-time recovery is on, with seven days of transaction logs in Cloud Storage.
On-demand backups are kept until someone deletes them and never consume one of the seven slots.

### Restore validation

Runway restores the newest backup into `runway-db-secrets-manager-gke-restore-instance` daily and runs `SELECT COUNT(*), NOW() FROM openbao_kv_store HAVING COUNT(*) > 0;` against it.
That proves the backup restores and the table came back holding rows.
It does not prove that any row decrypts, because OpenBao takes no part in the check.

Both alerts are `s4` and route to Runway, so neither one pages us, and no restore-validation alert covers staging.
See [Cloud SQL Restore Pipeline Troubleshooting](../runway/cloudsql_restore_pipeline_troubleshooting.md).

Pipeline history is in `runway-db-secrets-manager-gke-production-us-east1`, under the private [`cloudsql_backups_validation`](https://ops.gitlab.net/gitlab-com/gl-infra/platform/runway/cloudsql_backups_validation) group on `ops.gitlab.net`.
Ask in `#f_runway` if it returns `404`.

### Restoring from a backup

Follow [Restore/Backup Runway-managed Cloud SQL](../runway/cloudsql_backup_restore.md).
The restore runs from a Runway provisioner MR that an SRE approves, so line that approval up before you scale OpenBao down — otherwise the service sits at zero pods for the length of a review.

1. Scale OpenBao down to zero pods.
1. Restore the PostgreSQL instance.
1. Scale OpenBao back up to two pods.

Ask in `#f_runway` to run scale down and scale up command as write access to the cluster is required.
Afterward confirm the pods unsealed, per [Healthy startup baseline](../secrets-manager-gke/README.md#healthy-startup-baseline).

### Consistency with the Rails main database

OpenBao derives its namespace paths from Rails `main` database IDs, and neither side stores a cross-reference to the other.

Restore both databases to the same point in time.
Otherwise Rails keeps offering namespaces that are no longer there, CI jobs receive paths that resolve to nothing, and the rotation reminder job deletes its own rows once the identifier it reads back from OpenBao stops matching.
No task reconciles the two.
Ask in `#sec-secrets-manager-openbao` if that is not possible.

## Security/Compliance

A direct `SELECT` gives you row counts and sizes and nothing else, because namespaces and mounts appear only as UUIDs and KVv2 key names are encrypted or hashed.
See [Security/Compliance](../secrets-manager-gke/README.md#securitycompliance) for the barrier and KMS setup.

### Access needed for a restore

The engineer performing the restore must have Developer access to the [Runway provisioner](https://gitlab.com/gitlab-com/gl-infra/platform/runway/provisioner) project to open the required MR.

## Alerts

The two alerts do not mean the same thing.

* `RunwayDbSecretsManagerGkeServiceTransactionsPrimaryTrafficCessation` fires when the `transactions_primary` series is present and reads zero, and was at least `0.167` ops/s an hour ago.
* `RunwayDbSecretsManagerGkeServiceTransactionsPrimaryTrafficAbsent` fires when the series existed an hour ago and is not being reported now, so it can be a gap in the GCP metric export rather than a real outage.

Confirm the series is still reported before treating that one as an outage.

OpenBao is this instance's only client and holds its leader election here, so genuine zero traffic means the `secrets-manager-gke` pods are not reaching the database.
Check first whether a restore or a deliberate scale-down is in progress: [Restoring from a backup](#restoring-from-a-backup) scales OpenBao to zero pods, which fires both alerts with nothing wrong.
Then work the pod side ([`secrets-manager-gke` troubleshooting](../secrets-manager-gke/README.md#troubleshooting)) and the database side ([Cloud SQL connection or latency](../secrets-manager-gke/README.md#cloud-sql-connection-or-latency)).

Both alerts are `s4` and neither pages.

* [`RunwayDbSecretsManagerGkeServiceTransactionsPrimaryTrafficAbsent`](../alerts/TrafficAbsent.md)
* [`RunwayDbSecretsManagerGkeServiceTransactionsPrimaryTrafficCessation`](../alerts/TrafficAbsent.md)
