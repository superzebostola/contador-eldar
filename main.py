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
LOG_FILE = "log.json"
user_counters = {}

def get_display_name(user: discord.User | discord.Member) -> str:
    return user.display_name if isinstance(user, discord.Member) else user.name

# ---------------- Funções de Log ----------------
def registrar_log(usuario, acao, novo_valor, feito_por=None):
    log_entry = {
        "usuario": get_display_name(usuario),
        "user_id": usuario.id,
        "acao": acao,
        "novo_valor": novo_valor,
        "feito_por": get_display_name(feito_por) if feito_por else "Sistema",
        "feito_por_id": feito_por.id if feito_por else None,
        "timestamp": datetime.utcnow().isoformat()
    }

    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    logs.append(log_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=4)

def carregar_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

# -------------------------------------------------------------

@bot.event
async def on_ready():
    global user_counters
    user_counters = load_data()
    print(f"✅ Bot conectado como {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"🔄 Comandos sincronizados: {len(synced)}")
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

        if str(user_id) in user_counters:
            user_counters[str(user_id)] += 1
        else:
            user_counters[str(user_id)] = 1

        save_data()

        user = bot.get_user(user_id) or await bot.fetch_user(user_id)

        # Log
        registrar_log(user, "incrementou", user_counters[str(user_id)], message.author)

        await message.channel.send(
            f"🔢 {get_display_name(user)} já cometeu {user_counters[str(user_id)]} teamkills! Escola Lozenilson de TK está orgulhosa!"
        )

    await bot.process_commands(message)

#---------- upload do datajson------------
@tasks.loop(minutes=15)
async def backup_drive():
    try:
        upload_file(DATA_FILE)
        print("☁️ Backup do data.json enviado para o Google Drive")
    except Exception as e:
        print(f"⚠️ Erro no backup automático: {e}")

# ---------------- Google Drive Config ----------------
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
DRIVE_FILE_ID = os.getenv("DRIVE_FILE_ID")

if not GOOGLE_CREDENTIALS or not DRIVE_FILE_ID:
    print("❌ Faltando variáveis de ambiente GOOGLE_CREDENTIALS ou DRIVE_FILE_ID")
    exit(1)

creds = service_account.Credentials.from_service_account_info(
    json.loads(GOOGLE_CREDENTIALS),
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build("drive", "v3", credentials=creds)

def upload_file(local_path=DATA_FILE):
    media = MediaFileUpload(local_path, mimetype="application/json", resumable=True)
    drive_service.files().update(
        fileId=DRIVE_FILE_ID,
        media_body=media
    ).execute()

def download_file(local_path=DATA_FILE):
    request = drive_service.files().get_media(fileId=DRIVE_FILE_ID)
    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

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
        embed.add_field(name="/backup", value="📂 Envia o arquivo data.json.", inline=False)
        embed.add_field(name="/restaurar", value="♻️ Restaura o arquivo data.json enviado.", inline=False)
        embed.add_field(name="/logs", value="📝 Mostra os últimos registros de alteração.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------- Comandos de barra ----------------
@bot.tree.command(name="zerar", description="Reseta o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer resetar")
@app_commands.default_permissions(administrator=True)
async def zerar(interaction: discord.Interaction, usuario: discord.User):
    user_counters[str(usuario.id)] = 0
    save_data()
    registrar_log(usuario, "zerado", 0, interaction.user)
    await interaction.response.send_message(f"🔄 O contador de {get_display_name(usuario)} foi resetado para 0.")

@bot.tree.command(name="remover", description="Diminui em 1 o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer diminuir o contador")
@app_commands.default_permissions(administrator=True)
async def remover(interaction: discord.Interaction, usuario: discord.User):
    user_id = str(usuario.id)
    if user_id in user_counters and user_counters[user_id] > 0:
        user_counters[user_id] -= 1
        save_data()
        registrar_log(usuario, "removido", user_counters[user_id], interaction.user)
        await interaction.response.send_message(f"➖ O contador de {get_display_name(usuario)} foi diminuído para {user_counters[user_id]}.")
    else:
        await interaction.response.send_message(f"⚠️ O contador de {get_display_name(usuario)} já está em 0 e não pode ser diminuído.")

# ---------------- LOGS ----------------
@bot.tree.command(name="logs", description="Mostra os últimos 10 registros de alterações.")
@app_commands.default_permissions(administrator=True)
async def logs(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    try:
        if not os.path.exists("logs.txt"):
            await interaction.response.send_message(
                "⚠️ Ainda não há registros disponíveis.",
                ephemeral=True
            )
            return

        with open("logs.txt", "r", encoding="utf-8") as f:
            linhas = f.readlines()

        # Pega só os últimos 10 registros
        ultimos = linhas[-10:] if len(linhas) > 10 else linhas

        embed = discord.Embed(
            title="📜 Últimos Logs",
            description="Aqui estão os últimos registros de alterações:",
            color=discord.Color.orange()
        )

        # Junta os registros dentro de um bloco de código
        embed.add_field(
            name="Registros",
            value="```" + "".join(ultimos) + "```",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro ao carregar os logs: {e}",
            ephemeral=True
        )

@bot.tree.command(name="exportlogs", description="Exporta todos os registros de alterações em um arquivo.")
@app_commands.default_permissions(administrator=True)
async def exportlogs(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    try:
        if not os.path.exists("logs.txt"):
            await interaction.response.send_message(
                "⚠️ Ainda não há registros disponíveis.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "📂 Aqui está o arquivo completo de logs:",
            file=discord.File("logs.txt"),
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro ao exportar logs: {e}",
            ephemeral=True
        )


# ---------------- EXPORTAR LOGS ----------------
@bot.tree.command(name="exportlogs", description="Envia o arquivo log.json completo (apenas admins).")
@app_commands.default_permissions(administrator=True)
async def exportlogs(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    if not os.path.exists(LOG_FILE):
        await interaction.response.send_message(
            "⚠️ Nenhum log foi registrado ainda.",
            ephemeral=True
        )
        return

    try:
        await interaction.response.send_message(
            "📂 Aqui está o arquivo completo de logs:",
            file=discord.File(LOG_FILE)
        )
    except Exception as e:
        await interaction.response.send_message(
            f"⚠️ Erro ao enviar log.json: {e}",
            ephemeral=True
        )


# ---------------- Funções de salvar/carregar ----------------
def load_data():
    try:
        download_file(DATA_FILE)
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_counters, f, indent=4)
    try:
        upload_file(DATA_FILE)
    except Exception as e:
        print(f"⚠️ Erro ao salvar no Drive: {e}")

# ----------------------------------------------------
bot_token = os.getenv("DISCORD_BOT_TOKEN")
if bot_token:
    keep_alive()
    bot.run(bot_token)
else:
    print("❌ DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
