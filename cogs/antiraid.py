import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
import database_handler as db
import time, asyncio
from collections import defaultdict, deque
from utils.checks import has_command_permission

class AntiRaid(commands.Cog):
    """Système de protection avancé contre les raids."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Structure: {guild_id: {user_id: {action_type: deque([timestamps])}}}
        self.action_tracker = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: deque(maxlen=15))))

    # --- Fonctions internes (le cerveau du système) ---
    async def _is_immune(self, member: discord.Member) -> bool:
        if member.id == member.guild.owner_id or member.guild_permissions.administrator:
            return True
        return await db.is_whitelisted(member.guild.id, member.id)

    async def _process_raid_action(self, member: discord.Member, action_type: str):
        if await self._is_immune(member): return False
        
        is_on = await db.get_guild_setting(member.guild.id, f"{action_type}_on")
        if not is_on: return False

        sensitivity_str = await db.get_guild_setting(member.guild.id, f"{action_type}_sensitivity")
        try:
            limit, seconds = map(int, sensitivity_str.replace('s', '').split('/'))
        except (ValueError, AttributeError):
            limit, seconds = (3, 5)

        tracker = self.action_tracker[member.guild.id][member.id][action_type]
        tracker.append(time.time())
        while tracker and time.time() - tracker[0] > seconds:
            tracker.popleft()

        if len(tracker) >= limit:
            punishment_type = await db.get_guild_setting(member.guild.id, f"{action_type}_punishment")
            await self._trigger_punishment(member, punishment_type, f"Déclenchement de l'anti-raid ({action_type})")
            return True
        return False

    async def _trigger_punishment(self, member: discord.Member, punishment: str, reason: str):
        # ... (Logique de punition et de log)
        pass

    # --- Listeners pour chaque protection ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Anti-Token & Creation Limit
        creation_limit_seconds = await db.get_guild_setting(member.guild.id, 'creation_limit_seconds')
        if creation_limit_seconds and creation_limit_seconds > 0:
            account_age = (discord.utils.utcnow() - member.created_at).total_seconds()
            if account_age < creation_limit_seconds:
                await member.kick(reason=f"Anti-Raid: Compte trop récent (créé il y a {int(account_age/60)} minutes).")
                # Log l'action...
                return
        
        # Anti-Bot
        if member.bot:
            antibot_on = await db.get_guild_setting(member.guild.id, 'antibot_on')
            if antibot_on:
                try: # L'audit log peut ne pas être instantané
                    async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                        if entry.target.id == member.id and not await self._is_immune(entry.user):
                            punishment = await db.get_guild_setting(member.guild.id, 'antibot_punishment')
                            await self._trigger_punishment(entry.user, punishment, "Ajout de bot non autorisé")
                            await member.kick("Anti-Raid: Ajout de bot non autorisé")
                            break
                except discord.Forbidden: pass

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    if await self._process_raid_action(entry.user, 'antichannel'):
                        await channel.delete(reason="Anti-Raid: Mass Channel Create")
        except discord.Forbidden: pass
        
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    await self._process_raid_action(entry.user, 'antiban')
        except discord.Forbidden: pass

    # ... implémentez les autres listeners (on_guild_role_create, on_message pour antieveryone, etc.) ...
    
    # --- Commandes de configuration ---
    secur_group = SlashCommandGroup("secur", "Gère la sécurité globale du serveur.")

    @secur_group.command(name="set", description="Active ou désactive toutes les protections d'un coup.")
    @has_command_permission()
    async def secur_set(self, ctx: discord.ApplicationContext, etat: discord.Option(str, "on/off/max", choices=["on", "off", "max"])):
        # ... logique pour activer/désactiver toutes les protections dans la DB ...
        await ctx.respond(f"✅ Toutes les protections sont maintenant sur `{etat}`.", ephemeral=True)

    @secur_group.command(name="punishment", description="Définit une punition pour une protection spécifique.")
    @has_command_permission()
    async def punishment(self, ctx: discord.ApplicationContext,
                         protection: discord.Option(str, "Protection à configurer", choices=["antiban", "antichannel", "..."]),
                         sanction: discord.Option(str, "Punition à appliquer", choices=["kick", "ban", "derank"])):
        await db.set_guild_setting(ctx.guild.id, f"{protection}_punishment", sanction)
        await ctx.respond(f"✅ La punition pour `{protection}` est maintenant `{sanction}`.", ephemeral=True)
    
    @secur_group.command(name="whitelist", description="Gère la whitelist anti-raid.")
    @has_command_permission()
    async def whitelist(self, ctx: discord.ApplicationContext,
                        action: discord.Option(str, "Action", choices=["add", "remove"]),
                        membre: discord.Option(discord.Member, "Membre")):
        # ... logique pour ajouter/retirer de la whitelist ...
        await ctx.respond("✅ Opération effectuée.", ephemeral=True)

    @secur_group.command(name="creation_limit", description="Définit l'âge minimum de compte pour rejoindre.")
    @has_command_permission()
    async def creation_limit(self, ctx: discord.ApplicationContext, duree: discord.Option(str, "Durée (ex: 30m, 2h, 1d). 0 pour désactiver")):
        # ... logique pour convertir la durée et la stocker dans la DB ...
        await ctx.respond("✅ Limite d'âge de compte mise à jour.", ephemeral=True)

def setup(bot):
    bot.add_cog(AntiRaid(bot))