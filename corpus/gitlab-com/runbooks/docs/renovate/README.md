# Renovate at GitLab: Current Implementation Documentation

## Overview

[Renovate](https://github.com/renovatebot/renovate) is a dependency update tool used at GitLab to automate the process of keeping dependencies up-to-date. This document outlines the current implementation, configurations, and workflows of Renovate within the GitLab infrastructure.

## Current Implementation Approach

GitLab uses [`common-ci-tasks`](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks) as the
single, standard approach for running Renovate across projects.

**Repository**: [https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks)

**Key Characteristics**:

- Per-project CI job implementation
- Requires CI include and `renovate.json` configuration. This can be generated for you using our [`common-template-copier` template](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/docs/project-templates.md).
- Uses custom container image with specific tooling installed
- Onboarding is driven by `infra-mgmt`, which enables the `common_ci_tasks` stanza for a
  project (in combination with the `common-template-copier` template)

**Focus Areas**:

- Security and isolation by running one job per project
- Custom tooling baked into the image to generate/update templates and non-standard files

**Documentation**:

- [Main documentation](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/renovate-bot.md)
- [Project setup guide](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/docs/project-setup.md)
- [Configuration file](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/renovate-bot.yml)

## Adding dependencies

To configure Renovate Bot for a given project, follow the [Automated Project Setup](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/docs/project-setup.md#automated-project-setup) documentation in `common-ci-tasks`.

## Related Resources

- [Renovate official documentation](https://docs.renovatebot.com/)
- [GitLab Renovate epic](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/1479)
- [Consolidation issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16148)
  (closed) -- record of the decision to standardize on `common-ci-tasks` and retire the
  global Renovate runner

## Best Practices

[Renovate best practices](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/renovate-bot.md#best-practices) are documented in the `common-ci-tasks` project.

## Troubleshooting

### Dependency not being picked up

If you configured a dependency and it isn't getting picked up by Renovate
check the output of the latest scheduled pipeline job on the project in question.

If you need further debug data, check the `renovate-log.ndjson` file on the CI
job's artifacts and grep for the project's name.

### Testing out Renovate changes

If you suspect your `renovate.json` may need adjustments, you can try them out
before merging them the following way:

- `npm install -g renovate`
- From a local copy of the project you're testing against, do one of the following:

For a quick test of dependency logic, use:

```
LOG_LEVEL=DEBUG RENOVATE_PLATFORM=gitlab RENOVATE_TOKEN="${GITLAB_TOKEN}" renovate --platform=local --include-paths "some/path/to/test/**"
```

If you need to check the logic behind branch creation and opening MRs, use:

```
RENOVATE_REPOSITORIES=some/repo/to/test RENOVATE_BASE_BRANCH_PATTERNS=some-branch-to-test \
LOG_LEVEL=DEBUG RENOVATE_PLATFORM=gitlab RENOVATE_TOKEN="${GITLAB_TOKEN}" renovate --dry-run=full --include-paths "some/path/to/test/**" \
--branch-prefix-old "test/" --branch-prefix="test/" --use-base-branch-config=merge --autodiscover=false
```
