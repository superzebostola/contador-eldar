import discord
from discord.ext import tasks, commands
from discord import app_commands
from keep_alive import keep_alive
import re
import json
import os
import io
from datetime import datetime

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
LOGS_FILE = "logs.txt"
user_counters = {}

def get_display_name(user: discord.User | discord.Member) -> str:
    """Retorna o apelido (display_name) se for membro, senão o nome global."""
    return user.display_name if isinstance(user, discord.Member) else user.name

# ---------------- Google Drive Config ----------------
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
DRIVE_FILE_ID = os.getenv("DRIVE_FILE_ID")
DRIVE_LOGS_ID = os.getenv("DRIVE_LOGS_ID")

if not GOOGLE_CREDENTIALS or not DRIVE_FILE_ID or not DRIVE_LOGS_ID:
    print("❌ Faltando variáveis de ambiente GOOGLE_CREDENTIALS, DRIVE_FILE_ID ou DRIVE_LOGS_ID")
    exit(1)

creds = service_account.Credentials.from_service_account_info(
    json.loads(GOOGLE_CREDENTIALS),
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build("drive", "v3", credentials=creds)

def upload_file(local_path=DATA_FILE):
    media = MediaFileUpload(local_path, mimetype="application/json", resumable=True)
    drive_service.files().update(fileId=DRIVE_FILE_ID, media_body=media).execute()

def download_file(local_path=DATA_FILE):
    request = drive_service.files().get_media(fileId=DRIVE_FILE_ID)
    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

def upload_logs(local_path=LOGS_FILE):
    media = MediaFileUpload(local_path, mimetype="text/plain", resumable=True)
    drive_service.files().update(fileId=DRIVE_LOGS_ID, media_body=media).execute()

def download_logs(local_path=LOGS_FILE):
    request = drive_service.files().get_media(fileId=DRIVE_LOGS_ID)
    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

# ---------------- Funções de salvar/carregar ----------------
def load_data():
    try:
        download_file(DATA_FILE)
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Arquivo data.json inválido. Criando novo.")
        return {}
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

# ---------------- Sistema de Logs ----------------
def log_action(texto: str, user: discord.User | discord.Member = None, admin: bool = False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if admin and user:
        linha = f"[{timestamp}] ADMIN {get_display_name(user)} ({user.id}) {texto}"
    else:
        linha = f"[{timestamp}] {texto}"

    with open(LOGS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{linha}\n")

    try:
        upload_logs(LOGS_FILE)
    except Exception as e:
        print(f"⚠️ Erro ao salvar logs no Drive: {e}")

# ---------------- BOT EVENTS ----------------
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
    backup_drive.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    pattern = r"<@!?(\d+)>\s+tk"
    matches = re.findall(pattern, message.content, re.IGNORECASE)

    for user_id_str in matches:
        user_id = int(user_id_str)
        user_counters[str(user_id)] = user_counters.get(str(user_id), 0) + 1
        save_data()
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        await message.channel.send(
            f"🔢 {get_display_name(user)} já cometeu {user_counters[str(user_id)]} teamkills!"
        )
        log_action(f"TK: {get_display_name(user)} ({user_id}) → total: {user_counters[str(user_id)]}")

    await bot.process_commands(message)

# ---------------- BACKUP AUTOMÁTICO ----------------
@tasks.loop(minutes=15)
async def backup_drive():
    try:
        upload_file(DATA_FILE)
        upload_logs(LOGS_FILE)
        print("☁️ Backup automático de data.json e logs.txt enviado para o Google Drive")
    except Exception as e:
        print(f"⚠️ Erro no backup automático: {e}")

# ---------------- HELP ----------------
@bot.tree.command(name="help", description="Mostra todos os comandos disponíveis.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Lista de Comandos",
        description="Aqui estão os comandos disponíveis para o bot:",
        color=discord.Color.blue()
    )

    embed.add_field(name="/contador [usuário]", value="📊 Mostra quantos teamkills um usuário já cometeu.", inline=False)
    embed.add_field(name="/meucontador", value="🙋 Mostra quantos teamkills você mesmo já cometeu.", inline=False)
    embed.add_field(name="/top", value="🏆 Mostra o ranking dos 10 usuários com mais teamkills.", inline=False)

    if interaction.user.guild_permissions.administrator:
        embed.add_field(name="/zerar [usuário]", value="🔄 Zera o contador de um usuário.", inline=False)
        embed.add_field(name="/remover [usuário]", value="➖ Diminui em 1 o contador de um usuário.", inline=False)
        embed.add_field(name="/backup", value="📂 Envia o arquivo `data.json`.", inline=False)
        embed.add_field(name="/restaurar", value="♻️ Restaura o `data.json` a partir de um upload.", inline=False)
        embed.add_field(name="/logs", value="📜 Mostra os últimos registros de alterações.", inline=False)
        embed.add_field(name="/exportlogs", value="📤 Exporta todo o arquivo `logs.txt`.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------- LOGS ----------------
@bot.tree.command(name="logs", description="Mostra os últimos registros (apenas admins).")
@app_commands.default_permissions(administrator=True)
async def logs(interaction: discord.Interaction):
    if not os.path.exists(LOGS_FILE):
        await interaction.response.send_message("⚠️ Nenhum log encontrado.", ephemeral=True)
        return
    try:
        with open(LOGS_FILE, "r", encoding="utf-8") as f:
            linhas = f.readlines()[-10:]
        texto = "".join(linhas) if linhas else "⚠️ Nenhum log registrado."
        await interaction.response.send_message(f"📜 **Últimos registros:**\n```\n{texto}\n```", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Erro ao carregar logs: {e}", ephemeral=True)

@bot.tree.command(name="exportlogs", description="Exporta o arquivo completo de logs (apenas admins).")
@app_commands.default_permissions(administrator=True)
async def exportlogs(interaction: discord.Interaction):
    if not os.path.exists(LOGS_FILE):
        await interaction.response.send_message("⚠️ Nenhum log encontrado.", ephemeral=True)
        return
    try:
        download_logs(LOGS_FILE)
        await interaction.response.send_message("📤 Aqui está o arquivo `logs.txt`:", file=discord.File(LOGS_FILE), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Erro ao exportar logs: {e}", ephemeral=True)

# ---------------- BOT TOKEN ----------------
bot_token = os.getenv("DISCORD_BOT_TOKEN")
if bot_token:
    keep_alive()
    bot.run(bot_token)
else:
    print("❌ DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
