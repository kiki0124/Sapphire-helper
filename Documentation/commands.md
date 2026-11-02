# Commands and staff workflows

Commands below use their registered names in the current source. Slash commands are available in guild contexts. **Staff** means a member with at least one configured Community Expert, Moderator or Developer role; it does not mean every account with Discord administrator permissions.

Mention commands use the bot's actual mention as a prefix, for example `@Sapphire Helper ping`. Run `@Sapphire Helper sync` after command changes to update Discord's registrations.

## Support posts

These commands operate in the configured support forum's threads.

| Command | Access | Behaviour |
| --- | --- | --- |
| `/solved` | Staff or post owner | Marks the post solved and schedules archiving after one hour. Posts needing developer review or with “forwarded” in their title require confirmation. |
| `/unsolve` | Staff or post owner | Cancels a tracked closure task and changes the post back to not solved. The handler does not explicitly clear the archived flag. |
| `/needs-dev-review` | Staff | Offers a choice between adding the developer-review tag and sending the associated questions. |
| `/atbl` | Staff | Adds an `[ATBL]` title prefix, developer-review tag and priority guidance. It does not create an issue in an external tracker. |
| `/remove` | Staff | Removes a selected member from the thread, with an optional reason. The post owner cannot be removed. |
| `/incomplete-post` | Members | Requests more information. Rejects solved/developer-review posts and posts already recorded as receiving automatic incomplete-post guidance. Also available as a mention command. |
| `/unrelated` | Members; non-staff cooldown | Sends guidance for questions outside Sapphire or appeal.gg. Staff use also locks the post and marks it solved; the code attempts delayed archiving after ten minutes. |

Staff checks and owner checks are enforced separately from Discord's permissions. The bot must also have permission to perform the requested action.

## Reusable answer tags

Reusable answer tags are stored responses. They are separate from the forum tags used to track post state.

| Command | Access | Behaviour |
| --- | --- | --- |
| `/tag create` | Staff | Opens a modal to create a named response. |
| `/tag edit` | Staff | Opens a modal to change its name, content or both. |
| `/tag delete` | Staff | Shows a confirmation before deletion. |
| `/tag use` | Members | Shows an ephemeral preview; Confirm sends the answer to the channel and increments its usage count. Non-staff have a cooldown of one use per minute per channel and user. |
| `/tag info` | Members | Shows the response, creator, creation time and usage count. |
| `/tag debug` | Staff | Shows the cached tag names. |

Autocomplete uses up to 100 cached tag names, returning at most 25 choices for a query. A confirmed answer in an unanswered forum post replaces its unanswered tag with not solved.

## Emergency Post Information

EPI means **Emergency Post Information**. All commands in this section require staff access.

| Command | Behaviour |
| --- | --- |
| `/epi enable` | Enables incident messages in newly created support posts. Accepts an optional custom message and status-message ID, plus a sticky-message choice. |
| `/epi edit` | Updates incident text, status-message reference or sticky behaviour. Omitted values retain their existing settings; use `-` to remove the text or status reference. |
| `/epi disable` | Requires confirmation, sends resolution updates, notifies subscribed users, removes the sticky message and clears incident state. |
| `/epi view` | Shows incident state and the most recent page. |
| `/page` | Sends an ntfy notification to the lead developer for a selected service, message, priority and Custom Branding impact. |

Users can toggle resolution notifications through the button on an EPI message. Subscriptions belong to the current in-memory incident.

Paging priorities range from information to a critical night-time page. If a page was sent within the last 15 minutes, another manual page requires confirmation. Paging can also occur automatically for recognised bot messages mentioning the lead developer in the configured hard-coded rate-limit channels.

## Emergency channel controls

These commands require staff access and are intended for emergencies. Each opens a menu selecting one to five text or forum channels. The selection handler checks that the invoking user can send messages there and that everyone can view the channel.

| Command | Behaviour |
| --- | --- |
| `/lock` | Saves everyone's permission overwrite, then replaces channel overwrites to restrict ordinary members while allowing configured staff roles to send messages. |
| `/unlock` | Restores the saved everyone overwrite for a channel recorded as locked. It does not restore a complete snapshot of all previous overwrites. |
| `/slowmode` | Sets the selected channels' slowmode using a duration such as `30s` or `1m, 30s`; `0s` disables it. |

