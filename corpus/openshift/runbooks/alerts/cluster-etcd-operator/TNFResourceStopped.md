# TNFResourceStopped

## Meaning

This alert fires when a Pacemaker-managed resource in the Two Nodes with
Fencing (TNF) cluster has stopped and is not running on a node. The
`tnf_resource_started` metric reports `0` for the affected resource and node.

Resources managed by Pacemaker in a TNF cluster include `Etcd` and `Kubelet`.
The alert labels identify the specific `resource` and `node`.

This is a `critical` severity alert that fires after the condition persists for
5 minutes.

## Impact

The impact depends on which resource has stopped:

- **Etcd**: The node is no longer contributing an etcd member. In a two-node
  cluster, this means quorum is lost and the Kubernetes API becomes
  unavailable for write operations.
- **Kubelet**: The node cannot run workloads. Pods on the node will not be
  managed.

The `TNFResourceDisabled` alert may also fire if the resource was
administratively disabled. Resource ordering constraints mean that disabling
one clone resource (e.g. `kubelet-clone`) may cascade and stop other
resources (e.g. `etcd-clone`).

## Diagnosis

Check the status of all Pacemaker-managed resources:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource status
```

Check overall cluster status:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

Verify the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_resource_started
```

### Post-recovery investigation

Check the disruption counter to see if the resource experienced
`started -> stopped` transitions, including any that may have occurred during
API downtime:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_resource_disruption_total
```

Query the disruption rate in Prometheus:

```console
$ curl -s 'localhost:9090/api/v1/query?query=rate(tnf_resource_disruption_total[10m])' | jq
```

## Mitigation

If the resource was intentionally stopped or disabled, re-enable it:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource enable <resource-name>
```

If the resource stopped due to quorum loss after a node failure, investigate
the root cause (see `TNFNodeOffline` runbook) and wait for the cluster to
recover.

After remediation, verify the resource is running:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource status
```

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
