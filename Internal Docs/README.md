# Internal documentation

Sapphire Helper is a single asynchronous Python process built on discord.py. Features are organised into cogs, with shared database and formatting helpers in `SH/utils.py`. Read [the command reference](../Documentation/commands.md) for user-visible behaviour and [configuration](../Documentation/configuration.md) for deployment requirements.

## Source layout

| Path | Responsibility |
| --- | --- |
| `SH/main.py` | Bot construction, startup, shared caches, owner resolution, webhook logging and unhandled-error reporting. |
| `SH/utils.py` | SQLite helpers, time and text formatting, random action IDs and the bounded cache. |
| `SH/cogs/utility.py` | Support commands, delayed closure, developer-review guidance and quick-reply cleanup. |
| `SH/cogs/autoadd.py` | New-post tags, incomplete-post guidance, solved-command suggestions and starter-deletion buttons. |
| `SH/cogs/waiting_for_reply.py` | Delayed waiting-for-reply tagging and cancellation on responses. |
| `SH/cogs/remind.py` | Hourly reminder processing, abandoned-post closure and pending-state recovery. |
| `SH/cogs/readthedamnrules.py` | Staff-triggered question redirection into support posts (RTDR). |
| `SH/cogs/tags.py` | Reusable-answer CRUD, previews, autocomplete and usage tracking. |
| `SH/cogs/epi.py` | Emergency Post Information, sticky messages, paging and emergency channel controls. |
| `SH/cogs/cluster_tracker.py` | Status websocket connection, cluster state and outage notifications. |
| `SH/cogs/bot.py` | Mention-based latency, statistics, extension reload and command sync. |
| `SH/cogs/debug.py` | Runtime post/cache inspection and database commands. |
| `SH/cogs/error_handler.py` | Prefix and application-command error handling. |
| `SH/test_functions.py` | Unit tests for time comparisons and the bounded cache. |
| `depracated or not ready/` | Older or unfinished code; excluded from automatic cog loading. |

## Startup and extension lifecycle

1. `main.py` loads environment variables and constructs `SHBot` with the configured gateway intents.
2. `setup_hook` runs the utility unittest module, then creates missing database tables.
3. Every `.py` file under `SH/cogs` is loaded as an extension through its module-level `setup` function.
4. Cog load hooks initialise feature state, start tasks or connect integrations. Tasks that need a populated Discord cache wait for readiness where implemented.
5. The bot connects to Discord; ready listeners register persistent views used by existing messages.

Command registration is a separate staff-triggered `sync` action. Startup does not automatically synchronise the command tree.

The mention-based `restart` command reloads extensions within the current process. Bot-owned caches and process uptime remain; cog-owned objects are reconstructed. Reloading is blocked while EPI is enabled because its incident state lives in the cog.

A new Python file placed in `SH/cogs` must be a loadable extension. Put standalone helpers elsewhere unless their loading is intentional.

## State and persistence

SQLite lives at `SH/database/data.db` locally. Its path is resolved relative to `utils.py`. The caller must create the parent directory and provide write access.

| Table created at startup | Purpose |
| --- | --- |
| `tags` | Reusable response name, content, creator, creation timestamp and usage count. |
| `locked_channels_permissions` | Saved everyone-role allow/deny bits for emergency channel controls. |
| `cluster_tracker_notify` | Outage notification subscriber IDs. |
| `reminder_waiting` | Retained reminder-related table; ordinary pending reminders use bot-owned memory in the current implementation. |

Database helpers open asynchronous SQLite connections and commit mutations. Startup uses `CREATE TABLE IF NOT EXISTS`; there is no versioned migration framework. Some older helpers still refer to tables that startup no longer creates. Do not assume every utility function describes an active feature.

Important in-memory state includes:

- `SHBot.rtdr_posts`: created post IDs mapped to their original owners.
- `SHBot.pending_posts`: post IDs mapped to reminder timestamps.
- `SHBot.incomplete_msg_posts`: bounded records used to avoid duplicate guidance.
- Cog-owned closure tasks, waiting-for-reply tasks, tag-name caches, incident state, recent-page data and cluster status.

