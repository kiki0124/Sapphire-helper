# Discord gateway intents

Gateway intents select the event categories delivered to the bot. Message Content is a privileged intent controlling access to message-content fields. Sapphire Helper constructs its intents explicitly in `SH/main.py`, starting with `discord.Intents.none()`.

## Enabled intents

| Intent | Use |
| --- | --- |
| `guilds` | Guild, channel and thread state needed by support workflows. |
| `guild_messages` | Message events for automatic tags, reminders, redirection and incident handling. |
| `guild_reactions` | Staff redirection reactions and eligible quick-reply deletion. |
| `message_content` | Message text used by content heuristics, redirection and recognised integration messages. |

Enable **Message Content** in the application's Discord developer-portal settings as well as in code. Any approval requirements imposed by Discord also apply to the deployed application.

Mention-based commands remain implemented, but removing them alone would not remove the content requirement: automated workflows also inspect message text.

## Members: deliberately disabled

The privileged Members intent is not enabled. Do not treat `Guild.members` or `Guild.get_member` as a complete or authoritative guild-member cache.

Interactions and guild messages can supply member objects for the users involved. Use those objects where sufficient. For additional lookup, the code uses methods such as `Guild.fetch_member` and targeted `Guild.query_members(user_ids=...)` rather than assuming all members are cached.

When changing a membership-dependent feature, consider incomplete results, users who have left, Discord failures and request limits. Preserve the deliberate intent choice unless the feature change explicitly requires revisiting it.

## Presence: deliberately disabled

The bot does not use member presence data. The privileged Presence intent remains disabled.

## Permissions are separate

An enabled intent allows relevant events or fields to be received. It does not grant permission to send messages, edit threads, delete messages or manage webhooks. Check role permissions and channel overwrites separately; see [configuration](../../Documentation/configuration.md).
