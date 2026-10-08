# Contributing to Sapphire Helper

Contributions should improve the support server's workflows or make the bot easier to maintain. Keep changes focused, explain the resulting behaviour, and provide enough evidence for someone else to review them.

For Sapphire or appeal.gg support, use [the support server](https://discord.gg/RrHJYrh4Mm). Repository issues are for Sapphire Helper itself.

## Reporting bugs

Search existing issues before opening a report. Use the bug-report form and include:

- The command or automatic workflow affected.
- Reproduction steps, including relevant post state, tags and user role.
- Expected behaviour and what actually happened.
- The full relevant traceback when available, or screenshots/video when you cannot inspect the running instance.
- For your own instance, the commit or version, Python and discord.py versions, operating system, and whether you use Docker.

Remove tokens, webhook credentials and other private configuration from logs and examples. A minimal reproducible example is useful when the problem can be isolated.

## Proposing features

Use the feature-request form to explain the problem, the proposed behaviour and any existing workaround. Include the effect on support users and staff, especially permissions, notifications and automated changes to posts.

## Before a pull request

**Create an issue before opening a pull request.** Link an existing issue if it already covers the work. Check whether someone is assigned; coordinate with the assignee before submitting overlapping work.

Use [the setup guide](../README.md) and [configuration reference](../Documentation/configuration.md) for a development instance. Use a test server for workflows that send messages, change permissions, delete content or notify people.

Read the relevant cog and its shared helpers before changing a feature. The [internal guide](../Internal%20Docs/README.md) explains ownership, persistence and known limitations.

## Code conventions

The repository does not configure a formatter, linter or formal style checker. Match the surrounding code without reformatting unrelated files.

- Use descriptive `snake_case` functions and variables, uppercase constants, and conventional class names for new code.
- Keep feature logic in the appropriate cog and shared helpers in `SH/utils.py` or a suitably scoped module.
- Use asynchronous APIs for Discord and database operations. Avoid blocking work on the event loop.
- Add useful type annotations and use `TYPE_CHECKING` imports where they avoid runtime import cycles.
- Prefer direct control flow and early returns. Introduce abstractions when they clarify a real shared responsibility.
- Preserve role/owner checks, channel restrictions, allowed mentions and interaction response behaviour.
- Track and clean up tasks where the workflow requires cancellation or extension unloading.
- Use UTC for ordinary time comparisons. Paging currently has a host-local-time exception; do not broaden it unintentionally.
- Keep stable custom IDs and view registration in mind when editing persistent buttons.

Existing formatting varies. A targeted change should not become a repository-wide style rewrite.

## Validation

For shared utility changes, run the existing tests from the repository root:

```sh
python -m unittest discover -s SH -p "test_*.py" -v
```

The suite currently covers time comparisons and the bounded cache. It does not cover Discord interactions, the database schema, background workflows or external services. The bot also runs this utility module during startup, but that is not a substitute for checking the test result separately.

For feature changes, verify the affected workflow in a test server. Check authorised and unauthorised users, relevant tag states, interaction responses, and task/restart behaviour where applicable. Add focused tests when they provide meaningful regression coverage.

For Docker changes, build and run the image using [the deployment guide](../docker-readme.md). For documentation changes, check local links, command names, source paths and whether the instructions describe implemented behaviour.

Report what you tested and any unverified behaviour. Do not describe a unit-test pass as live integration verification.

## Pull requests and commits

Keep each commit focused and reviewable. For a larger change, stack commits in dependency order so the setup, implementation and documentation changes can be reviewed coherently. Avoid mixing unrelated refactors with a bug fix.

The pull-request description should explain the problem and final behaviour, link the issue, and record validation. Update affected documentation when command names, requirements, configuration or user workflows change.

Use the supplied pull-request template. Keep review discussions respectful, and leave a comment once requested changes are ready for another review.

## Licence

The repository uses [Apache License 2.0](../LICENSE). Keep the licence text and existing attribution intact. Contributions intentionally submitted for inclusion are covered by the contribution terms in that licence unless explicitly stated otherwise.
