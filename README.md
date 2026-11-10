# Discord Bot

VoidSMP Control is a purple-themed Discord bot for community management, support tickets, welcoming new members, moderation, announcements, polls, and server information. It provides Discord bot commands for configuring server features and managing everyday community tasks.

## Install

1. Create a Discord application and bot in the Discord Developer Portal.
2. Enable the Server Members Intent and Message Content Intent for the bot.
3. Invite the bot to your server with the required permissions, including managing channels, messages, roles, and members as needed.
4. Install Python 3.10 or newer.
5. Install the dependencies with `pip install -r requirements.txt`.
6. Copy `.env.example` to `.env` and set `DISCORD_TOKEN` to your bot token. Optionally set `DATA_FILE` to choose where server configuration is stored.
7. Start the bot with `python main.py`.

## Use

1. Use `/help` in your Discord server to view available commands.
2. Configure welcomes with `/welcome_setup`, server logging with `/set_log_channel`, and ticket settings with `/set_ticket_category` and `/set_support_role`.
3. Post a ticket panel with `/ticket_panel`. Members can open one private ticket at a time and close it with the button or `/ticket_close`.
4. Use `/announce` to post a purple announcement, `/poll` to create a yes-or-no poll, and `/serverinfo` or `/userinfo` to view server and member details.
5. Use `/kick`, `/ban`, `/timeout`, `/untimeout`, `/purge`, and `/slowmode` for moderation. These commands require the corresponding Discord permissions.
6. Keep the bot running for commands, ticket interactions, welcome messages, and configured logs to work. Server configuration is stored in the file selected by `DATA_FILE`, defaulting to `data.json`.

---

More Discord bot projects by EnderDevelopment: https://github.com/EnderDevelopment

Project page: https://dash.enderdevelopment.com/community/577cdbbd-33f3-4970-96b9-1e66abf1e930?utm_source=github&utm_medium=readme&utm_campaign=auto_publish&utm_content=577cdbbd-33f3-4970-96b9-1e66abf1e930
