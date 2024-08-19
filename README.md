## Setup

### 1. Replace all of the variables in variables.py to their actual value.

### 2. In cogs/autoadd.py -> line 37, replace 123 with the command ID.

### 3. Install the libraries listed in requirements.txt
```
pip install -r requirements.txt
```
### 4. Run the main file- python main.py

### 5. Use the sync command to sync all slash commands, and restart your discord client.

## Files' explanations:

  ## main.py- run the bot (create the session with discord), load cogs (aka extensions- commands and event listeners from other files)
  ## /cogs/utility.py- utility related commands, includes:
  - /list-unsolved - lists all posts that meet the following requirements:
    - Not locked and not archived,
    - Without need-dev-review tag,
    - has not solved/unanswered or doesn't have solved,
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
  ## autoadd.py- Ask user to more information if their post's starter message length < 15, suggest to use /solved based on a specific regex and more.
  - On thread create:
    - Auto-add unanswered tag,
    - Auto-remove solved tag (if applied),
       Send a message asking the user to provide more information if starter message length < 15
  - On message:
    - If message matches the regex `(solved|^ty|\sty|thanks|work|fixed)` suggest to use /solved, and add the post to a list of ignored posts for this regex (list cleared on bot restart)
    - If the post has unanswered tag, and the message of the author isn't the creator of the post- replace it with not solved.
  ## functions.py- Functions to add/remove/view data from/to the database- Doesn't directly communicate with discord, these functions are used in the files that do communicate with discord though.
