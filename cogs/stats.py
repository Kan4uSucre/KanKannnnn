import discord
from discord.ext import commands, tasks
import asyncio
from utils.checks import has_command_permission # On garde la sécu pour la commande refresh

# ==============================================================================
#  CONFIGURATION MANUELLE - METS TES IDs DE SALONS ICI
# ==============================================================================
# Instructions:
# 1. Remplace 111222333444555666 par l'ID de TON serveur.
# 2. Remplace les IDs des salons par ceux que tu as créés sur ton serveur.
# 3. Si tu ne veux pas un certain compteur, laisse son ID à 0.
# 4. Tu peux ajouter d'autres serveurs en copiant le format.

STATS_CHANNELS = {
    1224814536750665888: { # <--- ID DE TON SERVEUR ICI
        "members": 1309668688537976883, # ID du salon "Membres"
        "online":  1309668689595076719, # ID du salon "En ligne"
        "vocal":   1309668690958094399, # ID du salon "En vocal"
        "boost":   1309668696918069379, # ID du salon "Boost"
    },
    # Exemple si tu avais un deuxième serveur :
    # 999888777666555444: {
    #     "members": 987654321098765432,
    #     "online":  987654321098765433,
    #     "vocal":   0, # Désactivé
    #     "boost":   987654321098765434,
    # },
}

class ServerStats(commands.Cog):
    """Gère les statistiques du serveur dans des salons vocaux pré-définis."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_stats_channels.start()

    def cog_unload(self):
        self.update_stats_channels.cancel()

    @tasks.loop(minutes=10)
    async def update_stats_channels(self):
        print("INFO: Lancement de la mise à jour des statistiques...")
        for guild_id, channels in STATS_CHANNELS.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                print(f"WARN: Le bot n'est pas sur le serveur configuré avec l'ID {guild_id}")
                continue

            await self.update_stats_for_guild(guild, channels)
            await asyncio.sleep(2) # Petite pause pour ne pas surcharger l'API
        print("INFO: Mise à jour des statistiques terminée.")

    @update_stats_channels.before_loop
    async def before_stats_update(self):
        await self.bot.wait_until_ready()

    async def update_stats_for_guild(self, guild: discord.Guild, channels: dict):
        """Met à jour les noms des salons pour un serveur spécifique."""
        # --- Calcul des stats ---
        total_members = guild.member_count
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
        vocal_members = sum(len(c.members) for c in guild.voice_channels)
        boost_count = guild.premium_subscription_count

        # --- Noms cibles ---
        channel_names = {
            'members': f"💎・Membres: {total_members}",
            'online': f"⭐・En ligne: {online_members}",
            'vocal': f"🎧・En vocal: {vocal_members}",
            'boost': f"🔮・Boosts: {boost_count}"
        }

        # --- Mise à jour ---
        for key, channel_id in channels.items():
            if not channel_id or channel_id == 0:
                continue

            channel = guild.get_channel(channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                new_name = channel_names.get(key)
                # On ne modifie le nom que si c'est nécessaire pour économiser les requêtes API
                if new_name and channel.name != new_name:
                    try:
                        await channel.edit(name=new_name, reason="Mise à jour des statistiques")
                    except discord.Forbidden:
                        print(f"ERREUR: Permissions manquantes pour éditer le salon de stats '{key}' sur {guild.name}")
                    except Exception as e:
                        print(f"ERREUR: Une erreur est survenue lors de la mise à jour du salon '{key}' sur {guild.name}: {e}")
            else:
                print(f"WARN: Salon de stats '{key}' introuvable ou n'est pas un salon vocal sur {guild.name} (ID: {channel_id})")
    
    @commands.slash_command(name="stats_refresh", description="Force la mise à jour immédiate des statistiques.")
    @has_command_permission()
    async def stats_refresh(self, ctx: discord.ApplicationContext):
        """Commande pour forcer manuellement la mise à jour."""
        await ctx.defer(ephemeral=True)
        
        if ctx.guild.id not in STATS_CHANNELS:
            return await ctx.followup.send("❌ Ce serveur n'est pas configuré dans le fichier du bot.", ephemeral=True)
        
        await self.update_stats_for_guild(ctx.guild, STATS_CHANNELS[ctx.guild.id])
        await ctx.followup.send("✅ Les statistiques ont été mises à jour manuellement !", ephemeral=True)

def setup(bot):
    bot.add_cog(ServerStats(bot))