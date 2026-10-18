# SSCS - Authentication & Authorization Runbooks

Ownership:

- [Authentication Group](https://handbook.gitlab.com/handbook/engineering/development/sec/security-platform/authentication/).
- [Authorization Group](https://handbook.gitlab.com/handbook/engineering/development/sec/security-platform/authorization/).

## Runbooks

The GATE Infra runbooks are maintained in the iam repository under [docs/runbooks](https://gitlab.com/gitlab-org/auth/iam/-/blob/main/docs/runbooks/README.md):

- [GATE / iam-data-access](https://gitlab.com/gitlab-org/auth/iam/-/blob/main/docs/runbooks/iam-data-access.md)
- [Cloud Connector authentication and key rotation](https://gitlab.com/gitlab-org/auth/iam/-/blob/main/docs/runbooks/cloud-connector.md)
- [YugabyteDB Aeon](https://gitlab.com/gitlab-org/auth/iam/-/blob/main/docs/runbooks/yugabytedb-aeon.md)

Runbooks maintained in this repository:

- [E-Mail based OTP](./email-based-one-time-passwords-otp.md)
- [Blocked user login attempts are high](./blocked-user-logins.md)
- [Rate of successful user logins is zero](./zero-successful-user-logins.md)
- [Project authorization refresh fan-out](./project-authorization-refresh-fan-out.md)
