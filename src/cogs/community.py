import asyncio
import random
import re
from pathlib import Path

import discord
from discord.ext import commands
from tortoise import timezone

from utils import checks, models
from utils.bot_class import MyBot
from utils.cog_class import Cog
from utils.ctx_class import MyContext
from utils.human_time import ShortTime
from utils.interaction import make_message_embed
from utils.models import AccessLevel, get_from_db


async def wait_cd(monitored_player, ctx, name, dt):
    _ = await ctx.get_translate_function(user_language=True)
    now = timezone.now()

    seconds = (dt - now).total_seconds()
    seconds = max(seconds, 1)
    await asyncio.sleep(seconds)
    ctx.logger.debug(f"{monitored_player.name} cooldown for {name} expired, notifying.")
    await ctx.send(
        _(
            "{monitored_player.mention}, RPG cooldown: **{name}** expired.",
            name=name,
            monitored_player=monitored_player,
        )
    )


saysounds_folder = Path("assets/Sounds")

saysounds_files = {
    file.name.split(".")[0]: file
    for file in saysounds_folder.glob("*.mp4")
}

saysounds_names = tuple(sorted(saysounds_files.keys(), key=lambda x: -len(x)))


def find_string(prefixes, string):
    for prefix in prefixes:
        if " " in prefix:
            if prefix in string:
                return prefix
        else:
            if string == prefix:
                return prefix
    return None


