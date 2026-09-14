## Support-Related Commands

- `/atbl` - Mark a post as added to bug list.
- `/incomplete-post` - Send a message asking the OP to provide more info.
- `/needs-dev-review` - Mark a post as *needs dev review*
- `/remove` - Remove a user from the post.
- `/solved` - Solve and eventually close the post.
- `unsolve` - Unsolve a post and reopen it if previously closed.
- `/unrelated` - Sends a message telling OP that the post is unrelated to Sapphire or appeal.gg. Post is eventually locked if run by CE/Mod/Dev.

## EPI-Related Commands
- `/epi enable` - Enable EPI mode.
- `/epi disable` - Disable EPI mode.
- `/epi edit` - Update EPI mode.
- `/epi debug_info` - Get information about the current EPI.
- `/page` - Pages and notifies Xge.

## Cluster-Tracker-Related Commands
- `/cluster_tracker_status` - Get the live status of Sapphire clusters and optionally set the threshold.
- `/cluster_tracker_search` - Get information about specific cluster(s).
- `/cluster_tracker_notify_me` - Add/Remove yourself from being pinged when threshold is hit.
- `/cluster_tracker_websocket` - Configure the websocket (connected to sapph.xyz) or get debug information about it.

## Tag-Related Commands
- `/tag create` - Create a new tag.
- `/tag delete` - Delete a tag.
- `tag edit` - Edit the tag's name or content.
- `/tag use` - Use the tag.
- `/tag info` - Get information about the tag.
- `/tag debug` - Get debug information about the cached tags.

## Utility-Related Commands
- `/lock` - Lock up to 5 channels at a time.
- `/unlock` - Unlock up to 5 channels at a time.
- `/slowmode` - Set a slowmode for 5 channels at a time.
Prefix commands:
- `ping` - Get the bot's latency.
- `restart` - Reload all extensions.
- `stats` - Get stats about the cpu/memory usage and more.

## Reminder-Related Commands
- `/reminders simulate` - Simulate running an internal function on a post that may or may not trigger a reminder.
- `/reminders get_active_threads` - Get all active threads in the support channel.
- `/reminders debug` - Get debug information about the last reminder check and more.
- `/reminders restore_pending_post` - Manually call an internal function to restore pending post. Though this should have already been done upon startup.
