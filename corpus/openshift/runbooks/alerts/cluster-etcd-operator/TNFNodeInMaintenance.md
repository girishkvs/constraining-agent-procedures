# TNFNodeInMaintenance

## Meaning

This alert fires when a specific node in the Two Nodes with Fencing (TNF)
cluster is placed in maintenance mode. The `tnf_node_in_service` metric
reports `0` when a node-level maintenance flag is set, meaning Pacemaker stops
monitoring resources on that node while continuing to monitor the other node.

This is different from cluster-wide maintenance mode
(`TNFClusterInMaintenance`), which affects all nodes.

This is a `warning` severity alert that fires after the condition persists for
2 minutes.

## Impact

While a node is in maintenance mode:

- Pacemaker stops monitoring resources on that node.
- Resources on the node continue to run but are not managed.
- If a resource fails on the maintenance node, Pacemaker will not restart it
  or take corrective action.
- Fencing is still active for the node (unlike cluster-wide maintenance mode).

Operators may also see a console notification banner indicating the node is in
maintenance mode.

## Diagnosis

Check which nodes are in maintenance mode:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

Check node attributes for the maintenance flag:

```console
$ oc debug node/<node-name> -- chroot /host pcs node attribute
```

Verify the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_node_in_service
```

## Mitigation

If maintenance work on the node is complete, remove the maintenance flag:

```console
$ oc debug node/<node-name> -- chroot /host pcs node unmaintenance <node-name>
```

After removing maintenance mode, verify that Pacemaker resumes resource
monitoring on the node:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

If maintenance mode was enabled unintentionally, remove it immediately.
Resources on the node are unmonitored while in maintenance mode.

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
