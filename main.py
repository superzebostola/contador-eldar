import discord
from discord.ext import commands, tasks
from discord import app_commands
# from keep_alive import keep_alive  # 🔴 removido para execução local
import re
import json
import os
import logging
import datetime

# IDs autorizados a usar comandos de admin (substitua pelos seus IDs reais)
ADMIN_IDS = [
    245362455377739778,
    310194866191859712,
]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------------------------
# Observação: tudo relacionado ao Google Drive foi
# removido/comentado para execução local apenas.
# ---------------------------------------------
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
# ---------------------------------------------

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

# ---------------- Funções de salvar/carregar ----------------
def load_data():
    """Carrega dados do arquivo local data.json (se existir)."""
    try:
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logging.warning("⚠️ data.json vazio ou inexistente, iniciando novo contador.")
            return {}
    except Exception as e:
        logging.error(f"⚠️ Erro ao carregar dados locais: {e}")
        return {}


def save_data():
    """Salva os dados em data.json localmente."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_counters, f, indent=4, ensure_ascii=False)
        logging.info("💾 Dados salvos localmente em data.json")
    except Exception as e:
        logging.error(f"⚠️ Erro ao salvar dados locais: {e}")

# ---------------- Backup Automático (local) ----------------
@tasks.loop(minutes=10)
async def backup_periodico():
    try:
        if user_counters:
            save_data()
            logging.info("💾 Backup automático concluído com sucesso.")
        else:
            logging.debug("🔁 Backup automático ignorado (sem dados).")
    except Exception as e:
        logging.error(f"❌ Erro no backup automático: {e}")


# INICIANDO O BOT
@bot.event
async def on_ready():
    global user_counters
    user_counters = load_data()
    logging.info(f"✅ Bot conectado como {bot.user}")

    try:
        # Sincroniza comandos globais
        synced_global = await bot.tree.sync()
        logging.info(f"🌍 Comandos globais sincronizados: {len(synced_global)}")

        # Sincroniza comandos no guild (mais rápido para testes)
        # Substitua pelo ID do seu servidor para sincronizar só nele
        GUILD_ID = 1420208320551063674
        guild = discord.Object(id=GUILD_ID)
        synced_guild = await bot.tree.sync(guild=guild)
        logging.info(f"⚡ Comandos sincronizados no servidor {GUILD_ID}: {len(synced_guild)}")

        # Inicia backup periódico (se ainda não estiver em execução)
        if not backup_periodico.is_running():
            backup_periodico.start()
            logging.info("⏰ Backup automático iniciado (a cada 10 min).")

    except Exception as e:
        logging.error(f"❌ Erro ao sincronizar comandos: {e}")


# ---------------- Eventos ----------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Padrão: @culpado tk @vitima
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

        # tenta pegar o usuário em cache; se não, faz fetch (pode falhar se ID inválido)
        try:
            culpado = bot.get_user(int(culpado_id)) or await bot.fetch_user(int(culpado_id))
        except Exception:
            culpado = None
        try:
            vitima = bot.get_user(int(vitima_id)) or await bot.fetch_user(int(vitima_id))
        except Exception:
            vitima = None

        hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        author_name = getattr(message.author, 'display_name', str(message.author))
        culpado_name = culpado.display_name if culpado else f"<@{culpado_id}"
        vitima_name = vitima.display_name if vitima else f"<@{vitima_id}"

        logging.info(f"[{hora}] {author_name} registrou TK: {culpado_name} ➝ {vitima_name}")

        await message.channel.send(
            f"💥 {culpado_name} deu TK em {vitima_name}!\n"
            f"📊 Agora {culpado_name} já tem {user_counters['kills'][culpado_id]} TK(s), "
            f"e {vitima_name} já sofreu {user_counters['deaths'][vitima_id]} TK(s)!"
        )

    await bot.process_commands(message)


# ---------------- Slash Commands ----------------
@bot.tree.command(name="ajuda", description="Mostra todos os comandos disponíveis.")
async def ajuda_command(interaction: discord.Interaction):
    explicacao_tk = (
        "📌 **Como usar o comando de TK:**\n"
        "Digite no chat: `@culpado tk @vitima`\n"
        "➡️ Exemplo: `@joao tk @mateus`\n\n"
    )

    embed = discord.Embed(
        title="📖 Lista de Comandos",
        description="Aqui estão os comandos disponíveis para o bot:",
        color=discord.Color.blue()
    )

    embed.add_field(name="/contador [usuário]", value="📊 Mostra quantos teamkills um usuário já cometeu.", inline=False)
    embed.add_field(name="/meucontador", value="🙋 Mostra quantos teamkills você mesmo já cometeu.", inline=False)
    embed.add_field(name="/top", value="🏆 Mostra o ranking dos 10 usuários com mais teamkills.", inline=False)

    if is_admin(interaction.user.id):
        embed.add_field(name="⠀", value="**⚙️ Comandos de Administração:**", inline=False)
        embed.add_field(name="/zerar [usuário]", value="🔄 Zera o contador de um usuário.", inline=False)
        embed.add_field(name="/remover [usuário]", value="➖ Diminui em 1 o contador de um usuário.", inline=False)
        embed.add_field(name="/exportarlogs", value="📂 Exporta o arquivo de log do bot.", inline=False)
        embed.add_field(name="/exportardata", value="📤 Exporta o arquivo data.json atual.", inline=False)
        embed.add_field(name="/importardata", value="📥 Importa e substitui o arquivo data.json.", inline=False)

    await interaction.response.send_message(explicacao_tk, ephemeral=True)
    await interaction.followup.send(embed=embed, ephemeral=True)


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
            top_text += f"**{i}.** <@{user_id}> — {count} TK(s)\n"
        top_text += "\n"

    deaths_sorted = sorted(user_counters.get("deaths", {}).items(), key=lambda x: x[1], reverse=True)
    if deaths_sorted:
        top_text += "**☠️ TOP 5 TKs Sofridos:**\n"
        for i, (user_id, count) in enumerate(deaths_sorted[:5], start=1):
            top_text += f"**{i}.** <@{user_id}> — {count} TK(s)\n"

    await interaction.response.send_message(top_text)


@bot.tree.command(name="zerar", description="Reseta o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer resetar")
async def zerar(interaction: discord.Interaction, usuario: discord.User):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_id = str(usuario.id)
    user_counters.setdefault("kills", {})[user_id] = 0
    user_counters.setdefault("deaths", {})[user_id] = 0

    save_data()
    logging.info(f"[ZERAR] {interaction.user.display_name} resetou o contador de {usuario.display_name}")

    await interaction.response.send_message(f"🔄 O contador de {usuario.display_name} foi resetado para 0.")


@bot.tree.command(name="remover", description="Diminui em 1 o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer diminuir o contador")
async def remover(interaction: discord.Interaction, usuario: discord.User):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_id = str(usuario.id)
    if "kills" not in user_counters:
        user_counters["kills"] = {}

    if user_id in user_counters["kills"] and user_counters["kills"][user_id] > 0:
        user_counters["kills"][user_id] -= 1
        save_data()
        logging.info(f"[REMOVER] {interaction.user.display_name} diminuiu 1 TK de {usuario.display_name}. Novo valor: {user_counters['kills'][user_id]}")
        await interaction.response.send_message(
            f"➖ O contador de {usuario.display_name} foi diminuído para {user_counters['kills'][user_id]}."
        )
    else:
        await interaction.response.send_message(
            f"⚠️ O contador de {usuario.display_name} já está em 0 e não pode ser diminuído."
        )


@bot.tree.command(name="exportarlogs", description="Exporta o arquivo de logs do bot (apenas admins).")
async def exportarlogs(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    if os.path.exists(LOG_FILE):
        logging.info(f"[EXPORTAR LOGS] {interaction.user.display_name} exportou o logs.txt")
        await interaction.response.send_message(file=discord.File(LOG_FILE), ephemeral=True)
    else:
        await interaction.response.send_message("❌ Nenhum log encontrado.", ephemeral=True)


@bot.tree.command(name="exportardata", description="Exporta o arquivo data.json (apenas admins).")
async def exportardata(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    if os.path.exists(DATA_FILE):
        logging.info(f"[EXPORTAR DATA] {interaction.user.display_name} exportou o data.json")
        await interaction.response.send_message(file=discord.File(DATA_FILE), ephemeral=True)
    else:
        await interaction.response.send_message("❌ Nenhum data.json encontrado.", ephemeral=True)


@bot.tree.command(name="importardata", description="Importa e substitui o arquivo data.json (apenas admins).")
async def importardata(interaction: discord.Interaction, arquivo: discord.Attachment):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    if not arquivo.filename.endswith(".json"):
        await interaction.response.send_message("❌ O arquivo precisa ser um .json válido.", ephemeral=True)
        return

    try:
        file_bytes = await arquivo.read()
        with open(DATA_FILE, "wb") as f:
            f.write(file_bytes)

        global user_counters
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            user_counters = json.load(f)

        save_data()
        logging.info(f"[IMPORTAR DATA] {interaction.user.display_name} importou um novo data.json ({arquivo.filename})")

        await interaction.response.send_message("✅ data.json importado e atualizado com sucesso!", ephemeral=True)
    except Exception as e:
        logging.error(f"Erro ao importar data.json: {e}")
        await interaction.response.send_message("❌ Erro ao importar data.json.", ephemeral=True)


# ----------------------------------------------------
# BOT TOKEN (defina seu token aqui para rodar localmente)
bot_token = "COLOQUE_SEU_TOKEN_AQUI"
if not bot_token or bot_token == "COLOQUE_SEU_TOKEN_AQUI":
    logging.error("❌ Defina o bot_token na variável 'bot_token' no arquivo antes de rodar.")
else:
    bot.run(bot_token)
