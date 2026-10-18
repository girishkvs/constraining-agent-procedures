# TNFResourceFailed

## Meaning

This alert fires when a Pacemaker-managed resource in the Two Nodes with
Fencing (TNF) cluster has failed. The `tnf_resource_operational` metric
reports `0` when a resource agent reported an error during a monitor, start,
or stop operation.

Resources managed by Pacemaker in a TNF cluster include `Etcd` and `Kubelet`.
The alert labels identify the specific `resource` and `node`.

This is a `critical` severity alert that fires after the condition persists for
2 minutes.

> **Note:** For the `Etcd` resource, this alert is an API blind spot in
> 2-node topology. If the etcd process dies, quorum is lost (1 of 2 members),
> and the Kubernetes API becomes unavailable, preventing the PacemakerCluster
> CR from being updated. Only the `Kubelet` resource failure path fires in
> practice through the normal observability pipeline.

## Impact

A failed resource indicates an operational error. Pacemaker may automatically
attempt to restart the resource depending on the failure count and configured
thresholds. If the failure persists beyond the retry limit, the resource
remains stopped and manual intervention is required.

Operators may also see a console notification banner indicating a resource
failure.

## Diagnosis

Check the resource status and fail count:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource status
```

```console
$ oc debug node/<node-name> -- chroot /host pcs resource failcount show <resource-name>
```

Check the resource agent logs for error details:

```console
$ oc debug node/<node-name> -- chroot /host journalctl -u pacemaker -n 100 --no-pager
```

Check overall cluster status:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

Verify the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_resource_operational
```

### Post-recovery investigation

Check the disruption counter to see if the resource experienced transitions
during API downtime:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_resource_disruption_total
```

Query the disruption rate in Prometheus:

```console
$ curl -s 'localhost:9090/api/v1/query?query=rate(tnf_resource_disruption_total[10m])' | jq
```

## Mitigation

Reset the resource fail count and trigger Pacemaker to re-probe the resource:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource cleanup <resource-name>
```

If the resource continues to fail after cleanup:

- Check the resource agent configuration for errors.
- For `Etcd`: verify the etcd data directory, podman container state, and
  network connectivity.
- For `Kubelet`: verify the kubelet service status and configuration.

After remediation, verify the resource is operational:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource status
```

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
