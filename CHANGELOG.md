# Changelog

All notable changes to this project will be documented in this file.

## [6.2] - 10/7/26

### Added
- Cv2 for majority of messages ([#49](https://github.com/kiki0124/Sapphire-helper/issues/49))
- `hasn't` to negative regex when auto suggesting `/solved` command
- Allow usage of `ping` command for non experts/dev/mod but with cooldown ([#48](https://github.com/kiki0124/Sapphire-helper/pull/48))
- Better debugging UX ([#63](https://github.com/kiki0124/Sapphire-helper/pull/63))
- Error logging for `task.loop` errors ([#64](https://github.com/kiki0124/Sapphire-helper/pull/64))
- `uptime` and `last_restarted` stats in `sh!stats`
- Reminders are now sent if the last message is more than 3 days ago, regardless if the last message was sent by the post owner or not.


### Fixed
- Bunch of bug fixes ([57](https://github.com/kiki0124/Sapphire-helper/pull/57))
- Fix `discord.Thread` not being able to resolve if a post is archived
- Fix `need-dev-review` button being able to be spammed multiple times. (Found by Calypso)
- Fix status-ping loop

### Notable Internal Changes
- Optimize `pending_post` loop ([51](https://github.com/kiki0124/Sapphire-helper/pull/51))
- Factor out log functions ([60](https://github.com/kiki0124/Sapphire-helper/pull/60))
- Simplify and reduce nesting in code ([61](https://github.com/kiki0124/Sapphire-helper/pull/61))
- Refactor and Improve tags ([65](https://github.com/kiki0124/Sapphire-helper/pull/65))
- Use UTC for all datetimes (except paging) ([69](https://github.com/kiki0124/Sapphire-helper/pull/69))
- Refactor reminders + close_abandoned_posts ([74](https://github.com/kiki0124/Sapphire-helper/pull/74))
- Change Backend in Paging ([78](https://github.com/kiki0124/Sapphire-helper/pull/78))

See [commits](https://github.com/kiki0124/Sapphire-helper/commits/main/) for all changes!
