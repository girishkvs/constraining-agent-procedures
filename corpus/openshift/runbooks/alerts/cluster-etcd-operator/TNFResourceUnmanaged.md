# TNFResourceUnmanaged

## Meaning

This alert fires when a Pacemaker-managed resource in the Two Nodes with
Fencing (TNF) cluster has been placed in unmanaged mode. The
`tnf_resource_managed` metric reports `0` when a resource is unmanaged,
meaning Pacemaker stops monitoring the resource but does not stop it.

Resources managed by Pacemaker in a TNF cluster include `Etcd` and `Kubelet`.
The alert labels identify the specific `resource` and `node`.

This is a `warning` severity alert that fires after the condition persists for
5 minutes.

## Impact

While a resource is unmanaged:

- The resource continues to run but is not monitored by Pacemaker.
- If the resource fails, Pacemaker will not restart it or take any corrective
  action.
- Automatic failover is disabled for this resource.

Unmanaging a resource is typically done intentionally for debugging or manual
maintenance.

## Diagnosis

Check the resource status to identify unmanaged resources:

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
    curl -sk https://localhost:8443/metrics | grep tnf_resource_managed
```

### Post-recovery investigation

Check the disruption counter to see if the resource experienced transitions
while unmanaged:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_resource_disruption_total
```

## Mitigation

If the maintenance or debugging work is complete, return the resource to
managed mode:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource manage <resource-name>
```

After re-managing the resource, verify that Pacemaker resumes monitoring:

```console
$ oc debug node/<node-name> -- chroot /host pcs resource status
```

If the resource was unmanaged unintentionally, re-manage it immediately. The
resource is not protected while unmanaged.

For operational guidance, see the [Two Nodes with Fencing
documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
