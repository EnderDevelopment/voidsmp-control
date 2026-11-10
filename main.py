import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("voidsmp")
DATA_FILE = Path(os.getenv("DATA_FILE", "data.json"))
PURPLE = discord.Color.from_rgb(139, 92, 246)


def load_data() -> dict[str, Any]:
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("guilds", {})
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"guilds": {}}


data = load_data()


def save_data() -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def guild_config(guild_id: int) -> dict[str, Any]:
    return data.setdefault("guilds", {}).setdefault(str(guild_id), {
        "welcome_channel": None,
        "welcome_message": "Willkommen {user} auf **{server}**!",
        "ticket_category": None,
        "ticket_support_role": None,
        "log_channel": None,
        "tickets": {},
    })


def purple_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=PURPLE, timestamp=datetime.now(timezone.utc))


class VoidSMPBot(commands.Bot):
    async def setup_hook(self) -> None:
        synced = await self.tree.sync()
        self.add_view(TicketView())
        self.add_view(CloseTicketView())
        log.info("%d Slash-Befehle synchronisiert", len(synced))


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = VoidSMPBot(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=False))


@bot.event
async def on_ready() -> None:
    log.info("Angemeldet als %s (%s)", bot.user, bot.user.id if bot.user else "unbekannt")
    await bot.change_presence(activity=discord.Game(name="VoidSMP | /help"))


@bot.event
async def on_member_join(member: discord.Member) -> None:
    cfg = guild_config(member.guild.id)
    channel = member.guild.get_channel(cfg.get("welcome_channel")) if cfg.get("welcome_channel") else None
    if channel:
        message = str(cfg.get("welcome_message", "Willkommen {user} auf **{server}**!"))
        await channel.send(embed=purple_embed("Willkommen bei VoidSMP!", message.format(user=member.mention, server=member.guild.name, member=member.display_name)))


@bot.event
async def on_member_remove(member: discord.Member) -> None:
    cfg = guild_config(member.guild.id)
    channel = member.guild.get_channel(cfg.get("log_channel")) if cfg.get("log_channel") else None
    if channel:
        await channel.send(embed=purple_embed("Mitglied hat den Server verlassen", f"**{discord.utils.escape_markdown(str(member))}** ({member.id}) hat den Server verlassen."))


@bot.event
async def on_message_delete(message: discord.Message) -> None:
    if message.author.bot or not message.guild:
        return
    cfg = guild_config(message.guild.id)
    channel_id = cfg.get("log_channel")
    channel = message.guild.get_channel(channel_id) if channel_id and message.channel.id != channel_id else None
    if channel:
        body = discord.utils.escape_mentions(message.content[:1500]) or "[kein Text]"
        await channel.send(embed=purple_embed("Nachricht gelöscht", f"**Autor:** {message.author.mention} ({message.author.id})\n**Kanal:** {message.channel.mention}\n**Inhalt:** {body}"))


