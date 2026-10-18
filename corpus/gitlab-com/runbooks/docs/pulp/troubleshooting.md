## Troubleshooting Pulp

The commands in this runbook use the Pulp CLI.
To install and configure it, see [Pulp CLI](./README.md#pulp-cli).

### Uploaded package not available in repository

1. Ensure that a content has been created for the uploaded package

   ```bash
   pulp deb content list --package=<package-name> --version=<package-version> --architecture=<architecture>
   pulp rpm content list --name=<package-name> --version=<package-version> --arch=<architecture>
   ```

   If not, upload the package again, and ensure the task has completed successfully.

1. Get href of the latest version of the repository

   ```bash
   pulp deb repository show --name=<repository-name> | jq -r '.latest_version_href'
   pulp rpm repository show --name=<repository-name> | jq -r '.latest_version_href'
   ```

1. Check if package is in the latest version of the repository

   ```bash
   pulp deb content list --package=<package-name> --version=<package-version> --architecture=<architecture> --repository-version=<repository-version-href>
   pulp rpm content list --name=<package-name> --version=<package-version> --arch=<architecture> --repository-version=<repository-version-href>
   ```

1. If not, add the content to the repository

   ```bash
   pulp deb repository content add --repository=<repository_name> --package-href=<package-content-href>
   pulp rpm repository content add --repository=<repository_name> --package-href=<package-content-href>
   ```

1. Check if a publication exists that points to the latest version of the repository

   ```bash
   pulp deb publication list --repository-version=<latest-repository-version-href>
   pulp rpm publication list --repository-version=<latest-repository-version-href>
   ```

1. If not, create a publication manually

   ```bash
   pulp deb publication create --repository=<repository-name>
   pulp rpm publication create --repository=<repository-name>
   ```

1. Verify that a publication exist with the content

   ```bash
   # Note that `--content` requires a JSON array of hrefs
   pulp deb publication list --content='["<package-content-href>"]'
   pulp rpm publication list --content='["<package-content-href>"]'
   ```

### GPG verification fails with 404 for repomd.xml.asc

Package installation from an RPM repository fails with an error like this:

```plaintext
Errors during downloading metadata for repository 'gitlab_pre-release':
  - Status code: 404 for https://pulp.gitlab.com/gitlab/pre-release/el/8/aarch64/repodata/repomd.xml.asc
Error: Failed to download metadata for repo 'gitlab_pre-release': GPG verification is enabled, but GPG signature is not available.
```

A 404 for `repomd.xml.asc` while `repomd.xml` downloads correctly means the served publication is not signed.
Pulp only generates `repomd.xml.asc` when it creates the publication with a metadata signing service.

1. Check if the repository has a metadata signing service:

   ```bash
   pulp rpm repository show --name=<repository-name> | jq -r '.metadata_signing_service'
   ```

   If the value is `null`, the repository is detached from the signing service.
   Every new publication for this repository is unsigned.

   > [!warning]
   > When someone deletes a signing service, Pulp sets `metadata_signing_service` to `null` on **every** RPM repository that references it.
   > Check the other repositories as well.
   > A repository that still serves signed metadata breaks on its next package upload.

1. Check that the canonical signing service exists:

   ```bash
   pulp signing-service list | jq -r '.[] | [.name, .pulp_created] | @tsv'
   ```

   If `rpm-signing-service` is missing, recreate it first.
   See [manage repository metadata signing keys](./manage-repository-metadata-signing-keys.md).
   A recent `pulp_created` timestamp on a canonical signing service shows that someone recreated it.
   Recreation does not re-attach the service to repositories.

1. Re-attach the signing service to all repositories.

   Run a pipeline on `main` in [`pulp-resources-automation` on ops.gitlab.net](https://ops.gitlab.net/gitlab-com/gl-infra/pulp-resources-automation).
   No CI variables are needed.
   The `repositories:pre` and `repositories:ops` jobs detect the missing signing service and update every repository.

1. Create new publications for the repositories that serve unsigned metadata.

   Re-attaching the signing service does not republish.
   Autopublish only fires on new content, so an unsigned publication stays live until a new one replaces it.

   For a single repository:

   ```bash
   pulp rpm publication create --repository=<repository-name>
   ```

   For a set of repositories, iterate over the repository names.
   Adjust the name prefix to select the affected repositories.
   Set `--limit` higher than the total repository count, or the list is incomplete.
   The `--background` flag dispatches the task without waiting, so Pulp workers process the publications in parallel:

   ```bash
   pulp rpm repository list --limit 5000 \
     | jq -r '.[] | select(.name | startswith("gitlab-pre-release-"))
                   | select(.name | endswith("SRPMS") | not) | .name' \
     | while IFS= read -r repo; do
         service=$(pulp rpm repository show --name="$repo" | jq -r '.metadata_signing_service // "null"')
         if [[ "$service" == "null" ]]; then
           echo "SKIP $repo: signing service not attached"
           continue
         fi
         echo "Publishing $repo"
         pulp --background rpm publication create --repository="$repo"
       done
   ```

   Check that the dispatched tasks complete:

   ```bash
   pulp task list --name pulp_rpm.app.tasks.publishing.publish --state-in waiting --state-in running --limit 5000 | jq length
   pulp task list --name pulp_rpm.app.tasks.publishing.publish --state failed --limit 10 | jq -r '.[] | .error.description'
   ```

   Do not create publications before the signing service is re-attached.
   A publication created from a detached repository is unsigned and extends the outage.

   The loop above excludes SRPM repositories because the automation normally creates their publications.
   However, the automation only creates an SRPM publication when none exists for the latest repository version.
   If an SRPM repository received an unsigned publication while detached, a pipeline rerun does not replace it.
   Create a publication for it manually with `pulp rpm publication create`.

1. Verify that the signature is served.

   The distribution shares its name with the repository.
   Get the distribution path from its `base_path`, for example `gitlab/pre-release/el/8/aarch64`:

   ```bash
   pulp rpm distribution show --name=<repository-name> | jq -r '.base_path'
   ```

   ```bash
   curl -sL -o /dev/null -w '%{http_code}' https://pulp.gitlab.com/<base-path>/repodata/repomd.xml.asc
   ```

   Expect `200`.
   Private repositories need authentication, for example `-u <user>:<token>`.

### Database statistics are wrong after a Cloud SQL restart

Some Cloud SQL changes restart the instance and reset the PostgreSQL table statistics, for example an edition or machine type change.
After the reset, `n_live_tup`, `n_dead_tup` and the values that autovacuum uses start again from 0.
The rows are not lost, and the query plans do not change.

You see these effects:

* The `live` and `toast_live` values of the `stackdriver_cloudsql_database_cloudsql_googleapis_com_database_postgresql_tuple_size` metric drop to a small part of their usual value.
* Autovacuum does not process the large tables for a long time, because it compares the reset values with its usual limits.

Run `VACUUM (ANALYZE)` to set the statistics again.
Always run the scripts in pre first, and check the result there before you run them in ops.
Run the scripts when no package release is uploading.
In ops in October 2026, the vacuum of all tables took about 7 minutes.

All scripts use the database connection of a Pulp API pod.
Each script first prints `error: Macro %add_sysuser has unterminated body`.
This is a warning from the RPM library in the image, and you can ignore it.

1. Check the statistics. This script is read-only:

   ```bash
   kubectl -n pulp exec -i deploy/pulp-api -- pulpcore-manager shell <<'EOF'
   from django.db import connection
   with connection.cursor() as c:
       c.execute("SELECT stats_reset FROM pg_stat_database WHERE datname = current_database()")
       print("stats_reset:", c.fetchone()[0])
       print("Tables:")
       c.execute("""SELECT s.relname, s.n_live_tup, s.n_dead_tup, c.reltuples::bigint,
                           s.last_vacuum, s.last_analyze
                    FROM pg_stat_user_tables s JOIN pg_class c ON c.oid = s.relid
                    ORDER BY c.reltuples DESC LIMIT 10""")
       for r in c.fetchall(): print(r)
       print("TOAST tables:")
       c.execute("""SELECT m.relname, s.n_live_tup, s.n_dead_tup, t.reltuples::bigint,
                           s.last_vacuum, s.last_autovacuum
                    FROM pg_class m
                    JOIN pg_class t ON t.oid = m.reltoastrelid
                    JOIN pg_stat_all_tables s ON s.relid = t.oid
                    WHERE m.relnamespace = 'public'::regnamespace
                    ORDER BY t.reltuples DESC LIMIT 10""")
       for r in c.fetchall(): print(r)
   EOF
   ```

   The statistics are reset if `stats_reset` is near the time of the restart and `n_live_tup` is much smaller than `reltuples` on the large tables.

1. Vacuum the tables one at a time, from the smallest to the largest:

   ```bash
   kubectl -n pulp exec -i deploy/pulp-api -- pulpcore-manager shell <<'EOF'
   import time
   from django.db import connection
   with connection.cursor() as c:
       c.execute("""SELECT format('%I.%I', schemaname, relname),
                           pg_size_pretty(pg_total_relation_size(relid))
                    FROM pg_stat_user_tables
                    WHERE last_vacuum IS NULL OR last_vacuum < now() - interval '1 day'
                    ORDER BY pg_total_relation_size(relid)""")
       tables = c.fetchall()
       print(f"{len(tables)} tables to vacuum", flush=True)
       for name, size in tables:
           t = time.time()
           c.execute(f"VACUUM (ANALYZE) {name}")
           print(f"{name} ({size}): {time.time() - t:.0f}s", flush=True)
   print("done")
   EOF
   ```

   `VACUUM` does not block reads or writes.
   The script skips the tables that were vacuumed in the last day, so you can run it again after a stop.

1. Optional: in a second terminal, show the progress of the current table:

   ```bash
   kubectl -n pulp exec -i deploy/pulp-api -- pulpcore-manager shell <<'EOF'
   from django.db import connection
   with connection.cursor() as c:
       c.execute("""SELECT p.relid::regclass, p.phase,
                           round(100.0 * p.heap_blks_scanned / nullif(p.heap_blks_total, 0), 1) AS pct_scanned,
                           now() - a.query_start AS running_for
                    FROM pg_stat_progress_vacuum p
                    JOIN pg_stat_activity a ON a.pid = p.pid""")
       for r in c.fetchall(): print(r)
   EOF
   ```

1. If the database load is too high, stop the vacuum.
   Ctrl-C does not stop the `VACUUM` on the database side, so use this script:

   ```bash
   kubectl -n pulp exec -i deploy/pulp-api -- pulpcore-manager shell <<'EOF'
   from django.db import connection
   with connection.cursor() as c:
       c.execute("""SELECT pid, pg_cancel_backend(pid), left(query, 60)
                    FROM pg_stat_activity
                    WHERE query ILIKE 'VACUUM%' AND pid <> pg_backend_pid()""")
       for r in c.fetchall(): print(r)
   EOF
   ```

1. Run the check script again.
   `n_live_tup` must be close to `reltuples`, and `last_vacuum` must show the current time.
