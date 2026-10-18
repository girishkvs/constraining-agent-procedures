# TNFNodeOffline

## Meaning

This alert fires when a node in the Two Nodes with Fencing (TNF) cluster is
offline. The `tnf_node_online` metric reports `0` when Corosync has lost
communication with the node, indicating a node failure, reboot, or network
partition.

This is a `critical` severity alert that fires after the condition persists for
2 minutes.

## Impact

In a two-node cluster, losing one node means etcd loses quorum (1 of 2
members). The Kubernetes API becomes unavailable for write operations.
Pacemaker will attempt to fence the offline node via STONITH to ensure data
consistency before stopping resources on the surviving node.

If fencing succeeds, the surviving node transitions to a known-good state with
resources stopped. If fencing fails, the cluster remains frozen in an unclean
state.

## Diagnosis

Check Pacemaker cluster status from the surviving node:

```console
$ oc debug node/<surviving-node> -- chroot /host pcs status
```

> **Note:** If the offline node was hosting the Prometheus pod, the
> `oc port-forward` session may break. Re-establish it from the surviving
> node if needed.

Check detailed node states:

```console
$ oc debug node/<surviving-node> -- chroot /host crm_mon -1
```

Verify node status from the OpenShift perspective:

```console
$ oc get nodes -l node-role.kubernetes.io/master=
```

Check the metric value:

```console
$ oc exec -n openshift-etcd-operator deploy/etcd-operator -- \
    curl -sk https://localhost:8443/metrics | grep tnf_node_online
```

Check for any related alerts that may help with diagnosis:

```console
$ curl -s 'localhost:9090/api/v1/query?query=ALERTS{alertname=~"TNF.*"}' | jq
```

### Hardware and network investigation

- Verify the node's hardware status via the BMC (Redfish) console.
- Check network connectivity between the two nodes.
- Review system logs on the surviving node for Corosync communication errors.

## Mitigation

- If the node is rebooting (e.g., after an upgrade or maintenance), wait for
  it to come back online. Pacemaker will automatically re-integrate the node
  when Corosync communication is restored.
- If the node has failed due to a hardware issue, address the hardware problem
  and power the node back on.
- If there is a network partition, restore network connectivity between the
  nodes.

After the node recovers, verify that both nodes are online and resources are
running:

```console
$ oc debug node/<node-name> -- chroot /host pcs status
```

For operational guidance on degraded TNF clusters, see the [Two Nodes with
Fencing documentation][docs].

[docs]: https://docs.openshift.com/container-platform/latest/edge_computing/deploy-two-node-with-fencing.html
