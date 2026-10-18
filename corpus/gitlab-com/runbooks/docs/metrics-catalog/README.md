# Metrics Catalog

The Metrics-Catalog is a declarative approach to monitoring GitLab using Service-Level Monitoring.

At present, the documentation on the Metrics-Catalog requires some work, but there are several conference talks on the approach we use:

* <https://www.youtube.com/watch?v=CbX1nZL7biQ>
* <https://www.youtube.com/watch?v=6sfr2IGJQXk>
* <https://www.youtube.com/watch?v=YHV0qkKBz7o>
* <https://vimeo.com/341141334>
* <https://www.youtube.com/watch?v=2zL9DymXi1E>
* <https://www.youtube.com/watch?v=swnj6KTRg08>

## Configuration Reference

* [Service-Level Monitoring](service-level-monitoring.md) - notes on the Service-Level Monitoring implementation, including minimum sample size thresholds.
* [Monitoring Overrides](monitoring-overrides.md) - the `monitoring` stanza of a service definition, and the per-SLI alert overrides available under it.
* [Traffic Cessation Alerts](traffic-cessation-alerts.md) - how we alert on an SLI that stops receiving traffic.
* [Cost Attribution](cost-attribution.md) - the `costAttribution` stanza of a service definition, and the usage recording rule it generates for the cost warehouse.

## Source Locations

The metrics-catalog source can be found in the following locations in this project:

1. [`metrics-catalog`](https://gitlab.com/gitlab-com/runbooks/-/tree/master/metrics-catalog) - the GitLab.com Metrics-Catalog.
1. [`reference-architectures/get-hybrid`](https://gitlab.com/gitlab-com/runbooks/-/tree/master/reference-architectures/get-hybrid) - A [Reference Architecture](https://docs.gitlab.com/administration/reference_architectures/) Metrics-Catalog for a [GitLab Environment Toolkit](https://gitlab.com/gitlab-org/gitlab-environment-toolkit) Hybrid (VM+Kubernetes) GitLab deployment
1. [`libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/tree/master/libsonnet) - common source-code, written in [Jsonnet](https://jsonnet.org), for generating the configuration.
