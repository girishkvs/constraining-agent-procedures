<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# ClickHouse Cloud Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22clickhouse%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Service::ClickHouseCloud"

## Logging

* [ClickHouse Cloud monitoring](https://console.clickhouse.cloud/services)

<!-- END_MARKER -->

## Summary

[ClickHouse Cloud](https://console.clickhouse.cloud/) is a managed verion of [ClickHouse DB](https://github.com/ClickHouse/ClickHouse).  It is managed by [ClickHouse Inc.](https://clickhouse.com)

We are adding ClickHouse Cloud databases to the GitLab.com staging and production environments.

### Contact

Any questions please reach out to the team in Slack via `#f_clickhouse` or tag `@gitlab-org/maintainers/clickhouse`

### Provisioners

For a list of team members responsible for provisioning and deprovisioning ClickHouse Cloud DBs see [tech_stack.yml](https://gitlab.com/gitlab-com/www-gitlab-com/-/blob/master/data/tech_stack.yml)

### ClickHouse Cloud Console

The management console for ClickHouse Cloud can be accessed at:

[https://console.clickhouse.cloud/services](https://console.clickhouse.cloud/services)

Log in via Google SSO.

You will need to have access granted by a [ClickHouse Cloud admin](https://gitlab.com/gitlab-com/team-member-epics/access-requests/-/issues/23987) to access the management console.  An Access Request is a typical way of granting this permission. ([example](https://gitlab.com/gitlab-com/team-member-epics/access-requests/-/issues/23987))

### Network Interconnect

Sidekiq and the Web tier will connect via HTTP on port 8443 via a public IP/host.  Inbound connection can be allow listed via IPv4 ranges.  See [ClickHouse IP Access List Docs](https://clickhouse.com/docs/manage/security/ip-access-list) for details.

* [GitLab Development Docs:](https://docs.gitlab.com/development/database/clickhouse/clickhouse_within_gitlab/#writing-database-queries)
* [ClickHouse HTTPS interface docs:](https://clickhouse.com/docs/interfaces/http)
* ClickHouse Cloud is configured to accept HTTPS connections on port 8443.

### GitLab.com Staging Database

GitLab.com Staging Database has the following attributes:

Name: gitlab-com-staging
Console URL: [https://console.clickhouse.cloud/service/57fa3208-48a1-494b-9f44-ea895895a369](https://console.clickhouse.cloud/service/57fa3208-48a1-494b-9f44-ea895895a369)

### GitLab.com Production Database

GitLab.com Production Database has the following attributes:

Name: gitlab-com-production
Console URL: [https://console.clickhouse.cloud/service/ad02dd6a-1dde-4f8f-858d-37462fd06058](https://console.clickhouse.cloud/service/ad02dd6a-1dde-4f8f-858d-37462fd06058)

### ClickHouse Cloud Backup & Restore

Runbook for restoring a ClickHouse Cloud instance from a backup after failure of an instance. [[Link](backup-restore.md)]

<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

Built in Monitoring Dashboards can be accessed via the [ClickHouse Cloud Console](https://console.clickhouse.cloud/services).

A dashboard for monitoring and alerting performance metrics has been configured in [Runbooks](https://gitlab.com/gitlab-com/runbooks/-/blob/master/dashboards/clickhouse/clickhouse_service.json), [clickhouse-cloud-services](https://dashboards.gitlab.net/d/clickhouse-clickhouse_service/clickhouse3a-clickhouse-cloud-services)

Alerting has been configured through Runbooks to alert into Slack channel `#f_clickhouse_infra_alerts`

## Falling back to PostgreSQL

Several [analytics features](https://docs.gitlab.com/user/analytics/) are implemented using [ClickHouse at GitLab](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/clickhouse_usage/). Contribution Analytics was one of the first features to make use of ClickHouse; originally implemented using PostgreSQL, which performed poorly, the ClickHouse-based implementation provided a much better performance.

In case of an outage in ClickHouse cloud services, the impact would include:

* Slower load times for the [Contribution Analytics](https://docs.gitlab.com/user/group/contribution_analytics/) pages.
* An outage in features that are implemented in ClickHouse only, for example: [AI impact analytics](https://docs.gitlab.com/user/analytics/duo_and_sdlc_trends/) and [CI/CD analytics](https://docs.gitlab.com/user/analytics/ci_cd_analytics/).

While the option is there to switch back to PostgreSQL by [disabling ClickHouse](https://docs.gitlab.com/administration/analytics/), this could be helpful in restoring some features that are implmeneted in both PG and CH, but won't be helpful for features that depend only on CH.

When we disable the analytics ClickHouse integration for features that exist in PG too (Contribution Analytics), we're not creating a data split. Data is always present in PG and it's the source of truth. When ClickHouse integration is disabled, the backend falls back to querying PG. Once the integration is switched back on, background workers will ensure data during the outage is synced to ClickHouse.

## Password rotation

Password rotation can be done without downtime if the following steps are carefully followed.

The idea is to let the user authenticate with both the old and the new password during the
transition, migrate every consumer (dictionaries, Vault) to the new password, and only then drop
the old one. Replace `your_user`, `new_password_here`, and the database/dictionary names below with
the real values.

Requirements:

* Admin access on ClickHouse Cloud UI

Steps:

1. Determine which ClickHouse instance (account) needs rotation.
1. Determine which user needs rotation (`gitlab`, `gitlab-ro`, `siphon`, etc.).
1. Determine the database name, usually starts with `gitlab_clickhouse_`.
1. Go to the correct instance.
1. Add a new password without invalidating the existing password.

   ```sql
   ALTER USER your_user ADD IDENTIFIED WITH sha256_password BY 'new_password_here';
   ```

1. Locate all dictionaries in the database and inspect each definition if it uses the affected
   user. Dictionaries embed the credentials in their DDL, so they need to be updated explicitly.

   ```sql
   SELECT
     name
   FROM
     system.dictionaries
   WHERE
     database = 'your_database_name_here';
   ```

1. For each dictionary, do the following:
   1. Inspect the definition, look for the `USER` entry and verify if it's using the affected user.

      ```sql
      SHOW CREATE DICTIONARY your_dictionary_name_here
      ```

   1. Copy the definition, paste the new password and then change `CREATE DICTIONARY` to
      `CREATE OR REPLACE DICTIONARY`. Execute the statement.
1. Update the relevant ClickHouse password in the Vault and ensure that the secret is propagated to
   all nodes.
1. Verify that the new password works end to end (dictionaries refresh without errors, applications
   reconnect successfully) **before** dropping the old password. At this point both passwords are
   still valid, so there's no downtime risk if something was missed.
1. Set the new password explicitly so the old password is dropped.

   ```sql
   ALTER USER your_user IDENTIFIED WITH sha256_password BY 'new_password_here';
   ```
<!-- ## Links to further Documentation -->
