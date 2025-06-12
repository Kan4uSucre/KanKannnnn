import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
import database_handler as db
from utils.checks import is_bot_owner
import os
import sys
import aiohttp

class Owner(commands.Cog):
    """Commandes réservées aux propriétaires du bot."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Groupes de Commandes (avec le nom corrigé) ---
    config_bot_group = SlashCommandGroup("bot", "Gère l'apparence et la présence du bot.")
    owner_group = SlashCommandGroup("owner", "Gère les propriétaires du bot.")
    blacklist_group = SlashCommandGroup("blacklist", "Gère la blacklist globale du bot.")

    # --- Commandes de Gestion du Profil du Bot ---
    @config_bot_group.command(name="set_name", description="Change le nom d'utilisateur du bot.")
    @is_bot_owner()
    async def set_name(self, ctx: discord.ApplicationContext, nom: discord.Option(str, "Le nouveau nom")):
        try:
            await self.bot.user.edit(username=nom)
            await ctx.respond(f"✅ Mon nom a été changé en `{nom}`.", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"❌ Une erreur est survenue: {e}", ephemeral=True)

    @config_bot_group.command(name="set_avatar", description="Change la photo de profil du bot via une URL.")
    @is_bot_owner()
    async def set_avatar(self, ctx: discord.ApplicationContext, url: discord.Option(str, "L'URL de l'image")):
        await ctx.defer(ephemeral=True)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return await ctx.followup.send("Impossible de télécharger l'image depuis cette URL.", ephemeral=True)
                    image_bytes = await resp.read()
                    await self.bot.user.edit(avatar=image_bytes)
                    await ctx.followup.send("✅ Mon avatar a été mis à jour.", ephemeral=True)
            except Exception as e:
                await ctx.followup.send(f"❌ Une erreur est survenue: {e}", ephemeral=True)

    @config_bot_group.command(name="set_activity", description="Change l'activité du bot.")
    @is_bot_owner()
    async def set_activity(self, ctx: discord.ApplicationContext, 
                           type: discord.Option(str, "Type d'activité", choices=["Joue à", "Écoute", "Regarde"]),
                           message: discord.Option(str, "Le message à afficher")):
        activity_type_map = {
            "Joue à": discord.ActivityType.playing,
            "Écoute": discord.ActivityType.listening,
            "Regarde": discord.ActivityType.watching
        }
        activity = discord.Activity(type=activity_type_map[type], name=message)
        await self.bot.change_presence(activity=activity)
        await ctx.respond("✅ Mon activité a été mise à jour.", ephemeral=True)

    @config_bot_group.command(name="set_status", description="Change le statut du bot.")
    @is_bot_owner()
    async def set_status(self, ctx: discord.ApplicationContext, 
                         statut: discord.Option(str, "Statut", choices=["En ligne", "Inactif", "Ne pas déranger", "Invisible"])):
        status_map = {
            "En ligne": discord.Status.online,
            "Inactif": discord.Status.idle,
            "Ne pas déranger": discord.Status.dnd,
            "Invisible": discord.Status.invisible
        }
        await self.bot.change_presence(status=status_map[statut])
        await ctx.respond("✅ Mon statut a été mis à jour.", ephemeral=True)

    # --- Commandes de Gestion Globale ---
    @commands.slash_command(name="say", description="Fait parler le bot dans un salon spécifique.")
    @is_bot_owner()
    async def say(self, ctx: discord.ApplicationContext, message: discord.Option(str, "Le message à envoyer"),
                  salon: discord.Option(discord.TextChannel, "Le salon où envoyer le message")):
        try:
            await salon.send(message)
            await ctx.respond(f"✅ Message envoyé dans {salon.mention}", ephemeral=True)
        except discord.Forbidden:
            await ctx.respond("❌ Je n'ai pas la permission d'envoyer de messages dans ce salon.", ephemeral=True)

    @config_bot_group.command(name="serverlist", description="Liste tous les serveurs où le bot se trouve.")
    @is_bot_owner()
    async def serverlist(self, ctx: discord.ApplicationContext):
        description = ""
        for guild in self.bot.guilds:
            description += f"- **{guild.name}** (ID: `{guild.id}`, Membres: {guild.member_count})\n"
        embed = discord.Embed(title=f"Serveurs ({len(self.bot.guilds)})", description=description, color=discord.Color.blurple())
        await ctx.respond(embed=embed, ephemeral=True)

    @config_bot_group.command(name="leave", description="Fait quitter un serveur au bot via son ID.")
    @is_bot_owner()
    async def leave(self, ctx: discord.ApplicationContext, guild_id: discord.Option(str, "L'ID du serveur à quitter")):
        try:
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return await ctx.respond("❌ Je ne suis pas sur ce serveur.", ephemeral=True)
            await guild.leave()
            await ctx.respond(f"✅ J'ai quitté le serveur **{guild.name}**.", ephemeral=True)
        except ValueError:
            await ctx.respond("❌ L'ID du serveur doit être un nombre.", ephemeral=True)

    # --- Commandes de gestion des propriétaires ---
    @owner_group.command(name="add", description="Ajoute un co-propriétaire au bot.")
    @is_bot_owner()
    async def add_owner(self, ctx: discord.ApplicationContext, membre: discord.Option(discord.Member, "Le membre à ajouter")):
        success = await db.add_bot_owner(membre.id)
        if success: await ctx.respond(f"✅ {membre.mention} est maintenant un co-propriétaire du bot.", ephemeral=True)
        else: await ctx.respond(f"ℹ️ {membre.mention} est déjà un co-propriétaire.", ephemeral=True)

    @owner_group.command(name="remove", description="Retire un co-propriétaire du bot.")
    @is_bot_owner()
    async def remove_owner(self, ctx: discord.ApplicationContext, membre: discord.Option(discord.Member, "Le membre à retirer")):
        await db.remove_bot_owner(membre.id)
        await ctx.respond(f"✅ {membre.mention} n'est plus un co-propriétaire.", ephemeral=True)
    
    @owner_group.command(name="list", description="Affiche la liste des propriétaires du bot.")
    @is_bot_owner()
    async def list_owners(self, ctx: discord.ApplicationContext):
        app_info = await self.bot.application_info()
        main_owner = app_info.owner
        db_owners_id = await db.get_bot_owners()
        description = f"**Propriétaire Principal :** {main_owner.mention}\n\n**Co-propriétaires :**\n"
        if not db_owners_id:
            description += "Aucun co-propriétaire ajouté."
        else:
            for user_id in db_owners_id:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                description += f"- {user.mention} (`{user.id}`)\n"
        embed = discord.Embed(title="Liste des Propriétaires du Bot", description=description, color=discord.Color.gold())
        await ctx.respond(embed=embed, ephemeral=True)

    # --- Commandes de gestion de la Blacklist ---
    @blacklist_group.command(name="add", description="Blackliste un utilisateur de l'usage du bot.")
    @is_bot_owner()
    async def blacklist_add(self, ctx: discord.ApplicationContext, user_id: discord.Option(str, "L'ID de l'utilisateur"), raison: discord.Option(str, "Raison")):
        try:
            user_id_int = int(user_id)
            success = await db.add_to_blacklist(user_id_int, raison)
            if success: await ctx.respond(f"✅ L'utilisateur `{user_id_int}` a été blacklisté.", ephemeral=True)
            else: await ctx.respond(f"ℹ️ L'utilisateur `{user_id_int}` est déjà blacklisté.", ephemeral=True)
        except ValueError:
            await ctx.respond("❌ ID d'utilisateur invalide.", ephemeral=True)

    @blacklist_group.command(name="remove", description="Retire un utilisateur de la blacklist.")
    @is_bot_owner()
    async def blacklist_remove(self, ctx: discord.ApplicationContext, user_id: discord.Option(str, "L'ID de l'utilisateur")):
        try:
            user_id_int = int(user_id)
            await db.remove_from_blacklist(user_id_int)
            await ctx.respond(f"✅ L'utilisateur `{user_id_int}` a été retiré de la blacklist.", ephemeral=True)
        except ValueError:
            await ctx.respond("❌ ID d'utilisateur invalide.", ephemeral=True)

def setup(bot):
    bot.add_cog(Owner(bot))