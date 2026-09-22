# Deployment Telegram Notifications

Depends on ab_deploy and ab_telegram_bot. Notifications are automatic with an enabled ab_deploy subscription; installing this
addon does not send messages or register webhooks. No Telegram deployment commands,
approval callbacks or automatic log attachments are implemented.

## Configure

1. Configure a bot and known group in Telegram Bots. Associate the bot with the group.
2. In Module Subscriptions, choose module **ab_deploy**, select the bot and default
   destination, choose English/Arabic, and enable the subscription.
3. Grant request authors read access by adding them to the bot's Authorized Users.
   Deployment developers, approvers and executors inherit Telegram Viewer only;
   they do not gain token access or permission to send arbitrary messages.
4. Notifications apply automatically to every deployment; there is no request checkbox.
   In the **Telegram Notifications** tab, leave overrides empty for subscription defaults, or override the bot, group/chat
   and topic. An explicit chat ID takes precedence over a selected group. Topic zero
   inherits the subscription topic; use a subscription without a topic for the main chat.
5. Request approval. Odoo saves the effective bot, destination, language and company.
   Missing or invalid configuration leaves a note without blocking deployment. Requests
   without a saved destination retry configuration at their next notification event.
   Existing saved destinations are preserved. No Telegram network call is required to approve.
6. Approve and queue selected targets as usual. Reports are sent only when a batch finishes.
   Executors and deployment administrators can also use **Send Deployment Report** on
   any request form, including before execution or while it is running.

The request company scopes its targets, jobs, runs, attempts and captured logs. Existing
requests receive the installation company's default company. Server/catalog records
remain governed by ab_deploy; this addon does not duplicate or repartition servers.
The operator must configure a group appropriate for the data they intend to disclose.

## Notifications

Manual and automatic completion reports share one builder and include every target on
this request, including successes from earlier batches. No approval or queued-batch
notification is sent. Each report consists of:

1. A text summary: request reference, title, full description, executor and totals for
   failed, unfinished, cancelled, delayed and succeeded targets. Long summaries split
   into multiple Telegram text messages without truncating the description.
2. A UTF-8 `<request>-servers.md` attachment: Arabic headers and status labels, with
   server serial, server name, area and current target status. Markdown columns use
   `---:` for right alignment in compatible viewers; Telegram receives a document.

Targets are counted once using their current deployment status. Queued/running/unknown
are counted and displayed as unfinished in the report. Rows and summary totals sort by
failed, unfinished, cancelled, delayed, succeeded; then Serial and name. Serial contains
the actual server value, not row numbering. Empty areas remain blank. Pipes/backslashes
are escaped and multiline cells are flattened.

Automatic reports show the finishing batch's executor; manual reports show the latest
batch's executor or Not started. Reports retain saved routing and topic settings.
Summary and attachment are queued atomically with the same ordering key. Repeated
completion callbacks do not duplicate a report. Each manual click intentionally creates
a fresh report; manual errors are displayed to the user. Files and content are immutable
snapshots in outgoing delivery history. No commands, tokens or logs are attached.

Enqueueing uses short ORM transactions already owned by approval/batch state updates.
SSH threads never access Telegram or the ORM. Delivery uses root.telegram rather than
root.deployment. Delivery failures do not alter deployment state. A construction failure
leaves a Telegram Notification Note on the request for diagnosis; it is not replayed by
re-running a deployment. Use Message History for delivery failures and retries.

A hard process kill before batch finalization can leave a run without an outcome message.
Use existing deployment monitoring recovery; no new periodic coordinator or cron is added.

## Installation and validation

Install both addons, restart the main Odoo service and refresh the separate queue-runner
service's registry/code after installation. Configure root.telegram capacity one under a
root capacity of at least two. Validate with a targeted module upgrade and inspect its log.
No installation step sends real Telegram messages. Use Send Test Message explicitly,
then an approved deployment, to confirm delivery to your chosen group.

Existing approved requests without a saved destination automatically use the subscription
at their next completion event or manual report. Past events are not replayed and deployments are not rerun.
