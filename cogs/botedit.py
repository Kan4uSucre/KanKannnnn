import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils.checks import is_bot_owner # On importe notre check de permission personnalisé
import aiohttp # Pour télécharger les images depuis une URL

class BotEdit(commands.Cog):
    """Commandes pour que le propriétaire modifie l'apparence du bot."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # On crée un groupe pour garder les commandes organisées
    profile_group = SlashCommandGroup("botprofile", "Modifie le profil de ton bot.")

    @profile_group.command(name="set_name", description="Change le nom d'utilisateur du bot.")
    @is_bot_owner()
    async def set_name(self, ctx: discord.ApplicationContext, nom: discord.Option(str, "Le nouveau nom du bot")):
        try:
            await self.bot.user.edit(username=nom)
            await ctx.respond(f"✅ Mon nom a été changé en `{nom}`.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.respond(f"❌ Erreur: Impossible de changer le nom trop rapidement. Réessaie plus tard. ({e})", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"❌ Une erreur inattendue est survenue: {e}", ephemeral=True)

    @profile_group.command(name="set_avatar", description="Change la photo de profil du bot via une URL.")
    @is_bot_owner()
    async def set_avatar(self, ctx: discord.ApplicationContext, url: discord.Option(str, "L'URL de l'image (PNG, JPG, GIF)")):
        await ctx.defer(ephemeral=True)
        
        # On utilise aiohttp pour télécharger l'image de manière asynchrone
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return await ctx.followup.send("Impossible de télécharger l'image depuis cette URL.", ephemeral=True)
                    
                    image_bytes = await resp.read()
                    
                    await self.bot.user.edit(avatar=image_bytes)
                    await ctx.followup.send("✅ Mon avatar a été mis à jour.", ephemeral=True)

            except Exception as e:
                await ctx.followup.send(f"❌ Une erreur est survenue. L'URL est-elle valide ? L'image est-elle trop grande ?\n`{e}`", ephemeral=True)

    @profile_group.command(name="set_activity", description="Change l'activité du bot (ce à quoi il 'Joue').")
    @is_bot_owner()
    async def set_activity(self, ctx: discord.ApplicationContext, 
                           type: discord.Option(str, "Type d'activité", choices=["Joue à", "Écoute", "Regarde", "Participe à"]),
                           message: discord.Option(str, "Le message à afficher")):
        
        activity_type_map = {
            "Joue à": discord.ActivityType.playing,
            "Écoute": discord.ActivityType.listening,
            "Regarde": discord.ActivityType.watching,
            "Participe à": discord.ActivityType.competing
        }

        # On récupère le statut actuel pour ne pas l'écraser
        current_status = ctx.guild.get_member(self.bot.user.id).status
        
        activity = discord.Activity(type=activity_type_map[type], name=message)
        await self.bot.change_presence(status=current_status, activity=activity)
        await ctx.respond("✅ Mon activité a été mise à jour.", ephemeral=True)

    @profile_group.command(name="set_status", description="Change le statut du bot (En ligne, Inactif, etc.).")
    @is_bot_owner()
    async def set_status(self, ctx: discord.ApplicationContext, 
                         statut: discord.Option(str, "Statut", choices=["En ligne", "Inactif", "Ne pas déranger", "Invisible"])):
        
        status_map = {
            "En ligne": discord.Status.online,
            "Inactif": discord.Status.idle,
            "Ne pas déranger": discord.Status.dnd,
            "Invisible": discord.Status.invisible
        }
        
        # On récupère l'activité actuelle pour ne pas l'écraser
        current_activity = ctx.guild.get_member(self.bot.user.id).activity

        await self.bot.change_presence(status=status_map[statut], activity=current_activity)
        await ctx.respond("✅ Mon statut a été mis à jour.", ephemeral=True)


# --- Fonction indispensable pour charger le Cog ---
def setup(bot):
    bot.add_cog(BotEdit(bot))