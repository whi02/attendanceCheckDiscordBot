"""Entry point: python -m bot"""

from __future__ import annotations

import discord
from discord.ext import commands

from bot.cogs.attendance import Attendance
from bot.config import Config, load_config
from bot.db import AttendanceDB


class AttendanceBot(commands.Bot):
    def __init__(self, config: Config, db: AttendanceDB) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.config = config
        self.db = db

    async def setup_hook(self) -> None:
        await self.add_cog(Attendance(self, self.config, self.db))


def main() -> None:
    config = load_config()
    db = AttendanceDB(config.db_path)
    try:
        AttendanceBot(config, db).run(config.token)
    finally:
        db.close()


if __name__ == "__main__":
    main()
