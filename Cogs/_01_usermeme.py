from asyncio import TimeoutError
from random import choice
import discord
import aiohttp
from EZPaginator import Paginator
from discord.ext import commands, tasks
from tool import embedcolor, sendmeme, errorcolor, set_buttons, wait_buttons
from datetime import datetime, timedelta
import aiofiles
import aiosqlite as aiosql
from shutil import copy2
import asyncio
from os import remove
from discord_components import Button, ButtonStyle


class Usermeme(commands.Cog, name="짤 공유"):

    """
    유저들이 짤을 공유하고 보는 명령어들
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="업로드",
        aliases=("올리기", "ㅇㄹㄷ"),
        help="유저들이 공유하고 싶은 짤을 올리는 기능입니다",
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, commands.BucketType.user)
    async def _upload(self, ctx):
        await ctx.send("사진(파일 또는 URL)을 업로드해 주세요.")
        try:
            msg = await self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            )
        except TimeoutError:
            return await ctx.send("취소되었습니다.")
        if not msg.attachments:
            url = msg.content
        else:
            url = msg.attachments[0].url
        url = url.split("?")[0]
        if not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return await ctx.send("지원되지 않는 파일 형식입니다.")
        filename = (
            str(ctx.author.id)
            + " "
            + str(datetime.utcnow() + timedelta(hours=9))
            + "."
            + url.split(".")[-1]
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await resp.read())
        try:
            img_msg = await self.bot.get_channel(852811274886447114).send(
                file=discord.File(filename)
            )
            remove(filename)
        except discord.Forbidden:
            remove(filename)
            return await ctx.send("파일 크기가 너무 큽니다")
        await ctx.send("짤의 제목을 입력해주세요\n제목이 없으면 `없음`을 입력해주세요")
        msg = await self.bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
        )
        title = "" if msg.content == "없음" else msg.content
        embed = discord.Embed(title="확인", description=title, color=embedcolor)
        embed.set_image(url=url)
        await ctx.send(
            content="이 내용으로 짤을 등록할까요?",
            embed=embed,
            components=[
                [
                    Button(emoji='✅', style=ButtonStyle.green),
                    Button(emoji='❌', style=ButtonStyle.red),
                ]
            ]
        )
        interaction = await self.bot.wait_for(
            "button_click",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.component.label is None,
        )
        if interaction.component.emoji == '❌':
            await img_msg.delete()
            return await ctx.reply('취소되었습니다')
        async with aiosql.connect("memebot.db", isolation_level=None) as cur:
            await cur.execute(
                "INSERT INTO usermeme(id, uploader_id, title, url) VALUES(?, ?, ?, ?)",
                (img_msg.id, ctx.author.id, title, img_msg.attachments[0].url),
            )
        await ctx.reply("짤 업로드 완료")

    @commands.command(
        name="랜덤",
        aliases=("ㄹㄷ", "무작위", "랜덤보기", "뽑기"),
        help="유저들이 올린 짤들 중에서 랜덤으로 뽑아 올려줍니다",
    )
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _random(self, ctx):
        async with aiosql.connect("memebot.db") as cur:
            async with cur.execute("SELECT id FROM usermeme") as result:
                meme = choice(await result.fetchall())[0]
        await wait_buttons(
            msg=await sendmeme(
                bot=self.bot,
                memeid=meme,
                msg=await set_buttons(ctx),
            ),
            memeid=meme,
            bot=self.bot,
        )

    @commands.group(
        "내짤",
        invoke_without_command=True,
        usage="<갤러리/제거/수정> [짤 ID]",
        aliases=("ㄴㅉ", "짤"),
        help="올린 짤의 목록을 보거나 지우거나 수정합니다",
    )
    async def meme(self, ctx):
        async with aiosql.connect("memebot.db") as cur:
            async with cur.execute(
                "SELECT * FROM customprefix WHERE guild_id=?", (ctx.guild.id,)
            ) as result:
                prefix = await result.fetchall()
        prefix = prefix[0][1] if prefix else "ㅉ"
        await ctx.reply(f"{prefix}내짤 <목록/제거/수정> [짤 ID]\n(짤 ID는 목록 명령어 사용시 불필요)")

    @meme.command(
        name="목록",
        aliases=("ㅁㄹ", "보기"),
        help="내가 올린 짤의 목록을 봅니다",
    )
    @commands.max_concurrency(1, commands.BucketType.user)
    async def _mymeme(self, ctx):
        async with aiosql.connect("memebot.db", isolation_level=None) as cur:
            async with cur.execute(
                "SELECT * FROM usermeme WHERE uploader_id=?", (ctx.author.id,)
            ) as result:
                memes = await result.fetchall()
        embeds = [
            discord.Embed(
                title=f"{i[2] if i[2] != '' else '`제목 없음`'} - ({memes.index(i) + 1}/{len(memes)})",
                color=embedcolor,
            )
            .set_image(url=i[3])
            .set_footer(text=f"밈 ID: {i[0]}")
            for i in memes
        ]
        message = await ctx.reply(embed=embeds[0])
        page = Paginator(
            bot=self.bot,
            message=message,
            embeds=embeds,
            use_extend=True,
            timeout=10,
            only=ctx.author,
        )
        await page.start()

    @meme.command(
        name="제거",
        aliases=("ㅈㄱ", "삭제"),
        help="자신이 올렸던 짤을 삭제합니다",
        usage="<짤 ID>",
    )
    async def _delete(self, ctx, memeid=None):
        if memeid is None:
            return await ctx.send(
                f"사용법은 `{ctx.command.usage}`입니다.\n(짤 ID는 내짤 명령어에서 확인 할 수 있습니다.)"
            )
        async with aiosql.connect("memebot.db") as cur:
            async with cur.execute(
                "SELECT * FROM usermeme WHERE id=?", (memeid,)
            ) as result:
                try:
                    result = (await result.fetchall())[0]
                except IndexError:
                    return await ctx.send("짤을 찾을 수 없습니다")
        embed = discord.Embed(title=result[2], color=embedcolor)
        embed.set_image(url=result[3])
        m = await ctx.send("이 짤을 삭제할까요?\n`ㅇ`: OK, `ㄴ`: No", embed=embed)
        try:
            msg = await self.bot.wait_for(
                "message",
                check=lambda _m: _m.author == ctx.author and _m.channel == ctx.channel,
            )
        except TimeoutError:
            return await ctx.send("취소되었습니다")
        if msg.content != "ㅇ":
            return await ctx.send("취소되었습니다")
        await m.delete()
        async with aiosql.connect("memebot.db", isolation_level=None) as cur:
            await cur.execute("DELETE FROM usermeme WHERE id=?", (memeid,))
        await ctx.reply("삭제 완료")

    @meme.command(
        name="수정",
        aliases=("ㅅㅈ", "변경"),
        usage="<짤 ID>",
        help="자신이 올린 짤의 제목을 바꿉니다",
    )
    async def _edit(self, ctx, memeid=None):
        if memeid is None:
            return await ctx.send(
                f"사용법은 `{ctx.command.usage}`입니다.\n(짤 ID는 내짤 명령어에서 확인 할 수 있습니다.)"
            )
        async with aiosql.connect("memebot.db") as cur:
            async with cur.execute(
                "SELECT * FROM usermeme WHERE id=?", (memeid,)
            ) as result:
                if not await result.fetchall():
                    await ctx.send("짤을 찾을 수 없습니다")
        await ctx.send("바꿀 제목을 입력해 주세요")
        try:
            msg = await self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            )
        except TimeoutError:
            return await ctx.send("취소되었습니다")
        async with aiosql.connect("memebot.db", isolation_level=None) as cur:
            await cur.execute(
                "UPDATE usermeme SET title=? WHERE id=?", (msg.content, memeid)
            )
        await ctx.reply("제목이 수정되었습니다")

    @commands.command(name="조회", aliases=("ㅈㅎ",), usage="<짤 ID>", help="밈 ID로 짤을 찾습니다")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _findwithid(self, ctx, memeid: int):
        msg = await set_buttons(ctx)
        try:
            await wait_buttons(
                msg=await sendmeme(
                    bot=self.bot,
                    memeid=memeid,
                    msg=msg,
                ),
                memeid=memeid,
                bot=self.bot,
            )
        except ValueError:
            await msg.edit(embed=discord.Embed(title="짤을 찾을 수 없습니다.", color=errorcolor))


def setup(bot):
    bot.add_cog(Usermeme(bot))
