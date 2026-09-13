# What are intents?
Intents are what allows bots to receive a certain event over the gateway (Except for `Message content`).

There are three **privileged** intents, only one is used by Sapphire-Helper:
- [x] Message Content
- [ ] Members
- [ ] Presence

## Message Content
This is the only **privileged** intent that Sapphire-Helper has **enabled** and it allows Sapphire-Helper to read the contents of a message.
Even though we have this enabled, prefix commands will soon be deprecated.

## Members
This intent is **not enabled** even though Sapphire-Helper’s features do require getting data on members. As a result, we cannot use
the cache (`Guild.ge_member`, `Guild.members` etc.) and must instead use the rest API/Gateway query.
For instance, `Guild.fetch_member` or `Guild.query_members`.

Fortunately, the API often populates the Member data for us through:
- Interactions
- Messages

### Presence
This intent is not enabled nor is it needed.
