# START HERE IF THIS IS YOUR FIRST TIME VISITING THIS REPOSITORY:
  ## THIS IS NOT SAPPHIRE SUPPORT. If you require support for Sapphire or appeal.gg **always** use https://discord.gg/RrHJYrh4Mm 
  * Hi there, I've made this repository public on 9.9.25 (9.9.25 for the Americans between us) for the purpose of continuosly improving Sapphire Helper with both better features & performance, and for allowing people to learn from it.
  * If you've found an issue/bug - please create an issue on this github repository with all info requested on the Bug Report template.
  * If you'd like to suggest a new feature or an improvement to an existing feature - create an issue with all info requested on the Feature Request template and optionally a PR with relevant code.

### NOTICE:
  As mentioned in [License](/LICENSE), this software is provided "as is" without warranties or conditions for use.

## Setup

### 1. Rename `_.env` to `.env` and replace each variable with its respective value.

### 2. Install the libraries listed in requirements.txt -
```
pip install -r requirements.txt
```
### 3. Running the bot 
- Using docker: [docker-readme](/docker-readme.md)

- If you are not using docker, run these commands in the root folder:
  ```
  cd SH
  python main.py
  ```

### 4. Use the sync command - sh!sync - to sync all slash commands. Then, restart your discord client.