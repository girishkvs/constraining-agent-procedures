# TNFNodeUnclean

## Meaning

This alert fires when a node in the Two Nodes with Fencing (TNF) cluster is in
an "unclean" state. The `tnf_node_clean` metric reports `0` when Corosync has
lost contact with the node but fencing has not yet completed or has failed. The
node's state cannot be confirmed as safe.

This is a `critical` severity alert that fires after the condition persists for
5 minutes.

> **Note:** This alert is classified as an API blind spot in 2-node topology.
> The unclean state always coincides with etcd quorum loss (1 of 2 members
> available means no quorum), so the Kubernetes API is unavailable and the
> PacemakerCluster CR cannot be updated to record this state. This alert is
> included for edge-case completeness but is expected to have zero practical
> firings under normal conditions.

## Impact

While a node is unclean, Pacemaker will not start resources on the surviving
node to prevent a split-brain scenario. The cluster is effectively frozen:

- etcd is not running (quorum lost).
- The Kubernetes API is unavailable.
- No workloads can be scheduled.

The cluster remains in this state until fencing succeeds (confirming the failed
node is powered off) or an administrator intervenes.

### Typical timeline

1. Node goes offline, Corosync detects loss of communication.
2. Node transitions to `unclean` state.
3. etcd quorum is lost, API becomes unavailable.
4. Pacemaker initiates fencing via STONITH.
5. If fencing succeeds: node transitions to `offline` (clean), resources stop
   gracefully.
6. If fencing fails: cluster remains frozen indefinitely until manual
   intervention.

## Diagnosis

Check Pacemaker status from the surviving node:

```console
$ oc debug node/<surviving-node> -- chroot /host crm_mon -1
```

Check for fencing activity:

```console
$ oc debug node/<surviving-node> -- chroot /host pcs stonith status
```

Check STONITH history for recent fencing attempts:

```console
$ oc debug node/<surviving-node> -- chroot /host pcs stonith history
```

If the API is available, check the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_node_clean
```

## Mitigation

### If fencing is in progress

Wait for the fencing operation to complete. Once the failed node is
successfully fenced (powered off via BMC), Pacemaker will mark it as clean and
proceed with resource management.

### If fencing has failed

Manually fence the unclean node:

```console
$ oc debug node/<surviving-node> -- chroot /host pcs stonith fence <unclean-node>
```

If manual fencing also fails, verify BMC connectivity and credentials, then
retry. See the `TNFNodeFencingUnavailable` runbook for BMC troubleshooting
steps.

### After recovery

Once fencing succeeds, verify the cluster returns to a healthy state:

```console
$ oc debug node/<surviving-node> -- chroot /host pcs status
```

For operational guidance on degraded TNF clusters, see the [Two Nodes with
Fencing documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
