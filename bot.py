"""
Discord Broadcast Bot
----------------------
بوت يسمح للأدمن (أو رولات محددة) ببعث رسائل خاصة (DM) جماعية
لأعضاء السيرفر - إما للكل أو لأصحاب رول معين (opt-in).

يحترم rate limits تاع ديسكورد ويسجل مين وصلتو الرسالة ومين لا.
"""

import os
import asyncio
import logging
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
# آي دي الأشخاص المسموح لهم يستعملو أمر البروداكاست (الأدمنية)
ALLOWED_USER_IDS = {
    int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()
}
# الفاصل الزمني بين كل رسالة وأخرى (بالثواني) باش نتفاداو rate limit / حظر
DELAY_BETWEEN_MESSAGES = float(os.getenv("DELAY_BETWEEN_MESSAGES", "1.5"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("broadcast-bot")

intents = discord.Intents.default()
intents.members = True  # لازم تفعلها من Discord Developer Portal (Privileged Intents)
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def is_authorized(user_id: int) -> bool:
    """يتحقق واش المستخدم مسموحلو يستعمل أوامر البروداكاست."""
    return user_id in ALLOWED_USER_IDS


@bot.event
async def on_ready():
    logger.info(f"البوت متصل باسم {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        logger.info(f"تم تزامن {len(synced)} أوامر سلاش.")
    except Exception as e:
        logger.error(f"خطأ في تزامن الأوامر: {e}")


async def send_broadcast(
    interaction: discord.Interaction,
    members: list[discord.Member],
    message: str,
):
    """يبعث الرسالة لقايمة أعضاء، ويرجع تقرير بالنجاح والفشل."""
    success, failed, closed_dm = [], [], []

    await interaction.followup.send(
        f"🚀 بدأت عملية الإرسال لـ **{len(members)}** عضو... راهي تاخذ وقت.",
        ephemeral=True,
    )

    for member in members:
        if member.bot:
            continue
        try:
            embed = discord.Embed(
                description=message,
                color=discord.Color.blurple(),
                timestamp=datetime.utcnow(),
            )
            embed.set_footer(text=f"رسالة من سيرفر {interaction.guild.name}")
            await member.send(embed=embed)
            success.append(member)
            logger.info(f"✅ توصلت الرسالة لـ {member} ({member.id})")
        except discord.Forbidden:
            # العضو قافل الـ DMs أو حاظر البوت
            closed_dm.append(member)
            logger.warning(f"⛔ {member} قافل الـ DMs")
        except discord.HTTPException as e:
            failed.append(member)
            logger.error(f"❌ فشل الإرسال لـ {member}: {e}")

        await asyncio.sleep(DELAY_BETWEEN_MESSAGES)

    report = (
        f"✅ **تقرير الإرسال**\n"
        f"— نجحت: {len(success)}\n"
        f"— قافلين الـ DMs: {len(closed_dm)}\n"
        f"— فشلت لأسباب أخرى: {len(failed)}\n"
    )
    await interaction.followup.send(report, ephemeral=True)


@bot.tree.command(name="broadcast_all", description="ابعث رسالة خاصة لكل أعضاء السيرفر")
@app_commands.describe(message="نص الرسالة يلي تحب تبعثها")
async def broadcast_all(interaction: discord.Interaction, message: str):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ ما عندكش الصلاحية باش تستعمل هذا الأمر.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    members = [m async for m in interaction.guild.fetch_members(limit=None)]
    await send_broadcast(interaction, members, message)


@bot.tree.command(
    name="broadcast_role",
    description="ابعث رسالة خاصة لأعضاء عندهم رول معين (مثلا رول 'مشترك')",
)
@app_commands.describe(
    role="الرول يلي تحب تبعث لأعضائه", message="نص الرسالة يلي تحب تبعثها"
)
async def broadcast_role(
    interaction: discord.Interaction, role: discord.Role, message: str
):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ ما عندكش الصلاحية باش تستعمل هذا الأمر.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    members = [m for m in role.members]
    if not members:
        await interaction.followup.send(
            f"⚠️ ما فماش أعضاء عندهم رول {role.name}.", ephemeral=True
        )
        return
    await send_broadcast(interaction, members, message)


@bot.tree.command(
    name="broadcast_user",
    description="ابعث رسالة خاصة لعضو واحد محدد",
)
@app_commands.describe(user="العضو يلي تحب تبعثلو", message="نص الرسالة")
async def broadcast_user(
    interaction: discord.Interaction, user: discord.Member, message: str
):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ ما عندكش الصلاحية باش تستعمل هذا الأمر.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    await send_broadcast(interaction, [user], message)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("⚠️ لازم تحط DISCORD_TOKEN في ملف .env")
    bot.run(TOKEN)
