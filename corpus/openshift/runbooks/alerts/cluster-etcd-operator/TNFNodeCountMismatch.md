# TNFNodeCountMismatch

## Meaning

This alert fires when the Two Nodes with Fencing (TNF) cluster does not have
the expected number of nodes. In a TNF topology, exactly two control-plane
nodes are required. The `tnf_cluster_node_count_as_expected` metric reports `0`
when Corosync membership diverges from the expected count.

This is a `critical` severity alert that fires after the condition persists for
5 minutes.

> **Note:** This alert is classified as structurally unreachable in normal TNF
> operation. Corosync membership is fixed at two nodes in `corosync.conf`, and
> any deviation during node replacement is transient (seconds) and coincides
> with API unavailability, preventing the alert from being evaluated. This
> alert is included for edge-case completeness.

## Impact

If the cluster has fewer nodes than expected, etcd cannot maintain quorum and
the Kubernetes API becomes unavailable for write operations. Pacemaker will
attempt to fence the missing node and stop resources to protect data
consistency.

If an unexpected node has been added, cluster behavior is undefined as the TNF
topology supports exactly two nodes.

## Diagnosis

Check overall Pacemaker cluster health from one of the nodes:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

Verify the current Corosync membership:

```console
$ oc debug node/<node-name> -- chroot /host corosync-cmapctl | grep members
```

Check the expected node configuration:

```console
$ oc debug node/<node-name> -- chroot /host grep -A5 'nodelist' /etc/corosync/corosync.conf
```

Verify the metric value from the etcd-operator:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_cluster_node_count_as_expected
```

Check the OpenShift node status:

```console
$ oc get nodes -l node-role.kubernetes.io/master=
```

## Mitigation

Investigate why the node count has changed:

- If a node was removed or is being replaced, verify the replacement procedure
  was completed and the new node has joined the Pacemaker cluster.
- If a node failed and was fenced, wait for it to recover and rejoin the
  cluster. After recovery, verify that Corosync shows two members.

In normal TNF operation, this alert is not expected to fire. If it persists,
escalate to Red Hat support for guidance on the node replacement procedure.

For operational guidance on degraded TNF clusters, see the [Two Nodes with
Fencing documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
