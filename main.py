import discord
from discord import app_commands
from discord.ext import tasks, commands
from keep_alive import keep_alive
import re
import json
import os
import io
import traceback

# Google Drive API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# ---------------- Configurações ----------------
# Substitua pelos IDs das 3 guilds onde você quer forçar sync imediato
GUILD_IDS = [
    1417622405710614730,   # guild 1 (exemplo)
    432367752418820137,   # guild 2 (exemplo)
    1223066167825010709    # guild 3 (exemplo)
]

DATA_FILE = "data.json"
LOGS_FILE = "logs.txt"

# Ativando os intents necessários
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

user_counters = {}

def get_display_name(user: discord.User | discord.Member) -> str:
    return user.display_name if isinstance(user, discord.Member) else user.name

# ---------------- Google Drive Config ----------------
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
DRIVE_FILE_ID = os.getenv("DRIVE_FILE_ID")
DRIVE_LOGS_ID = os.getenv("DRIVE_LOGS_ID")

if not GOOGLE_CREDENTIALS or not DRIVE_FILE_ID or not DRIVE_LOGS_ID:
    print("❌ Faltando variáveis de ambiente GOOGLE_CREDENTIALS, DRIVE_FILE_ID ou DRIVE_LOGS_ID")
    # Não exit aqui caso você queira rodar local sem Drive — se quiser, descomente a linha abaixo
    # exit(1)

# Se houver GOOGLE_CREDENTIALS, tenta configurar o drive_service
drive_service = None
if GOOGLE_CREDENTIALS and DRIVE_FILE_ID and DRIVE_LOGS_ID:
    try:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(GOOGLE_CREDENTIALS),
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        drive_service = build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"⚠️ Erro ao inicializar Google Drive: {e}")
        traceback.print_exc()
        drive_service = None

def upload_file(local_path=DATA_FILE):
    if not drive_service:
        return
    media = MediaFileUpload(local_path, mimetype="application/json", resumable=True)
    drive_service.files().update(fileId=DRIVE_FILE_ID, media_body=media).execute()

def download_file(local_path=DATA_FILE):
    if not drive_service:
        return
    request = drive_service.files().get_media(fileId=DRIVE_FILE_ID)
    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

def upload_logs(local_path=LOGS_FILE):
    if not drive_service:
        return
    media = MediaFileUpload(local_path, mimetype="text/plain", resumable=True)
    drive_service.files().update(fileId=DRIVE_LOGS_ID, media_body=media).execute()

def download_logs(local_path=LOGS_FILE):
    if not drive_service:
        return
    request = drive_service.files().get_media(fileId=DRIVE_LOGS_ID)
    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

# ---------------- Funções de salvar/carregar ----------------
def load_data():
    try:
        # tenta baixar do Drive (se configurado)
        download_file(DATA_FILE)
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            print("⚠️ Arquivo data.json vazio. Mantendo dados locais.")
            return {}
    except json.JSONDecodeError:
        print("⚠️ Arquivo data.json inválido. Criando novo.")
        return {}
    except Exception as e:
        print(f"⚠️ Erro ao carregar dados do Drive: {e}")
        traceback.print_exc()
        return {}

def save_data():
    try:
        if not user_counters:
            print("⚠️ Dados estão vazios, não vou sobrescrever o data.json.")
            return
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_counters, f, indent=4, ensure_ascii=False)
        try:
            upload_file(DATA_FILE)
            print("☁️ data.json atualizado no Google Drive")
        except Exception as e:
            print(f"⚠️ Erro ao salvar no Drive: {e}")
            traceback.print_exc()
    except Exception as e:
        print(f"⚠️ Erro ao salvar localmente: {e}")
        traceback.print_exc()

