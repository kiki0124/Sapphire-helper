# Docker deployment

Docker provides the bot's Python runtime. You still need a configured Discord application, environment values and persistent database storage. Install Docker and start its engine before following this guide.

## Build the image

Run the commands in this guide yourself from the repository root:

```sh
docker build -f Dockerfile -t sapphire-helper SH
```

The root Dockerfile expects `requirements.txt` and `main.py` at the root of its build context. Using `SH` as the context places the application at `/app`, matching its startup command. Building with `docker build .` does not match the current repository layout.

The Dockerfile uses Python 3.11 and installs the pinned requirements. It also explicitly installs `aiocache`, which is already in the requirements file.

## Configuration and database

Copy `_.env` to `.env` at the repository root and configure it using [the configuration reference](Documentation/configuration.md). The run command passes those values into the container; the environment file does not need to be copied into the image.

The application stores SQLite at `/app/database/data.db` in this layout. The separate `/database` directory created by the Dockerfile is unused by the application.

Use a named volume mounted at `/app/database`. Docker creates it on first use, and it survives container replacement. There is no need to create a host database directory when using the named-volume commands below.

The repository's root `.dockerignore` is outside the `SH` build context. Keep that context free of secrets and local database files when building an image; the Dockerfile copies the entire context.

## Start the bot

For foreground logs:

```sh
docker run --name sapphire-helper --env-file .env -v sapphire-helper-data:/app/database sapphire-helper
```

For background operation, use this command instead:

```sh
docker run -d --name sapphire-helper --env-file .env -v sapphire-helper-data:/app/database sapphire-helper
```

These are alternatives. A container named `sapphire-helper` must not already exist when you run either command.

Register slash commands with `@Sapphire Helper sync` after the bot connects. The invoking account needs a configured staff role.

## Logs and lifecycle

```sh
docker logs -f sapphire-helper
docker stop sapphire-helper
docker start sapphire-helper
```

Stopping a container retains its files and volume. Starting an existing container reuses its original image and environment configuration.

After changing the application, rebuild the image and recreate the container. Stop and remove the old container first, then use the appropriate run command above with the same volume:

```sh
docker stop sapphire-helper
docker rm sapphire-helper
docker build -f Dockerfile -t sapphire-helper SH
```

The named volume remains available after these commands. Do not remove it unless you intend to discard the stored database.

The bot's mention-based `restart` command reloads cogs in the running process. It does not restart the container or use a newly built image.

## Persistence and validation

The volume retains reusable tags, saved channel permissions and cluster-notification subscriptions. Incident state and several caches live in memory. Pending reminder recovery inspects Discord messages rather than restoring a complete process snapshot.

Stop the bot before taking a simple file-copy backup of SQLite. Back up storage before changing its schema or replacing a production instance.

Before deployment, verify that the image builds, the bot connects, storage is writable, and the affected Discord workflows work in a test server. Startup utility tests do not validate permissions or external integrations. These instructions describe the source layout; they are not a report of a verified container build.