@bot.tree.command(name="help", description="Zeigt alle Funktionen des VoidSMP-Bots")
async def help_command(interaction: discord.Interaction) -> None:
    embed = purple_embed("VoidSMP Bot", "Das lila All-in-One-System für deinen Server.")
    embed.add_field(name="Community", value="`/welcome_setup` `/announce` `/poll` `/serverinfo` `/userinfo`", inline=False)
    embed.add_field(name="Tickets", value="`/ticket_panel` `/ticket_close`", inline=False)
    embed.add_field(name="Moderation", value="`/kick` `/ban` `/timeout` `/untimeout` `/purge` `/slowmode`", inline=False)
    embed.add_field(name="Konfiguration", value="`/set_log_channel` `/set_ticket_category` `/set_support_role`", inline=False)
    embed.set_footer(text="Für die Verwendung werden die passenden Discord-Berechtigungen benötigt.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


def admin_only():
    return app_commands.checks.has_permissions(administrator=True)


def moderator_only():
    return app_commands.checks.has_permissions(moderate_members=True)


@bot.tree.command(name="welcome_setup", description="Konfiguriert Willkommenskanal und Nachricht")
@admin_only()
@app_commands.describe(channel="Kanal für Begrüßungen", message="Verwende {user}, {server} oder {member}")
async def welcome_setup(interaction: discord.Interaction, channel: discord.TextChannel, message: str = "Willkommen {user} auf **{server}**!") -> None:
    cfg = guild_config(interaction.guild_id)
    cfg["welcome_channel"] = channel.id
    cfg["welcome_message"] = message[:1800]
    save_data()
    await interaction.response.send_message(embed=purple_embed("Willkommenssystem eingerichtet", f"Neue Mitglieder werden in {channel} begrüßt. Nachricht: {message}"), ephemeral=True)


@bot.tree.command(name="set_log_channel", description="Legt den Kanal für Mitglieder- und Nachrichtenlogs fest")
@admin_only()
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    guild_config(interaction.guild_id)["log_channel"] = channel.id
    save_data()
    await interaction.response.send_message(embed=purple_embed("Logging eingerichtet", f"Der Log-Kanal ist jetzt {channel}. Gelöschte Nachrichten und Serveraustritte werden dort protokolliert."), ephemeral=True)


@bot.tree.command(name="set_ticket_category", description="Legt die Kategorie für Ticketkanäle fest")
@admin_only()
async def set_ticket_category(interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
    guild_config(interaction.guild_id)["ticket_category"] = category.id
    save_data()
    await interaction.response.send_message(embed=purple_embed("Ticketkategorie eingerichtet", f"Tickets werden in **{category.name}** erstellt."), ephemeral=True)


@bot.tree.command(name="set_support_role", description="Legt die Rolle fest, die Tickets sehen darf")
@admin_only()
async def set_support_role(interaction: discord.Interaction, role: discord.Role) -> None:
    guild_config(interaction.guild_id)["ticket_support_role"] = role.id
    save_data()
    await interaction.response.send_message(embed=purple_embed("Support-Rolle eingerichtet", f"{role.mention} kann jetzt Tickets sehen."), ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket öffnen", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="voidsmp:ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Tickets können nur auf einem Server geöffnet werden.", ephemeral=True)
            return
        cfg = guild_config(guild.id)
        existing = cfg.setdefault("tickets", {}).get(str(interaction.user.id))
        old_channel = guild.get_channel(existing) if existing else None
        if old_channel:
            await interaction.response.send_message(f"Du hast bereits ein offenes Ticket: {old_channel.mention}", ephemeral=True)
            return
        category = guild.get_channel(cfg.get("ticket_category")) if cfg.get("ticket_category") else None
        if category is not None and not isinstance(category, discord.CategoryChannel):
            category = None
        support_role = guild.get_role(cfg.get("ticket_support_role")) if cfg.get("ticket_support_role") else None
        overwrites: dict[Any, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        }
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        safe_name = re.sub(r"[^a-z0-9-]", "", interaction.user.name.lower().replace(" ", "-"))[:18] or "mitglied"
        channel = await guild.create_text_channel(f"ticket-{safe_name}", category=category, overwrites=overwrites, reason=f"Support-Ticket von {interaction.user}")
        cfg["tickets"][str(interaction.user.id)] = channel.id
        save_data()
        mention = f" {support_role.mention}" if support_role else ""
        await channel.send(content=f"{interaction.user.mention}{mention}", embed=purple_embed("VoidSMP Support", "Beschreibe bitte dein Anliegen. Ein Teammitglied wird dir schnellstmöglich helfen."), view=CloseTicketView())
        await interaction.response.send_message(f"Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="voidsmp:ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel) or not interaction.guild:
            await interaction.response.send_message("Diese Schaltfläche funktioniert nur in einem Ticketkanal.", ephemeral=True)
            return
        cfg = guild_config(interaction.guild.id)
        owner_id = next((int(user_id) for user_id, channel_id in cfg.get("tickets", {}).items() if channel_id == interaction.channel.id), None)
        member = interaction.user
        is_staff = isinstance(member, discord.Member) and (member.guild_permissions.manage_channels or member.guild_permissions.administrator)
        if owner_id != member.id and not is_staff:
            await interaction.response.send_message("Nur der Ticket-Ersteller oder das Team darf dieses Ticket schließen.", ephemeral=True)
            return
        await interaction.response.send_message(embed=purple_embed("Ticket geschlossen", "Dieser Kanal wird in fünf Sekunden gelöscht."))
        if owner_id is not None:
            cfg["tickets"].pop(str(owner_id), None)
            save_data()
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket geschlossen von {member}")


@bot.tree.command(name="ticket_panel", description="Postet ein Panel zum Öffnen von Support-Tickets")
@admin_only()
async def ticket_panel(interaction: discord.Interaction) -> None:
    await interaction.channel.send(embed=purple_embed("VoidSMP Support-Tickets", "Klicke unten, um ein privates Support-Ticket zu erstellen. Bitte öffne immer nur ein Ticket gleichzeitig."), view=TicketView())
    await interaction.response.send_message("Das Ticket-Panel wurde gepostet.", ephemeral=True)


@bot.tree.command(name="ticket_close", description="Schließt den aktuellen Ticketkanal")
async def ticket_close(interaction: discord.Interaction) -> None:
    await CloseTicketView().close_ticket.callback(CloseTicketView(), interaction, discord.ui.Button(label="Ticket schließen"))


@bot.tree.command(name="announce", description="Postet eine lila Ankündigung")
@admin_only()
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str) -> None:
    await channel.send(embed=purple_embed(title[:256], message[:4000]))
    await interaction.response.send_message(f"Ankündigung wurde in {channel.mention} gesendet.", ephemeral=True)


@bot.tree.command(name="poll", description="Erstellt eine Ja-Nein-Umfrage")
async def poll(interaction: discord.Interaction, question: str) -> None:
    message = await interaction.channel.send(embed=purple_embed("Community-Umfrage", question[:4000]))
    await message.add_reaction("✅")
    await message.add_reaction("❌")
    await interaction.response.send_message("Die Umfrage wurde erstellt.", ephemeral=True)


@bot.tree.command(name="serverinfo", description="Zeigt Informationen über diesen Server")
async def serverinfo(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Dieser Befehl benötigt einen Server.", ephemeral=True)
        return
    embed = purple_embed(guild.name, f"**Mitglieder:** {guild.member_count}\n**Erstellt:** <t:{int(guild.created_at.timestamp())}:D>\n**Kanäle:** {len(guild.channels)}\n**Rollen:** {len(guild.roles)}\n**Besitzer:** <@{guild.owner_id}>")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Zeigt Informationen über ein Mitglied")
async def userinfo(interaction: discord.Interaction, member: discord.Member | None = None) -> None:
    member = member or interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message("Dieses Servermitglied wurde nicht gefunden.", ephemeral=True)
        return
    roles = ", ".join(role.mention for role in member.roles[1:]) or "Keine"
    embed = purple_embed(str(member), f"**ID:** {member.id}\n**Beigetreten:** {discord.utils.format_dt(member.joined_at, style='R') if member.joined_at else 'Unbekannt'}\n**Konto erstellt:** {discord.utils.format_dt(member.created_at, style='D')}\n**Rollen:** {roles}")
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="kick", description="Kickt ein Mitglied vom Server")
@moderator_only()
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben") -> None:
    if member == interaction.user or member == interaction.guild.owner:
        await interaction.response.send_message("Dieses Mitglied kann damit nicht gekickt werden.", ephemeral=True)
        return
    await member.kick(reason=f"{interaction.user}: {reason}")
    await interaction.response.send_message(embed=purple_embed("Mitglied gekickt", f"{member.mention} wurde gekickt.\n**Grund:** {reason}"))


@bot.tree.command(name="ban", description="Bannt ein Mitglied vom Server")
@moderator_only()
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben", delete_message_days: app_commands.Range[int, 0, 7] = 0) -> None:
    if member == interaction.user or member == interaction.guild.owner:
        await interaction.response.send_message("Dieses Mitglied kann damit nicht gebannt werden.", ephemeral=True)
        return
    await member.ban(reason=f"{interaction.user}: {reason}", delete_message_seconds=delete_message_days * 86400)
    await interaction.response.send_message(embed=purple_embed("Mitglied gebannt", f"{member} wurde gebannt.\n**Grund:** {reason}"))


@bot.tree.command(name="timeout", description="Gibt einem Mitglied bis zu 28 Tage Timeout")
@moderator_only()
@app_commands.default_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 40320], reason: str = "Kein Grund angegeben") -> None:
    if member == interaction.user or member == interaction.guild.owner:
        await interaction.response.send_message("Dieses Mitglied kann damit keinen Timeout erhalten.", ephemeral=True)
        return
    await member.timeout(discord.utils.utcnow() + timedelta(minutes=minutes), reason=f"{interaction.user}: {reason}")
    await interaction.response.send_message(embed=purple_embed("Timeout vergeben", f"{member.mention} hat für {minutes} Minuten Timeout erhalten.\n**Grund:** {reason}"))