def log_action(texto: str):
    try:
        with open(LOGS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{texto}\n")
        try:
            upload_logs(LOGS_FILE)
        except Exception as e:
            print(f"⚠️ Erro ao salvar logs no Drive: {e}")
    except Exception as e:
        print(f"⚠️ Erro ao gravar logs locais: {e}")
        traceback.print_exc()

# ---------------- BOT EVENTS ----------------
@bot.event
async def on_ready():
    global user_counters
    user_counters = load_data()
    print(f"✅ Bot conectado como {bot.user}")

    try:
        msgs = []
        # limpa e sincroniza por cada guild listado
        for gid in GUILD_IDS:
            try:
                guild_obj = discord.Object(id=gid)
                # limpa comandos antigos desta guild (síncrono)
                bot.tree.clear_commands(guild=guild_obj)
                # sincroniza
                synced = await bot.tree.sync(guild=guild_obj)
                msgs.append(f"✅ {len(synced)} comandos sincronizados com a guild {gid}")
            except Exception as gi_e:
                msgs.append(f"⚠️ Erro ao sincronizar guild {gid}: {gi_e}")
                traceback.print_exc()

        # limpa e sincroniza global (opcional) — útil caso haja comando global antigo
        try:
            bot.tree.clear_commands(guild=None)
            synced_global = await bot.tree.sync()
            msgs.append(f"🌍 {len(synced_global)} comandos sincronizados globalmente (após limpeza)")
        except Exception as g_e:
            msgs.append(f"⚠️ Erro ao sincronizar globalmente: {g_e}")
            traceback.print_exc()

        # imprime resumo
        for m in msgs:
            print(m)

    except Exception as e:
        print(f"⚠️ Erro inesperado no on_ready: {e}")
        traceback.print_exc()

    # inicia o loop de backup (se ainda não rodando)
    try:
        if not backup_drive.is_running():
            backup_drive.start()
    except Exception as e:
        print(f"⚠️ Erro ao iniciar backup_drive: {e}")
        traceback.print_exc()


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    pattern = r"<@!?(\d+)>\s+tk"
    matches = re.findall(pattern, message.content, re.IGNORECASE)
    for user_id_str in matches:
        try:
            user_id = int(user_id_str)
            user_counters[str(user_id)] = user_counters.get(str(user_id), 0) + 1
            save_data()
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            await message.channel.send(
                f"🔢 {get_display_name(user)} já cometeu {user_counters[str(user_id)]} teamkills!"
            )
            log_action(f"[TK] {get_display_name(user)} ({user_id}) → total: {user_counters[str(user_id)]}")
        except Exception as e:
            print(f"⚠️ Erro processando mensagem TK: {e}")
            traceback.print_exc()
    await bot.process_commands(message)

# ---------------- HELP (AJUDA) ----------------
@bot.tree.command(name="ajuda", description="Mostra todos os comandos disponíveis.")
async def ajuda_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
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

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"⚠️ Erro em /ajuda: {e}")
        traceback.print_exc()
        try:
            await interaction.followup.send("❌ Erro ao gerar a lista de comandos.", ephemeral=True)
        except:
            pass

# ---------------- COMANDOS ----------------
@bot.tree.command(name="contador", description="Veja quantos teamkills um usuário cometeu.")
@app_commands.describe(usuario="Usuário que você quer ver o contador")
async def contador(interaction: discord.Interaction, usuario: discord.User):
    await interaction.response.defer()
    try:
        count = user_counters.get(str(usuario.id), 0)
        await interaction.followup.send(f"📊 {get_display_name(usuario)} tem atualmente {count} teamkill(s).")
    except Exception as e:
        print(f"⚠️ Erro em /contador: {e}")
        traceback.print_exc()
        await interaction.followup.send("❌ Erro ao obter contador.", ephemeral=True)

