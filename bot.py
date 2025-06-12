import discord
import os
from dotenv import load_dotenv
import database_handler

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

async def global_blacklist_check(ctx: discord.ApplicationContext):
    is_user_blacklisted = await database_handler.is_blacklisted(ctx.author.id)
    return not is_user_blacklisted

intents = discord.Intents.all()

# --- MODIFICATION ICI ---
# Ajout de l'ID de ton serveur pour des mises à jour de commandes instantanées
bot = discord.Bot(intents=intents, debug_guilds=[1224814536750665888])

@bot.event
async def on_ready():
    """Cet événement se déclenche une fois que le bot est connecté et prêt."""
    # On initialise la base de données dès que possible
    await database_handler.setup_database()
    print("✅ Base de données initialisée et prête.")
    print(f"Connecté en tant que {bot.user}")
    print("Bot V2 prêt et opérationnel.")

if __name__ == '__main__':
    bot.add_check(global_blacklist_check)
    
    cogs_dir = "cogs"
    print("--- Chargement des Cogs ---")
    for filename in os.listdir(f'./{cogs_dir}'):
        if filename.endswith('.py'):
            try:
                bot.load_extension(f'{cogs_dir}.{filename[:-3]}')
                print(f"✅ Cog '{filename[:-3]}' chargé.")
            except Exception as e:
                print(f"❌ Erreur lors du chargement du cog '{filename[:-3]}': {e}")
    
    print("--- Tous les cogs ont été traités. Lancement du bot. ---")
    bot.run(TOKEN)