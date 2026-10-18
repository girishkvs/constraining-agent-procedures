<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Triage-ops reactive webhook processor (Runway) Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22dx-triage-ops%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::dx-triage-ops"


<!-- END_MARKER -->

## Quick Links

| Reference | Link |
| --- | --- |
| Source | [gitlab-org/quality/triage-ops](https://gitlab.com/gitlab-org/quality/triage-ops) |
| Production endpoint | <https://dx-triage-ops.runway.gitlab.net> |
| Environments | [Project environments](https://gitlab.com/gitlab-org/quality/triage-ops/-/environments) |
| Dashboard | [Grafana](https://dashboards.gitlab.net/d/runway-loadbalancer-cloudrun) |
| Production logs | [Cloud Logging](https://console.cloud.google.com/logs/query;query=resource.type%20%3D%20%22cloud_run_revision%22%0Aresource.labels.service_name%20%3D%20%22dx-triage-ops%22%0A%20severity%3E%3DDEFAULT;storageScope=project?project=gitlab-runway-production) |
| Owner | [Development Health](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/developer-experience/development-health/) |

## Summary

triage-ops is a Rack web application that processes GitLab webhooks and runs reactive triage policies. The Runway instance (`dx-triage-ops`) receives webhook events and routes them to configured processors via `config/processor_routing.yml`.

<!-- ## Architecture -->

<!-- ## Monitoring/Alerting -->
