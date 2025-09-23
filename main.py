import discord
from discord.ext import commands
from discord import app_commands
from keep_alive import keep_alive
import re
import json
import os
import io

# Google Drive API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Ativando os intents necessários
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"
user_counters = {}

# ---------------- Google Drive Config ----------------
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
DRIVE_FILE_ID = os.getenv("DRIVE_FILE_ID")

if not GOOGLE_CREDENTIALS or not DRIVE_FILE_ID:
    print("❌ Faltando variáveis de ambiente GOOGLE_CREDENTIALS ou DRIVE_FILE_ID")
    exit(1)

creds = service_account.Credentials.from_service_account_info(
    json.loads(GOOGLE_CREDENTIALS),
    scopes=["https://www.googleapis.com/auth/drive.file"]
)
drive_service = build("drive", "v3", credentials=creds)

def upload_file(local_path=DATA_FILE):
    """Sobrescreve o arquivo no Google Drive"""
    media = MediaFileUpload(local_path, mimetype="application/json", resumable=True)
    drive_service.files().update(
        fileId=DRIVE_FILE_ID,
        media_body=media,
        body={"name": os.path.basename(local_path)}
    ).execute()


def download_file(local_path=DATA_FILE):
    """Baixa o arquivo do Google Drive"""
    request = drive_service.files().get_media(fileId=DRIVE_FILE_ID)
    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
# -----------------------------------------------------

# ---------------- Funções de salvar/carregar ----------------
def load_data():
    try:
        download_file(DATA_FILE)
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Erro ao carregar dados do Drive: {e}")
        return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_counters, f, indent=4)
    try:
        upload_file(DATA_FILE)
    except Exception as e:
        print(f"⚠️ Erro ao salvar no Drive: {e}")
# -------------------------------------------------------------

@bot.event
async def on_ready():
    global user_counters
    user_counters = load_data()
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Comandos de barra sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")
# COMANDO TK
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # @culpado tk @vitima
    pattern = r"<@!?(\d+)>\s+tk\s+<@!?(\d+)>"
    matches = re.findall(pattern, message.content, flags=re.IGNORECASE)

    for culpado_id_str, vitima_id_str in matches:
        culpado_id = str(culpado_id_str)
        vitima_id = str(vitima_id_str)

        # Garante que as chaves existam no JSON
        if "kills" not in user_counters:
            user_counters["kills"] = {}
        if "deaths" not in user_counters:
            user_counters["deaths"] = {}

        # Atualiza contador de TKs cometidos (culpado)
        user_counters["kills"][culpado_id] = user_counters["kills"].get(culpado_id, 0) + 1

        # Atualiza contador de TKs sofridos (vítima)
        user_counters["deaths"][vitima_id] = user_counters["deaths"].get(vitima_id, 0) + 1

        save_data()

        culpado = bot.get_user(int(culpado_id)) or await bot.fetch_user(int(culpado_id))
        vitima = bot.get_user(int(vitima_id)) or await bot.fetch_user(int(vitima_id))

        await message.channel.send(
            f"💥 {culpado.mention} deu TK em {vitima.mention}!\n"
            f"📊 Agora {culpado.mention} já tem {user_counters['kills'][culpado_id]} TK(s), "
            f"e {vitima.mention} já sofreu {user_counters['deaths'][vitima_id]} TK(s)!"
        )

    await bot.process_commands(message)


# AJUDA - lista todos os comandos
# ----------------------------------------
@bot.tree.command(name="ajuda", description="Mostra todos os comandos disponíveis.")
async def ajuda_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Lista de Comandos",
        description="Aqui estão os comandos disponíveis para o bot:",
        color=discord.Color.blue()
    )

    embed.add_field(name="/contador [usuário]", value="📊 Mostra quantos teamkills um usuário já cometeu.", inline=False)
    embed.add_field(name="/meucontador", value="🙋 Mostra quantos teamkills você mesmo já cometeu.", inline=False)
    embed.add_field(name="/top", value="🏆 Mostra o ranking dos 10 usuários com mais teamkills.", inline=False)
    embed.add_field(name="/zerar [usuário] (admin)", value="🔄 Zera o contador de um usuário.", inline=False)
    embed.add_field(name="/remover [usuário] (admin)", value="➖ Diminui em 1 o contador de um usuário.", inline=False)

    await interaction.response.send_message(embed=embed)

