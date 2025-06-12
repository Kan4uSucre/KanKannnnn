import discord
from discord.ext import commands
import database_handler as db
import datetime

class Logs(commands.Cog):
    """Gère tous les journaux d'événements du serveur."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_log(self, guild_id: int, log_type: str, embed: discord.Embed):
        """Fonction centralisée pour envoyer un log."""
        channel_id = await db.get_guild_setting(guild_id, f"{log_type}_channel_id")
        if not channel_id: return
        
        channel = self.bot.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                print(f"Permissions manquantes pour envoyer des logs dans le salon {channel_id} du serveur {guild_id}")

    # --- Commande de configuration ---
    @commands.slash_command(name="logs", description="Configure les salons de logs.")
    async def logs(self, ctx: discord.ApplicationContext,
                   type_de_log: discord.Option(str, "Le type de log à configurer", choices=["modlog", "messagelog", "voicelog", "rolelog", "boostlog", "raidlog"]),
                   salon: discord.Option(discord.TextChannel, "Le salon où envoyer les logs (laisser vide pour désactiver)")):
        
        await db.set_guild_setting(ctx.guild.id, f"{type_de_log}_channel_id", salon.id if salon else None)
        if salon:
            await ctx.respond(f"✅ Les logs de type `{type_de_log}` seront maintenant envoyés dans {salon.mention}.", ephemeral=True)
        else:
            await ctx.respond(f"✅ Les logs de type `{type_de_log}` ont été désactivés.", ephemeral=True)

    # --- Listeners ---
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        embed = discord.Embed(
            description=f"**Message envoyé par {message.author.mention} supprimé dans {message.channel.mention}**\n{message.content}",
            color=discord.Color.orange(), timestamp=datetime.datetime.now(datetime.timezone.utc)
        ).set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        await self.send_log(message.guild.id, "messagelog", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content: return
        embed = discord.Embed(
            description=f"**Message de {before.author.mention} modifié dans {before.channel.mention}** [Aller au message]({after.jump_url})",
            color=discord.Color.blue(), timestamp=datetime.datetime.now(datetime.timezone.utc)
        ).set_author(name=before.author.display_name, icon_url=before.author.display_avatar.url)
        embed.add_field(name="Avant", value=f"```{before.content[:1020]}```", inline=False)
        embed.add_field(name="Après", value=f"```{after.content[:1020]}```", inline=False)
        await self.send_log(before.guild.id, "messagelog", embed)
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot: return
        action = None
        if not before.channel and after.channel:
            action = f"a rejoint le salon vocal **{after.channel.mention}**"
            color = discord.Color.green()
        elif before.channel and not after.channel:
            action = f"a quitté le salon vocal **{before.channel.mention}**"
            color = discord.Color.red()
        if not action: return
        embed = discord.Embed(description=f"{member.mention} {action}", color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        await self.send_log(member.guild.id, "voicelog", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Log des rôles
        if before.roles != after.roles:
            added_roles = [r for r in after.roles if r not in before.roles]
            removed_roles = [r for r in before.roles if r not in after.roles]
            if added_roles:
                embed = discord.Embed(description=f"**Rôle ajouté à {after.mention} :** {added_roles[0].mention}", color=discord.Color.green(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                await self.send_log(after.guild.id, "rolelog", embed)
            if removed_roles:
                embed = discord.Embed(description=f"**Rôle retiré à {after.mention} :** {removed_roles[0].mention}", color=discord.Color.orange(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                await self.send_log(after.guild.id, "rolelog", embed)
        # Log des boosts
        if not before.premium_since and after.premium_since:
            embed = discord.Embed(description=f"🚀 {after.mention} **vient de booster le serveur ! Merci !**", color=0xf47fff, timestamp=datetime.datetime.now(datetime.timezone.utc))
            await self.send_log(after.guild.id, "boostlog", embed)

    # --- Fonction appelée par le module de modération ---
    async def log_moderation_action(self, embed: discord.Embed, guild_id: int):
        await self.send_log(guild_id, "modlog", embed)

def setup(bot):
    bot.add_cog(Logs(bot))