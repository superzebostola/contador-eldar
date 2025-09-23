import discord
from discord.ext import commands
from discord import app_commands
from keep_alive import keep_alive
import re
import json
import os
import io
import logging

# Google Drive API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# ---------------- Logging ----------------
LOG_FILE = "logs.txt"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
# -----------------------------------------

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
DRIVE_LOGS_ID = os.getenv("DRIVE_LOGS_ID")

if not GOOGLE_CREDENTIALS or not DRIVE_FILE_ID or not DRIVE_LOGS_ID:
    logging.error("❌ Faltando variáveis de ambiente (GOOGLE_CREDENTIALS, DRIVE_FILE_ID ou DRIVE_LOGS_ID)")
    exit(1)

creds = service_account.Credentials.from_service_account_info(
    json.loads(GOOGLE_CREDENTIALS),
    scopes=["https://www.googleapis.com/auth/drive.file"]
)
drive_service = build("drive", "v3", credentials=creds)


def upload_file(local_path, file_id):
    """Sobrescreve o conteúdo de um arquivo no Google Drive"""
    try:
        # Define o mimetype conforme o arquivo
        mimetype = "application/json" if local_path.endswith(".json") else "text/plain"
        media = MediaFileUpload(local_path, mimetype=mimetype, resumable=False)
        drive_service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        logging.info(f"✅ Arquivo {local_path} sobrescrito no Google Drive (ID={file_id})")
    except Exception as e:
        logging.error(f"⚠️ Erro ao sobrescrever {local_path} no Drive: {e}")


def download_file(local_path, file_id):
    """Baixa o conteúdo de um arquivo do Google Drive"""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        logging.info(f"✅ Arquivo {local_path} baixado do Google Drive (ID={file_id})")
    except Exception as e:
        logging.error(f"⚠️ Erro ao baixar {local_path} do Drive: {e}")



# ---------------- Funções de salvar/carregar ----------------
def load_data():
    try:
        download_file(DATA_FILE)
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"⚠️ Erro ao carregar dados do Drive: {e}")
        return {}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_counters, f, indent=4, ensure_ascii=False)
    try:
        upload_file(DATA_FILE, DRIVE_FILE_ID)
        upload_file(LOG_FILE, DRIVE_LOGS_ID)  # <-- aqui envia os logs junto
    except Exception as e:
        logging.error(f"⚠️ Erro ao salvar arquivos no Drive: {e}")


# -------------------------------------------------------------

@bot.event
async def on_ready():
   @bot.event
async def on_ready():
    global user_counters
    user_counters = load_data()
    logger.info(f"✅ Bot conectado como {bot.user}")
    save_logs()  # <-- adiciona aqui
    try:
        synced = await bot.tree.sync()
        logger.info(f"Comandos de barra sincronizados: {len(synced)}")
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos: {e}")



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

        if "kills" not in user_counters:
            user_counters["kills"] = {}
        if "deaths" not in user_counters:
            user_counters["deaths"] = {}

        user_counters["kills"][culpado_id] = user_counters["kills"].get(culpado_id, 0) + 1
        user_counters["deaths"][vitima_id] = user_counters["deaths"].get(vitima_id, 0) + 1

        save_data()

        culpado = bot.get_user(int(culpado_id)) or await bot.fetch_user(int(culpado_id))
        vitima = bot.get_user(int(vitima_id)) or await bot.fetch_user(int(vitima_id))

        await message.channel.send(
            f"💥 {culpado.display_name} deu TK em {vitima.display_name}!\n"
            f"📊 Agora {culpado.display_name} já tem {user_counters['kills'][culpado_id]} TK(s), "
            f"e {vitima.display_name} já sofreu {user_counters['deaths'][vitima_id]} TK(s)!"
        )

    await bot.process_commands(message)


# ---------------- Slash Commands ----------------
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
    embed.add_field(name="/exportarlogs", value="📂 Exporta o arquivo de log do bot.", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="contador", description="Veja quantos teamkills um usuário cometeu e sofreu.")
