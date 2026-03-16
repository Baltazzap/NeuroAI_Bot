import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select, button
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone  # ✅ Добавлено timezone
from collections import defaultdict, deque
import re

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("❌ Ошибка: токен не найден в переменных окружения (.env)")
    exit()

# --- НАСТРОЙКИ ИНТЕНТОВ ---
intents = discord.Intents.all()
intents.message_content = True

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

# --- КОНФИГУРАЦИЯ ---
WELCOME_CHANNEL_ID = 1482814888509444298
RULES_CHANNEL_ID = 1482815082437284031
LOGS_CHANNEL_ID = 1482817870164656250
AUTO_ROLE_ID = 1482807093286142083
TICKET_CATEGORY_ID = 1482817236984008714
BOT_OWNER_ID = 314805583788244993
MUTE_ROLE_ID = 1482813904697692360

ADMIN_ROLE_IDS = [
    1482807083937169562, 1482807085791182978, 1482807086302760960,
    1482813905293017270, 1482813906085740724,
]

# --- НАСТРОЙКИ АВТО-МОДЕРАЦИИ ---
AUTO_MOD_CONFIG = {
    "spam_threshold": 5,
    "spam_time_window": 10,
    "mention_threshold": 5,
    "link_allowed_channels": [WELCOME_CHANNEL_ID, RULES_CHANNEL_ID],
    "bad_words": ["спам", "скам", "накрутка"],
    "raid_threshold": 10,
    "raid_time_window": 300,
    "new_account_threshold": 7,
}

# --- ХРАНИЛИЩА ДАННЫХ ---
message_cooldown = defaultdict(lambda: deque())
join_cooldown = deque()
warns = defaultdict(int)

# --- КАТЕГОРИИ ТИКЕТОВ ---
TICKET_TYPES = {
    "help_player": {
        "label": "Помощь игроку",
        "description": "Вопросы по геймплею, баги, проблемы с доступом, управление персонажем",
        "emoji": "🎫",
        "color": 0x00BFFF
    },
    "report_player": {
        "label": "Жалоба на игрока",
        "description": "Нарушения правил, токсичность, гриферство, неправомерные действия администрации",
        "emoji": "⚠️",
        "color": 0xFF6B6B
    },
    "suggestion": {
        "label": "Предложение",
        "description": "Идеи по улучшению сервера, новые механики, баланс, контент",
        "emoji": "💡",
        "color": 0xFFD700
    },
    "tech_support": {
        "label": "Техническая поддержка",
        "description": "Проблемы с лаунчером, подключением, донатом, установкой модов",
        "emoji": "🔧",
        "color": 0x9D00FF
    },
    "rp_event": {
        "label": "Сюжет и ивент",
        "description": "Предложения по ролевым событиям, историям, сотрудничество с фракциями",
        "emoji": "🎭",
        "color": 0xE91E63
    }
}

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: ЛОГИ ---
async def send_log(bot, title, description, color, fields=None, thumbnail=None):
    try:
        logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
        if logs_channel is None:
            return
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
        if fields:
            for field in fields:
                embed.add_field(**field)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text="🤖 NeuroAI system logs")
        await logs_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Ошибка отправки лога: {e}")

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: ПРОВЕРКА ПРАВ АДМИНА ---
def is_admin(member):
    return any(role.id in ADMIN_ROLE_IDS for role in member.roles) or member.id == BOT_OWNER_ID

# --- КНОПКА ПОДТВЕРЖДЕНИЯ ЗАКРЫТИЯ ---
class ConfirmCloseView(View):
    def __init__(self, channel: discord.TextChannel, user: discord.Member):
        super().__init__(timeout=60)
        self.channel = channel
        self.user = user
    
    @button(style=discord.ButtonStyle.success, label="Да, закрыть", emoji="✅", custom_id="confirm_close_btn")
    async def confirm_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Не ваше действие.", ephemeral=True)
            return
        await send_log(
            bot, "🔒 Тикет закрыт",
            f"{self.channel.mention} закрыт пользователем {self.user.mention}",
            0x2ECC71,
            [
                {"name": "📋 Канал", "value": f"`{self.channel.name}`", "inline": True},
                {"name": "👤 Закрыл", "value": f"`{self.user.name}`", "inline": True}
            ]
        )
        await interaction.response.defer()
        await self.channel.delete(reason="Тикет закрыт")
    
    @button(style=discord.ButtonStyle.secondary, label="Отмена", emoji="❌", custom_id="cancel_close_btn")
    async def cancel_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Не ваше действие.", ephemeral=True)
            return
        await interaction.response.edit_message(content="✅ Закрытие отменено.", view=None)

