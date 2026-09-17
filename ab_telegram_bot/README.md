# Telegram Bots

Manage multiple Telegram bots, known clients, groups and module routing in Odoo 19.
Dependencies: base, queue_job, Python requests. Manual Fetch Updates is available. No background polling, webhooks, scheduled jobs,
installation callbacks or automatic replies are installed.

## Setup

1. Give configuration owners **Telegram Administrator**. Settings administrators inherit it.
2. Create a bot using the token issued by BotFather. Use **Check Connection**.
3. Assign **Authorized Users** to each bot. Give senders **Telegram Operator**;
   viewers can inspect their assigned bots without sending. Tokens are admin-only,
   masked, excluded from the export action and never copied into delivery jobs.
   Tokens are stored in the Odoo database, not encrypted by this module: protect
   database access and backups. Token rotation is performed on the bot record.
4. Add the bot to the intended Telegram group. Register the known numeric chat ID
   (including the negative sign), associate the bot and use **Validate Group**.
   Channel posting and some reactions/deletions require Telegram administrator rights.
5. Create a Module Subscription, choose the installed module and bot, and set a group
   or explicit destination ID. Explicit IDs override group selection. Topic IDs are optional.
   Subscriptions start disabled. Set the notification language, then enable when ready.
6. **Send Test Message** sends only when explicitly clicked and confirmed.

Telegram user IDs, chat IDs and bot IDs are strings to preserve 64-bit values.
There is no group-enumeration endpoint. Known groups can be registered manually or
discovered from updates returned when you click Fetch Updates. Started Bots records
private /start commands received by Odoo, as well as manually recorded associations. Private recipients must already have
started the bot. Group validation checks membership but does not grant permissions.

## Queue

Configure the existing queue runner with:

```ini
[queue_job]
channels = root:2,root.deployment:1,root.telegram:1
```

Use at least two queue-capable HTTP workers so a long deployment does not occupy the
only worker. The addon defines root.telegram as a dedicated channel. Explicit capacity is required: dynamically created channels otherwise inherit the
parent capacity. The configuration above gives Telegram its own single worker slot.
Restart the queue-runner service after installing new Python modules or changing its
configuration. Do not run a second queue runner in the main UI service.

Messages record their payload, source, state, attempt count and returned Telegram IDs.
Files are copied to delivery-owned attachments before queueing. The queue arguments
contain only the record, never a token or file content. One HTTP attempt has bounded
connect/read timeouts. A conservative three-second interval per bot limits fan-out.
Retryable responses use backoff and Telegram retry_after, with at most five attempts.
Messages for the same event stream are attempted in creation order.

Send intent is committed before contacting Telegram. If a worker disappears after that
point, recovery marks the delivery unknown rather than blindly sending it again.
Read/connection ambiguity is also marked unknown. Inspect Telegram before **Retry
Delivery**: Telegram does not support exactly-once sending. Failed/unknown/cancelled
messages do not permanently block subsequent event messages. A queued job can be
recovered through Job Queue; retry on a Sending message is permitted only after its
queue job is no longer active. Cancel Delivery never retracts already delivered messages.

## Python API

Public methods enforce operator membership, assigned-bot access and allowed companies.
They return ab_telegram_bot_message recordsets for queued operations. Delivery state and
Telegram message IDs are available later. Private helpers are for trusted module code.

```python
bot.send_message('-1001234567890', 'Deployment approved')
bot.send_message(chat, 'Hello', reply_parameters={'message_id': 123})
bot.send_message(chat, '<b>Ready</b>', parse_mode='HTML',
                 reply_markup={'inline_keyboard': [[{'text': 'Open Odoo', 'url': 'https://example.com'}]]})
bot.send_document(chat, attachment.id, caption='Report')
bot.send_file(chat, {'filename': 'report.txt', 'data': base64_data}, caption='Report')
bot.send_photo(chat, telegram_file_id, caption='Photo')  # send_image is an alias
bot.send_video(chat, attachment.id, caption='Video')
bot.send_audio(chat, attachment.id)
bot.send_voice(chat, attachment.id)
bot.send_animation(chat, attachment.id)
bot.send_media_group(chat, [{'type': 'photo', 'media': photo1.id},
                           {'type': 'photo', 'media': photo2.id}])
bot.edit_message_text(chat, message_id, 'Updated')
bot.edit_message_caption(chat, message_id, 'Updated caption')
bot.delete_message(chat, message_id)
bot.forward_message(chat, source_chat, message_id)
bot.copy_message(chat, source_chat, message_id, caption='Copy')
bot.set_message_reaction(chat, message_id, '👍')
bot.send_chat_action(chat, 'typing')
bot.get_me()
bot.get_chat(chat)
bot.get_chat_member(chat, telegram_user_id)
bot.get_file(file_id)
attachment_id = bot.download_file(file_id, filename='download.bin')
```

Media sources accept an authorized attachment ID, a base64 upload dict, or a Telegram
file ID. Bot API-supported remote URLs can also be supplied as media strings; Telegram
fetches them. Uploads are limited to 10 MiB for photos and 50 MiB for other media;
Telegram may impose additional format/dimension restrictions. Captions must fit 1024
UTF-16 units. Plain long text splits at safe newline/code-point boundaries; formatted
text must be supplied as separately formatted blocks of at most 4000 UTF-16 units.
Downloads are bounded to 20 MiB and return an attachment ID, never a token-bearing URL.

References: https://core.telegram.org/bots/api and https://core.telegram.org/bots/faq

## Manual incoming updates

Open a bot and click **Fetch Updates** (Telegram Operator or Administrator). One click
retrieves at most 100 updates immediately, without waiting in a polling loop. A full
batch prompts another click. This action consumes updates for that bot: use only one
receiver, and do not also poll the same token from another Odoo database or application.
Telegram keeps undelivered updates for at most 24 hours; this is not a history backfill.
Webhook-enabled bots are rejected without changing their webhook or dropping updates.

**Incoming Updates** and the bot smart button show text/captions, sender/chat IDs,
processing state and raw JSON. Media files remain on Telegram; metadata/file IDs are
preserved in raw updates. Unsupported updates are retained as Ignored. There are no
automatic replies or Telegram deployment commands.

Raw data is immutable and company/bot scoped. A unique bot/update key prevents duplicate
storage. A protected offset commits with each batch; the next manual fetch acknowledges
the previously committed batch. Never loop with an advanced offset before committing.
Only one bot record per Telegram identity may claim polling within this database.
Rotate tokens only for the same identity; another Telegram bot needs a new Odoo record.

Private /start commands (including start parameters) add Started Bots. Group activity
adds only Observed Bots. Human senders refresh client names/usernames. Bot membership
changes update group associations; left/kicked bots are removed without deleting the
group or history. Observed Bots retains historical visibility. Profile/membership event
versions prevent an older failed update from undoing a newer processed event. Unsupported
chat migration/service details remain visible in raw JSON for manual configuration.

Failures processing individual updates are retained for **Retry Processing**; they do not
block fetching later updates. Retry Processing does not call Telegram, send replies or
advance the polling offset. Archived client/group records are reused without unarchiving.