@app_commands.describe(usuario="Usuário que você quer ver o contador")
async def contador(interaction: discord.Interaction, usuario: discord.User):
    kills = user_counters.get("kills", {}).get(str(usuario.id), 0)
    deaths = user_counters.get("deaths", {}).get(str(usuario.id), 0)
    await interaction.response.send_message(
        f"📊 {usuario.display_name} já cometeu **{kills} TK(s)** e sofreu **{deaths} TK(s)**."
    )


@bot.tree.command(name="meucontador", description="Veja quantos teamkills você já cometeu e sofreu.")
async def meucontador(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    kills = user_counters.get("kills", {}).get(user_id, 0)
    deaths = user_counters.get("deaths", {}).get(user_id, 0)
    await interaction.response.send_message(
        f"🙋 {interaction.user.display_name}, você já cometeu **{kills} TK(s)** e sofreu **{deaths} TK(s)**."
    )


@bot.tree.command(name="top", description="Mostra o ranking de usuários com mais TKs cometidos e sofridos.")
async def top(interaction: discord.Interaction):
    if not user_counters or ("kills" not in user_counters and "deaths" not in user_counters):
        await interaction.response.send_message("❌ Ainda não há contadores registrados.")
        return

    top_text = "🏆 **Ranking de Teamkills ELDAR**:\n\n"

    kills_sorted = sorted(user_counters.get("kills", {}).items(), key=lambda x: x[1], reverse=True)
    if kills_sorted:
        top_text += "**🔪 TOP 5 TKs Cometidos:**\n"
        for i, (user_id, count) in enumerate(kills_sorted[:5], start=1):
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            top_text += f"**{i}.** {user.display_name} — {count} TK(s)\n"
        top_text += "\n"

    deaths_sorted = sorted(user_counters.get("deaths", {}).items(), key=lambda x: x[1], reverse=True)
    if deaths_sorted:
        top_text += "**☠️ TOP 5 TKs Sofridos:**\n"
        for i, (user_id, count) in enumerate(deaths_sorted[:5], start=1):
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            top_text += f"**{i}.** {user.display_name} — {count} TK(s)\n"

    await interaction.response.send_message(top_text)


@bot.tree.command(name="zerar", description="Reseta o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer resetar")
@app_commands.default_permissions(administrator=True)
async def zerar(interaction: discord.Interaction, usuario: discord.User):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_id = str(usuario.id)
    user_counters.setdefault("kills", {})[user_id] = 0
    user_counters.setdefault("deaths", {})[user_id] = 0

    save_data()
    await interaction.response.send_message(f"🔄 O contador de {usuario.display_name} foi resetado para 0.")


@bot.tree.command(name="remover", description="Diminui em 1 o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer diminuir o contador")
@app_commands.default_permissions(administrator=True)
async def remover(interaction: discord.Interaction, usuario: discord.User):
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_id = str(usuario.id)
    if "kills" not in user_counters:
        user_counters["kills"] = {}

    if user_id in user_counters["kills"] and user_counters["kills"][user_id] > 0:
        user_counters["kills"][user_id] -= 1
        save_data()
        await interaction.response.send_message(
            f"➖ O contador de {usuario.display_name} foi diminuído para {user_counters['kills'][user_id]}."
        )
    else:
        await interaction.response.send_message(
            f"⚠️ O contador de {usuario.display_name} já está em 0 e não pode ser diminuído."
        )


# exportarlogs
@bot.tree.command(name="exportarlogs", description="Exporta o arquivo de logs do bot.")
async def exportarlogs(interaction: discord.Interaction):
    try:
        download_file(LOG_FILE, DRIVE_LOGS_ID)  # pega a versão mais recente do Drive
    except Exception as e:
        logging.warning(f"⚠️ Não foi possível atualizar logs do Drive: {e}")

    if os.path.exists(LOG_FILE):
        await interaction.response.send_message(
            file=discord.File(LOG_FILE),
            ephemeral=True
        )
    else:
        await interaction.response.send_message("❌ Nenhum log encontrado.", ephemeral=True)


# ----------------------------------------------------

bot_token = os.getenv("DISCORD_BOT_TOKEN")
if bot_token:
    keep_alive()
    bot.run(bot_token)
else:
    logging.error("❌ DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
