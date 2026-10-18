# Alertmanager configuration

We manage our Alertmanager configuration here using jsonnet. The resultant
Kubernetes secret object is uploaded, and is consumed by
[the Prometheus operator deployment](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/prometheus).

The CI jobs for this are run on `ops.gitlab.net` where the variables are configured.
See: <https://ops.gitlab.net/gitlab-com/runbooks/-/settings/ci_cd>

## Routing alerts

The routing tree is defined in [`alertmanager.jsonnet`](./alertmanager.jsonnet).
Each `Route` matches alert labels and sends matching alerts to a receiver.
Alertmanager evaluates child routes in their defined order.

### Team Slack channels

Teams with a `slack_alerts_channel` in
[`services/teams.yml`](../services/teams.yml) get a corresponding receiver named
`team_<team-name>_alerts_channel`. For example, the `observability` team maps to
the `team_observability_alerts_channel` receiver.

Generated routes send alerts to these receivers based on their `team`,
`product_stage_group`, or `feature_category` labels. Add the `team` label to a
manual alert when this standard team-based routing is sufficient.

### Custom routes

Add a custom `Route` to `routingTree.routes` when routing must use another
label, such as `shard`, or when it needs different routing behavior. Reuse an
existing receiver when possible and match only the labels needed to identify the
alerts.

```jsonnet
Route(
  receiver=receiverNameForTeamSlackChannel('observability'),
  continue=false,
  matchers={
    env: 'gprd',
    type: 'ci-runners',
    component: 'runner_api_requests',
    shard: 'tamland',
  },
),
```

`continue=true` sends a notification to the matching receiver and evaluates
later sibling routes. `continue=false` stops evaluating later routes for that
alert. Use the latter only when the custom route should replace default routing,
including PagerDuty or incident.io notifications.

Route order is significant. A route intended to prevent incident.io or PagerDuty
notifications must appear before their routes in the tree. In particular, put a
route that suppresses paging before the incident.io route; routes in the
terminator section run too late to do so. The terminator section is the final
block of routes in `routingTree.routes` in
[`alertmanager.jsonnet`](./alertmanager.jsonnet) (marked with the comment
`// Terminators go last`). These routes have `continue=false` and act as
catch-alls — once an alert reaches them, no later sibling routes are evaluated.

### Test routing changes

Add a case to [`routing-tests.jsonnet`](./routing-tests.jsonnet) for each custom
route. Include representative labels and the complete expected receiver list,
then run:

```shell
make test-alertmanager
```

Use the Alertmanager routing tree editor to inspect changes when useful:
<https://prometheus.io/webtools/alerting/routing-tree-editor/>. Do not include
secrets when pasting generated configuration into external tools.

## Variables

### `ALERTMANAGER_SECRETS_FILE`

Type: File

Value: A jsonnet file, based on the dummy-secrets.jsonnet template.

## CI Jobs

These jobs run in a CI pipeline, view the [.gitlab-ci.yml](../.gitlab-ci.yml) to
determine how this is configured.

To run a manual deploy, you will need a local secrets file with the filename
exported in the `ALERTMANAGER_SECRETS_FILE` variable.

For the production alertmanger, this content is stored in vault at [`
ops-gitlab-net/gitlab-com/runbooks/ops/alertmanager`](https://vault.gitlab.net/ui/vault/secrets/ci/kv/ops-gitlab-net%2Fgitlab-com%2Frunbooks%2Fops%2Falertmanager/details?version=2).

Then run:

```shell
kubectl apply --namespace monitoring --filename k8s_alertmanager_secret.yaml
```

* Generate the `alertmanager.yml` file.

  ```shell
  ./generate.sh
  ```

* Validate the `alertmanager.yml` looks reasonable.
* The contents of this file are visible as a base64 encoded secret, in the
  manifest k8s_alertmanager_secret.yaml.
* When this secret is uploaded to a namespace containing a prometheus operator
  and an Alertmanager CRD (which these days is only the ops GKE cluster's
  monitoring namespace), Alertmanager's config will automatically be updated.
