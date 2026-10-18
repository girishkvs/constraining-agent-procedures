# Config Management

GitLab.com virtual machines are managed by Chef.

* [Chef Troubleshooting](chef-troubleshooting.md)
* [Chef Client Process](chef-vm-process.md) - How nodes are built and
  provisioned with Chef
* [Chef Server](chef-server.md)

## Chef Change Management

GitLab's cookbooks reside in the
[gitlab-cookbooks group](https://gitlab.com/gitlab-cookbooks) and are mirrored
to the [Ops GitLab instance](https://ops.gitlab.net/gitlab-cookbooks).

The [chef-repo project](https://gitlab.com/gitlab-com/gl-infra/chef-repo)
provides a central control for managing how cookbooks are pinned to
environments and where environments, roles, and nodes are version controlled.

* [Chef Guidelines](chef-guidelines.md) - When to make a new cookbook and
  good patterns for Chef
* [Creating new cookbooks](chef-cookbook-process.md) - How to generate a new cookbook
* [Chef Testing with Chefspec](chefspec.md)
* [Chef Vault Secrets](chef-vault.md)
* [VM User Management](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/doc/user-administration.md) -
  Adding and removing users and managing group memberships (chef-repo, internal)
