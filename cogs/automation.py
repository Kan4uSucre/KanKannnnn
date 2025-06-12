import discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup
import database_handler as db
from utils.checks import has_command_permission
import asyncio

class Automation(commands.Cog):
    """Commandes d'automatisation et de gestion du serveur."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_support_roles.start()

    def cog_unload(self):
        self.check_support_roles.cancel()

    # --- Groupes de commandes ---
    welcome_group = SlashCommandGroup("welcome", "Configure les messages de bienvenue.")
    goodbye_group = SlashCommandGroup("goodbye", "Configure les messages de départ.")
    rolemenu_group = SlashCommandGroup("rolemenu", "Gère les menus de rôles par réaction.")
    autoreact_group = SlashCommandGroup("autoreact", "Gère les réactions automatiques.")
    
    # --- Messages de Bienvenue/Départ ---
    @welcome_group.command(name="set", description="Définit le salon et le message de bienvenue.")
    @has_command_permission()
    async def welcome_set(self, ctx: discord.ApplicationContext,
                          salon: discord.Option(discord.TextChannel, "Le salon où envoyer les messages"),
                          message: discord.Option(str, "Message. Utilisez {member.mention} et {server.name}", required=False)):
        await db.set_guild_setting(ctx.guild.id, 'welcome_channel_id', salon.id)
        if message:
            await db.set_guild_setting(ctx.guild.id, 'welcome_message', message)
        await ctx.respond(f"✅ Salon de bienvenue configuré sur {salon.mention}.", ephemeral=True)

    @goodbye_group.command(name="set", description="Définit le salon et le message de départ.")
    @has_command_permission()
    async def goodbye_set(self, ctx: discord.ApplicationContext,
                           salon: discord.Option(discord.TextChannel, "Le salon où envoyer les messages"),
                           message: discord.Option(str, "Message. Utilisez {member.name} et {server.name}", required=False)):
        await db.set_guild_setting(ctx.guild.id, 'leave_channel_id', salon.id)
        if message:
            await db.set_guild_setting(ctx.guild.id, 'leave_message', message)
        await ctx.respond(f"✅ Salon de départ configuré sur {salon.mention}.", ephemeral=True)

    @commands.slash_command(name="autorole", description="Définit un rôle à donner automatiquement aux nouveaux membres.")
    @has_command_permission()
    async def autorole(self, ctx: discord.ApplicationContext, role: discord.Option(discord.Role, "Le rôle à donner (laisser vide pour désactiver)", required=False)):
        role_id = role.id if role else None
        await db.set_guild_setting(ctx.guild.id, 'autorole_id', role_id)
        if role:
            await ctx.respond(f"✅ Le rôle automatique est maintenant {role.mention}.", ephemeral=True)
        else:
            await ctx.respond(f"✅ L'autorole a été désactivé.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        # Autorole
        role_id = await db.get_guild_setting(member.guild.id, 'autorole_id')
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try: await member.add_roles(role, reason="Autorole")
                except discord.Forbidden: print(f"Permissions manquantes pour l'autorole sur le serveur {member.guild.name}")
        
        # Message de bienvenue
        channel_id = await db.get_guild_setting(member.guild.id, 'welcome_channel_id')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                welcome_msg_template = await db.get_guild_setting(member.guild.id, 'welcome_message') or "Bienvenue {member.mention} sur **{server.name}** !"
                message = welcome_msg_template.format(member=member, server=member.guild)
                try: await channel.send(message)
                except discord.Forbidden: print(f"Permissions manquantes pour le message de bienvenue sur {member.guild.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot: return
        channel_id = await db.get_guild_setting(member.guild.id, 'leave_channel_id')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                leave_msg_template = await db.get_guild_setting(member.guild.id, 'leave_message') or "**{member.name}** nous a quitté."
                message = leave_msg_template.format(member=member, server=member.guild)
                try: await channel.send(message)
                except discord.Forbidden: print(f"Permissions manquantes pour le message de départ sur {member.guild.name}")

    # --- Rôle de Soutien ---
    @commands.slash_command(name="soutien", description="Configure le rôle de soutien automatique.")
    @has_command_permission()
    async def soutien(self, ctx: discord.ApplicationContext,
                      role: discord.Option(discord.Role, "Le rôle à donner aux soutiens"),
                      message: discord.Option(str, "Le message à rechercher dans le statut")):
        await db.set_guild_setting(ctx.guild.id, 'support_role_id', role.id)
        await db.set_guild_setting(ctx.guild.id, 'support_message', message)
        await ctx.respond(f"✅ Le rôle de soutien {role.mention} sera donné à ceux qui ont `{message}` dans leur statut.", ephemeral=True)
        
    @tasks.loop(minutes=5)
    async def check_support_roles(self):
        for guild in self.bot.guilds:
            role_id = await db.get_guild_setting(guild.id, 'support_role_id')
            support_message = await db.get_guild_setting(guild.id, 'support_message')
            if not role_id or not support_message: continue
            
            support_role = guild.get_role(role_id)
            if not support_role: continue

            for member in guild.members:
                try:
                    has_support_activity = any(isinstance(activity, discord.CustomActivity) and support_message in activity.name for activity in member.activities)
                    if has_support_activity:
                        if support_role not in member.roles: await member.add_roles(support_role, reason="Soutien")
                    else:
                        if support_role in member.roles: await member.remove_roles(support_role, reason="Soutien retiré")
                except discord.Forbidden: continue
    
    @check_support_roles.before_loop
    async def before_support_check(self):
        await self.bot.wait_until_ready()

    # --- Rôles par Réaction ---
    @rolemenu_group.command(name="create", description="Crée un nouveau menu de rôles par réaction.")
    @has_command_permission()
    async def rolemenu_create(self, ctx: discord.ApplicationContext,
                              channel: discord.Option(discord.TextChannel, "Le salon où poster le menu"),
                              message: discord.Option(str, "Le message du menu (ex: 'Cliquez pour obtenir vos rôles')")):
        embed = discord.Embed(title="Menu de Rôles", description=message, color=discord.Color.blue())
        sent_message = await channel.send(embed=embed)
        await ctx.respond(f"✅ Menu créé avec l'ID `{sent_message.id}`. Utilisez `/rolemenu add` pour y ajouter des rôles.", ephemeral=True)

    @rolemenu_group.command(name="add", description="Ajoute une option rôle/réaction à un menu existant.")
    @has_command_permission()
    async def rolemenu_add(self, ctx: discord.ApplicationContext,
                           message_id: discord.Option(str, "L'ID du message du menu"),
                           emoji: discord.Option(str, "L'émoji pour la réaction"),
                           role: discord.Option(discord.Role, "Le rôle à donner")):
        try:
            msg = await ctx.channel.fetch_message(int(message_id))
        except (discord.NotFound, ValueError):
            return await ctx.respond("❌ ID de message invalide ou message non trouvé dans ce salon.", ephemeral=True)
        
        success = await db.add_reaction_role(ctx.guild.id, msg.id, emoji, role.id)
        if not success:
            return await ctx.respond("ℹ️ Cet émoji est déjà utilisé pour un autre rôle sur ce message.", ephemeral=True)
            
        await msg.add_reaction(emoji)
        await ctx.respond(f"✅ L'option {emoji} donnant le rôle {role.mention} a été ajoutée au menu.", ephemeral=True)

    # --- Auto-Réaction ---
    @autoreact_group.command(name="add", description="Ajoute une réaction automatique à un salon.")
    @has_command_permission()
    async def autoreact_add(self, ctx: discord.ApplicationContext, salon: discord.TextChannel, emoji: str):
        await db.add_autoreact(ctx.guild.id, salon.id, emoji)
        await ctx.respond(f"✅ L'émoji {emoji} sera maintenant ajouté à tous les messages dans {salon.mention}.", ephemeral=True)

    @autoreact_group.command(name="remove", description="Retire une réaction automatique d'un salon.")
    @has_command_permission()
    async def autoreact_remove(self, ctx: discord.ApplicationContext, salon: discord.TextChannel, emoji: str):
        await db.remove_autoreact(ctx.guild.id, salon.id, emoji)
        await ctx.respond(f"✅ L'émoji {emoji} ne sera plus ajouté automatiquement dans {salon.mention}.", ephemeral=True)

    # --- Listeners (pour les systèmes ci-dessus) ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        
        reactions = await db.get_autoreact_for_channel(message.channel.id)
        for r in reactions:
            try: await message.add_reaction(r)
            except: continue

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id or payload.member.bot: return
        
        role_id = await db.get_reaction_role(payload.message_id, str(payload.emoji))
        if role_id:
            role = payload.member.guild.get_role(role_id)
            if role: await payload.member.add_roles(role, reason="Rôle par réaction")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return
        member = guild.get_member(payload.user_id)
        if not member or member.bot: return
        
        role_id = await db.get_reaction_role(payload.message_id, str(payload.emoji))
        if role_id:
            role = guild.get_role(role_id)
            if role: await member.remove_roles(role, reason="Rôle par réaction")

def setup(bot):
    bot.add_cog(Automation(bot))