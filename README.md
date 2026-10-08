# Sapphire Helper

Sapphire Helper is a Discord bot built for the Sapphire Support server. It manages support posts, automates follow-ups, provides reusable answers, and helps staff respond to service incidents.

The source was made public on 9 September 2025 so people can learn from it and contribute improvements. The current development version is **6.3 (unreleased)**.

> **Need support for Sapphire or appeal.gg?** Visit the [support server](https://discord.gg/RrHJYrh4Mm). Use this repository for Sapphire Helper bugs, feature requests and contributions.

## Features

- Support-post management: solved and unsolved states, developer-review requests, automatic tags, and delayed closure.
- Follow-ups: inactivity reminders, closure of abandoned posts, and requests for missing information.
- Reusable answer tags with autocomplete, previews and usage tracking.
- Staff-triggered redirection of support questions into their own forum posts.
- Emergency Post Information (EPI): incident messages, optional sticky updates, and resolution notifications.
- Developer paging through ntfy, including automated pages for recognised rate-limit messages.
- Live Sapphire cluster monitoring with outage notifications and staff subscriptions.
- Runtime diagnostics, error handling and action logs.

## Requirements

- Python 3.11 or later; the Dockerfile uses Python 3.11.
- The pinned dependencies in [SH/requirements.txt](SH/requirements.txt).
- A Discord bot token and the roles, channels and forum tags referenced by the environment configuration.
- The **Message Content** privileged intent enabled in the Discord developer portal. Members and Presence intents are deliberately disabled.
- Discord permissions for the enabled features, including sending messages, reading history, managing messages and threads, managing webhooks, and managing channels where required.
- Writable SQLite storage and network access to Discord, Sapphire's status services and ntfy.

This bot is tailored to one support server. Some integrations use hard-coded IDs and channel names; review [configuration](Documentation/configuration.md) before adapting it to another server.

## Local setup

Run these commands yourself from the repository root.

1. Copy `_.env` to `.env` and replace its placeholder values. See [the configuration reference](Documentation/configuration.md).
2. Create a virtual environment:

   ```sh
   python -m venv .venv
   ```

3. Activate it using the command for your shell:

   | Shell | Command |
   | --- | --- |
   | PowerShell | `.\.venv\Scripts\Activate.ps1` |
   | Windows Command Prompt | `.venv\Scripts\activate.bat` |
   | bash/zsh | `source .venv/bin/activate` |

4. Install dependencies:

   ```sh
   python -m pip install -r SH/requirements.txt
   ```

5. Create an empty `SH/database` directory. Startup creates the database tables, but does not create the directory.
6. Start the bot:

   ```sh
   cd SH
   python main.py
   ```

7. In the server, use `@Sapphire Helper sync` from an account with a configured expert, moderator or developer role. Use your instance's actual bot mention. Refresh the Discord client if slash commands do not appear immediately.

Missing or malformed numeric environment values can prevent startup. Keep the completed `.env` out of version control.

For container deployment, see [the Docker guide](docker-readme.md).

## Documentation

- [Configuration](Documentation/configuration.md): environment variables, permissions and server assumptions.
- [Commands and staff workflows](Documentation/commands.md): command names, access rules and automatic behaviour.
- [Internal documentation](Internal%20Docs/README.md): architecture, state and extension lifecycle.
- [Discord intents](Internal%20Docs/Main/intents.md): gateway configuration and member lookup.
- [Contributing](.github/CONTRIBUTING.md): issues, style, validation and pull requests.
- [Changelog](CHANGELOG.md): recorded release and development changes.

## Contributing

Create an issue before opening a pull request, check whether it is already assigned, and link the pull request to that issue. Include reproduction steps for bugs and test code changes before submitting them. Read [the contribution guide](.github/CONTRIBUTING.md) for details.

## Licence

Sapphire Helper is licensed under [Apache License 2.0](LICENSE), with the copyright notice for kiki0124 retained in the licence file.
