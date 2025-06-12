import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
import datetime
import io
from utils.checks import has_command_permission # On importe notre check

# --- Vue pour la pagination (pour les longues listes) ---
class PaginatorView(discord.ui.View):
    def __init__(self, pages, ctx):
        super().__init__(timeout=120)
        self.pages = pages
        self.current_page = 0
        self.ctx = ctx

    async def update_message(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Tu ne peux pas utiliser ces boutons.", ephemeral=True)
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
        embed = self.pages[self.current_page]
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.primary, disabled=True)
    async def previous_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary)
    async def next_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_page += 1
        await self.update_message(interaction)

# --- Modal pour créer un Embed ---
class EmbedCreateModal(discord.ui.Modal):
    def __init__(self, target_channel):
        super().__init__(title="Créateur d'Embed")
        self.target_channel = target_channel
        self.add_item(discord.ui.InputText(label="Titre de l'embed", required=False))
        self.add_item(discord.ui.InputText(label="Description", style=discord.InputTextStyle.long, required=True))
        self.add_item(discord.ui.InputText(label="Couleur (code hexadécimal)", placeholder="Ex: #3498db ou 3498db", required=False))
        self.add_item(discord.ui.InputText(label="URL de l'image principale", required=False))
        self.add_item(discord.ui.InputText(label="Texte du pied de page (footer)", required=False))

    async def callback(self, interaction: discord.Interaction):
        title = self.children[0].value
        description = self.children[1].value
        color_str = self.children[2].value
        image_url = self.children[3].value
        footer_text = self.children[4].value
        color = discord.Color.default()
        if color_str:
            try:
                color = discord.Color(int(color_str.replace("#", ""), 16))
            except ValueError:
                return await interaction.response.send_message("❌ Couleur hexadécimale invalide.", ephemeral=True)
        embed = discord.Embed(title=title, description=description, color=color)
        if image_url: embed.set_image(url=image_url)
        if footer_text: embed.set_footer(text=footer_text)
        try:
            await self.target_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Embed envoyé dans {self.target_channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Je n'ai pas la permission d'envoyer de messages dans ce salon.", ephemeral=True)

class Utility(commands.Cog):
    """Commandes utilitaires pour obtenir des informations et plus."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sniped_messages = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.author.bot and message.content:
            self.sniped_messages[message.channel.id] = {'content': message.content, 'author': message.author, 'timestamp': datetime.datetime.now(datetime.timezone.utc)}

    # --- Groupes de commandes ---
    server_group = SlashCommandGroup("server", "Affiche des informations sur le serveur.")
    list_group = SlashCommandGroup("list", "Affiche différentes listes de membres.")

    # --- Commandes d'information (publiques, pas de check) ---
    @server_group.command(name="info", description="Affiche les informations relatives au serveur.")
    async def serverinfo(self, ctx: discord.ApplicationContext):
        guild = ctx.guild
        embed = discord.Embed(title=f"Informations sur {guild.name}", color=discord.Color.blue())
        if guild.icon: embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="👑 Propriétaire", value=guild.owner.mention, inline=True)
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="📅 Créé le", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="👥 Membres", value=f"{guild.member_count}", inline=True)
        embed.add_field(name="💬 Salons", value=f"{len(guild.text_channels)} textuels | {len(guild.voice_channels)} vocaux", inline=True)
        embed.add_field(name="🎨 Rôles", value=f"{len(guild.roles)}", inline=True)
        if guild.premium_tier > 0:
            embed.add_field(name="🚀 Boosts", value=f"Niveau {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        await ctx.respond(embed=embed)
    
    @server_group.command(name="icon", description="Affiche l'icône du serveur.")
    async def server_icon(self, ctx: discord.ApplicationContext):
        if not ctx.guild.icon: return await ctx.respond("ℹ️ Ce serveur n'a pas d'icône.", ephemeral=True)
        embed = discord.Embed(title=f"Icône de {ctx.guild.name}", color=discord.Color.blue()).set_image(url=ctx.guild.icon.url)
        await ctx.respond(embed=embed)

    @server_group.command(name="banner", description="Affiche la bannière du serveur.")
    async def server_banner(self, ctx: discord.ApplicationContext):
        if not ctx.guild.banner: return await ctx.respond("ℹ️ Ce serveur n'a pas de bannière.", ephemeral=True)
        embed = discord.Embed(title=f"Bannière de {ctx.guild.name}", color=discord.Color.blue()).set_image(url=ctx.guild.banner.url)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="userinfo", description="Affiche les informations sur un utilisateur ou vous-même.")
    async def userinfo(self, ctx: discord.ApplicationContext, membre: discord.Option(discord.Member, "Le membre à inspecter", required=False)):
        target = membre or ctx.author
        embed = discord.Embed(title=f"Informations sur {target.display_name}", color=target.color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="👤 Nom & ID", value=f"`{target}`\n`{target.id}`", inline=True)
        embed.add_field(name="Rôle le plus haut", value=target.top_role.mention, inline=True)
        embed.add_field(name="📅 Compte créé", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=False)
        embed.add_field(name="👋 A rejoint le", value=f"<t:{int(target.joined_at.timestamp())}:R>", inline=False)
        roles = [role.mention for role in target.roles if role.name != "@everyone"]
        roles.reverse()
        role_str = ", ".join(roles) if roles else "Aucun rôle"
        if len(role_str) > 1024: role_str = role_str[:1020] + "..."
        embed.add_field(name=f"🎨 Rôles ({len(roles)})", value=role_str, inline=False)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="roleinfo", description="Affiche les informations sur un rôle.")
    async def roleinfo(self, ctx: discord.ApplicationContext, role: discord.Option(discord.Role, "Le rôle à inspecter")):
        embed = discord.Embed(title=f"Informations sur @{role.name}", color=role.color)
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Couleur", value=f"`{role.color}`", inline=True)
        embed.add_field(name="Membres", value=f"{len(role.members)}", inline=True)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="channelinfo", description="Affiche les informations sur un salon.")
    async def channelinfo(self, ctx: discord.ApplicationContext, salon: discord.Option(discord.TextChannel, "Le salon à inspecter", required=False)):
        target = salon or ctx.channel
        embed = discord.Embed(title=f"Informations sur #{target.name}", color=discord.Color.dark_green())
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Type", value=str(target.type).capitalize(), inline=True)
        embed.add_field(name="Position", value=target.position, inline=True)
        embed.add_field(name="Créé le", value=f"<t:{int(target.created_at.timestamp())}:D>", inline=False)
        await ctx.respond(embed=embed)

    # --- Commandes de listes (protégées pour éviter le spam d'API) ---
    @list_group.command(name="rolemembers", description="Affiche les membres ayant un rôle précis.")
    @has_command_permission()
    async def rolemembers(self, ctx: discord.ApplicationContext, role: discord.Option(discord.Role, "Rôle")):
        await self._send_paginated_list(ctx, role.members, f"Membres avec le rôle @{role.name}", role.color)

    @list_group.command(name="bots", description="Affiche la liste des bots présents sur le serveur.")
    @has_command_permission()
    async def allbots(self, ctx: discord.ApplicationContext):
        bots = [m for m in ctx.guild.members if m.bot]
        await self._send_paginated_list(ctx, bots, "Bots sur le serveur")

    @list_group.command(name="admins", description="Affiche la liste des administrateurs (humains).")
    @has_command_permission()
    async def alladmins(self, ctx: discord.ApplicationContext):
        admins = [m for m in ctx.guild.members if not m.bot and m.guild_permissions.administrator]
        await self._send_paginated_list(ctx, admins, "Administrateurs sur le serveur", discord.Color.red())

    @list_group.command(name="boosters", description="Affiche la liste des membres qui boostent le serveur.")
    @has_command_permission()
    async def boosters(self, ctx: discord.ApplicationContext):
        await self._send_paginated_list(ctx, ctx.guild.premium_subscribers, "Boosters du serveur", discord.Color.fuchsia())

    # --- Outils (certains publics, d'autres protégés) ---
    @commands.slash_command(name="pic", description="Affiche la photo de profil d'un membre.")
    async def pic(self, ctx: discord.ApplicationContext, membre: discord.Option(discord.Member, "Le membre", required=False)):
        target = membre or ctx.author
        embed = discord.Embed(title=f"Photo de profil de {target.display_name}", color=target.color).set_image(url=target.display_avatar.url)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="banner", description="Affiche la bannière d'un membre.")
    async def banner(self, ctx: discord.ApplicationContext, membre: discord.Option(discord.Member, "Le membre", required=False)):
        target = membre or ctx.author
        user = await self.bot.fetch_user(target.id)
        if not user.banner: return await ctx.respond(f"ℹ️ {user.name} n'a pas de bannière.", ephemeral=True)
        embed = discord.Embed(title=f"Bannière de {user.name}", color=user.accent_color or discord.Color.blue()).set_image(url=user.banner.url)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="snipe", description="Affiche le dernier message supprimé du salon.")
    async def snipe(self, ctx: discord.ApplicationContext):
        if ctx.channel.id in self.sniped_messages:
            sniped = self.sniped_messages[ctx.channel.id]
            if (datetime.datetime.now(datetime.timezone.utc) - sniped['timestamp']).total_seconds() > 60:
                 return await ctx.respond("ℹ️ Pas de message récent à sniper.", ephemeral=True)
            embed = discord.Embed(description=sniped['content'], color=sniped['author'].color, timestamp=sniped['timestamp'])
            embed.set_author(name=str(sniped['author']), icon_url=sniped['author'].display_avatar.url)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("ℹ️ Aucun message à sniper dans ce salon.", ephemeral=True)

    @commands.slash_command(name="embed", description="Affiche un menu pour créer et envoyer un embed.")
    @has_command_permission()
    async def create_embed(self, ctx: discord.ApplicationContext, salon: discord.Option(discord.TextChannel, "Le salon où envoyer l'embed")):
        modal = EmbedCreateModal(salon)
        await ctx.send_modal(modal)

    @commands.slash_command(name="createemoji", description="Crée un émoji sur le serveur à partir d'une image.")
    @has_command_permission()
    async def createemoji(self, ctx: discord.ApplicationContext, nom: discord.Option(str, "Nom de l'émoji"), image: discord.Option(discord.Attachment, "Le fichier image de l'émoji")):
        if not image.content_type.startswith('image/'):
            return await ctx.respond("❌ Le fichier doit être une image (PNG, JPG, GIF).", ephemeral=True)
        try:
            emoji_bytes = await image.read()
            new_emoji = await ctx.guild.create_custom_emoji(name=nom, image=emoji_bytes, reason=f"Créé par {ctx.author}")
            await ctx.respond(f"✅ L'émoji {new_emoji} a été créé avec succès !")
        except Exception as e:
            await ctx.respond(f"❌ Une erreur est survenue. L'image est peut-être trop grande (max 256kb) ou je n'ai pas la permission. Erreur: {e}", ephemeral=True)

    # --- Fonction helper interne ---
    async def _send_paginated_list(self, ctx, member_list, title, color=discord.Color.default()):
        if not member_list:
            return await ctx.respond(f"ℹ️ La liste pour '{title}' est vide.", ephemeral=True)
        
        pages = []
        chunk_size = 10 
        chunks = [member_list[i:i + chunk_size] for i in range(0, len(member_list), chunk_size)]
        
        for chunk in chunks:
            embed = discord.Embed(title=f"{title} ({len(member_list)})", color=color)
            description = "\n".join(f"{member.mention} (`{member.id}`)" for member in chunk)
            embed.description = description
            pages.append(embed)
            
        view = PaginatorView(pages, ctx)
        first_embed = pages[0]
        first_embed.set_footer(text=f"Page 1/{len(pages)}")
        await ctx.respond(embed=first_embed, view=view)

def setup(bot):
    bot.add_cog(Utility(bot))