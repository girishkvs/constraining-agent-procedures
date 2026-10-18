# TNFNodeFencingUnavailable

## Meaning

This alert fires when fencing (STONITH) is not available for a node in the Two
Nodes with Fencing (TNF) cluster. The `tnf_node_fencing_available` metric
reports `0` when all fence devices for the node are unhealthy, meaning the
cluster cannot safely fence the node in case of failure.

Common causes include an unreachable BMC (Redfish endpoint), invalid BMC
credentials, or all fence devices being administratively disabled.

This is a `critical` severity alert that fires after the condition persists for
5 minutes.

## Impact

Without fencing, the cluster cannot protect against split-brain scenarios. If
a node failure occurs while fencing is unavailable, Pacemaker cannot guarantee
data consistency and will refuse to start resources on the surviving node. The
cluster is effectively unprotected.

Operators may also see a console notification banner indicating that fencing is
unavailable.

## Diagnosis

Check the status of STONITH devices:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith status
```

Check the detailed STONITH configuration:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith config
```

Check the fail count for fence devices:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith show <device-name> --full
```

Verify the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_node_fencing_available
```

### BMC connectivity

Test connectivity to the BMC (Redfish) endpoint from the node:

```console
$ oc debug node/<node-name> -- chroot /host curl -sk https://<bmc-ip>/redfish/v1/Systems
```

### Fencing retry exhaustion

After `stonith-max-attempts` (default: 10) failed fencing attempts, Pacemaker
**stops retrying permanently**. The fencing operation transitions to
`pcmk__graph_wait` and no further attempts are made, even if the BMC becomes
reachable again. Pacemaker does **not** automatically re-probe.

Check whether the fail count has reached the maximum:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith failcount show <device-name>
```

## Mitigation

### Fix BMC connectivity

1. Verify the BMC network is reachable from both nodes.
2. Verify BMC credentials are correct in the STONITH resource configuration.
3. If the BMC was temporarily unreachable, verify it is back online.

### Re-enable disabled fence devices

If the fence device was administratively disabled:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith enable <device-name>
```

### Reset after fencing retry exhaustion

After fixing the underlying issue (BMC connectivity, credentials), you
**must** manually reset the fail count. Recovery is **not** automatic:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith cleanup <device-name>
```

This resets the fail count and triggers Pacemaker to re-probe the fence device.

### Verify recovery

After remediation, confirm that fencing is available:

```console
$ oc debug node/<node-name> -- chroot /host pcs stonith status
```

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
