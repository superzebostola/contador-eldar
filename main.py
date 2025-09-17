import discord
from discord.ext import commands
from discord import app_commands
from keep_alive import keep_alive
import re
import json
import os


# Ativando os intents necessários
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"
user_counters = {}

# ---------------- Funções de salvar/carregar ----------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_counters, f, indent=4)
# -------------------------------------------------------------

@bot.event
async def on_ready():
    global user_counters
    user_counters = load_data()
    print(f"Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Comandos de barra sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    pattern = r"<@!?(\d+)>\s+tk"
    matches = re.findall(pattern, message.content)

    for user_id_str in matches:
        user_id = int(user_id_str)

        if str(user_id) in user_counters:
            user_counters[str(user_id)] += 1
        else:
            user_counters[str(user_id)] = 1

        save_data()

        mentioned_user = await bot.fetch_user(user_id)
        await message.channel.send(
            f"🔢 {mentioned_user.mention} ja cometeu {user_counters[str(user_id)]} teamkills! Escola Lozenilson de TK está orgulhosa!"
        )

    await bot.process_commands(message)

# ---------------- Comandos de barra ----------------

# Ver contador de 1 usuário
@bot.tree.command(name="contador", description="Veja quantos teamkills um usuário cometeu.")
@app_commands.describe(usuario="Usuário que você quer ver o contador")
async def contador(interaction: discord.Interaction, usuario: discord.User):
    count = user_counters.get(str(usuario.id), 0)
    await interaction.response.send_message(
        f"📊 {usuario.mention} tem atualmente {count} teamkills(s)."
    )

# Ver o próprio contador
@bot.tree.command(name="meucontador", description="Veja quantos teamkills você já cometeu.")
async def meucontador(interaction: discord.Interaction):
    count = user_counters.get(str(interaction.user.id), 0)
    await interaction.response.send_message(
        f"🙋 {interaction.user.mention}, você tem atualmente {count} tk(s)."
    )

# Mostrar ranking
@bot.tree.command(name="top", description="Mostra o ranking de usuários com mais teamkills do esquadrão.")
async def top(interaction: discord.Interaction):
    if not user_counters:
        await interaction.response.send_message("❌ Ainda não há contadores registrados.")
        return

    ranking = sorted(user_counters.items(), key=lambda x: x[1], reverse=True)
    top_text = "🏆 **Ranking de Teamkills ELDAR**:\n\n"

    for i, (user_id, count) in enumerate(ranking[:10], start=1):
        user = await bot.fetch_user(int(user_id))
        top_text += f"**{i}.** {user.mention} — {count} teamkill(s)\n"

    await interaction.response.send_message(top_text)

# Resetar contador de um usuário (somente admins)
@bot.tree.command(name="reset", description="Reseta o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer resetar")
@app_commands.default_permissions(administrator=True)
async def reset(interaction: discord.Interaction, usuario: discord.User):
    # Additional runtime check as fallback
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_counters[str(usuario.id)] = 0
    save_data()
    await interaction.response.send_message(f"🔄 O contador de {usuario.mention} foi resetado para 0.")

# ----------------------------------------------------

# Use environment variable for the token
bot_token = os.getenv("DISCORD_BOT_TOKEN")
if bot_token:
    keep_alive() # 🔥 inicia o servidor web para manter ativo
    bot.run(bot_token)
else:
    print("❌ DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
    print("Por favor, configure o token do bot nas configurações de segredos.")
