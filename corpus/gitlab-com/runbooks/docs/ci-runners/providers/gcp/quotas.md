# Quotas

There is a limit of how many requests we can send to Google Cloud API.
There are different kind of quotas some API request specific and some
resource specific.

To read about this you can look at GCP quotas:

- [Resource quotas](https://docs.cloud.google.com/compute/resource-usage)
- [API quota](https://docs.cloud.google.com/docs/quotas/view-manage#api_specific_quota)
- [Increase quota](https://docs.cloud.google.com/docs/quotas/view-manage#requesting_higher_quota)

## Dashboard

There is a specific quota usage dashboard which can be found in:
<https://dashboards.gitlab.net/goto/_6E_Q_TSR?orgId=1>
This doesn't cover the API quota because they aren't exported yet.

## Runner logs

You should be able to see if `gitlab-runner` is reaching the Quota limits
by searching in the `pubsub-runner-inf-gprd` index in
[Kibana](https://log.gprd.gitlab.net/app/r/s/OtI2W).

![resource quota exceeded example](./img/quota_exceeded_resource.png)
![api quota exceeded example](./img/quota_exceeded_api.png)
![api quota exceeded example](./img/quota_exceeded_operation.png)