## Cluster monitoring

All cluster commands require staff access. They are subcommands of `/cluster_tracker`, not separate commands with underscore-separated suffixes.

| Command | Behaviour |
| --- | --- |
| `/cluster_tracker status` | Shows cluster availability, the five slowest clusters, dashboard/Custom Branding status and receipt time. Can change the outage threshold or clear tracked state. |
| `/cluster_tracker search` | Looks up comma-separated cluster numbers or sorts by ping. |
| `/cluster_tracker notify_me` | Adds or removes the invoking user's outage subscription, or lists subscribers. |
| `/cluster_tracker websocket` | Views connection state or requests connect, disconnect or force-disconnect. |

The default outage threshold is eight minutes. Monitoring begins when the cog loads. It sends a notification after the threshold is reached and a recovery update when all clusters return online. Subscriber IDs persist in SQLite; cluster state and threshold edits do not.

## Reminder diagnostics

All reminder commands require staff access.

| Command | Behaviour |
| --- | --- |
| `/reminders debug` | Shows loop state, timing and information about previously fetched posts. |
| `/reminders get_active_threads` | Fetches active support threads; optionally checks whether a selected post is included. |
| `/reminders restore_pending_posts` | Attempts to reconstruct pending reminders from qualifying Discord messages. |
| `/reminders simulate` | Runs the real reminder eligibility function for one post after a short delay. It can send a reminder and change pending state. |

Despite its name, `simulate` is not a dry run.

## General diagnostics

| Command | Access | Behaviour |
| --- | --- | --- |
| `@Sapphire Helper ping` | Members | Reports gateway and message-request latency. Non-staff have a 15-second cooldown. |
| `@Sapphire Helper stats` | Staff | Shows version, host CPU/memory figures, uptime and extension-reload time. |
| `@Sapphire Helper restart` | Staff | Reloads all cogs. Refuses while EPI is enabled. It does not restart the process. |
| `@Sapphire Helper sync` | Staff | Registers the current application commands with Discord. |
| `/debug post` | Staff | Shows owner, tags, archive/lock state and pending-reminder state for a post. |
| `/debug global_cache` | Staff | Opens a modal to inspect or change RTDR or pending-post caches. |
| `/debug create_db_table` | Staff | Runs the same table-creation helper used at startup. |
| `/debug eval_sql` | Staff | Executes submitted SQL against the real database. It can change or delete data; results are sent as a normal channel response. |

## Automatic workflows

### Post tags and guidance

New support posts receive the unanswered tag. A response from someone other than the owner replaces it with not solved. Short or repeated starter content can trigger a request for more information.

Messages from the owner that resemble a resolution can trigger a suggestion to use `/solved`. This is a text heuristic, not an automatic resolution decision. Deleting an eligible starter message triggers buttons asking whether to close the post or keep it open.

An owner message in an eligible answered post schedules the waiting-for-reply tag after ten minutes. Another user's reply cancels the pending task or removes the tag.

### Inactivity reminders

The hourly reminder loop excludes locked, archived, solved, unanswered and developer-review posts from ordinary inactivity reminders. It sends a reminder after more than 24 hours without a message when the last sender was not the owner, or after more than three days regardless of the last sender.

A pending reminder can lead to closure after more than another day. An eligible owner reply or Still need help button clears pending state. Exact execution depends on the hourly loop, Discord access and current post state.

The loop also handles eligible posts whose owners have left the server. That path has separate filters; unanswered posts are not excluded in the same way as ordinary reminders.

### Redirecting questions to support

Staff can reply to another user's message with the bot mention, optionally followed by a post title, or react with ❓ or ❔. The RTDR workflow creates a support post from the source message and qualifying subsequent messages from the same author, includes supported attachments, and deletes the moved source messages.

The created thread belongs to the bot in Discord. The original user's ID is recorded in a cache and appended to the thread title so owner checks can recover it after a restart.

### Removing quick replies

In support posts, 🗑️ or ❌ reactions can remove eligible messages from Sapphire or Sapphire Helper. Staff can remove them; non-staff must match the recognised interaction, recommendation or reply attribution. Deletions are logged.

For implementation details and known limitations, see [internal documentation](../Internal%20Docs/README.md).
