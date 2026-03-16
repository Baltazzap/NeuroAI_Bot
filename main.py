import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("❌ ОШИБКА: Токен не найден в переменных окружения (.env)")
    exit()

# --- НАСТРОЙКИ ИНТЕНТОВ (ПРАВА ДОСТУПА) ---
intents = discord.Intents.default()
intents.members = True  # Необходимо для отслеживания входа участников
intents.message_content = True

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = commands.Bot(command_prefix="!", intents=intents)

# --- КОНФИГУРАЦИЯ КАНАЛОВ ---
WELCOME_CHANNEL_ID = 1482814888509444298  # Канал для приветствий
RULES_CHANNEL_ID = 1482815082437284031     # Канал с правилами
LOGS_CHANNEL_ID = 1482817870164656250       # Канал для логов

# --- СОБЫТИЕ: БОТ ЗАПУЩЕН ---
@bot.event
async def on_ready():
    # Устанавливаем статус DND (Не беспокоить)
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name="за симуляцией NeuroAI"))
    
    print(f"🤖 AI Кардинал подключен к системе...")
    print(f"📡 Имя: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🔗 Статус: DND (Не беспокоить)")
    print(f"📊 Серверов: {len(bot.guilds)}")
    print("-" * 30)
    
    # Отправляем сообщение в лог-канал о запуске
    try:
        logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_channel:
            embed = discord.Embed(
                title="🟢 СИСТЕМА ЗАПУЩЕНА",
                description="**AI Кардинал** успешно подключился к нейросети.",
                color=0x2ECC71,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="📡 Статус", value="`Онлайн (DND)`", inline=True)
            embed.add_field(name="🔗 Серверов", value=f"`{len(bot.guilds)}`", inline=True)
            embed.set_footer(text="🤖 NeuroAI System Logs")
            await logs_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Не удалось отправить лог запуска: {e}")

# --- СОБЫТИЕ: НОВЫЙ ПОЛЬЗОВАТЕЛЬ (WELCOME) ---
@bot.event
async def on_member_join(member):
    try:
        # Получаем канал для приветствий
        channel = bot.get_channel(WELCOME_CHANNEL_ID)
        
        if channel is None:
            print(f"⚠️ Канал приветствий {WELCOME_CHANNEL_ID} не найден.")
            return

        # Формируем Embed (Встроенное сообщение)
        embed = discord.Embed(
            title="📡 ОБНАРУЖЕНО НОВОЕ ПОДКЛЮЧЕНИЕ",
            description=(
                f"**Пользователь:** {member.mention}\n"
                f"**ID Системы:** `{member.id}`\n"
                f"**Статус:** Синхронизация...\n\n"
                f"Добро пожаловать в **GTA 5 NeuroAI RolePlay**.\n"
                f"Вы успешно подключились к симуляции. Для получения доступа к нейросети необходимо ознакомиться с протоколами системы.\n\n"
                f"⚠️ **ВНИМАНИЕ:** Нарушение протоколов приведет к блокировке доступа."
            ),
            color=0x9D00FF,  # Неоновый фиолетовый (Цвет Нейро-Ядра)
            timestamp=datetime.utcnow()
        )

        # Добавляем поле с инструкцией (только правила)
        embed.add_field(
            name="📜 ШАГ 1: ОЗНАКОМЛЕНИЕ С ПРОТОКОЛАМИ",
            value=f"Внимательно изучите правила системы в канале <#{RULES_CHANNEL_ID}>\n\nПосле ознакомления ожидайте дальнейших инструкций.",
            inline=False
        )

        # Настройки футера и миниатюры
        embed.set_footer(text="🤖 AI Кардинал | NeuroAI System v1.0", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

        # Отправка сообщения
        await channel.send(embed=embed)
        
        # Логирование в консоль
        print(f"✅ Приветствие отправлено для: {member.name} ({member.id})")
        
        # Отправка лога в лог-канал
        try:
            logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
            if logs_channel:
                log_embed = discord.Embed(
                    title="👤 НОВЫЙ ПОЛЬЗОВАТЕЛЬ",
                    description=f"{member.mention} присоединился к симуляции.",
                    color=0x00BFFF,
                    timestamp=datetime.utcnow()
                )
                log_embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)
                log_embed.add_field(name="📛 Ник", value=f"`{member.name}`", inline=True)
                log_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                log_embed.set_footer(text="📊 NeuroAI Join Logs")
                await logs_channel.send(embed=log_embed)
        except Exception as e:
            print(f"⚠️ Не удалось отправить лог входа: {e}")

    except Exception as e:
        print(f"❌ Ошибка при отправке приветствия: {e}")

# --- СОБЫТИЕ: ПОЛЬЗОВАТЕЛЬ ПОКИНУЛ СЕРВЕР ---
@bot.event
async def on_member_remove(member):
    try:
        logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_channel:
            log_embed = discord.Embed(
                title="👤 ПОЛЬЗОВАТЕЛЬ ПОКИНУЛ СИСТЕМУ",
                description=f"{member.mention} отключился от симуляции.",
                color=0xDC143C,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)
            log_embed.add_field(name="📛 Ник", value=f"`{member.name}`", inline=True)
            log_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            log_embed.set_footer(text="📊 NeuroAI Leave Logs")
            await logs_channel.send(embed=log_embed)
            print(f"✅ Лог выхода отправлен для: {member.name}")
    except Exception as e:
        print(f"⚠️ Не удалось отправить лог выхода: {e}")

# --- ЗАПУСК БОТА ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ ОШИБКА: Неверный токен бота.")
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА СИСТЕМЫ: {e}")