@bot.tree.command(name="untimeout", description="Entfernt den Timeout eines Mitglieds")
@moderator_only()
@app_commands.default_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben") -> None:
    await member.timeout(None, reason=f"{interaction.user}: {reason}")
    await interaction.response.send_message(embed=purple_embed("Timeout entfernt", f"Der Timeout von {member.mention} wurde entfernt."))


@bot.tree.command(name="purge", description="Löscht aktuelle Nachrichten in diesem Kanal")
@moderator_only()
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Verwende diesen Befehl in einem Textkanal.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"{len(deleted)} Nachrichten wurden gelöscht.", ephemeral=True)


@bot.tree.command(name="slowmode", description="Setzt den Slowmode dieses Kanals")
@moderator_only()
@app_commands.default_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Verwende diesen Befehl in einem Textkanal.", ephemeral=True)
        return
    await interaction.channel.edit(slowmode_delay=seconds, reason=f"Geändert von {interaction.user}")
    await interaction.response.send_message(embed=purple_embed("Slowmode aktualisiert", f"Der Slowmode beträgt jetzt {seconds} Sekunden."))


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        message = "Du hast keine Berechtigung für diesen Befehl."
    elif isinstance(error, app_commands.BotMissingPermissions):
        message = "Dem Bot fehlt eine benötigte Berechtigung."
    elif isinstance(error, app_commands.CommandOnCooldown):
        message = f"Bitte warte noch {error.retry_after:.1f} Sekunden."
    else:
        log.error("Befehlsfehler", exc_info=error)
        message = "Der Befehl ist fehlgeschlagen. Prüfe die Bot-Berechtigungen."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if not os.getenv("DISCORD_TOKEN"):
    raise RuntimeError("Setze DISCORD_TOKEN in deiner .env-Datei. Siehe .env.example.")

bot.run(os.environ["DISCORD_TOKEN"])