class Community(Cog):
    def __init__(self, bot: MyBot, *args, **kwargs):
        super().__init__(bot, *args, **kwargs)
        self.epic_rpg_cd_coros = {}
        self.message_link_regex = re.compile(
            r"discord\.com/channels/"
            r"(?P<guild_id>[0-9]*)/"
            r"(?P<channel_id>[0-9]*)/"
            r"(?P<message_id>[0-9]*)",
            flags=re.MULTILINE | re.IGNORECASE,
        )

    @commands.command()
    @checks.needs_access_level(models.AccessLevel.BOT_MODERATOR)
    async def beta_invite(self, ctx: MyContext):
        """
        Invite someone to the beta server, letting them try the bot before the others
        """
        beta_server = self.bot.get_guild(734810932529856652)
        beta_channel = beta_server.get_channel(734810933091762188)

        _ = await ctx.get_translate_function()

        invite = await beta_channel.create_invite(
            reason=f"{ctx.author.name} created an invite on #{ctx.channel.name} ({ctx.guild.name})",
            max_uses=1,
            max_age=120,
            unique=True,
        )

        await ctx.reply(
            _(f"Here's the invite you requested {invite}", invite=invite.url)
        )

    async def is_in_server(self, message):
        return message.guild and message.guild.id in self.config()["servers"]

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "❌":
            return

        if payload.guild_id not in self.config()["servers"]:
            return

        if (
                payload.user_id
                not in self.config()["moderators_that_can_delete_with_reactions"]
        ):
            return

        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        self.bot.logger.info(
            f"Deleting message from {message.author.name} in #{channel.name} ({guild.name}) because a mod reacted with ❌. "
        )
        await message.delete()

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not await self.is_in_server(message):
            return

        ctx: MyContext = await self.bot.get_context(message, cls=MyContext)
        db_member = None

        if message.author.id == 555955826880413696:
            await self.epic_rpg_cooldowns(message)
            await self.epic_rpg_pings(message)

        if not message.author.bot:
            links_matches = list(self.message_link_regex.finditer(message.content))

            if links_matches and len(links_matches) <= 5:
                for match in links_matches:
                    match_guild_id = int(match.group("guild_id"))
                    match_channel_id = int(match.group("channel_id"))
                    match_message_id = int(match.group("message_id"))

                    match_guild = self.bot.get_guild(match_guild_id)

                    if not match_guild:
                        continue

                    match_channel = match_guild.get_channel(
                        match_channel_id
                    ) or match_guild.get_thread(match_channel_id)

                    if not match_channel:
                        continue

                    # Permissions check !
                    permissions = match_channel.permissions_for(
                        await match_guild.fetch_member(message.author.id)
                    )

                    if (
                            not permissions.read_message_history
                            or not permissions.read_messages
                    ):
                        # The user can't read messages
                        db_member = db_member or await get_from_db(
                            message.author, as_user=True
                        )
                        if db_member.access_level_override < AccessLevel.BOT_MODERATOR:
                            # And isn't a BOT_MODERATOR or higher, so we won't show anything.
                            continue
                    try:
                        match_message = await match_channel.fetch_message(
                            match_message_id
                        )
                    except discord.Forbidden:
                        # Whoops, we don't have perms to see the message
                        continue

                    embed = await make_message_embed(match_message)
                    await ctx.send(embed=embed)

            maybe_sound = find_string(saysounds_names, message.content.lower().replace("'", ""))

            if maybe_sound:
                ctx.logger.info(f"Playing sound {maybe_sound} ({message.content})")
                await ctx.reply(file=discord.File(saysounds_files[maybe_sound]))

        if message.channel.id == 1020670134072901713:
            # Counter
            await self.counter(message)

        if "cookie" in message.content.lower():
            await message.add_reaction("🍪")

        if not message.author.bot and not message.content.startswith("!") and not message.content.lower().startswith("dh"):
            roundome = random.randint(1, 3600)

            if roundome == 1:
                # TRUE as a reaction
                await message.add_reaction("🇹")
                await message.add_reaction("🇷")
                await message.add_reaction("🇺")
                await message.add_reaction("🇪")
            elif roundome == 2:
                # FALSE as a reaction
                await message.add_reaction("🇫")
                await message.add_reaction("🇦")
                await message.add_reaction("🇱")
                await message.add_reaction("🇸")
                await message.add_reaction("🇪")
            elif roundome == 3:
                await message.add_reaction("😂")
                await message.add_reaction("🤣")
            elif roundome == 4:
                await message.add_reaction("🦆")
            elif roundome == 5:
                await message.add_reaction("❤️")
            elif roundome == 6:
                await message.add_reaction("💖")
            elif roundome == 7:
                # TROUT as a reaction
                await message.add_reaction("🇹")
                await message.add_reaction("🇷")
                await message.add_reaction("🇴")
                await message.add_reaction("🇺")
                await message.add_reaction("<:letter_T:501145536821461003>")
                await message.add_reaction("🐟")
            elif roundome == 8:
                # ayy lmao
                await message.add_reaction("👽")
            elif roundome == 9:
                await message.add_reaction("💯")
            elif roundome == 10:
                await message.add_reaction("👀")
            elif roundome == 11:
                await message.add_reaction("💀")
            elif roundome == 12:
                await message.add_reaction("🔥")
            elif roundome == 13:
                await message.add_reaction("👌")
            elif roundome == 14:
                await message.add_reaction("👍")
            elif roundome == 15:
                await message.add_reaction("👎")
            elif roundome == 16:
                await message.add_reaction("🤔")
            elif roundome == 17:
                await message.add_reaction("🤨")
            elif roundome == 18:
                await message.add_reaction("😎")
            elif roundome == 19:
                await message.add_reaction("🥹")
            elif roundome == 20:
                await message.add_reaction("🥳")

    async def counter(self, message):
        if message.author.bot:
            return
        try:
            current_count = int(message.content)
        except ValueError:
            return

        if current_count % 100 == 0:
            await message.add_reaction("🎉")

        if random.randint(1, 20) == 5:
            next_count = current_count + 1
            await message.channel.send(str(next_count))

    async def parse_embed_cooldowns(self, embed: discord.Embed):
        now = timezone.now()
        cooldowns = []

        for field in embed.fields:
            for cooldown in str(field.value).splitlines():
                splitted_cooldown = cooldown.split(" ")
                emoji = splitted_cooldown[0]

                if emoji == ":clock4:":
                    name_and_duration = splitted_cooldown[2:]
                    in_name = True
                    name = ""
                    duration = ""

                    for element in name_and_duration:
                        if in_name:
                            name += element.replace("*", "").replace("`", "")
                            if element.endswith("`**"):
                                in_name = False
                            else:
                                name += " "
                        else:
                            duration += (
                                element.replace("*", "")
                                .replace("(", "")
                                .replace(")", "")
                            )

                    parsed_duration = ShortTime(duration, now=now)
                    cooldowns.append((name, parsed_duration.dt))
        return cooldowns

    async def get_rpg_role(self, ctx):
        return discord.utils.get(ctx.guild.roles, name=self.config()["rpg_role_name"])

    async def epic_rpg_pings(self, message: discord.Message):
        has_embeds = len(message.embeds)
        is_pingable = False

        if has_embeds:
            embed: discord.Embed = message.embeds[0]
            is_pingable = str(embed.description).startswith(
                "<:epicrpgarena:697563611698298922>"
            )
            is_pingable = is_pingable or (
                str(embed.author.name).endswith("'s miniboss")
            )
            if len(embed.fields) >= 1:
                first_field_name = (
                    str(embed.fields[0].name).replace("*", "").replace("`", "").lower()
                )
                is_pingable = is_pingable or first_field_name.startswith(
                    "an epic tree has just grown"
                )
                is_pingable = is_pingable or first_field_name.startswith(
                    "<:coin:541384484201693185>"
                )
                is_pingable = is_pingable or first_field_name.startswith(
                    "epic npc: i have a special trade today!"
                )
                is_pingable = is_pingable or first_field_name.startswith(
                    "<:epiccoin:551605190965329926> oops!"
                )
                is_pingable = is_pingable or first_field_name.startswith(
                    "a megalodon has spawned"
                )
                is_pingable = is_pingable or first_field_name.startswith(
                    "it's raining coins"
                )

        if is_pingable:
            ctx: MyContext = await self.bot.get_context(message, cls=MyContext)
            rpg_role = await self.get_rpg_role(ctx)
            _ = await ctx.get_translate_function()
            await ctx.send(
                _(
                    "{rpg_role.mention}, you might want to click the reaction above/do what the bot says.",
                    rpg_role=rpg_role,
                )
            )

    async def epic_rpg_cooldowns(self, message: discord.Message):
        has_embeds = len(message.embeds)
        if has_embeds:
            embed: discord.Embed = message.embeds[0]
            is_cooldown = str(embed.author.name).endswith("'s cooldowns")
        else:
            return

        if is_cooldown:
            ctx: MyContext = await self.bot.get_context(message, cls=MyContext)
            try:
                monitored_player_id = int(embed.author.icon_url.split("/")[4])  # ID
            except ValueError:
                await message.add_reaction("❌")
                return
            monitored_player: discord.Member = await ctx.guild.fetch_member(
                monitored_player_id
            )

            maybe_gather = self.epic_rpg_cd_coros.get(monitored_player_id, None)
            if maybe_gather:
                try:
                    maybe_gather.cancel()
                    await maybe_gather
                except asyncio.CancelledError:
                    pass

            rpg_role = await self.get_rpg_role(ctx)
            if rpg_role in monitored_player.roles:
                cooldowns = await self.parse_embed_cooldowns(embed)

                coros = []
                for name, dt in cooldowns:
                    coros.append(wait_cd(monitored_player, ctx, name, dt))

                await message.add_reaction("<:ah:327906673249484800>")
                ctx.logger.debug(
                    f"Adding monitoring for {len(coros)} cooldowns for the RPG account of {monitored_player.name}."
                )
                self.epic_rpg_cd_coros[monitored_player_id] = asyncio.gather(*coros)


setup = Community.setup