# --- SELECT MENU ДЛЯ ВЫБОРА КАТЕГОРИИ ---
class TicketCategorySelect(Select):
    def __init__(self, user: discord.Member):
        options = [
            discord.SelectOption(
                label=config["label"],
                value=key,
                emoji=config["emoji"],
                description=config["description"][:100] + "..." if len(config["description"]) > 100 else config["description"]
            )
            for key, config in TICKET_TYPES.items()
        ]
        super().__init__(
            placeholder="📋 Выберите категорию обращения...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select"
        )
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        config = TICKET_TYPES[ticket_type]
        await self.create_ticket(interaction, ticket_type, config)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, config: dict):
        user = self.user
        
        base_name = user.name.lower().replace(' ', '-').replace('_', '-')
        sanitized_name = ''.join(c for c in base_name if c.isalnum() or c == '-')
        channel_name = f"ticket-{sanitized_name}"
        
        existing_channels = [ch for ch in interaction.guild.channels if ch.name == channel_name and ch.category_id == TICKET_CATEGORY_ID]
        if existing_channels:
            channel_name = f"{channel_name}-{user.discriminator}"
        
        for channel in interaction.guild.channels:
            if channel.name.startswith(f"ticket-{sanitized_name}") and channel.category_id == TICKET_CATEGORY_ID:
                await interaction.response.send_message(
                    f"⚠️ У вас уже есть открытый тикет: {channel.mention}",
                    ephemeral=True
                )
                return
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_id in ADMIN_ROLE_IDS:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        
        category = bot.get_channel(TICKET_CATEGORY_ID)
        
        if category is None:
            await interaction.response.send_message("⚠️ Категория для тикетов не найдена!", ephemeral=True)
            return
            
        new_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Тикет: {user.name} — {config['label']}"
        )
        
        embed = discord.Embed(
            title=f"{config['emoji']} {config['label']}",
            description=(
                f"{user.mention}, ваш тикет успешно создан!\n\n"
                f"📋 Детали обращения:\n"
                f"• Категория: `{config['label']}`\n"
                f"• Описание: {config['description']}\n"
                f"• Создан: <t:{int(datetime.now(timezone.utc).timestamp())}:R>\n"
                f"• Статус: `🟡 Ожидает ответа`\n\n"
                f"💬 Что дальше?\n"
                f"Опишите вашу ситуацию максимально подробно. Администрация ответит в ближайшее время."
            ),
            color=config["color"],
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url="https://i.imgur.com/hbG3hwa.png")
        embed.set_footer(text="🤖 AI кардинал | Система поддержки")
        
        owner_username = channel_name.replace('ticket-', '').split('-')[0] if '-' in channel_name else channel_name.replace('ticket-', '')
        view = TicketView(owner_username)
        
        await new_channel.send(embed=embed, view=view)
        await new_channel.send(f"🔔 На связи: {user.mention}")
        
        await send_log(
            bot, "🎫 Тикет создан",
            f"{user.mention} создал тикет: {config['label']}",
            config["color"],
            [
                {"name": "📋 Категория", "value": f"`{config['label']}`", "inline": True},
                {"name": "🆔 Канал", "value": f"{new_channel.mention} (`{channel_name}`)", "inline": True},
                {"name": "👤 Пользователь", "value": f"`{user.name} ({user.id})`", "inline": False}
            ],
            user.avatar.url if user.avatar else None
        )
        
        await interaction.response.send_message(
            f"✅ Тикет создан: {new_channel.mention}\n📋 Категория: `{config['label']}`",
            ephemeral=True
        )

