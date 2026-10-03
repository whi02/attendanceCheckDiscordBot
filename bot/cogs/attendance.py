"""Weekend attendance commands."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime

import discord
from discord.ext import commands

from bot.config import Config
from bot.db import AttendanceDB
from bot.streak import (
    FRIDAY,
    WEEKDAY_NAMES,
    best_streak,
    build_ranking,
    format_day,
    is_check_in_open,
    is_weekend,
    next_open_at,
    stats,
    to_kst,
    weekend_of,
)

log = logging.getLogger(__name__)

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
EMBED_COLOR = discord.Color.orange()
EMBED_DESCRIPTION_LIMIT = 4096


class NotInAttendanceChannel(commands.CheckFailure):
    """Raised after the user has already been pointed to the right channel."""


class DateFormatError(commands.BadArgument):
    pass


def parse_date(argument: str) -> date:
    try:
        return date.fromisoformat(argument)
    except ValueError:
        raise DateFormatError("날짜는 `YYYY-MM-DD` 형식으로 입력해 주세요. 예: `2026-10-03`")


def short_day(d: date) -> str:
    """'10/9(금)'"""
    return f"{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})"


def display_name(user: discord.abc.User) -> str:
    return discord.utils.escape_markdown(user.display_name)


class Attendance(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config, db: AttendanceDB) -> None:
        self.bot = bot
        self.config = config
        self.db = db

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if ctx.channel.id != self.config.attendance_channel_id:
            await ctx.reply(
                f"출석 명령어는 <#{self.config.attendance_channel_id}> 채널에서 사용해 주세요.",
                mention_author=False,
            )
            raise NotInAttendanceChannel()
        return True

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s)", self.bot.user, self.bot.user.id)
        if self.bot.get_channel(self.config.attendance_channel_id) is None:
            log.warning("Attendance channel %s not found", self.config.attendance_channel_id)
        if self.config.study_role_id is None:
            log.warning("STUDY_ROLE_ID is not set; ranking will skip the not-attended line")

    @commands.command(name="주말출석")
    async def check_in(self, ctx: commands.Context) -> None:
        created = ctx.message.created_at
        local = to_kst(created)

        if not is_check_in_open(created):
            if local.weekday() == FRIDAY:
                text = "⏰ 주말 출석은 오늘 17:00부터 할 수 있어요."
            else:
                opens = next_open_at(created)
                text = (
                    "⏰ 주말 출석은 금 17:00 ~ 일 23:59(KST)에 할 수 있어요. "
                    f"다음 출석: {short_day(opens.date())} 17:00"
                )
            await ctx.reply(text, mention_author=False)
            return

        today = local.date()
        before = self.db.user_dates(ctx.guild.id, ctx.author.id)
        inserted = self.db.add(ctx.guild.id, ctx.author.id, today, created)
        s = stats(before | {today}, today)

        if not inserted:
            await ctx.reply(
                f"이미 오늘({format_day(today)}) 출석했어요. 🔥 {s.current}일 연속 유지 중",
                mention_author=False,
            )
            return

        try:
            await ctx.message.add_reaction("✅")
        except discord.HTTPException:
            log.warning("Could not add reaction to message %s", ctx.message.id)

        lines = [
            f"✅ {display_name(ctx.author)}님 주말 출석 완료! ({format_day(today)})",
            f"🔥 {s.current}일 연속 · 최고 {s.best}일 · 누적 {s.total}일",
        ]
        if not before:
            lines.append("🎉 첫 주말 출석이에요!")
        elif s.best > best_streak(before):
            lines.append("🏅 최고 기록 갱신!")
        await ctx.reply("\n".join(lines), mention_author=False)

    @commands.command(name="스트릭", usage="[@멤버]")
    async def streak(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        member = member or ctx.author
        created = ctx.message.created_at
        today = to_kst(created).date()
        dates = self.db.user_dates(ctx.guild.id, member.id)
        s = stats(dates, today)

        weekend = " · ".join(
            f"{WEEKDAY_NAMES[d.weekday()]} {'✅' if d in dates else '⬜'}"
            for d in weekend_of(today)
        )
        embed = discord.Embed(title=f"🔥 {display_name(member)}님의 주말 스트릭", color=EMBED_COLOR)
        embed.add_field(name="현재", value=f"{s.current}일 연속")
        embed.add_field(name="최고", value=f"{s.best}일")
        embed.add_field(name="누적", value=f"{s.total}일")
        embed.add_field(name="이번 주말", value=weekend, inline=False)

        if is_weekend(today) and today not in dates and s.current > 0:
            when = "오늘 출석하면" if is_check_in_open(created) else "오늘 17:00 이후 출석하면"
            embed.set_footer(text=f"{when} {s.current + 1}일 연속이 돼요")

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="랭킹")
    async def ranking(self, ctx: commands.Context) -> None:
        today = to_kst(ctx.message.created_at).date()
        records = self.db.guild_dates(ctx.guild.id)
        entries = build_ranking(records, today)

        lines = []
        for e in entries:
            if e.rank is None:
                continue
            medal = MEDALS.get(e.rank, "▫️")
            lines.append(f"{medal} {e.rank}등  <@{e.user_id}>  {e.stats.current}일")

        broken = [f"<@{e.user_id}>" for e in entries if e.rank is None]
        if broken:
            lines += ["", "😴 0일: " + ", ".join(broken)]

        never = self._never_attended(ctx.guild, records)
        if never:
            lines += ["", "🙅 출석안함: " + ", ".join(f"<@{m.id}>" for m in never)]

        description = "\n".join(lines).strip() or "아직 출석 기록이 없어요."
        if len(description) > EMBED_DESCRIPTION_LIMIT:
            description = description[: EMBED_DESCRIPTION_LIMIT - 1] + "…"

        embed = discord.Embed(
            title=f"🏆 주말 스트릭 랭킹 ({format_day(today)} 기준)",
            description=description,
            color=EMBED_COLOR,
        )
        await ctx.reply(embed=embed, mention_author=False)

    def _never_attended(
        self, guild: discord.Guild, records: dict[int, set[date]]
    ) -> list[discord.Member]:
        if self.config.study_role_id is None:
            return []
        role = guild.get_role(self.config.study_role_id)
        if role is None:
            log.warning("Study role %s not found in guild %s", self.config.study_role_id, guild.id)
            return []
        members = [m for m in role.members if not m.bot and m.id not in records]
        return sorted(members, key=lambda m: m.id)

    @commands.command(name="도움말")
    async def help(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title="📆 주말 출석 봇 도움말", color=EMBED_COLOR)
        embed.add_field(
            name="명령어",
            value=(
                "`!주말출석` 오늘 주말 출석하기\n"
                "`!스트릭 [@멤버]` 연속 출석 일수 보기\n"
                "`!랭킹` 현재 스트릭 랭킹 보기\n"
                "`!도움말` 이 안내 보기"
            ),
            inline=False,
        )
        embed.add_field(
            name="출석 규칙",
            value=(
                "• 금 17:00 ~ 일 23:59(KST)에 하루 한 번 출석해요.\n"
                "• 금·토·일을 하루도 빠뜨리지 않으면 스트릭이 이어져요.\n"
                "• 월~목은 건너뛰고 일요일 다음은 다음 주 금요일이에요."
            ),
            inline=False,
        )
        embed.add_field(
            name="관리자 (서버 관리 권한)",
            value=(
                "`!출석추가 @멤버 YYYY-MM-DD` 출석 추가\n"
                "`!출석삭제 @멤버 YYYY-MM-DD` 출석 삭제"
            ),
            inline=False,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="출석추가", usage="@멤버 YYYY-MM-DD")
    @commands.has_guild_permissions(manage_guild=True)
    async def admin_add(
        self, ctx: commands.Context, user: discord.User, day: parse_date
    ) -> None:
        today = to_kst(ctx.message.created_at).date()
        if not is_weekend(day):
            await ctx.reply(
                f"{short_day(day)}은 주말이 아니에요. 금·토·일 날짜만 추가할 수 있어요.",
                mention_author=False,
            )
            return
        if day > today:
            await ctx.reply("미래 날짜는 추가할 수 없어요.", mention_author=False)
            return

        name = display_name(user)
        if not self.db.add(ctx.guild.id, user.id, day, discord.utils.utcnow(), source="admin"):
            await ctx.reply(f"{name}님은 {short_day(day)}에 이미 출석 기록이 있어요.", mention_author=False)
            return

        s = stats(self.db.user_dates(ctx.guild.id, user.id), today)
        log.info("%s added attendance for %s on %s", ctx.author.id, user.id, day)
        await ctx.reply(
            f"✅ {name}님의 {short_day(day)} 출석을 추가했어요. 🔥 현재 {s.current}일 연속",
            mention_author=False,
        )

    @commands.command(name="출석삭제", usage="@멤버 YYYY-MM-DD")
    @commands.has_guild_permissions(manage_guild=True)
    async def admin_remove(
        self, ctx: commands.Context, user: discord.User, day: parse_date
    ) -> None:
        name = display_name(user)
        if not self.db.remove(ctx.guild.id, user.id, day):
            await ctx.reply(f"{name}님은 {short_day(day)}에 출석 기록이 없어요.", mention_author=False)
            return

        today = to_kst(ctx.message.created_at).date()
        s = stats(self.db.user_dates(ctx.guild.id, user.id), today)
        log.info("%s removed attendance for %s on %s", ctx.author.id, user.id, day)
        await ctx.reply(
            f"🗑️ {name}님의 {short_day(day)} 출석을 삭제했어요. 🔥 현재 {s.current}일 연속",
            mention_author=False,
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, (commands.CommandNotFound, NotInAttendanceChannel, commands.NoPrivateMessage)):
            return

        if isinstance(error, commands.MissingPermissions):
            text = "이 명령어는 서버 관리 권한이 있는 사람만 쓸 수 있어요."
        elif isinstance(error, DateFormatError):
            text = str(error)
        elif isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
            text = "멤버를 찾을 수 없어요. `@멘션`으로 지정해 주세요."
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            text = f"사용법: `!{ctx.command.qualified_name} {ctx.command.usage or ''}`".rstrip()
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if isinstance(original, sqlite3.Error):
                log.exception("Database error in %s", ctx.command, exc_info=original)
            else:
                log.exception("Unexpected error in %s", ctx.command, exc_info=original)
            text = "처리 중 오류가 생겼어요. 잠시 후 다시 시도해 주세요."
        else:
            log.warning("Unhandled command error in %s: %r", ctx.command, error)
            return

        await ctx.reply(text, mention_author=False)
