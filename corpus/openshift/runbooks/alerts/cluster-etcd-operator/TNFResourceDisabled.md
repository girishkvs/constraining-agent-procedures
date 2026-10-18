# TNFResourceDisabled

## Meaning

This alert fires when a Pacemaker-managed resource in the Two Nodes with
Fencing (TNF) cluster has been administratively disabled. The
`tnf_resource_enabled` metric reports `0` when a resource is disabled,
meaning Pacemaker has stopped the resource and will not start it.

Resources managed by Pacemaker in a TNF cluster include `Etcd` and `Kubelet`.
The alert labels identify the specific `resource` and `node`.

This is a `warning` severity alert that fires after the condition persists for
5 minutes.

> **Note:** Disabling a resource also stops it, so the `TNFResourceStopped`
> alert may fire at the same time for the same resource.

## Impact

A disabled resource is intentionally stopped. The impact depends on which
resource is disabled:

- **Etcd**: The node loses its etcd member. In a two-node cluster, this means
  quorum is lost and the Kubernetes API becomes unavailable.
- **Kubelet**: The node cannot run workloads.

> **Warning:** In a two-node TNF cluster, disabling any Pacemaker clone
> resource (`etcd-clone` or `kubelet-clone`) is destructive. Resource ordering
> constraints cause cascading stops — disabling `kubelet-clone` also stops
> `etcd-clone`. The Kubernetes API becomes unavailable, and recovery requires
> direct node access (SSH or BMC console) to re-enable the resource.

## Diagnosis

Check the resource status to identify disabled resources:

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
    curl -sk https://localhost:8443/metrics | grep tnf_resource_enabled
```

### Post-recovery investigation

Check the disruption counter to see if the resource experienced transitions:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_resource_disruption_total
```

Query the disruption rate in Prometheus:

```console
$ curl -s 'localhost:9090/api/v1/query?query=rate(tnf_resource_disruption_total[10m])' | jq
```

## Mitigation

If the resource was disabled intentionally and the work is complete, re-enable
it:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource enable <resource-name>
```

After re-enabling, verify that the resource starts and is running:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource status
```

If the resource was disabled unintentionally, re-enable it immediately. The
cluster is operating in a degraded state while the resource is disabled.

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
