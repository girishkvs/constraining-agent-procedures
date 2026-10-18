# TNFClusterInMaintenance

## Meaning

This alert fires when the entire Two Nodes with Fencing (TNF) Pacemaker
cluster is placed in maintenance mode. The `tnf_cluster_in_service` metric
reports `0` when the cluster-wide `maintenance-mode` property is set to `true`.

This is a `warning` severity alert that fires after the condition persists for
2 minutes.

## Impact

While in maintenance mode, Pacemaker stops monitoring and managing all
resources on all nodes. This means:

- No automatic failover if a node fails.
- No fencing of unresponsive nodes.
- No resource recovery (etcd, Kubelet) after failures.
- The cluster is effectively unprotected against split-brain scenarios.

Maintenance mode is typically enabled intentionally for administrative tasks.
This alert serves as a reminder that protection is disabled.

Operators may also see a console notification banner indicating the cluster is
in maintenance mode.

## Diagnosis

Check whether maintenance mode is enabled:

```console
$ oc debug node/<node-name> -- chroot /host pcs property show maintenance-mode
```

Check overall cluster status to see the effect on resources:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

Verify the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_cluster_in_service
```

## Mitigation

If maintenance work is complete, disable maintenance mode:

```console
$ oc debug node/<node-name> -- chroot /host pcs property set maintenance-mode=false
```

After disabling maintenance mode, verify that Pacemaker resumes resource
monitoring:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

If maintenance mode was enabled unintentionally, disable it immediately.
The cluster is unprotected while in maintenance mode.

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