# --- VIEW ДЛЯ ТИКЕТА ---
class TicketView(View):
    def __init__(self, owner_username: str):
        super().__init__(timeout=None)
        self.owner_username = owner_username
        
    @button(style=discord.ButtonStyle.danger, label="Закрыть тикет", emoji="🔒", custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        channel = interaction.channel
        
        is_admin = any(role.id in ADMIN_ROLE_IDS for role in user.roles) or user.id == BOT_OWNER_ID
        channel_owner = channel.name.replace('ticket-', '').split('-')[0] if '-' in channel.name else channel.name.replace('ticket-', '')
        is_owner = channel_owner.lower() == user.name.lower()
        
        if not is_admin and not is_owner:
            await interaction.response.send_message("⚠️ Нет прав для закрытия.", ephemeral=True)
            return
        
        confirm_view = ConfirmCloseView(channel, user)
        await interaction.response.send_message("⚠️ Закрыть тикет?", view=confirm_view, ephemeral=True)
    
    @button(style=discord.ButtonStyle.primary, label="Взять в работу", emoji="👨‍💼", custom_id="claim_ticket_btn")
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if not any(role.id in ADMIN_ROLE_IDS for role in user.roles):
            await interaction.response.send_message("⚠️ Только администрация может брать тикеты в работу.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="👨‍💼 Тикет взят в работу",
            description=f"{user.mention} начал обработку вашего обращения.\nОжидайте ответа в этом канале.",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="🤖 AI кардинал")
        await interaction.channel.send(embed=embed)
        await interaction.response.defer()
        
        await send_log(
            bot, "👨‍💼 Тикет взят в работу",
            f"{user.mention} взял в работу {interaction.channel.mention}",
            0x2ECC71,
            [
                {"name": "👤 Админ", "value": f"`{user.name}`", "inline": True},
                {"name": "📋 Канал", "value": f"`{interaction.channel.name}`", "inline": True}
            ]
        )

# --- КНОПКА: СОЗДАТЬ ОБРАЩЕНИЕ ---
class CreateTicketButton(Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Создать обращение",
            emoji="🎫",
            custom_id="create_ticket_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📋 Выбор категории",
            description="Выберите тип вашего обращения из списка ниже:",
            color=0x9D00FF
        )
        embed.set_footer(text="🤖 AI кардинал")
        
        view = View(timeout=180)
        view.add_item(TicketCategorySelect(interaction.user))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- VIEW ДЛЯ ПАНЕЛИ ТИКЕТОВ ---
class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CreateTicketButton())

