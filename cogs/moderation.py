import discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup
import datetime, re, asyncio
import database_handler as db
from utils.checks import has_command_permission

def parse_duration(duration_str: str) -> int:
    regex = re.compile(r'(\d+)([smhdwy])')
    matches = regex.findall(duration_str.lower())
    if not matches: return 0
    total_seconds = 0
    time_units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800, 'y': 31536000}
    for value, unit in matches:
        total_seconds += int(value) * time_units[unit]
    return total_seconds

class Moderation(commands.Cog):
    """Commandes de modération (kick, ban, warn, etc.)"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_expired_sanctions.start()

    # --- Groupes de commandes pour l'organisation ---
    sanctions_group = SlashCommandGroup("sanctions", "Gère les sanctions des membres.")
    voice_group = SlashCommandGroup("voice", "Commandes de modération vocale.")
    channel_group = SlashCommandGroup("channel", "Gère les salons textuels.")
    role_group = SlashCommandGroup("role", "Gère les rôles des membres.")
    prison_group = SlashCommandGroup("prison", "Gère le système de prison.")

    def cog_unload(self):
        self.check_expired_sanctions.cancel()

    async def log_action(self, ctx, title, color, member, reason, duration=None):
        embed = discord.Embed(title=title, color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.add_field(name="Utilisateur", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=False)
        embed.add_field(name="Raison", value=reason, inline=False)
        if duration: embed.add_field(name="Durée", value=duration, inline=False)
        
        logs_cog = self.bot.get_cog('Logs')
        if logs_cog and hasattr(logs_cog, 'log_moderation_action'):
            await logs_cog.log_moderation_action(embed=embed, guild_id=ctx.guild.id)
        
        try:
            await member.send(f"Vous avez reçu une sanction sur le serveur **{ctx.guild.name}**.", embed=embed)
        except discord.Forbidden:
            pass

    @tasks.loop(minutes=1)
    async def check_expired_sanctions(self):
        expired = await db.get_expired_sanctions()
        for s in expired:
            s_id, guild_id, user_id, _, sanc_type, _, _, _, _, role_id_from_db = s
            guild = self.bot.get_guild(guild_id)
            if not guild: continue
            try:
                if sanc_type == 'ban':
                    await guild.unban(discord.Object(id=user_id), reason="Tempban terminé.")
                else:
                    member = await guild.fetch_member(user_id)
                    if sanc_type == 'timeout':
                        await member.timeout(None, reason="Timeout terminé.")
                    elif sanc_type == 'temprole' and role_id_from_db:
                        role_to_remove = guild.get_role(role_id_from_db)
                        if role_to_remove and role_to_remove in member.roles:
                            await member.remove_roles(role_to_remove, reason="Temprole terminé.")
                    elif sanc_type == 'prison':
                        prison_role_id = await db.get_guild_setting(guild.id, 'prison_role_id')
                        prison_role = guild.get_role(prison_role_id) if prison_role_id else None
                        if prison_role and prison_role in member.roles:
                            await member.remove_roles(prison_role, reason="Fin de la peine de prison.")
                        original_role_ids = await db.restore_user_roles(guild.id, user_id)
                        roles_to_restore = [r for r in [guild.get_role(rid) for rid in original_role_ids] if r is not None]
                        if roles_to_restore:
                            await member.add_roles(*roles_to_restore, reason="Fin de la peine de prison.")
                await db.deactivate_sanction(guild_id, user_id, sanc_type)
            except Exception as e:
                print(f"Erreur lors du traitement d'une sanction expirée (ID: {s_id}): {e}")

    @check_expired_sanctions.before_loop
    async def before_check_sanctions(self):
        await self.bot.wait_until_ready()

    # --- Commandes de Sanctions de base ---
    @commands.slash_command(name="kick", description="Expulse un membre du serveur.")
    @has_command_permission()
    async def kick(self, ctx: discord.ApplicationContext, membre: discord.Member, raison: str = "Aucune raison."):
        if membre.top_role >= ctx.author.top_role or membre.id == ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas sanctionner ce membre.", ephemeral=True)
        await self.log_action(ctx, "Expulsion", discord.Color.orange(), membre, raison)
        await membre.kick(reason=f"{raison} (Par {ctx.author})")
        await ctx.respond(f"👢 {membre.mention} a été expulsé.", ephemeral=True)

    @commands.slash_command(name="ban", description="Bannit un membre du serveur.")
    @has_command_permission()
    async def ban(self, ctx: discord.ApplicationContext, membre: discord.Member, raison: str = "Aucune raison."):
        if membre.top_role >= ctx.author.top_role or membre.id == ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas sanctionner ce membre.", ephemeral=True)
        await db.add_sanction(ctx.guild.id, membre.id, ctx.author.id, 'ban', raison)
        await self.log_action(ctx, "Bannissement", discord.Color.red(), membre, raison)
        await membre.ban(reason=f"{raison} (Par {ctx.author})")
        await ctx.respond(f"🔨 {membre.mention} a été banni.", ephemeral=True)

    @commands.slash_command(name="unban", description="Révoque le bannissement d'un utilisateur.")
    @has_command_permission()
    async def unban(self, ctx: discord.ApplicationContext, user_id: str, raison: str = "Aucune raison."):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user, reason=f"{raison} (Par {ctx.author})")
            await db.deactivate_sanction(ctx.guild.id, user.id, 'ban')
            await ctx.respond(f"✅ {user.name} a été débanni.", ephemeral=True)
        except (discord.NotFound, ValueError):
            return await ctx.respond("❌ ID invalide ou utilisateur non banni.", ephemeral=True)

    @commands.slash_command(name="unbanall", description="[DANGEREUX] Révoque tous les bannissements du serveur.")
    @has_command_permission()
    async def unbanall(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        banned_users = await ctx.guild.bans(limit=2000).flatten()
        if not banned_users:
            return await ctx.followup.send("ℹ️ Il n'y a aucun utilisateur banni sur ce serveur.", ephemeral=True)
        unban_count = 0
        for ban_entry in banned_users:
            try:
                await ctx.guild.unban(ban_entry.user, reason=f"Unbanall par {ctx.author}")
                unban_count += 1
                await asyncio.sleep(1)
            except discord.Forbidden:
                await ctx.followup.send(f"⚠️ Je n'ai pas pu débannir {ban_entry.user}. Arrêt de l'opération.", ephemeral=True)
                break
        await ctx.followup.send(f"✅ {unban_count} utilisateur(s) ont été débannis.", ephemeral=True)

    @commands.slash_command(name="timeout", description="Exclut temporairement un membre.")
    @has_command_permission()
    async def timeout(self, ctx: discord.ApplicationContext, membre: discord.Member, duree: str, raison: str = "Aucune raison."):
        if membre.top_role >= ctx.author.top_role or membre.id == ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas sanctionner ce membre.", ephemeral=True)
        duration_seconds = parse_duration(duree)
        if not (0 < duration_seconds <= 2419200):
            return await ctx.respond("❌ Durée invalide ou supérieure à 28 jours.", ephemeral=True)
        max_duration = await db.get_permission_constraint(ctx.author.top_role.id, "timeout", "max_duration")
        if max_duration is not None and duration_seconds > max_duration:
            return await ctx.respond(f"❌ Votre rôle vous autorise un timeout de `{max_duration}`s maximum.", ephemeral=True)
        end_time = discord.utils.utcnow() + datetime.timedelta(seconds=duration_seconds)
        await db.add_sanction(ctx.guild.id, membre.id, ctx.author.id, 'timeout', raison, duration_seconds)
        await membre.timeout(end_time, reason=f"{raison} (Par {ctx.author})")
        await self.log_action(ctx, "Exclusion Temporaire", discord.Color.light_grey(), membre, raison, duree)
        await ctx.respond(f"🤫 {membre.mention} a été exclu jusqu'au <t:{int(end_time.timestamp())}:F>.", ephemeral=True)

    @commands.slash_command(name="untimeout", description="Annule l'exclusion d'un membre.")
    @has_command_permission()
    async def untimeout(self, ctx: discord.ApplicationContext, membre: discord.Member):
        if not membre.is_timed_out():
            return await ctx.respond("❌ Ce membre n'est pas exclu.", ephemeral=True)
        await db.deactivate_sanction(ctx.guild.id, membre.id, 'timeout')
        await membre.timeout(None, reason=f"Annulation par {ctx.author}")
        await self.log_action(ctx, "Fin d'Exclusion", discord.Color.green(), membre, "Annulation manuelle")
        await ctx.respond(f"👍 L'exclusion de {membre.mention} a été levée.", ephemeral=True)

    @commands.slash_command(name="warn", description="Avertit un membre.")
    @has_command_permission()
    async def warn(self, ctx: discord.ApplicationContext, membre: discord.Member, raison: str):
        if membre.top_role >= ctx.author.top_role or membre.id == ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas sanctionner ce membre.", ephemeral=True)
        await db.add_sanction(ctx.guild.id, membre.id, ctx.author.id, 'warn', raison)
        await self.log_action(ctx, "Avertissement", discord.Color.yellow(), membre, raison)
        await ctx.respond(f"⚠️ {membre.mention} a été averti.", ephemeral=True)
    
    @sanctions_group.command(name="list", description="Affiche l'historique des sanctions d'un membre.")
    @has_command_permission()
    async def list_sanctions(self, ctx: discord.ApplicationContext, membre: discord.Member):
        user_sanctions = await db.get_user_sanctions(ctx.guild.id, membre.id)
        if not user_sanctions:
            return await ctx.respond(f"ℹ️ {membre.mention} n'a aucune sanction enregistrée.", ephemeral=True)
        embed = discord.Embed(title=f"Sanctions pour {membre.display_name}", color=membre.color)
        for s in user_sanctions:
            s_id, _, _, mod_id, s_type, reason, start, end, active, _ = s
            mod = self.bot.get_user(mod_id) or (await self.bot.fetch_user(mod_id))
            status = "🔴 Actif" if active else "🟢 Terminé"
            end_str = f" se termine <t:{int(datetime.datetime.fromisoformat(end).timestamp())}:R>" if end and active else ""
            embed.add_field(name=f"ID: {s_id} | {s_type.capitalize()} par {mod.name} ({status})", value=f"**Raison:** {reason}\n*Donné <t:{int(datetime.datetime.fromisoformat(start).timestamp())}:R>{end_str}*", inline=False)
        await ctx.respond(embed=embed, ephemeral=True)

    @sanctions_group.command(name="delete", description="Supprime une sanction de l'historique d'un membre.")
    @has_command_permission()
    async def delete_sanction(self, ctx: discord.ApplicationContext, id_sanction: discord.Option(int, "L'ID de la sanction à supprimer")):
        await db.delete_sanction_by_id(id_sanction)
        await ctx.respond(f"✅ Sanction avec l'ID `{id_sanction}` supprimée de la base de données.", ephemeral=True)

    # --- Commandes de Gestion de Rôles ---
    @role_group.command(name="add", description="Ajoute un rôle à un membre.")
    @has_command_permission()
    async def add_role(self, ctx: discord.ApplicationContext, membre: discord.Member, role: discord.Role):
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas gérer un rôle supérieur ou égal au vôtre.", ephemeral=True)
        await membre.add_roles(role, reason=f"Ajouté par {ctx.author}")
        await ctx.respond(f"✅ Rôle {role.mention} ajouté à {membre.mention}.", ephemeral=True)

    @role_group.command(name="remove", description="Retire un rôle à un membre.")
    @has_command_permission()
    async def remove_role(self, ctx: discord.ApplicationContext, membre: discord.Member, role: discord.Role):
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas gérer un rôle supérieur ou égal au vôtre.", ephemeral=True)
        await membre.remove_roles(role, reason=f"Retiré par {ctx.author}")
        await ctx.respond(f"✅ Rôle {role.mention} retiré de {membre.mention}.", ephemeral=True)
    
    @role_group.command(name="temprole", description="Donne un rôle pour une durée déterminée.")
    @has_command_permission()
    async def temprole(self, ctx: discord.ApplicationContext, membre: discord.Member, role: discord.Role, duree: str):
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas gérer un rôle supérieur ou égal au vôtre.", ephemeral=True)
        duration_seconds = parse_duration(duree)
        if duration_seconds <= 0: return await ctx.respond("❌ Durée invalide.", ephemeral=True)
        await db.add_sanction(ctx.guild.id, membre.id, ctx.author.id, 'temprole', f"Rôle {role.name}", duration_seconds, role.id)
        await membre.add_roles(role, reason=f"Temprole par {ctx.author}")
        await ctx.respond(f"✅ Rôle {role.mention} ajouté à {membre.mention} pour `{duree}`.", ephemeral=True)

    @role_group.command(name="massadd", description="[LENT] Ajoute un rôle à tous les membres.")
    @has_command_permission()
    async def mass_add_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas gérer un rôle supérieur ou égal au vôtre.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        count = 0
        for member in ctx.guild.members:
            if not member.bot and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Massrole par {ctx.author}")
                    count += 1
                    await asyncio.sleep(0.5)
                except discord.Forbidden: continue
        await ctx.followup.send(f"✅ Rôle {role.mention} ajouté à {count} membre(s).", ephemeral=True)

    @role_group.command(name="massremove", description="[LENT] Retire un rôle à tous les membres qui l'ont.")
    @has_command_permission()
    async def mass_remove_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond("❌ Vous ne pouvez pas gérer un rôle supérieur ou égal au vôtre.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        count = 0
        for member in list(role.members):
            if not member.bot:
                try:
                    await member.remove_roles(role, reason=f"Massrole par {ctx.author}")
                    count += 1
                    await asyncio.sleep(0.5)
                except discord.Forbidden: continue
        await ctx.followup.send(f"✅ Rôle {role.mention} retiré de {count} membre(s).", ephemeral=True)

    # --- Commandes de Gestion de Salons ---
    @channel_group.command(name="clear", description="Supprime un nombre de messages dans ce salon.")
    @has_command_permission()
    async def clear(self, ctx: discord.ApplicationContext, nombre: int, membre: discord.Member = None):
        if not (1 <= nombre <= 100):
            return await ctx.respond("Le nombre doit être entre 1 et 100.", ephemeral=True)
        check = (lambda m: m.author == membre) if membre else (lambda m: True)
        deleted = await ctx.channel.purge(limit=nombre, check=check)
        await ctx.respond(f"✅ {len(deleted)} messages ont été supprimés.", ephemeral=True, delete_after=5)

    @channel_group.command(name="lock", description="Verrouille le salon actuel pour @everyone.")
    @has_command_permission()
    async def lock(self, ctx: discord.ApplicationContext):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"Lock par {ctx.author}")
        await ctx.respond(f"🔒 Le salon {ctx.channel.mention} a été verrouillé.")

    @channel_group.command(name="unlock", description="Déverrouille le salon actuel.")
    @has_command_permission()
    async def unlock(self, ctx: discord.ApplicationContext):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None, reason=f"Unlock par {ctx.author}")
        await ctx.respond(f"🔓 Le salon {ctx.channel.mention} a été déverrouillé.")

    @channel_group.command(name="renew", description="[DANGEREUX] Recrée le salon à l'identique (purge totale).")
    @has_command_permission()
    async def renew(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        try:
            new_channel = await ctx.channel.clone(reason=f"Renew par {ctx.author}")
            await new_channel.edit(position=ctx.channel.position, reason=f"Renew par {ctx.author}")
            await ctx.channel.delete(reason=f"Renew par {ctx.author}")
            await new_channel.send(f"Salon recréé avec succès par {ctx.author.mention}.")
        except discord.Forbidden:
            await ctx.followup.send("❌ Je n'ai pas les permissions pour cloner ou supprimer ce salon.", ephemeral=True)
        except Exception as e:
            await ctx.followup.send(f"❌ Une erreur est survenue: {e}", ephemeral=True)
            
    # --- Commandes Vocales ---
    @voice_group.command(name="kick", description="Expulse un membre d'un salon vocal.")
    @has_command_permission()
    async def voice_kick(self, ctx: discord.ApplicationContext, membre: discord.Member):
        if not membre.voice or not membre.voice.channel:
            return await ctx.respond(f"{membre.mention} n'est dans aucun salon vocal.", ephemeral=True)
        channel_name = membre.voice.channel.name
        await membre.move_to(None, reason=f"Voice kick par {ctx.author}")
        await ctx.respond(f"{membre.mention} a été expulsé de **{channel_name}**.", ephemeral=True)
        
    @voice_group.command(name="moveall", description="Déplace tous les membres d'un salon vers un autre.")
    @has_command_permission()
    async def voicemove(self, ctx: discord.ApplicationContext, depart: discord.VoiceChannel, arrivee: discord.VoiceChannel):
        if not depart.members:
            return await ctx.respond(f"Le salon {depart.mention} est vide.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        count = 0
        for member in list(depart.members):
            try:
                await member.move_to(arrivee, reason=f"Moveall par {ctx.author}")
                count += 1
                await asyncio.sleep(0.5)
            except discord.Forbidden: continue
        await ctx.followup.send(f"✅ {count} membre(s) déplacé(s) de {depart.mention} vers {arrivee.mention}.")


def setup(bot):
    bot.add_cog(Moderation(bot))