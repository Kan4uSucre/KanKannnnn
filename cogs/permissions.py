# cogs/permissions.py
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
import database_handler as db
from utils.checks import has_command_permission

class Permissions(commands.Cog):
    """Commandes pour gérer le système de permissions du bot."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    perms_group = SlashCommandGroup("permissions", "Gère les permissions des rôles sur les commandes du bot.")

    @perms_group.command(name="grant", description="Donne l'accès à une commande pour un rôle.")
    @commands.has_permissions(administrator=True)
    async def grant(self, ctx: discord.ApplicationContext,
                    role: discord.Option(discord.Role, "Rôle à qui donner la permission"),
                    command: discord.Option(str, "La commande à autoriser")):
        
        success = await db.grant_permission(ctx.guild.id, role.id, command.lower())
        if success:
            await ctx.respond(f"✅ Le rôle {role.mention} peut maintenant utiliser la commande `/{command.lower()}`.", ephemeral=True)
        else:
            await ctx.respond(f"ℹ️ Le rôle {role.mention} a déjà la permission pour cette commande.", ephemeral=True)

    @perms_group.command(name="revoke", description="Retire l'accès à une commande pour un rôle.")
    @commands.has_permissions(administrator=True)
    async def revoke(self, ctx: discord.ApplicationContext,
                    role: discord.Option(discord.Role, "Rôle à qui retirer la permission"),
                    command: discord.Option(str, "La commande à interdire")):

        await db.revoke_permission(ctx.guild.id, role.id, command.lower())
        await ctx.respond(f"✅ Le rôle {role.mention} ne peut plus utiliser la commande `/{command.lower()}`.", ephemeral=True)

    @perms_group.command(name="set_limit", description="Définit une limite pour une commande et un rôle (ex: durée max).")
    @commands.has_permissions(administrator=True)
    async def set_limit(self, ctx: discord.ApplicationContext,
                        role: discord.Option(discord.Role, "Rôle concerné"),
                        command: discord.Option(str, "Commande à limiter (ex: timeout)"),
                        limit_type: discord.Option(str, "Type de limite", choices=["max_duration", "max_amount"]),
                        value: discord.Option(int, "Valeur de la limite (ex: 500 pour 500 secondes)")):
        
        result = await db.set_permission_constraint(ctx.guild.id, role.id, command.lower(), limit_type, value)
        if result is None:
            return await ctx.respond(f"❌ Erreur : Le rôle {role.mention} n'a pas la permission de base pour la commande `/{command.lower()}`. Utilisez d'abord `/permissions grant`.", ephemeral=True)
        
        await ctx.respond(f"✅ Pour le rôle {role.mention}, la limite `{limit_type}` sur la commande `/{command.lower()}` a été fixée à **{value}**.", ephemeral=True)
        
    @perms_group.command(name="view", description="Affiche les permissions d'un rôle.")
    @commands.has_permissions(administrator=True)
    async def view(self, ctx: discord.ApplicationContext, role: discord.Option(discord.Role, "Rôle à inspecter")):
        permissions = await db.get_permissions_for_role(ctx.guild.id, role.id)
        if not permissions:
            return await ctx.respond(f"Le rôle {role.mention} n'a aucune permission de bot personnalisée.", ephemeral=True)
        
        description = "Ce rôle a accès aux commandes suivantes :\n"
        for command in permissions:
            description += f"- `/{command}`\n"
        
        embed = discord.Embed(title=f"Permissions pour {role.name}", description=description, color=role.color)
        await ctx.respond(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(Permissions(bot))