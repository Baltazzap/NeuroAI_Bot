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
intents.members = True
intents.message_content = True
intents.mod_actions = True

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = commands.Bot(command_prefix="!", intents=intents)

# --- КОНФИГУРАЦИЯ КАНАЛОВ И РОЛЕЙ ---
WELCOME_CHANNEL_ID = 1482814888509444298  # Канал для приветствий
RULES_CHANNEL_ID = 1482815082437284031     # Канал с правилами
LOGS_CHANNEL_ID = 1482817870164656250       # Канал для логов
AUTO_ROLE_ID = 1482807093286142083          # Роль для авто-выдачи

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: ОТПРАВКА ЛОГА ---
async def send_log(bot, title, description, color, fields=None, thumbnail=None):
    """Отправляет лог-сообщение в канал логов"""
    try:
        logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_channel is None:
            print(f"⚠️ Канал логов {LOGS_CHANNEL_ID} не найден.")
            return
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        
        if fields:
            for field in fields:
                embed.add_field(**field)
        
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        embed.set_footer(text="🤖 NeuroAI System Logs")
        await logs_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Ошибка отправки лога: {e}")

# --- СОБЫТИЕ: БОТ ЗАПУЩЕН ---
@bot.event
async def on_ready():
    # Устанавливаем статус DND (Не беспокоить)
    await bot.change_presence(
        status=discord.Status.dnd, 
        activity=discord.Activity(type=discord.ActivityType.watching, name="за симуляцией NeuroAI")
    )
    
    print(f"🤖 AI Кардинал подключен к системе...")
    print(f"📡 Имя: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🔗 Статус: DND (Не беспокоить)")
    print(f"📊 Серверов: {len(bot.guilds)}")
    print(f"👥 Пользователей: {sum(guild.member_count for guild in bot.guilds)}")
    print("-" * 30)
    
    # Лог о запуске
    await send_log(
        bot,
        "🟢 СИСТЕМА ЗАПУЩЕНА",
        "**AI Кардинал** успешно подключился к нейросети.",
        0x2ECC71,
        [
            {"name": "📡 Статус", "value": "`Онлайн (DND)`", "inline": True},
            {"name": "🔗 Серверов", "value": f"`{len(bot.guilds)}`", "inline": True},
            {"name": "👥 Пользователей", "value": f"`{sum(guild.member_count for guild in bot.guilds)}`", "inline": True}
        ]
    )

# --- СОБЫТИЕ: НОВЫЙ ПОЛЬЗОВАТЕЛЬ (WELCOME + AUTO-ROLE) ---
@bot.event
async def on_member_join(member):
    try:
        # 1. Авто-выдача роли
        try:
            auto_role = discord.Object(id=AUTO_ROLE_ID)
            await member.add_roles(auto_role)
            print(f"✅ Роль выдана: {member.name}")
        except Exception as e:
            print(f"⚠️ Не удалось выдать роль: {e}")
        
        # 2. Приветствие в welcome-канале
        channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="📡 ОБНАРУЖЕНО НОВОЕ ПОДКЛЮЧЕНИЕ",
                description=(
                    f"**Пользователь:** {member.mention}\n"
                    f"**ID Системы:** `{member.id}`\n"
                    f"**Статус:** Синхронизация завершена\n\n"
                    f"Добро пожаловать в **GTA 5 NeuroAI RolePlay**.\n"
                    f"Вам автоматически выдана роль доступа к системе.\n\n"
                    f"⚠️ **ВНИМАНИЕ:** Нарушение протоколов приведет к блокировке доступа."
                ),
                color=0x9D00FF,
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="📜 ОЗНАКОМЛЕНИЕ С ПРОТОКОЛАМИ",
                value=f"Внимательно изучите правила в канале <#{RULES_CHANNEL_ID}>",
                inline=False
            )
            embed.set_footer(text="🤖 AI Кардинал | NeuroAI System v1.0")
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            await channel.send(embed=embed)
        
        # 3. Лог входа
        await send_log(
            bot,
            "👤 НОВЫЙ ПОЛЬЗОВАТЕЛЬ",
            f"{member.mention} присоединился к симуляции.",
            0x00BFFF,
            [
                {"name": "🆔 ID", "value": f"`{member.id}`", "inline": True},
                {"name": "📛 Ник", "value": f"`{member.name}`", "inline": True},
                {"name": "🎭 Авто-роль", "value": f"`<@&{AUTO_ROLE_ID}>`", "inline": True},
                {"name": "📅 Аккаунт создан", "value": f"<t:{int(member.created_at.timestamp())}:R>", "inline": False}
            ],
            member.avatar.url if member.avatar else None
        )
        print(f"✅ Приветствие отправлено для: {member.name} ({member.id})")
        
    except Exception as e:
        print(f"❌ Ошибка при обработке входа: {e}")