# ---------------- Comandos de barra ----------------
# comando /contador
@bot.tree.command(name="contador", description="Veja quantos teamkills um usuário cometeu e sofreu.")
@app_commands.describe(usuario="Usuário que você quer ver o contador")
async def contador(interaction: discord.Interaction, usuario: discord.User):
    kills = user_counters.get("kills", {}).get(str(usuario.id), 0)
    deaths = user_counters.get("deaths", {}).get(str(usuario.id), 0)
    await interaction.response.send_message(
        f"📊 {usuario.mention} já cometeu **{kills} TK(s)** e sofreu **{deaths} TK(s)**."
    )
# comando /meucontador
@bot.tree.command(name="meucontador", description="Veja quantos teamkills você já cometeu e sofreu.")
async def meucontador(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    kills = user_counters.get("kills", {}).get(user_id, 0)
    deaths = user_counters.get("deaths", {}).get(user_id, 0)
    await interaction.response.send_message(
        f"🙋 {interaction.user.mention}, você já cometeu **{kills} TK(s)** e sofreu **{deaths} TK(s)**."
    )
# comando /top
@bot.tree.command(name="top", description="Mostra o ranking de usuários com mais TKs cometidos e sofridos.")
async def top(interaction: discord.Interaction):
    if not user_counters or ("kills" not in user_counters and "deaths" not in user_counters):
        await interaction.response.send_message("❌ Ainda não há contadores registrados.")
        return

    top_text = "🏆 **Ranking de Teamkills ELDAR**:\n\n"

    # Ranking de quem mais matou
    kills_sorted = sorted(user_counters.get("kills", {}).items(), key=lambda x: x[1], reverse=True)
    if kills_sorted:
        top_text += "**🔪 TOP 5 TKs Cometidos:**\n"
        for i, (user_id, count) in enumerate(kills_sorted[:5], start=1):
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            top_text += f"**{i}.** {user.mention} — {count} TK(s)\n"
        top_text += "\n"

    # Ranking de quem mais morreu
    deaths_sorted = sorted(user_counters.get("deaths", {}).items(), key=lambda x: x[1], reverse=True)
    if deaths_sorted:
        top_text += "**☠️ TOP 5 TKs Sofridos:**\n"
        for i, (user_id, count) in enumerate(deaths_sorted[:5], start=1):
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            top_text += f"**{i}.** {user.mention} — {count} TK(s)\n"

    await interaction.response.send_message(top_text)

# comando /zerar
@bot.tree.command(name="zerar", description="Reseta o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer resetar")
@app_commands.default_permissions(administrator=True)
async def zerar(interaction: discord.Interaction, usuario: discord.User):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_counters[str(usuario.id)] = 0
    save_data()
    await interaction.response.send_message(f"🔄 O contador de {usuario.mention} foi resetado para 0.")
# comando /remover
@bot.tree.command(name="remover", description="Diminui em 1 o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer diminuir o contador")
@app_commands.default_permissions(administrator=True)
async def remover(interaction: discord.Interaction, usuario: discord.User):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_id = str(usuario.id)
    if user_id in user_counters and user_counters[user_id] > 0:
        user_counters[user_id] -= 1
        save_data()
        await interaction.response.send_message(f"➖ O contador de {usuario.mention} foi diminuído para {user_counters[user_id]}.")
    else:
        await interaction.response.send_message(f"⚠️ O contador de {usuario.mention} já está em 0 e não pode ser diminuído.")

# ----------------------------------------------------

bot_token = os.getenv("DISCORD_BOT_TOKEN")
if bot_token:
    keep_alive()
    bot.run(bot_token)
else:
    print("❌ DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
