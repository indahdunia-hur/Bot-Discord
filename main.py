# main.py (Diedit untuk View Persisten EkstraVerifikasi)

import discord
from discord.ext import commands
import os
import asyncio
import datetime # Untuk timestamp & timeout
import logging # Untuk logging lebih baik
import time # Untuk start time botinfo/uptime
import pytz # Pastikan pytz diimport juga di main jika dipakai di on_ready/status
import sqlite3 # <<< BARU: Untuk database view persisten

# --- Load variabel dari .env ---
from dotenv import load_dotenv
load_dotenv() # Memuat variabel dari file .env ke environment
# ---------------------------------------------

# --- Impor View dari Cog Ask ---
try:
    # Perlu import class Cog nya juga jika ingin akses methodnya (tapi tidak perlu untuk add_view)
    from cogs.ask import AskView #, AskCog # AskCog mungkin tidak perlu diimpor di sini
    ASK_VIEW_AVAILABLE = True
except ImportError:
    logging.error("Gagal import AskView dari cogs.ask.")
    ASK_VIEW_AVAILABLE = False
# --------------------------------

# --- BARU: Impor View dan Custom ID dari Cog EkstraVerifikasi ---
try:
    from cogs.ekstra_verifikasi import VerificationStartView, CUSTOM_ID_PERSISTENT_VERIF_BUTTON
    EKSTRA_VERIFIKASI_VIEW_AVAILABLE = True
except ImportError:
    logging.error("Gagal import VerificationStartView/CUSTOM_ID_PERSISTENT_VERIF_BUTTON dari cogs.ekstra_verifikasi.")
    EKSTRA_VERIFIKASI_VIEW_AVAILABLE = False
# -------------------------------------------------------------

# --- Konfigurasi Logging ---
# (Konfigurasi logging tetap sama)
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log = logging.getLogger(__name__) # Logger utama

# --- Konfigurasi Bot ---
# (Konfigurasi bot lainnya tetap sama)
BOT_PREFIX = "?"
ALLOWED_CHANNEL_ID = 1288467928219652109
VERIFICATION_CHANNEL_ID = 1276540177413701723
STATUS_CHANNEL_ID = 1256150623246614609
UNVERIFIED_ROLE_ID = 1249295746935689246
VERIFIED_ROLE_ID = 1247424846695235594

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.moderation = True

BAD_WORDS = { "anjing", "bangsat", "kontol", "memek", "ngentot", "bgst", "anjg", "kntl",}

