# TNFNodeFencingDegraded

## Meaning

This alert fires when one or more fence devices for a node in the Two Nodes
with Fencing (TNF) cluster have failed, but at least one device remains
operational — a state referred to as *fencing degraded*. The
`tnf_node_fencing_healthy` metric reports `0` while
`tnf_node_fencing_available` is still `1`.

This is a `warning` severity alert that fires after the condition persists for
10 minutes.

> **Note:** This alert requires a multi-agent fencing setup where a node has
> more than one fence device configured. In current TNF deployments, each node
> typically has a single Redfish BMC agent, making this alert uncommon.

## Impact

Fencing redundancy is reduced. The cluster can still fence the node using the
remaining healthy device(s), but if those also fail, fencing becomes
unavailable entirely (triggering `TNFNodeFencingUnavailable`).

## Diagnosis

Check the status of all STONITH devices:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith status
```

Identify which device has failed:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith config
```

Check the fail count for each fence device:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith failcount show <device-name>
```

Verify the metric values:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep -E 'tnf_node_fencing_(healthy|available)'
```

## Mitigation

Reset the failed fence device:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith cleanup <device-name>
```

If the device continues to fail, check its configuration:

- Verify BMC connectivity for the affected device.
- Verify credentials are correct.
- Check the device-specific configuration parameters.

After remediation, confirm all fence devices are healthy:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith status
```

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
