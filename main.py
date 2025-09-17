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
    """Envia o arquivo local para o Google Drive"""
    media = MediaFileUpload(local_path, mimetype="application/json", resumable=True)
    drive_service.files().update(
        fileId=DRIVE_FILE_ID,
        media_body=media
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

        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        await message.channel.send(
            f"🔢 {user.mention} já cometeu {user_counters[str(user_id)]} teamkills! Escola Lozenilson de TK está orgulhosa!"
        )

    await bot.process_commands(message)

# ---------------- Comandos de barra ----------------

@bot.tree.command(name="contador", description="Veja quantos teamkills um usuário cometeu.")
@app_commands.describe(usuario="Usuário que você quer ver o contador")
async def contador(interaction: discord.Interaction, usuario: discord.User):
    count = user_counters.get(str(usuario.id), 0)
    await interaction.response.send_message(
        f"📊 {usuario.mention} tem atualmente {count} teamkill(s)."
    )

@bot.tree.command(name="meucontador", description="Veja quantos teamkills você já cometeu.")
async def meucontador(interaction: discord.Interaction):
    count = user_counters.get(str(interaction.user.id), 0)
    await interaction.response.send_message(
        f"🙋 {interaction.user.mention}, você tem atualmente {count} tk(s)."
    )

@bot.tree.command(name="top", description="Mostra o ranking de usuários com mais teamkills do esquadrão.")
async def top(interaction: discord.Interaction):
    if not user_counters:
        await interaction.response.send_message("❌ Ainda não há contadores registrados.")
        return

    ranking = sorted(user_counters.items(), key=lambda x: x[1], reverse=True)
    top_text = "🏆 **Ranking de Teamkills ELDAR**:\n\n"

    for i, (user_id, count) in enumerate(ranking[:10], start=1):
        user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
        top_text += f"**{i}.** {user.mention} — {count} teamkill(s)\n"

    await interaction.response.send_message(top_text)

@bot.tree.command(name="reset", description="Reseta o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer resetar")
@app_commands.default_permissions(administrator=True)
async def reset(interaction: discord.Interaction, usuario: discord.User):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_counters[str(usuario.id)] = 0
    save_data()
    await interaction.response.send_message(f"🔄 O contador de {usuario.mention} foi resetado para 0.")

# ----------------------------------------------------

bot_token = os.getenv("DISCORD_BOT_TOKEN")
if bot_token:
    keep_alive()
    bot.run(bot_token)
else:
    print("❌ DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