@bot.tree.command(name="meucontador", description="Veja quantos teamkills você já cometeu.")
async def meucontador(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        count = user_counters.get(str(interaction.user.id), 0)
        await interaction.followup.send(f"🙋 {get_display_name(interaction.user)}, você tem atualmente {count} tk(s).")
    except Exception as e:
        print(f"⚠️ Erro em /meucontador: {e}")
        traceback.print_exc()
        await interaction.followup.send("❌ Erro ao obter seu contador.", ephemeral=True)

@bot.tree.command(name="top", description="Mostra o ranking de usuários com mais teamkills do esquadrão.")
async def top(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        if not user_counters:
            await interaction.followup.send("❌ Ainda não há contadores registrados.")
            return
        ranking = sorted(user_counters.items(), key=lambda x: x[1], reverse=True)
        top_text = "🏆 **Ranking de Teamkills ELDAR**:\n\n"
        for i, (user_id, count) in enumerate(ranking[:10], start=1):
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            top_text += f"**{i}.** {get_display_name(user)} — {count} teamkill(s)\n"
        await interaction.followup.send(top_text)
    except Exception as e:
        print(f"⚠️ Erro em /top: {e}")
        traceback.print_exc()
        await interaction.followup.send("❌ Erro ao gerar ranking.", ephemeral=True)

# ---------------- ADM COMANDOS ----------------
@bot.tree.command(name="zerar", description="Reseta o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer resetar")
@app_commands.default_permissions(administrator=True)
async def zerar(interaction: discord.Interaction, usuario: discord.User):
    await interaction.response.defer()
    try:
        user_counters[str(usuario.id)] = 0
        save_data()
        log_action(f"[ZERAR] {get_display_name(interaction.user)} resetou o contador de {get_display_name(usuario)} ({usuario.id})")
        await interaction.followup.send(f"🔄 O contador de {get_display_name(usuario)} foi resetado para 0.")
    except Exception as e:
        print(f"⚠️ Erro em /zerar: {e}")
        traceback.print_exc()
        await interaction.followup.send("❌ Erro ao resetar contador.", ephemeral=True)

@bot.tree.command(name="remover", description="Diminui em 1 o contador de um usuário (apenas admins).")
@app_commands.describe(usuario="Usuário que você quer diminuir o contador")
@app_commands.default_permissions(administrator=True)
async def remover(interaction: discord.Interaction, usuario: discord.User):
    await interaction.response.defer()
    try:
        user_id = str(usuario.id)
        if user_id in user_counters and user_counters[user_id] > 0:
            user_counters[user_id] -= 1
            save_data()
            log_action(f"[REMOVER] {get_display_name(interaction.user)} diminuiu o contador de {get_display_name(usuario)} ({usuario.id}) → {user_counters[user_id]}")
            await interaction.followup.send(f"➖ O contador de {get_display_name(usuario)} foi diminuído para {user_counters[user_id]}.")
        else:
            await interaction.followup.send(f"⚠️ O contador de {get_display_name(usuario)} já está em 0 e não pode ser diminuído.")
    except Exception as e:
        print(f"⚠️ Erro em /remover: {e}")
        traceback.print_exc()
        await interaction.followup.send("❌ Erro ao diminuir contador.", ephemeral=True)

@bot.tree.command(name="backup", description="Envia o arquivo data.json (apenas admins).")
@app_commands.default_permissions(administrator=True)
async def backup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        download_file(DATA_FILE)
        log_action(f"[BACKUP] {get_display_name(interaction.user)} exportou o data.json")
        await interaction.followup.send("📂 Aqui está o backup do arquivo `data.json`:", file=discord.File(DATA_FILE))
    except Exception as e:
        print(f"⚠️ Erro em /backup: {e}")
        traceback.print_exc()
        await interaction.followup.send(f"⚠️ Erro ao gerar backup: {e}", ephemeral=True)

@bot.tree.command(name="restaurar", description="Restaura o data.json a partir de um arquivo enviado (apenas admins).")
@app_commands.default_permissions(administrator=True)
async def restaurar(interaction: discord.Interaction, arquivo: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    try:
        if not arquivo.filename.endswith(".json"):
            await interaction.followup.send("⚠️ Envie um arquivo `.json` válido.", ephemeral=True)
            return

        class ConfirmarView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)

            @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.green)
            async def confirmar(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                await interaction_btn.response.defer(ephemeral=True)
                try:
                    file_bytes = await arquivo.read()
                    with open(DATA_FILE, "wb") as f:
                        f.write(file_bytes)

                    global user_counters
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        user_counters = json.load(f)

                    save_data()
                    log_action(f"[RESTAURAR] {get_display_name(interaction.user)} restaurou o data.json")
                    await interaction_btn.followup.send("♻️ O arquivo `data.json` foi restaurado com sucesso!", ephemeral=True)
                except Exception as e:
                    print(f"⚠️ Erro ao confirmar restauração: {e}")
                    traceback.print_exc()
                    try:
                        await interaction_btn.followup.send(f"⚠️ Erro ao restaurar: {e}", ephemeral=True)
                    except:
                        pass

            @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.red)
            async def cancelar(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                try:
                    await interaction_btn.response.edit_message(content="❌ Restauração cancelada.", view=None)
                except:
                    pass

        await interaction.followup.send(
            "⚠️ Tem certeza que deseja **sobrescrever** o arquivo `data.json`?",
            view=ConfirmarView(),
            ephemeral=True
        )
    except Exception as e:
        print(f"⚠️ Erro em /restaurar: {e}")
        traceback.print_exc()
        try:
            await interaction.followup.send(f"⚠️ Erro ao processar restauração: {e}", ephemeral=True)
        except:
            pass

# ---------------- LOGS ----------------
@bot.tree.command(name="logs", description="Mostra os últimos registros (apenas admins).")
@app_commands.default_permissions(administrator=True)
async def logs(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        if not os.path.exists(LOGS_FILE):
            await interaction.followup.send("⚠️ Nenhum log encontrado.", ephemeral=True)
            return
        with open(LOGS_FILE, "r", encoding="utf-8") as f:
            linhas = f.readlines()[-10:]
        texto = "".join(linhas) if linhas else "⚠️ Nenhum log registrado."
        log_action(f"[LOGS] {get_display_name(interaction.user)} consultou os últimos registros")
        await interaction.followup.send(f"📜 **Últimos registros:**\n```\n{texto}\n```", ephemeral=True)
    except Exception as e:
        print(f"⚠️ Erro em /logs: {e}")
        traceback.print_exc()
        await interaction.followup.send(f"⚠️ Erro ao carregar logs: {e}", ephemeral=True)

@bot.tree.command(name="exportlogs", description="Exporta o arquivo completo de logs (apenas admins).")
@app_commands.default_permissions(administrator=True)
async def exportlogs(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        if not os.path.exists(LOGS_FILE):
            await interaction.followup.send("⚠️ Nenhum log encontrado.", ephemeral=True)
            return
        download_logs(LOGS_FILE)
        log_action(f"[EXPORTLOGS] {get_display_name(interaction.user)} exportou o arquivo logs.txt")
        await interaction.followup.send("📤 Aqui está o arquivo `logs.txt`:", file=discord.File(LOGS_FILE), ephemeral=True)
    except Exception as e:
        print(f"⚠️ Erro em /exportlogs: {e}")
        traceback.print_exc()
        await interaction.followup.send(f"⚠️ Erro ao exportar logs: {e}", ephemeral=True)

# ---------------- BACKUP AUTOMÁTICO ----------------
@tasks.loop(minutes=15)
async def backup_drive():
    try:
        if user_counters and os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 2:
            upload_file(DATA_FILE)
            print("☁️ Backup do data.json enviado para o Google Drive")
        else:
            print("⚠️ Backup do data.json ignorado (vazio ou inexistente)")
        if os.path.exists(LOGS_FILE) and os.path.getsize(LOGS_FILE) > 0:
            upload_logs(LOGS_FILE)
            print("☁️ Backup do logs.txt enviado para o Google Drive")
        else:
            print("⚠️ Backup do logs.txt ignorado (vazio ou inexistente)")
    except Exception as e:
        print(f"⚠️ Erro no backup automático: {e}")
        traceback.print_exc()

# ---------------- RESYNC ----------------
@app_commands.default_permissions(administrator=True)
@bot.tree.command(name="resync", description="(ADM) Limpa e resincroniza os comandos (global + 3 guilds).")
async def resync(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        msgs = []
        # limpa comandos globais e ressincroniza global
        try:
            bot.tree.clear_commands(guild=None)
            synced_global = await bot.tree.sync()
            msgs.append(f"🌍 {len(synced_global)} comandos sincronizados globalmente (após limpeza)")
        except Exception as e:
            msgs.append(f"⚠️ Erro ao limpar/sincronizar globalmente: {e}")
            traceback.print_exc()

        # limpa e sincroniza cada guild configurada
        for gid in GUILD_IDS:
            try:
                guild_obj = discord.Object(id=gid)
                bot.tree.clear_commands(guild=guild_obj)
                synced = await bot.tree.sync(guild=guild_obj)
                msgs.append(f"🏠 {len(synced)} comandos ressincronizados na guild {gid}")
            except Exception as e:
                msgs.append(f"⚠️ Erro ao ressincronizar guild {gid}: {e}")
                traceback.print_exc()

        await interaction.followup.send("\n".join(msgs), ephemeral=True)
    except Exception as e:
        print(f"⚠️ Erro em /resync: {e}")
        traceback.print_exc()
        try:
            await interaction.followup.send(f"❌ Erro ao resincronizar: {e}", ephemeral=True)
        except:
            pass

# ---------------- RUN ----------------
bot_token = os.getenv("DISCORD_BOT_TOKEN")
if bot_token:
    try:
        keep_alive()
    except Exception:
        # keep_alive é opcional; segue mesmo se falhar
        pass
    bot.run(bot_token)
else:
    print("❌ DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