# --- СОБЫТИЕ: ПОЛЬЗОВАТЕЛЬ ПОКИНУЛ СЕРВЕР ---
@bot.event
async def on_member_remove(member):
    await send_log(
        bot,
        "👤 ПОЛЬЗОВАТЕЛЬ ПОКИНУЛ СИСТЕМУ",
        f"{member.mention} отключился от симуляции.",
        0xDC143C,
        [
            {"name": "🆔 ID", "value": f"`{member.id}`", "inline": True},
            {"name": "📛 Ник", "value": f"`{member.name}`", "inline": True},
            {"name": "📅 Был на сервере", "value": f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "N/A", "inline": True}
        ],
        member.avatar.url if member.avatar else None
    )
    print(f"✅ Лог выхода: {member.name}")

# --- СОБЫТИЕ: СООБЩЕНИЕ УДАЛЕНО ---
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    
    await send_log(
        bot,
        "🗑️ СООБЩЕНИЕ УДАЛЕНО",
        f"Сообщение от {message.author.mention} было удалено.",
        0xFF6B6B,
        [
            {"name": "📛 Автор", "value": f"`{message.author.name}`", "inline": True},
            {"name": "🆔 ID", "value": f"`{message.author.id}`", "inline": True},
            {"name": "📍 Канал", "value": f"{message.channel.mention}", "inline": True},
            {"name": "📝 Содержимое", "value": f"```{message.content[:1000]}```" if message.content else "*Нет текста*", "inline": False}
        ],
        message.author.avatar.url if message.author.avatar else None
    )

# --- СОБЫТИЕ: СООБЩЕНИЕ ИЗМЕНЕНО ---
@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    if before.content == after.content:
        return
    
    await send_log(
        bot,
        "✏️ СООБЩЕНИЕ ИЗМЕНЕНО",
        f"{before.author.mention} отредактировал сообщение.",
        0xFFA500,
        [
            {"name": "📛 Автор", "value": f"`{before.author.name}`", "inline": True},
            {"name": "📍 Канал", "value": f"{before.channel.mention}", "inline": True},
            {"name": "📝 До", "value": f"```{before.content[:500]}```" if before.content else "*Нет текста*", "inline": False},
            {"name": "📝 После", "value": f"```{after.content[:500]}```" if after.content else "*Нет текста*", "inline": False}
        ],
        before.author.avatar.url if before.author.avatar else None
    )

# --- СОБЫТИЕ: ПОЛЬЗОВАТЕЛЬ ЗАБАНЕН ---
@bot.event
async def on_member_ban(guild, user):
    await send_log(
        bot,
        "🔨 ПОЛЬЗОВАТЕЛЬ ЗАБАНЕН",
        f"{user.mention} заблокирован в системе.",
        0xFF0000,
        [
            {"name": "📛 Ник", "value": f"`{user.name}`", "inline": True},
            {"name": "🆔 ID", "value": f"`{user.id}`", "inline": True},
            {"name": "🏷️ Дискриминатор", "value": f"`{user.discriminator}`", "inline": True}
        ],
        user.avatar.url if user.avatar else None
    )

# --- СОБЫТИЕ: ПОЛЬЗОВАТЕЛЬ РАЗБАНЕН ---
@bot.event
async def on_member_unban(guild, user):
    await send_log(
        bot,
        "✅ ПОЛЬЗОВАТЕЛЬ РАЗБАНЕН",
        f"{user.mention} разблокирован в системе.",
        0x2ECC71,
        [
            {"name": "📛 Ник", "value": f"`{user.name}`", "inline": True},
            {"name": "🆔 ID", "value": f"`{user.id}`", "inline": True}
        ],
        user.avatar.url if user.avatar else None
    )

