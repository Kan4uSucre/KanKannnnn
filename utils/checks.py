# utils/checks.py
import discord
from discord.ext import commands
import database_handler as db

# --- LISTE DES COMMANDES PUBLIQUES ---
# Ces commandes seront toujours autorisées pour tout le monde.
PUBLIC_COMMANDS = [
    'help', 
    'pic', 
    'banner', 
    'snipe', 
    'serverinfo', 
    'userinfo',
    'channelinfo'
]

def has_command_permission():
    """
    Check intelligent qui applique une logique "tout est interdit par défaut".
    1. Autorise les commandes publiques pour tous.
    2. Autorise les admins à tout faire.
    3. Pour le reste, vérifie la permission dans la base de données.
    """
    async def predicate(ctx: discord.ApplicationContext):
        command_name = ctx.command.name

        # Règle 1: La commande est-elle publique ?
        if command_name in PUBLIC_COMMANDS:
            return True

        # On s'assure qu'on est bien sur un serveur et que l'auteur est un membre
        if not isinstance(ctx.author, discord.Member):
            return False
        
        author = ctx.author

        # Règle 2: L'auteur est-il un administrateur du serveur ?
        if author.id == ctx.guild.owner_id or author.guild_permissions.administrator:
            return True
        
        # Règle 3: L'auteur a-t-il un rôle avec la permission explicite ?
        for role in reversed(author.roles):
            # On vérifie si un des rôles a la permission "admin" (passe-partout)
            # ou la permission pour la commande spécifique.
            perms = await db.get_permissions_for_role(ctx.guild.id, role.id)
            if "admin" in perms or command_name in perms:
                return True
        
        # Si aucune des règles ci-dessus n'est remplie, on refuse.
        await ctx.respond(f"❌ Vous n'avez pas la permission d'utiliser la commande `/{command_name}`.", ephemeral=True)
        return False
        
    return commands.check(predicate)

def is_bot_owner():
    """Check pour vérifier si l'auteur est un propriétaire du bot."""
    async def predicate(ctx: discord.ApplicationContext):
        app_info = await ctx.bot.application_info()
        if ctx.author.id == app_info.owner.id:
            return True
        db_owners = await db.get_bot_owners()
        if ctx.author.id in db_owners:
            return True
        await ctx.respond("❌ Seuls les propriétaires du bot peuvent utiliser cette commande.", ephemeral=True)
        return False
    return commands.check(predicate)