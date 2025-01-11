## Setup

### 1. Rename `_.env` to `.env` and replace each variable with its actual value.

### 2. Install the libraries listed in requirements.txt
```
pip install -r requirements.txt
```
### 3. Run the main file- python main.py

### 4. Use the sync command to sync all slash commands, and restart your discord client.

## Files' explanations:

  ## main.py- run the bot (create the session with discord), load cogs (aka extensions- commands and event listeners from other files)
  ## /cogs/utility.py- utility related commands, includes:
  - /solved - only usable in #support by Moderators, Experts or the post's creator. Takes the following actions when used:
    - Reply with a message saying that the post was solved and will be closed in 1 hour.
    - Removes not solved and unanswered tags,
    - Adds solved tag.
    - After 1 hour, the post will also be archived.
  - /unsolved - only usable in #support by Moderators, Experts or the post's creator. Takes the following actions when used:
    - Reply with a message saying that the post was unsolved.
    - Removes solved tag,
    - Adds unsolved tag.
  - /need-dev-review - Only usable by Moderators and Experts. Responds with the normal need-dev-review template (including buttons), adds the need-dev-review tag, and sends a notification to 1145088659545141421
  ## /cogs/remind.py- Remind users of unsolved posts where they have been inactive, and close posts if their owners left.
  ## /cogs/bot.py- bot control related commands (only sync for now) and error handlers.
  ## /cogs/autoadd.py- Ask user to more information if their post's starter message length < 15, suggest to use /solved based on a specific regex and more.
  - On thread create:
    - Auto-add unanswered tag,
    - Auto-remove solved tag (if applied),
       Send a message asking the user to provide more information if starter message length < 15
  - On message:
    - If message matches the regex `(solved|^ty|\sty|thanks|work|fixed)` suggest to use /solved, and add the post to a list of ignored posts for this regex (list cleared on bot restart)
    - If the post has unanswered tag, and the message of the author isn't the creator of the post- replace it with not solved.
  ## /cogs/readthedamnrules.py- create a post for a user with the details they provided if they ask for help in #general
  ## cogs/waiting_for_reply.py- autoadd waiting for reply tag after 10 minutes from op if no message from a user that isn't op was sent, and remove that tag on any message from not op.
  ## functions.py- Functions to add/remove/view data from/to the database- Doesn't directly communicate with discord, these functions are used in the files that do communicate with discord though.

### Function tests:
  To run the tests (only tests functions.check_time_more_than_day) run test_functions.py