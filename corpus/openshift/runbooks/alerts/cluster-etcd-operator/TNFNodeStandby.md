# TNFNodeStandby

## Meaning

This alert fires when a node in the Two Nodes with Fencing (TNF) cluster is
placed in standby mode. The `tnf_node_active` metric reports `0` when a node
is in standby, meaning Pacemaker will move all resources off the node and
prevent new resources from being started on it.

This is a `warning` severity alert that fires after the condition persists for
5 minutes.

## Impact

When a node is in standby:

- All resources running on the node are stopped.
- In a two-node cluster, this means resources can only run on the remaining
  active node.
- etcd loses one member, which in a two-node cluster means quorum is lost and
  the Kubernetes API becomes unavailable for write operations.
- The node remains a member of the Pacemaker cluster and fencing is still
  active.

Operators may also see a console notification banner indicating the node state.

## Diagnosis

Check which nodes are in standby:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

Check node attributes:

```console
$ oc debug node/<node-name> -- chroot /host pcs node attribute
```

Verify the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_node_active
```

## Mitigation

If the standby was intentional and the maintenance work is complete, remove
the standby flag:

```console
$ oc debug node/<node-name> -- chroot /host pcs node unstandby <node-name>
```

After removing standby, verify that resources restart on the node:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

If standby was enabled unintentionally, remove it immediately. The cluster is
operating in a degraded state with only one active node.

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
