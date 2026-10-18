# Debugging Service Desk

[Docs](https://docs.gitlab.com/user/project/service_desk/)

## When to Use This Document

This document is for **Service Desk-specific debugging** after you've determined the issue is not a [general email infrastructure problem](../mailroom/README.md).

### First Steps for Service Desk Issues

1. **Check if this affects all email processing** (both Service Desk AND Reply by Email):
   - If yes → **Start with [Mailroom Infrastructure Triage](../mailroom/README.md)**
   - If no → Continue with this Service Desk debugging guide

2. **Check `#alerts_mailroom`** (Slack channel) for recent Mailroom processing errors

3. **Quick infrastructure check**:
   - [Mailroom Overview Dashboard](https://dashboards.gitlab.net/d/mailroom-main/mailroom-overview)
   - Are emails being processed by Mailroom but Service Desk logic failing?

### Service Desk System Context

**Service Desk builds on Reply by Email infrastructure:**

- **Initial ticket creation**: Uses separate email handler from reply by email functionality
- **Response functionality**: Service Desk responses use Reply by Email logic
- **Infrastructure dependency**: Both features depend on Mailroom → Sidekiq → GitLab processing

**Key email addresses:**

- `incoming+[project-key]@incoming.gitlab.com` (default)
- `contact-project+[project-key]@incoming.gitlab.com` (alias)

### Cross-References

- **Email infrastructure issues**: [Mailroom README](../mailroom/README.md) (main entry point)
- **Reply by Email problems**: Service Desk uses this for responses
- **Outgoing email delivery**: [Mailgun Operations](../mailgun/mailgun.md)

## DRI

The [Plan: Work Items group](https://handbook.gitlab.com/handbook/product/categories/#work-items-group) is responsible for Service Desk product development and maintenance.

Additionally, the [Scalability group](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/) has been doing some infrastructure work around mailroom on gitlab.com.

## Assessing impact

Despite being a free feature, Service Desk has low usage and spikes up and down (e.g. weekends/holidays).
Zoom out to a few days (3 or 7) to get a feel for the impact.

- Is traffic completely flat?
  - There could be a problem with Sidekiq, Mailroom or email ingestion as a whole. See [Determine root cause](#determine-root-cause).
  - There may be a recent change merged to [Gitlab::Email::Handler](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/email/handler.rb).
  - There may be a problem with GitLab DNS.
- Is traffic lower than normal?
  - There may be a recent breaking change to regular incoming email (for example, [`Gitlab::Email::Receiver`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/email/receiver.rb) or Service Desk email ingestion (for example, [`Gitlab::Email::ServiceDeskReceiver`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/email/service_desk_receiver.rb).
  - There could be a problem with a 3rd party service customers use for redirection; such as GMail or Google Groups. See [Find where the email goes](#find-where-the-emails-go).
- No detectable change?
  - Customers may be using an uncommon service for redirection that has changed its headers.
  - The customer's email may be marked as Spam in the incoming mail inbox.
    - SREs can log in to the mailboxes (`incoming@gitlab.com` and `contact-project@incoming.gitlab.com`) and search the spam folder.

Check the [Mailroom Grafana charts](https://dashboards.gitlab.net/d/mailroom-main/mailroom-overview)

- Is there a noticeable impact?

There are helpful links to the side of the charts (e.g. Kibana links).

## Determine root cause

Try to reproduce via a known Service Desk - e.g. [this sandbox](https://gitlab.com/issue-reproduce/mailroom-sandbox)

A good place to start is to get two emails sent to a known Service Desk experiencing issues - one that works (or worked), one that doesn't.
[Get them forwarded as `eml` files](https://support.google.com/mail/answer/9261412?hl=en) to ensure headers are intact.
Ask someone with a service desk setup to send you the emails they received.

### Email ingestion

**Docs**: [Incoming email](https://docs.gitlab.com/administration/incoming_email/) and [Configuring Service Desk](https://docs.gitlab.com/user/project/service_desk/#configuring-service-desk)

Since our email ingestion (and eventually Service Desk) uses header content to determine where an email is going, compare the headers to see if anything has changed.

- [The headers we accept](https://docs.gitlab.com/administration/incoming_email/#accepted-headers)
- Header comparison source code is in [`lib/gitlab/email/receiver.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/email/receiver.rb)

[Production issue 6419](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/6419) was due to a change in headers, specifically `Delivered-To` no longer being added to Google Group emails.

The project key should be visible in the headers, and that's how Service Desk knows which project to create the new issue in.

### Find where the emails go

At the time of writing, most Service Desk setups use a redirection mechanism (e.g. through a third-party Google group) or forwarding since it allows the user to distribute a fully customized email address, and reduces chance of abuse by obscuring the Service Desk email address and allowing it to be changed.

- Did the issue get created in that project, or another project (was the project key correct)?
- Did the sender get a "thank you" email (either a thank you email for that Service Desk, a different Service Desk, or a "I don't know where that email should go" email)
- If no thank you email, did the email wind up as a note somewhere (ie. ingested into a different part of the GitLab instance)?

In the past we've had:

- redirection of emails (third-party intermediary dropped headers, etc) causing [Production issue 6419](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/6419)
- incompatibility of JSON and non-UTF-8 encoding causing [Production issue 7029](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/7029)
  ... etc

### Trace a specific email

For gitlab.com - SREs have access to the `incoming@gitlab.com` mailbox, which can be checked to see if an email was received at all.

You can look up what happened to a specific e-mail by matching its SMTP `Message-Id` header to the `json.mail_uid` field.

In Kibana, find the logs via search: `json.mail_uid: <Message-Id>` and either `json.class: EmailReceiverWorker` or `json.class: ServiceDeskEmailReceiverWorker` (Service Desk emails may be serviced by either worker class, so it's ideal to check both)
[Here's an example](https://gitlab.com/gitlab-org/gitlab/-/issues/362030#note_942296374).

The headers we log are in [`lib/gitlab/email/receiver.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/98b8898604f3bc8d43ec079d51814d7ecadd3419/lib/gitlab/email/receiver.rb#L32-49).

| SMTP header     | Log field             |
|-----------------|-----------------------|
| `Message-Id`    | `json.mail_uid`       |
| `From`          | `json.from_address`   |
| `To`            | `json.to_address`     |
| `Delivered-To`  | `json.delivered_to`   |
| `Envelope-To`   | `json.envelope_to`    |
| `X-Envelope-To` | `json.x_envelope_to`  |

A full list of the headers we accept can be found the [incoming email](https://docs.gitlab.com/administration/incoming_email/#accepted-headers) documentation.

### Code flow

Emails go through the following to get to Service Desk:

- [Mailroom](https://gitlab.com/gitlab-org/gitlab-mail_room)
  - See [mail-room runbooks](../mailroom/README.md) for detailed debugging
  - Mailroom is a separate process outside of Rails. It ingests emails and determines whether to send them to different processes (e.g. Sidekiq queue, API, etc)
    - Reply to a note
    - Service Desk
    - etc
  - Mailroom interacts with rails using redis (adding a job to a sidekiq queue directly). This might be changed to an API call that enqueues the job instead.
    - [Infra epic &644](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/644) and [Scalability epic 1462](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/1462)
    - `POST /api/:version/internal/mail_room/*mailbox_type`
  - For source and Omnibus installs, we use [`config/mail_room.yml`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/config/mail_room.yml) (via [`files/gitlab-cookbooks/gitlab/recipes/mailroom.rb`](https://gitlab.com/gitlab-org/omnibus-gitlab/-/blob/master/files/gitlab-cookbooks/gitlab/recipes/mailroom.rb#L25) for Omnibus).
  - For charts, we use [`config/mail_room.yml`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/config/mail_room.yml)
    - [Charts docs](https://docs.gitlab.com/charts/charts/gitlab/mailroom/)
- Rails - either Mailroom-direct-to-Sidekiq (old method) or API-call-to-Sidekiq (new method)
  - If a Mailroom-initiated Sidekiq job:
    - In Kibana, make the following query to `pubsub-sidekiq-inf-gprd`:
      - `json.class: EmailReceiverWorker`
      - `json.delivered_to: exists`
    - Code path:
      - [`app/workers/service_desk_email_receiver_worker.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/workers/service_desk_email_receiver_worker.rb) OR [`app/workers/email_receiver_worker.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/workers/email_receiver_worker.rb)
      - [`lib/gitlab/email/service_desk_receiver.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/email/service_desk_receiver.rb)
  - If an API call-initiated job, we make a postback POST request to our internal API, which enqueues the job via Sidekiq:
    - In Kibana, make the following query to `pubsub-rails-inf-gprd`:
      - `json.route: /api/:version/internal/mail_room/*mailbox_type`
      - `json.method: POST`
      - (if needed) `json.project_id: <the project ID>`
    - [`lib/api/internal/base.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/509e4ffb7626999af33406638bb80cd0de695d85/lib/api/internal/base.rb#L278-284)
    - [`lib/api/internal/mail_room.rb](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/api/internal/mail_room.rb)