# --- СОБЫТИЕ: ИЗМЕНЕНИЕ РОЛЕЙ ---
@bot.event
async def on_member_update(before, after):
    # Проверка изменений ролей
    before_roles = set(before.roles)
    after_roles = set(after.roles)
    
    added_roles = after_roles - before_roles
    removed_roles = before_roles - after_roles
    
    if added_roles:
        roles_list = ", ".join([r.mention for r in added_roles if not r.is_default()])
        if roles_list:
            await send_log(
                bot,
                "➕ РОЛИ ВЫДАНЫ",
                f"{after.mention} получил новые роли.",
                0x9D00FF,
                [
                    {"name": "📛 Пользователь", "value": f"`{after.name}`", "inline": True},
                    {"name": "🆔 ID", "value": f"`{after.id}`", "inline": True},
                    {"name": "🎭 Новые роли", "value": roles_list, "inline": False}
                ],
                after.avatar.url if after.avatar else None
            )
    
    if removed_roles:
        roles_list = ", ".join([r.mention for r in removed_roles if not r.is_default()])
        if roles_list:
            await send_log(
                bot,
                "➖ РОЛИ СНЯТЫ",
                f"{after.mention} потерял роли.",
                0xFF6B6B,
                [
                    {"name": "📛 Пользователь", "value": f"`{after.name}`", "inline": True},
                    {"name": "🆔 ID", "value": f"`{after.id}`", "inline": True},
                    {"name": "🎭 Снятые роли", "value": roles_list, "inline": False}
                ],
                after.avatar.url if after.avatar else None
            )
    
    # Проверка изменения ника
    if before.nick != after.nick:
        await send_log(
            bot,
            "📛 НИК ИЗМЕНЕН",
            f"{after.mention} сменил никнейм.",
            0x00CED1,
            [
                {"name": "🆔 ID", "value": f"`{after.id}`", "inline": True},
                {"name": "📝 До", "value": f"`{before.nick or before.name}`", "inline": True},
                {"name": "📝 После", "value": f"`{after.nick or after.name}`", "inline": True}
            ],
            after.avatar.url if after.avatar else None
        )

# --- СОБЫТИЕ: ИЗМЕНЕНИЕ КАНАЛА ---
@bot.event
async def on_guild_channel_create(channel):
    await send_log(
        bot,
        "📍 КАНАЛ СОЗДАН",
        f"Канал {channel.mention} был создан.",
        0x2ECC71,
        [
            {"name": "📛 Название", "value": f"`{channel.name}`", "inline": True},
            {"name": "🆔 ID", "value": f"`{channel.id}`", "inline": True},
            {"name": "📂 Тип", "value": f"`{channel.type}`", "inline": True}
        ]
    )

@bot.event
async def on_guild_channel_delete(channel):
    await send_log(
        bot,
        "🗑️ КАНАЛ УДАЛЕН",
        f"Канал `{channel.name}` был удален.",
        0xFF0000,
        [
            {"name": "📛 Название", "value": f"`{channel.name}`", "inline": True},
            {"name": "🆔 ID", "value": f"`{channel.id}`", "inline": True},
            {"name": "📂 Тип", "value": f"`{channel.type}`", "inline": True}
        ]
    )

# --- СОБЫТИЕ: ИЗМЕНЕНИЕ НАСТРОЕК СЕРВЕРА ---
@bot.event
async def on_guild_update(before, after):
    changes = []
    
    if before.name != after.name:
        changes.append(f"Название: `{before.name}` → `{after.name}`")
    if before.icon != after.icon:
        changes.append("Иконка сервера изменена")
    if before.description != after.description:
        changes.append("Описание сервера изменено")
    
    if changes:
        await send_log(
            bot,
            "⚙️ НАСТРОЙКИ СЕРВЕРА ИЗМЕНЕНЫ",
            "Администратор обновил конфигурацию сервера.",
            0xFFD700,
            [
                {"name": "📛 Сервер", "value": f"`{after.name}`", "inline": True},
                {"name": "🆔 ID", "value": f"`{after.id}`", "inline": True},
                {"name": "📝 Изменения", "value": "\n".join(changes), "inline": False}
            ]
        )

# --- ЗАПУСК БОТА ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ ОШИБКА: Неверный токен бота.")
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА СИСТЕМЫ: {e}")