`MaxCache` stores entries with a fixed maximum size and evicts the oldest entry when adding a new one would exceed that size. It is used for bounded duplicate-suppression records.

A process restart loses in-memory state. Pending reminder recovery inspects qualifying active threads and their last bot messages for the reminder's Components V2 text. It is a reconstruction heuristic, not a complete persisted queue.

## Post ownership and transitions

For ordinary threads, owner resolution uses Discord's `owner_id`. For bot-created RTDR threads, it first checks the owner cache, then parses the user ID appended in parentheses to the thread title. Failure returns `0`. Retain this suffix when changing RTDR titles.

Support state is primarily encoded in forum tags. Typical transitions replace unanswered with not solved, then replace the working state with solved or developer review. Several transitions preserve Custom Branding and appeal.gg tags; check the specific handler before changing that behaviour.

Closure, reminder and waiting-for-reply handling span multiple event listeners and tasks. A change to one transition can affect another feature's eligibility checks or outstanding timers.

## Discord UI and errors

Most feature messages use Components V2 through `LayoutView`, containers, text displays, action rows and modals. Some older flows still use embeds or ordinary views.

Persistent views use fixed custom IDs and are registered on readiness. Their callbacks still need valid post ownership and staff checks; a button remaining visible is not sufficient authorisation.

Shared logging sends webhook messages into configured threads. The bot caches the alerts webhook URL and can fall back to finding or creating a webhook. Action IDs correlate log entries with thread audit reasons.

The error cog handles expected command-check failures and cooldowns. Other command errors are reported through `SHBot.send_unhandled_error`, which includes available interaction/task context and prints a traceback. Background-task error reporting is implemented by individual features rather than a universal supervisor.

## Integrations and time

Cluster tracking implements the relevant Engine.IO/Socket.IO text exchange over an aiohttp websocket. It handles heartbeat frames, receives status payloads, and reconnects with exponential backoff capped at 45 seconds. Its default outage threshold is eight minutes.

EPI periodically checks the status page while enabled. Paging publishes ntfy notifications with Discord webhook acknowledgement actions. Automatic rate-limit paging uses local host time for its night-time priority decision; most other time comparisons use UTC.

Changing these integrations requires checking their payload assumptions and response handling. Local utility tests do not validate their live behaviour.

## Current limitations

These describe the inspected source, not fixes delivered by the documentation revision:

- Local execution requires the database directory to exist. The Dockerfile expects a build context rooted at `SH`; see [the deployment guide](../docker-readme.md).
- Environment configuration does not cover all server IDs, channel names and UI links.
- `/unsolve` changes tags and cancels a tracked task but does not explicitly unarchive the thread.
- The unrelated-post closure path creates a task without inserting it into `close_tasks`, while the shared closure helper pops that mapping before archiving. Its intended ten-minute archive should not be treated as guaranteed.
- Emergency lock/unlock saves only the everyone-role overwrite and replaces channel overwrite mappings. It does not restore the full original permission configuration.
- Tag autocomplete is bounded to 100 cached names. The helper labelled “most used” currently queries `ORDER BY uses` in ascending order.
- Reminder recovery depends on accessible Discord messages and their current structure. The startup recovery gate mixes `perf_counter()` with an uptime value created using `time.time()`, so its recent-start comparison is not a reliable elapsed-time check.
- Runtime SQL and cache commands can mutate production state; `/reminders simulate` calls the real reminder function.
- Utility test results are printed at startup through `unittest.main(..., exit=False)`; a failing test does not explicitly abort startup through that call.

## Working on the code

Match the surrounding feature's naming and structure. Prefer direct helpers and early returns, retain UTC comparisons where used, and avoid changing permissions or state transitions incidentally. Read [the contribution guide](../.github/CONTRIBUTING.md) for validation and review expectations.
