> [!IMPORTANT]
> **This is not Sapphire support.** If you require support for Sapphire or appeal.gg, go to: https://discord.gg/RrHJYrh4Mm 

From Kiki
>  Hi there, I've made this repository public on 9.9.25 (9.9.25 for the Americans between us) for the purpose of continuosly improving Sapphire Helper in both features & performance, and also allowing people to learn from it.


## About
This is a (private) helper bot made for the Sapphire Support server. Among the many things it does, here are the major features:
- Managing supports posts (solve/unsolve cmds, auto-cleanup, auto-reminders and more!)
- Paging the lead developer
- Overall, improving QOL of users

## Setup

### 1. Rename `_.env` to `.env` and replace each variable with its respective value.

### 2. Install the libraries needed.
```
pip install -r requirements.txt
```

### 3. Setting up the database
- Create an empty folder named `database` in the `SH` folder.
  - This will automatically be used to store the database files.

### 4. Running the bot 
- Using docker: [docker-readme](/docker-readme.md)

- If you are not using docker, run these commands in the root folder:
  ```sh
  cd SH
  python main.py
  ```

### 4. Use the sync command - `sh!sync` - to sync all slash commands. Then, restart your discord client.


## Contributing
- If you've found an issue/bug - please create an issue on this github repository with all info requested on the Bug Report template.
- If you'd like to suggest a new feature or an improvement to an existing feature - create an issue with all info requested on the Feature Request template and optionally a PR with relevant code.

See more at the `Contributing` page.


