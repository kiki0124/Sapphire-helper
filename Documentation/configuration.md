# Configuration

Copy the root `_.env` template to `.env` and replace each placeholder. Local modules call `load_dotenv()`; a root environment file is used by the documented local setup. Docker receives values through `--env-file .env`.

Most IDs are converted to integers when modules are imported. Missing values, blank values and values that are not integers can prevent startup. IDs must refer to the resources intended for this instance.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `BOT_TOKEN` | Discord bot authentication token. |
| `SUPPORT_CHANNEL_ID` | Support forum used for post management, reminders and redirection. |
| `FEEDBACK_CHANNEL_ID` | Feedback forum recognised by the redirection workflow. |
| `GENERAL_CHANNEL_ID` | General channel used for optional EPI sticky messages. |
| `NDR_CHANNEL_ID` | Channel used by the developer-review guidance. |
| `ALERTS_THREAD_ID` | Thread receiving action logs, diagnostics and unhandled errors. |
| `QR_LOG_THREAD_ID` | Thread receiving logs for removed quick replies. |
| `EPI_LOG_THREAD_ID` | Thread receiving incident and paging logs. |
| `TAG_LOGGING_THREAD_ID` | Thread receiving reusable-tag creation, edit and deletion logs. |
| `EXPERTS_ROLE_ID` | Community expert role used by staff checks. |
| `MODERATORS_ROLE_ID` | Moderator role used by staff checks. |
| `DEVELOPERS_ROLE_ID` | Developer role used by staff checks. |
| `UNANSWERED_TAG_ID` | Forum tag for posts without a response. |
| `NOT_SOLVED_TAG_ID` | Forum tag for answered posts that remain unresolved. |
| `SOLVED_TAG_ID` | Forum tag for resolved posts. |
| `NEED_DEV_REVIEW_TAG_ID` | Forum tag for posts awaiting developer review. |
| `CUSTOM_BRANDING_TAG_ID` | Forum tag identifying Custom Branding posts. |
| `WAITING_FOR_REPLY_TAG_ID` | Forum tag for posts awaiting a reply to their owner. |
| `APPEAL_GG_TAG_ID` | Forum tag identifying appeal.gg posts. |
| `NTFY_TOPIC_NAME` | ntfy topic receiving developer pages. |

Forum tags must belong to the configured support forum. Log thread IDs must identify threads whose parent channels allow the bot to access or create the webhooks used for logging.

## Discord application and permissions

Enable **Message Content** in the Discord developer portal. The application enables guild, guild-message and guild-reaction events in code. It deliberately leaves Members and Presence disabled; see [the intent notes](../Internal%20Docs/Main/intents.md).

Install the bot into the intended guild with access to bot functionality and application commands. Grant permissions according to the features you use:

| Feature | Relevant permissions |
| --- | --- |
| Messages and guidance | View channels, send messages, send messages in threads, read message history; embed links and attach files where used. |
| Post management | Create public threads and manage threads. |
| Redirection and quick-reply cleanup | Manage messages, plus access to the source channel and support forum. |
| Logging and paging acknowledgements | Manage webhooks in the relevant parent channels. |
| Emergency locking and slowmode | Manage channels. |

This table is a feature overview, not a complete permission calculation. Channel overwrites and thread visibility also affect access. Validate the enabled actions in your test server.

## Server-specific assumptions

The environment template does not cover every server-specific value. Review these source locations when running another instance:

- `SH/cogs/epi.py`: the lead developer ID, recognised rate-limit channel IDs, and channel names such as `status` and `sapphire-experts`.
- `SH/cogs/cluster_tracker.py`: the `sapphire-experts` channel lookup and Sapphire status websocket endpoint.
- `SH/main.py`: user IDs mentioned in unhandled-error notifications and fallback slash-command IDs.
- UI messages throughout the cogs: Sapphire links, custom emoji and support-server wording.

Paging posts to `https://ntfy.sh/`. Live cluster tracking connects to Sapphire's status websocket; EPI also checks `https://sapph.xyz/status`. These integrations require network access.

## Storage

For local execution, create `SH/database`. The database path is resolved relative to `SH/utils.py`, not the shell's current directory. In the documented Docker layout, it becomes `/app/database/data.db`.

Startup creates missing tables. It does not provide a general migration system. See [internal documentation](../Internal%20Docs/README.md) for the distinction between persisted data, caches and reminder recovery.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Startup fails while converting an environment value | Ensure every required numeric variable is populated with an integer ID. |
| SQLite cannot open the database | Ensure the parent directory exists and the process can write to it. |
| Slash commands are missing or outdated | Use the bot mention followed by `sync` with a configured staff account, then refresh the client. |
| A command reports missing permissions | Check both the bot's role permissions and the channel overwrites. |
| Automated message handling does not work | Check Message Content in the portal and the configured forum/channel IDs. |
| Paging or cluster tracking fails | Check external-service access and the integration configuration; inspect alerts and process logs. |
