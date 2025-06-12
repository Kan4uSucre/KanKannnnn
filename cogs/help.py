import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup

class Help(commands.Cog):
    """Affiche l'aide sur les commandes du bot."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="help", description="Affiche l'aide sur les commandes du bot.")
    async def help_command(self, ctx: discord.ApplicationContext, 
                           module: discord.Option(str, "Choisissez un module pour voir les détails", required=False, autocomplete=discord.utils.basic_autocomplete(c for c in ['Moderation', 'Utility', 'Permissions', 'Logs', 'Anti-Raid']))):
        
        # Si aucun module n'est spécifié, afficher la liste complète
        if not module:
            embed = discord.Embed(
                title=f"📜 Aide complète de {self.bot.user.name}",
                description="Voici la liste de toutes les commandes disponibles, groupées par module.\n"
                            "Utilisez `/help <module>` pour avoir les descriptions détaillées de chaque commande.",
                color=discord.Color.blurple()
            )
            
            # Modules à ne pas afficher dans l'aide publique
            hidden_cogs = ['Owner', 'Help']
            
            # Trier les cogs par ordre alphabétique pour un affichage cohérent
            sorted_cogs = sorted(self.bot.cogs.items())

            for cog_name, cog in sorted_cogs:
                if cog_name not in hidden_cogs:
                    commands_list = []
                    # Itérer à travers les commandes du cog
                    for cmd in cog.get_commands():
                        if isinstance(cmd, discord.SlashCommand):
                            commands_list.append(f"`/{cmd.name}`")
                        elif isinstance(cmd, SlashCommandGroup):
                             for sub_cmd in cmd.subcommands:
                                 commands_list.append(f"`/{cmd.name} {sub_cmd.name}`")
                    
                    if commands_list:
                        embed.add_field(
                            name=f"**{cog.description or cog_name}**",
                            value=" ".join(commands_list),
                            inline=False
                        )
            
            await ctx.respond(embed=embed)

        # Si un module est spécifié, afficher les détails de ce module
        else:
            cog = self.bot.get_cog(module.capitalize())
            if not cog:
                return await ctx.respond(f"❌ Le module `{module}` n'existe pas.", ephemeral=True)

            embed = discord.Embed(
                title=f"Aide pour le module : {cog.__class__.__name__}",
                description=cog.description or "",
                color=discord.Color.green()
            )
            
            commands_list_details = []
            for cmd in cog.get_commands():
                description = cmd.description or "Pas de description."
                if isinstance(cmd, discord.SlashCommand):
                    commands_list_details.append(f"**`/{cmd.name}`**\n*└ {description}*")
                elif isinstance(cmd, SlashCommandGroup):
                     for sub_cmd in cmd.subcommands:
                         sub_description = sub_cmd.description or "Pas de description."
                         commands_list_details.append(f"**`/{cmd.name} {sub_cmd.name}`**\n*└ {sub_description}*")
            
            if commands_list_details:
                embed.description = (embed.description or "") + "\n\n" + "\n".join(commands_list_details)
            else:
                embed.add_field(name="Commandes", value="Aucune commande disponible dans ce module.")
                
            await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Help(bot))