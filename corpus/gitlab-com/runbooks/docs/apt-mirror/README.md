<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Internal apt mirror Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22apt-mirror%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::AptMirror"


<!-- END_MARKER -->

A Pulp (`pulp_deb`) deployment per environment that mirrors the upstream apt
repositories our VMs install from, so a package stays installable after upstream
stops serving it.

* Content: `https://apt-mirror.<env>.gke.gitlab.net/pulp/content/<base_path>/`
* Config: [`services/apt-mirror/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/apt-mirror) in argocd/apps
* Namespace `apt-mirror` on `gstg-gitlab-gke` and `gprd-gitlab-gke`
* Tracking issue: <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/27726>

It exists because some upstreams publish exactly one build per series and drop
the rest — the vbernat HAProxy PPA among them — so once a minor version is
superseded there is no way back from upstream. The mirror keeps what upstream
deletes.

## Alerts

* [AptMirrorContentUnavailable](alerts/AptMirrorContentUnavailable.md) — nothing
  is serving content, so mirror-sourced nodes fail their converge
* [AptMirrorSyncJobFailed](alerts/AptMirrorSyncJobFailed.md) — a sync failed, so
  no new upstream content is arriving
* [AptMirrorSyncStale](alerts/AptMirrorSyncStale.md) — no sync has completed in
  36 hours

## Reaching it

The content endpoint is an internal LB restricted to the environment's own VPC by
`loadBalancerSourceRanges` (`10.224.0.0/13` in gstg, `10.216.0.0/13` in gprd), so
`curl` it from a VM in that environment rather than from a laptop.

`kubectl` needs the SOCKS proxy through the **console server**, not a bastion —
the console server's egress is in the cluster's master authorized networks and
`lb-bastion`'s is not:

```shell
glsh kube use-cluster gstg   # or gprd
```

## What it mirrors

| Repository | `base_path` | Policy | Why |
| --- | --- | --- | --- |
| haproxy 2.8 | `haproxy/jammy` | `immediate` | Retention: the PPA serves one build per series |
| haproxy 3.0 | `haproxy-3.0/jammy` | `immediate` | Retention, for the 3.0 rollout |
| pgdg | `postgresql/jammy` | `on_demand` | Availability |
| fluentd | `fluentd/jammy` | `on_demand` | Availability |
| google-cloud-sdk | `google-cloud-sdk` | `on_demand` | Availability |
| wiz sensor | `wiz-sensor` | `on_demand` | Availability |

`immediate` downloads every package at sync time, which is what preserves a
version upstream later deletes. `on_demand` stores only the package indices and
fetches a `.deb` from upstream the first time a node installs it, then keeps it —
so it protects `apt-get update` and anything already fetched, but a package no
one has pulled still needs upstream reachable. Use `immediate` only where
retention is the point; the storage cost of `immediate` everywhere was estimated
at ~11.6 GB and rising.

## Adding a repository

1. Add an entry to `services/apt-mirror/env/<env>/values-apt-repos.yaml`:

    ```yaml
      - name: fluentd-jammy
        url: "https://packages.treasuredata.com/lts/5/ubuntu/jammy"
        distributions: "jammy"
        components: "contrib"
        architectures: "amd64"
        policy: "on_demand"
        base_path: "fluentd/jammy"
    ```

2. Check the values against the upstream `Release` file before merging, rather
   than copying from a cookbook attribute. `dists/<distribution>/Release` lists
   the real `Components` and `Architectures`, and a component that upstream does
   not declare cannot be mirrored.
3. Merge. ArgoCD syncs, the PostSync `Job` reconciles remotes, repositories and
   distributions through the Pulp REST API, syncs, and publishes.
4. Wait. Repositories appear one at a time as each publish completes — four new
   repositories took about eight minutes end to end on gprd, and each path
   returns 404 until its own publication exists.

## Verifying a publication

From a VM in that environment:

```shell
B=https://apt-mirror.gprd.gke.gitlab.net/pulp/content
curl -sL -o /dev/null -w '%{http_code}\n' $B/fluentd/jammy/dists/jammy/InRelease
curl -sL $B/fluentd/jammy/dists/jammy/InRelease | head -3
curl -sL $B/fluentd/jammy/dists/jammy/main/binary-amd64/Packages | grep -A1 '^Package: '
```

`-L` matters: Pulp answers with a 302 to object storage, and without it you get
`302: Found` as a body rather than the file.

Three things make a publication good:

* **200**, not 404. A 404 means the publish has not happened, not that the
  repository is missing.
* `-----BEGIN PGP SIGNED MESSAGE-----` at the top of `InRelease`. Autopublish
  only fires on a *new repository version*, so a sync that completed before
  signing worked leaves a publication unsigned and apt will reject it.
* The upstream `Origin` intact, e.g. `Origin: apt.postgresql.org`. Pulp preserves
  it, which is what lets an apt pin target the mirrored repository by origin.

## Sync cadence

* The PostSync `Job` runs on every ArgoCD sync of the app.
* A CronJob re-syncs daily at `17 3 * * *` (`apt-mirror-resync-cronjob.yaml`).

Nothing watches either today. A repository whose upstream stops publishing, or a
sync that fails every night, is currently silent.

## When a sync fails

```shell
kubectl -n apt-mirror get cronjob,job
kubectl -n apt-mirror logs job/<name>
```

The sync script is idempotent — it `PATCH`es existing remotes rather than
recreating them — so re-running it is safe. Trigger a run by syncing the app in
ArgoCD, or create a Job from the CronJob:

```shell
kubectl -n apt-mirror create job --from=cronjob/<cronjob-name> manual-resync
```

## Known limitations

* **`main/debug` cannot be mirrored.** The vbernat PPA's jammy `Release` declares
  only `main`, and `pulp_deb` has no `.ddeb` support
  ([pulp/pulp_deb#384](https://github.com/pulp/pulp_deb/issues/384)). A
  mirror-sourced node therefore loses `haproxy-dbgsym` on any version change,
  because that package depends on the exact haproxy version.
* **Wiz cannot be pointed at the mirror.** Wiz's own installer writes
  `/etc/apt/sources.list.d/wiz.list` with `APT_URL` hardcoded, so no Chef
  attribute can move it.
* **Pulp's OTel metrics have no `pulp_` prefix.** Searching for `pulp_*` returns
  nothing and looks like a broken pipeline. Query instead:

    ```promql
    {cluster="gprd-gitlab-gke", namespace="apt-mirror", otel_scope_name="pulp.metrics"}
    ```

## Signing keys

The private key lives in Vault at `k8s/<env>-gitlab-gke/apt-mirror/gpg`. The
matching public keys are vendored in the
[`gitlab-apt-mirror`](https://gitlab.com/gitlab-cookbooks/gitlab-apt-mirror)
cookbook as `apt-mirror-gstg.gpg` and `apt-mirror-gprd.gpg`, and a node names one
of them with `signed-by=` so the mirror's key is trusted for the mirror's
repositories alone.

There is no rotation procedure for these keys yet.