# --- КОМАНДА: !tickets ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def tickets(ctx):
    """Создает панель управления тикетами"""
    
    categories_text = "\n\n".join([
        f"**{config['emoji']} {config['label']}**\n{config['description']}"
        for config in TICKET_TYPES.values()
    ])
    
    embed = discord.Embed(
        title="🎫 Система поддержки Neuro_AI",
        description=(
            f"Добро пожаловать в центр поддержки **GTA 5 NeuroAI RolePlay**.\n\n"
            f"Нажмите на кнопку ниже, чтобы создать обращение. Выберите категорию, и система автоматически создаст приватный канал для связи с администрацией.\n\n"
            f"📋 Доступные категории:\n{categories_text}\n\n"
            f"⚡ Преимущества:\n"
            f"• 🔒 Конфиденциальность — тикет видят только вы и администрация\n"
            f"• 📊 Быстрый ответ — среднее время: 15 минут\n"
            f"• 🤖 Прозрачность — статус отслеживается в реальном времени"
        ),
        color=0x9D00FF,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_image(url="https://i.imgur.com/hbG3hwa.png")
    embed.set_footer(text="🤖 AI кардинал | NeuroAI support v5.0")
    
    view = TicketPanelView()
    await ctx.send(embed=embed, view=view)

# ============================================
# 🛡️ СИСТЕМА АВТО-МОДЕРАЦИИ
# ============================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if is_admin(message.author):
        await bot.process_commands(message)
        return
    
    now = datetime.now(timezone.utc)
    
    # Проверка на спам
    message_cooldown[message.author.id].append(now)
    while message_cooldown[message.author.id] and now - message_cooldown[message.author.id][0] > timedelta(seconds=AUTO_MOD_CONFIG["spam_time_window"]):
        message_cooldown[message.author.id].popleft()
    
    if len(message_cooldown[message.author.id]) > AUTO_MOD_CONFIG["spam_threshold"]:
        await mute_user(message.author, "Спам", message.channel)
        message_cooldown[message.author.id].clear()
        return
    
    # Проверка на массовые упоминания
    if len(message.mentions) > AUTO_MOD_CONFIG["mention_threshold"]:
        await mute_user(message.author, "Массовые упоминания", message.channel)
        return
    
    # Проверка на ссылки
    if message.channel.id not in AUTO_MOD_CONFIG["link_allowed_channels"]:
        url_pattern = r'https?://\S+|www\.\S+'
        if re.search(url_pattern, message.content):
            await message.delete()
            await mute_user(message.author, "Отправка ссылок", message.channel)
            return
    
    # Проверка на стоп-слова
    content_lower = message.content.lower()
    for bad_word in AUTO_MOD_CONFIG["bad_words"]:
        if bad_word in content_lower:
            await message.delete()
            await mute_user(message.author, f"Стоп-слово: {bad_word}", message.channel)
            return
    
    # Проверка на капс
    if len(message.content) > 10:
        caps_ratio = sum(1 for c in message.content if c.isupper()) / len(message.content)
        if caps_ratio > 0.7:
            await message.delete()
            await mute_user(message.author, "Злоупотребление капсом", message.channel)
            return
    
    await bot.process_commands(message)

# --- ФУНКЦИЯ: МУТ ПОЛЬЗОВАТЕЛЯ ---
async def mute_user(member, reason, channel=None):
    try:
        mute_role = discord.Object(id=MUTE_ROLE_ID)
        await member.add_roles(mute_role, reason=f"AutoMod: {reason}")
        
        if channel:
            try:
                async for msg in channel.history(limit=100):
                    if msg.author == member:
                        await msg.delete()
            except:
                pass
        
        await send_log(
            bot, "🔇 Пользователь заглушен (AutoMod)",
            f"{member.mention} получил мут автоматически.",
            0xFF6B6B,
            [
                {"name": "👤 Пользователь", "value": f"`{member.name} ({member.id})`", "inline": True},
                {"name": "📋 Причина", "value": f"`{reason}`", "inline": True},
                {"name": "⏱️ Длительность", "value": "`Навсегда`", "inline": True}
            ],
            member.avatar.url if member.avatar else None
        )
        
        try:
            await member.send(f"⚠️ Вы были заглушены автоматически.\n**Причина:** {reason}\n\nОбратитесь в тикет для разблокировки.")
        except:
            pass
    except Exception as e:
        print(f"⚠️ Ошибка при муте: {e}")

# ============================================
# 👤 ПРИВЕТСТВИЕ И АВТО-РОЛЬ
# ============================================

@bot.event
async def on_member_join(member):
    """Обработка нового участника — приветствие + авто-роль + анти-рейд"""
    now = datetime.now(timezone.utc)  # ✅ Исправлено: используем timezone.utc
    
    # Добавляем в очередь для анти-рейда
    join_cooldown.append((member, now))
    
    # Удаляем старые записи
    while join_cooldown and now - join_cooldown[0][1] > timedelta(seconds=AUTO_MOD_CONFIG["raid_time_window"]):
        join_cooldown.popleft()
    
    # Проверка на рейд
    if len(join_cooldown) > AUTO_MOD_CONFIG["raid_threshold"]:
        await send_log(
            bot, "🚨 Обнаружен рейд!",
            f"Зафиксирован массовый вход пользователей ({len(join_cooldown)} за {AUTO_MOD_CONFIG['raid_time_window']} сек).",
            0xFF0000,
            [
                {"name": "🔒 Режим защиты", "value": "`Активирован`", "inline": True},
                {"name": "👥 Вошло пользователей", "value": f"`{len(join_cooldown)}`", "inline": True}
            ]
        )
        
        for new_member, join_time in list(join_cooldown):
            if now - join_time < timedelta(seconds=AUTO_MOD_CONFIG["raid_time_window"]):
                try:
                    await new_member.ban(reason="AutoMod: Рейд")
                    await send_log(
                        bot, "🔨 Пользователь забанен (Anti-Raid)",
                        f"{new_member.mention} забанен за участие в рейде.",
                        0xFF0000,
                        [
                            {"name": "👤 Пользователь", "value": f"`{new_member.name}`", "inline": True},
                            {"name": "📅 Аккаунт создан", "value": f"<t:{int(new_member.created_at.timestamp())}:R>", "inline": True}
                        ]
                    )
                except Exception as e:
                    print(f"⚠️ Не удалось забанить: {e}")
        
        join_cooldown.clear()
        return
    
    # ✅ ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ — ВЫПОЛНЯЕМ ВСЁ ПО ПОРЯДКУ
    
    # 1. Проверка на новый аккаунт
    account_age = (now - member.created_at).days  # ✅ Теперь работает корректно
    if account_age < AUTO_MOD_CONFIG["new_account_threshold"]:
        try:
            await mute_user(member, f"Новый аккаунт ({account_age} дн.)")
        except Exception as e:
            print(f"⚠️ Ошибка при муте нового аккаунта: {e}")
    
    # 2. Авто-выдача роли
    try:
        guild = member.guild
        auto_role = guild.get_role(AUTO_ROLE_ID)
        if auto_role:
            await member.add_roles(auto_role, reason="AutoRole: Новый участник")
            print(f"✅ Авто-роль выдана: {member.name}")
        else:
            print(f"⚠️ Роль {AUTO_ROLE_ID} не найдена на сервере")
    except Exception as e:
        print(f"❌ Ошибка выдачи авто-роли: {e}")
        await send_log(
            bot, "❌ Ошибка авто-роли",
            f"Не удалось выдать роль {AUTO_ROLE_ID} пользователю {member.mention}",
            0xFF0000,
            [
                {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
                {"name": "❌ Ошибка", "value": f"`{str(e)}`", "inline": False}
            ]
        )
    
    # 3. Приветственное сообщение
    try:
        channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="📡 Обнаружено новое подключение",
                description=(
                    f"**Пользователь:** {member.mention}\n"
                    f"**ID системы:** `{member.id}`\n"
                    f"**Статус:** Синхронизация завершена\n\n"
                    f"Добро пожаловать в **GTA 5 NeuroAI RolePlay**.\n"
                    f"Вам автоматически выдана роль доступа к системе.\n\n"
                    f"⚠️ Внимание: нарушение протоколов приведет к блокировке доступа."
                ),
                color=0x9D00FF,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="📜 Ознакомление с протоколами",
                value=f"Внимательно изучите правила в канале <#{RULES_CHANNEL_ID}>",
                inline=False
            )
            embed.set_footer(text="🤖 AI кардинал | NeuroAI system v1.0")
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            await channel.send(embed=embed)
            print(f"✅ Приветствие отправлено: {member.name}")
        else:
            print(f"⚠️ Канал приветствий {WELCOME_CHANNEL_ID} не найден")
    except Exception as e:
        print(f"❌ Ошибка отправки приветствия: {e}")
    
    # 4. Лог входа
    try:
        await send_log(
            bot, "👤 Новый пользователь",
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
    except Exception as e:
        print(f"⚠️ Ошибка отправки лога входа: {e}")

@bot.event
async def on_member_remove(member):
    await send_log(
        bot, "👤 Пользователь покинул систему",
        f"{member.mention} отключился от симуляции.",
        0xDC143C,
        [
            {"name": "🆔 ID", "value": f"`{member.id}`", "inline": True},
            {"name": "📛 Ник", "value": f"`{member.name}`", "inline": True},
            {"name": "📅 Был на сервере", "value": f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "N/A", "inline": True}
        ],
        member.avatar.url if member.avatar else None
    )

# ============================================
# ⚙️ АДМИН-КОМАНДЫ
# ============================================

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason: str = "Нарушение правил"):
    """Заглушить пользователя"""
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", ephemeral=True)
        return
    
    mute_role = discord.Object(id=MUTE_ROLE_ID)
    await member.add_roles(mute_role, reason=f"Moderator: {reason}")
    
    await send_log(
        bot, "🔇 Пользователь заглушен",
        f"{member.mention} получил мут от {ctx.author.mention}.",
        0xFF6B6B,
        [
            {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
            {"name": "👮 Модератор", "value": f"`{ctx.author.name}`", "inline": True},
            {"name": "📋 Причина", "value": f"`{reason}`", "inline": False}
        ]
    )
    await ctx.send(f"✅ {member.mention} заглушен. Причина: {reason}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    """Разглушить пользователя"""
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", ephemeral=True)
        return
    
    mute_role = discord.utils.get(ctx.guild.roles, id=MUTE_ROLE_ID)
    if mute_role in member.roles:
        await member.remove_roles(mute_role, reason=f"Moderator: {ctx.author.name}")
        await send_log(
            bot, "🔊 Пользователь разглушен",
            f"{member.mention} разглушен пользователем {ctx.author.mention}.",
            0x2ECC71,
            [
                {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
                {"name": "👮 Модератор", "value": f"`{ctx.author.name}`", "inline": True}
            ]
        )
        await ctx.send(f"✅ {member.mention} разглушен.")
    else:
        await ctx.send("⚠️ У пользователя нет роли мута.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def warn(ctx, member: discord.Member, *, reason: str = "Нарушение правил"):
    """Выдать предупреждение"""
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", ephemeral=True)
        return
    
    warns[member.id] += 1
    await send_log(
        bot, "⚠️ Пользователь предупреждён",
        f"{member.mention} получил предупреждение от {ctx.author.mention}.",
        0xFFA500,
        [
            {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
            {"name": "👮 Модератор", "value": f"`{ctx.author.name}`", "inline": True},
            {"name": "📋 Причина", "value": f"`{reason}`", "inline": False},
            {"name": "⚠️ Предупреждений", "value": f"`{warns[member.id]}`", "inline": True}
        ]
    )
    await ctx.send(f"⚠️ {member.mention} предупреждён. Причина: {reason}\nВсего предупреждений: {warns[member.id]}/3")
    
    if warns[member.id] >= 3:
        await mute(ctx, member, reason="3 предупреждения")
        warns[member.id] = 0

@bot.command()
@commands.has_permissions(manage_roles=True)
async def warns(ctx, member: discord.Member):
    """Проверить предупреждения пользователя"""
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", ephemeral=True)
        return
    
    await ctx.send(f"📋 У {member.mention} **{warns[member.id]}** предупреждений из 3.")

@bot.command()
@commands.has_permissions(administrator=True)
async def raidmode(ctx, status: str):
    """Включить/выключить режим защиты от рейдов"""
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", ephemeral=True)
        return
    
    if status.lower() in ["on", "вкл", "true"]:
        AUTO_MOD_CONFIG["raid_threshold"] = 3
        await ctx.send("🚨 Режим защиты от рейдов: **ВКЛЮЧЕН**")
        await send_log(bot, "🚨 Режим защиты от рейдов", "Активирован администратором.", 0xFF0000)
    else:
        AUTO_MOD_CONFIG["raid_threshold"] = 10
        await ctx.send("✅ Режим защиты от рейдов: **ВЫКЛЮЧЕН**")
        await send_log(bot, "🚨 Режим защиты от рейдов", "Деактивирован администратором.", 0x2ECC71)

# ============================================
# 🟢 СОБЫТИЯ БОТА
# ============================================

@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.watching, name="за симуляцией NeuroAI")
    )
    print(f"🤖 AI кардинал подключен...")
    print(f"📡 {bot.user.name} | 🆔 {bot.user.id}")
    print(f"🎫 Система тикетов: активна")
    print(f"🛡️ Авто-модерация: активна")
    print(f"🔇 Роль мута: {MUTE_ROLE_ID}")
    print(f"👋 Канал приветствий: {WELCOME_CHANNEL_ID}")
    print(f"🎭 Авто-роль: {AUTO_ROLE_ID}")
    print("-" * 30)
    await send_log(bot, "🟢 Система запущена", "**AI кардинал** подключился.", 0x2ECC71, [
        {"name": "📡 Статус", "value": "`Онлайн (DND)`", "inline": True},
        {"name": "🎫 Тикеты", "value": "`Активны`", "inline": True},
        {"name": "🛡️ Авто-мод", "value": "`Активен`", "inline": True}
    ])

# ============================================
# 🚀 ЗАПУСК
# ============================================

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Ошибка: неверный токен бота.")
    except Exception as e:
        print(f"❌ Критическая ошибка системы: {e}")