# Buat objek Bot
class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_message_id = None
        self.start_time = time.time()
        self.db_verif_conn = None # <<< BARU: Atribut untuk koneksi DB verifikasi

    async def setup_hook(self):
        log.info("Memulai setup_hook...")

        # --- BARU: Inisialisasi Koneksi Database untuk Verifikasi ---
        try:
            self.db_verif_conn = sqlite3.connect('verification_data.db') # Nama file DB
            self.db_verif_conn.row_factory = sqlite3.Row # Akses kolom pakai nama
            log.info("Koneksi database 'verification_data.db' berhasil dibuat/dibuka untuk bot.")
            
            # Pastikan tabel ada (cog juga akan melakukan ini, tapi baik untuk dilakukan di sini juga)
            with self.db_verif_conn as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS verified_users (
                        user_id INTEGER NOT NULL,
                        guild_id INTEGER NOT NULL,
                        verified_at REAL NOT NULL,
                        PRIMARY KEY (user_id, guild_id)
                    )
                ''')
                log.info("Tabel 'verified_users' dipastikan ada oleh setup_hook.")
        except sqlite3.Error as e:
            log.critical(f"GAGAL KONEKSI/SETUP DATABASE 'verification_data.db' di setup_hook: {e}", exc_info=True)
            # Jika DB gagal, view persisten untuk verifikasi tidak bisa didaftarkan dengan koneksi ini
            # Cog akan mencoba membuat koneksi lokal sebagai fallback.
        # -----------------------------------------------------------

        log.info("Memuat Cogs...")
        cogs_loaded = 0
        cog_files = [
            'general.py', 'ask.py', 'fun.py', 'moderation.py', 
            'auto_role.py', 'verifikasi.py', 
            'ekstra_verifikasi.py', # <<< BARU: Pastikan cog ini ada dalam daftar
            'counting.py', 'ticket.py', 'email.py', 'saran.py', 'ngobrol.py', 'gemini_ai.py', 'musik.py', 'games.py', 'bingung.py', 'format.py', 'warn.py', 'level.py',  'channel_filter_cog.py',  'polling.py', 'update.py', 'robdisc.py'
        ]
        extensions = []
        for filename in cog_files:
            filepath = f'./cogs/{filename}'
            if os.path.exists(filepath):
                extensions.append(f'cogs.{filename[:-3]}')
            else:
                log.warning(f"File Cog tidak ditemukan: {filepath}")

        for ext in extensions:
            try:
                await self.load_extension(ext)
                log.info(f'[OK] Loaded Cog: {ext.split(".")[-1]}.py')
                cogs_loaded += 1
            except Exception as e:
                log.error(f'[FAIL] Gagal load cog {ext}. Error: {e}', exc_info=True)

        log.info(f"------\n{cogs_loaded}/{len(extensions)} Cogs loaded.")

        # Register Persistent View dari AskCog
        if ASK_VIEW_AVAILABLE:
            try: # Tambahkan try-except untuk pendaftaran view
                self.add_view(AskView()) 
                log.info("AskView persistent view terdaftar.")
            except Exception as e:
                log.error(f"Gagal mendaftarkan AskView: {e}", exc_info=True)
        else:
            log.warning("AskView tidak di-register karena gagal import.")

        # --- BARU: Register Persistent View dari EkstraVerifikasiCog ---
        if EKSTRA_VERIFIKASI_VIEW_AVAILABLE and self.db_verif_conn:
            try:
                # Buat instance view dengan koneksi DB dari bot
                persistent_ekstra_verif_view = VerificationStartView(bot=self, db_conn=self.db_verif_conn)
                self.add_view(persistent_ekstra_verif_view)
                log.info(f"VerificationStartView (EkstraVerifikasi) persistent view dengan custom_id tombol '{CUSTOM_ID_PERSISTENT_VERIF_BUTTON}' telah ditambahkan.")
            except Exception as e:
                log.error(f"Gagal mendaftarkan VerificationStartView (EkstraVerifikasi): {e}", exc_info=True)
        elif not EKSTRA_VERIFIKASI_VIEW_AVAILABLE:
            log.warning("VerificationStartView (EkstraVerifikasi) tidak di-register karena gagal import.")
        elif not self.db_verif_conn:
            log.warning("VerificationStartView (EkstraVerifikasi) tidak di-register karena koneksi DB gagal.")
        # -----------------------------------------------------------------
        
        log.info("Setup_hook selesai.")

    async def on_ready(self):
        # (Fungsi on_ready tetap sama)
        print(f'Logged in as {self.user.name} ({self.user.id})')
        print(f'Prefix: {BOT_PREFIX}'); print(f'Cmd Ch: {ALLOWED_CHANNEL_ID}'); print(f'Verif Ch: {VERIFICATION_CHANNEL_ID}'); print(f'Status Ch: {STATUS_CHANNEL_ID}'); print('------')
        await self.post_status_message()
        await self.update_presence()

    async def post_status_message(self):
        # (Fungsi post_status_message tetap sama)
        channel = self.get_channel(STATUS_CHANNEL_ID);
        if not channel: log.warning(f"Status channel {STATUS_CHANNEL_ID} not found."); return
        try: 
            async for msg in channel.history(limit=10):
                if msg.author.id == self.user.id: await msg.delete(); log.info(f"Deleted old status msg {msg.id}"); await asyncio.sleep(0.5)
        except discord.Forbidden: log.error(f"Error deleting old status msg: Bot lacks permissions in {STATUS_CHANNEL_ID}.")
        except Exception as e: log.error(f"Error deleting old status msg: {e}")
        try: 
            embed = discord.Embed(title="🚀 Bot Online & Siap!", description=f"{self.user.mention} siap melayani.", color=discord.Color.green(), timestamp=datetime.datetime.now(pytz.utc))
            embed.add_field(name="Prefix", value=f"`{BOT_PREFIX}`", inline=True); embed.add_field(name="Command Channel", value=f"<#{ALLOWED_CHANNEL_ID}>", inline=True); embed.add_field(name="Verif Channel", value=f"<#{VERIFICATION_CHANNEL_ID}>", inline=True)
            embed.add_field(name="Perintah", value=f"{len(self.commands)}", inline=True); embed.add_field(name="Online Sejak", value=f"<t:{int(self.start_time)}:R>", inline=True)
            embed.set_footer(text=f"ID: {self.user.id}");
            if self.user.avatar: embed.set_thumbnail(url=self.user.avatar.url)
            msg = await channel.send(embed=embed); self.status_message_id = msg.id
            log.info(f"Status online msg sent (ID: {self.status_message_id}) to channel {STATUS_CHANNEL_ID}")
        except discord.Forbidden: log.error(f"Error sending status msg: Bot lacks permissions in {STATUS_CHANNEL_ID}.")
        except Exception as e: log.error(f"Error sending status msg: {e}")

    async def update_presence(self):
        # (Fungsi update_presence tetap sama)
        try: await self.change_presence(status=discord.Status.idle, activity=discord.Game(name=f"{BOT_PREFIX}help | Server Ngobrol")); log.info("Bot presence updated.")
        except Exception as e: log.error(f"Failed set presence: {e}")

    # --- BARU: Method close untuk menutup koneksi DB ---
    async def close(self):
        log.info("Menerima sinyal untuk menutup bot...")
        if self.db_verif_conn: # Tutup koneksi DB verifikasi jika ada
            try:
                self.db_verif_conn.close()
                log.info("Koneksi database 'verification_data.db' berhasil ditutup.")
            except sqlite3.Error as e:
                log.error(f"Error saat menutup koneksi database 'verification_data.db': {e}")
        
        log.info("Memanggil super().close() untuk cleanup lanjutan...")
        await super().close() # Panggil close dari parent class untuk cleanup lainnya
        log.info("Bot berhasil ditutup sepenuhnya.")
    # -------------------------------------------------

# Buat instance bot
bot = MyBot(command_prefix=BOT_PREFIX, intents=intents, help_command=None) # help_command=None jika kamu punya help custom

# --- Global Check: Batasi Channel ---
# (Fungsi restrict_or_allow_channels tetap sama)
@bot.check
async def restrict_or_allow_channels(ctx: commands.Context):
    if ctx.guild is None: return False
    if not ctx.command: return False
    if isinstance(ctx.author, discord.Member): can_manage_messages = ctx.channel.permissions_for(ctx.author).manage_messages
    else: can_manage_messages = False
    command_name = ctx.command.qualified_name
    if can_manage_messages: return command_name != 'verifikasi' or ctx.channel.id == VERIFICATION_CHANNEL_ID
    else: return (command_name == 'verifikasi' and ctx.channel.id == VERIFICATION_CHANNEL_ID) or (command_name != 'verifikasi' and ctx.channel.id == ALLOWED_CHANNEL_ID)


# --- Event Listener on_message ---
# (Fungsi on_message tetap sama)
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None or not message.content: return
    if message.channel.id == VERIFICATION_CHANNEL_ID:
        try:
            is_verify_command = message.content.strip().lower().startswith(f"{BOT_PREFIX}verifikasi")
            if isinstance(message.author, discord.Member):
                can_manage_messages = message.channel.permissions_for(message.author).manage_messages
                if not is_verify_command and not can_manage_messages:
                    verified_role = message.guild.get_role(VERIFIED_ROLE_ID)
                    has_verified_role = verified_role in message.author.roles if verified_role else False
                    if not has_verified_role:
                        log.info(f"Unverified user {message.author} sent non-verify msg in verify channel: {message.content[:50]}")
                        try: await message.delete()
                        except Exception: pass
                        try: await message.channel.send(f"{message.author.mention}, channel ini hanya untuk `{BOT_PREFIX}verifikasi`.", delete_after=10)
                        except Exception: pass
                        return
            # else: log.warning(f"message.author bukan Member di on_message verify check? User: {message.author}") # Hati-hati dengan log ini, bisa jadi spam jika ada webhook, dll.
        except Exception as e: log.error(f"Error in on_message verify channel check: {e}")
    
    # Filter Kata Kasar (kode tetap sama)
    if message.guild.me.guild_permissions.moderate_members and isinstance(message.author, discord.Member) and not message.author.guild_permissions.administrator:
        msg_lower = message.content.lower(); cleaned_msg = f" {msg_lower} "
        found = next((word for word in BAD_WORDS if f" {word} " in cleaned_msg or msg_lower.startswith(f"{word} ") or msg_lower.endswith(f" {word}") or msg_lower == word), None)
        if found:
            try:
                log_channel = bot.get_channel(ALLOWED_CHANNEL_ID); member = message.author
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    try: await message.delete(); log.info(f"Deleted bad word message from {member}")
                    except Exception as del_err: log.warning(f"Failed to delete bad word msg: {del_err}")
                duration = datetime.timedelta(minutes=30)
                await member.timeout(duration, reason=f"Auto: Kata kasar ('{found}')"); log.info(f"[MOD ACTION] {member} timed out 30m (Word: {found})")
                notif = f"   {member.mention} ditimer 30 menit (Auto: Kata kasar terdeteksi)."
                if log_channel:
                    try: await log_channel.send(notif, delete_after=60)
                    except Exception: pass
                try: await member.send(f"Anda ditimer 30 menit di server **{message.guild.name}** karena kata kasar (`{found}`).")
                except Exception: pass
                return # Setelah timeout, jangan proses command lagi untuk pesan ini
            except discord.Forbidden: log.error(f"Failed to timeout {member} (Word: {found}): Bot missing permissions.")
            except Exception as e: log.error(f"Error during auto-timeout for {member} (Word: {found}): {e}")
            
    await bot.process_commands(message)

# --- General Error Handler ---
# (Fungsi on_command_error tetap sama)
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): pass
    elif isinstance(error, commands.CheckFailure): log.warning(f"Cmd '{ctx.command}' blocked by check: {ctx.author} in #{ctx.channel.name}")
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send(f"Argumen `{error.param.name}` kurang. Cek `{BOT_PREFIX}help {ctx.command.qualified_name}`.", delete_after=15)
    elif isinstance(error, commands.MissingPermissions): await ctx.send(f"{ctx.author.mention}, kamu nggak punya izin.", delete_after=15)
    elif isinstance(error, commands.BotMissingPermissions): perms = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions); await ctx.send(f"Aku perlu izin: {perms}.", delete_after=20)
    elif isinstance(error, commands.CommandOnCooldown): await ctx.send(f"Command `{BOT_PREFIX}{ctx.command.name}` cooldown, coba lagi **{error.retry_after:.1f} detik**.", delete_after=10)
    elif isinstance(error, commands.UserInputError): await ctx.send(f"Input salah. Cek `{BOT_PREFIX}help {ctx.command.qualified_name}`.", delete_after=15)
    elif isinstance(error, commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.Forbidden): log.warning(f"Forbidden Error cmd {ctx.command}: {original}"); await ctx.send(f"Gagal: Aku nggak punya izin Discord.", delete_after=15)
        else: log.error(f'Unhandled invoke error cmd {ctx.command}:', exc_info=error); await ctx.send(f"Error internal cmd `{ctx.command.name}`.", delete_after=15)
    else: log.error(f'Unhandled command error type {type(error)} for cmd {ctx.command}:', exc_info=error); await ctx.send("Error tidak diketahui.", delete_after=15)


# --- Menjalankan Bot ---
if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN is None:
        print("="*30); print("!!! ERROR: DISCORD_TOKEN tidak ditemukan di environment variables ATAU file .env !!!"); print("="*30)
    else:
        log.info("Mencoba menjalankan bot...")
        try:
            # import pytz # Sudah diimport di atas
            bot.run(TOKEN, log_handler=None) # log_handler=None jika sudah setup basicConfig
        except discord.PrivilegedIntentsRequired: log.exception("Fatal Error: Intents belum diaktifkan!"); print("\n!!! ERROR: Intents belum diaktifkan! Aktifkan di Developer Portal. !!!")
        except discord.errors.LoginFailure as e: log.exception(f"Fatal Error: Login Gagal - {e}"); print(f"\n!!! ERROR LOGIN: {e} !!!"); print("PASTIKAN TOKEN BOT SUDAH BENAR DI FILE .env.")
        except ImportError as e:
             if 'pytz' in str(e).lower(): log.exception("Fatal Error: 'pytz' belum terinstall."); print("\n!!! ERROR: 'pytz' belum terinstall! Jalankan 'pip install pytz' !!!")
             elif 'dotenv' in str(e).lower(): log.exception("Fatal Error: 'dotenv' belum terinstall."); print("\n!!! ERROR: 'python-dotenv' belum terinstall! Jalankan 'pip install python-dotenv' !!!")
             else: log.exception("Fatal Error: Gagal import library."); print(f"\n!!! ERROR IMPORT: {e} !!!")
        except Exception as e: log.exception("Fatal error saat menjalankan bot:"); print(f"\n!!! ERROR FATAL: {e} !!!")

