import os
import discord
from discord.ext import commands
from discord.ui import Button, View, Select
from dotenv import load_dotenv
from datetime import datetime

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("❌ ОШИБКА: Токен не найден в переменных окружения (.env)")
    exit()

# --- НАСТРОЙКИ ИНТЕНТОВ ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.bans = True

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = commands.Bot(command_prefix="!", intents=intents)

# --- КОНФИГУРАЦИЯ ---
WELCOME_CHANNEL_ID = 1482814888509444298
RULES_CHANNEL_ID = 1482815082437284031
LOGS_CHANNEL_ID = 1482817870164656250
AUTO_ROLE_ID = 1482807093286142083
TICKET_CATEGORY_ID = 1482817236984008714  # Категория для тикетов
BOT_OWNER_ID = 314805583788244993  # Владелец бота

# Админ-роли с доступом к тикетам
ADMIN_ROLE_IDS = [
    1482807083937169562,  # Главный Администратор
    1482807085791182978,  # Зам Главного
    1482807086302760960,  # Старший Админ
    1482813905293017270,  # Администратор
    1482813906085740724,  # Модератор
]

# --- КАТЕГОРИИ ТИКЕТОВ ---
TICKET_TYPES = {
    "🎫・помощь_игроку": {
        "label": "🎫 Помощь игроку",
        "description": "Вопросы по игре, баги, проблемы с доступом",
        "emoji": "🎫",
        "color": 0x00BFFF
    },
    "⚠️・жалоба_на_игрока": {
        "label": "⚠️ Жалоба на игрока",
        "description": "Нарушения правил, токсичность, гриферство",
        "emoji": "⚠️",
        "color": 0xFF6B6B
    },
    "💡・предложение": {
        "label": "💡 Предложение",
        "description": "Идеи по улучшению сервера и симуляции",
        "emoji": "💡",
        "color": 0xFFD700
    },
    "🔧・техническая_поддержка": {
        "label": "🔧 Техническая поддержка",
        "description": "Проблемы с лаунчером, подключением, донатом",
        "emoji": "🔧",
        "color": 0x9D00FF
    },
    "🎭・сюжет_и_ивент": {
        "label": "🎭 Сюжет и ивент",
        "description": "Предложения по ролевым событиям и историям",
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
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
        if fields:
            for field in fields:
                embed.add_field(**field)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text="🤖 NeuroAI System Logs")
        await logs_channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Ошибка отправки лога: {e}")

# --- КЛАСС: КНОПКА СОЗДАНИЯ ТИКЕТА ---
class TicketButton(Button):
    def __init__(self, ticket_type: str, config: dict):
        super().__init__(style=discord.ButtonStyle.primary, label=config["label"], emoji=config["emoji"], custom_id=f"ticket_{ticket_type}")
        self.ticket_type = ticket_type
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        
        # Проверка: есть ли уже открытый тикет у пользователя
        for channel in interaction.guild.channels:
            if channel.name.startswith(f"ticket-{user.id}-") and channel.category_id == TICKET_CATEGORY_ID:
                await interaction.response.send_message(f"⚠️ У вас уже есть открытый тикет: {channel.mention}", ephemeral=True)
                return
        
        # Создание канала
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        # Добавляем доступ для админов
        for role_id in ADMIN_ROLE_IDS:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        
        channel_name = f"ticket-{user.id}-{self.ticket_type.split('・')[-1]}"
        category = bot.get_channel(TICKET_CATEGORY_ID)
        
        new_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Тикет создан: {user.name} - {self.config['label']}"
        )
        
        # Отправка приветственного сообщения в тикет
        embed = discord.Embed(
            title=f"{self.config['emoji']} {self.config['label']}",
            description=(
                f"{user.mention}, ваш тикет создан.\n"
                f"Опишите вашу проблему или вопрос максимально подробно.\n\n"
                f"📋 **Информация:**\n"
                f"• Тип: `{self.config['description']}`\n"
                f"• Создан: <t:{int(datetime.utcnow().timestamp())}:R>\n"
                f"• Статус: `Ожидает ответа`"
            ),
            color=self.config["color"],
            timestamp=datetime.utcnow()
        )
        embed.set_image(url="https://i.imgur.com/hbG3hwa.png")  # Баннер
        embed.set_footer(text="🤖 AI Кардинал | Система поддержки")
        
        # Кнопка закрытия тикета
        close_button = Button(style=discord.ButtonStyle.danger, label="🔒 Закрыть тикет", emoji="🔒", custom_id="close_ticket")
        view = View()
        view.add_item(close_button)
        
        await new_channel.send(embed=embed, view=view)
        await new_channel.send(f"👥 На связи: {user.mention}")
        
        # Лог
        await send_log(
            bot, "🎫 ТИКЕТ СОЗДАН",
            f"{user.mention} создал тикет в канале {new_channel.mention}",
            self.config["color"],
            [
                {"name": "📋 Тип", "value": f"`{self.config['label']}`", "inline": True},
                {"name": "🆔 ID Канала", "value": f"`{new_channel.id}`", "inline": True},
                {"name": "👤 Пользователь", "value": f"`{user.name} ({user.id})`", "inline": False}
            ],
            user.avatar.url if user.avatar else None
        )
        
        await interaction.response.send_message(f"✅ Тикет создан: {new_channel.mention}", ephemeral=True)

# --- КЛАСС: КНОПКА ЗАКРЫТИЯ ТИКЕТА ---
class CloseTicketButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="🔒 Закрыть тикет", emoji="🔒", custom_id="close_ticket")

    async def callback(self, interaction: discord.Interaction):
        # Проверка прав: только автор тикета или админ
        user = interaction.user
        channel = interaction.channel
        
        is_admin = any(role.id in ADMIN_ROLE_IDS for role in user.roles) or user.id == BOT_OWNER_ID
        is_owner = channel.name.startswith(f"ticket-{user.id}-")
        
        if not is_admin and not is_owner:
            await interaction.response.send_message("⚠️ У вас нет прав для закрытия этого тикета.", ephemeral=True)
            return
        
        # Подтверждение закрытия
        confirm_view = View()
        confirm_view.add_item(Button(style=discord.ButtonStyle.success, label="✅ Подтвердить", custom_id="confirm_close"))
        confirm_view.add_item(Button(style=discord.ButtonStyle.secondary, label="❌ Отмена", custom_id="cancel_close"))
        
        await interaction.response.send_message("⚠️ Вы уверены, что хотите закрыть тикет?", view=confirm_view, ephemeral=True)
        
        # Обработчик подтверждения
        async def confirm_callback(inter: discord.Interaction):
            if inter.user.id != user.id:
                await inter.response.send_message("❌ Это не ваше подтверждение.", ephemeral=True)
                return
            await inter.response.defer()
            
            # Лог перед закрытием
            await send_log(
                bot, "🔒 ТИКЕТ ЗАКРЫТ",
                f"Тикет {channel.mention} закрыт пользователем {user.mention}",
                0x2ECC71,
                [
                    {"name": "📋 Канал", "value": f"`{channel.name}`", "inline": True},
                    {"name": "👤 Закрыл", "value": f"`{user.name}`", "inline": True}
                ]
            )
            await channel.delete(reason="Тикет закрыт пользователем")
        
        async def cancel_callback(inter: discord.Interaction):
            if inter.user.id != user.id:
                await inter.response.send_message("❌ Это не ваше подтверждение.", ephemeral=True)
                return
            await inter.response.edit_message(content="✅ Закрытие отменено.", view=None)
        
        confirm_view.children[0].callback = confirm_callback
        confirm_view.children[1].callback = cancel_callback

# --- SELECT MENU ДЛЯ ВЫБОРА ТИПА ТИКЕТА ---
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=config["label"], value=key, emoji=config["emoji"], description=config["description"])
            for key, config in TICKET_TYPES.items()
        ]
        super().__init__(placeholder="🎫 Выберите тип обращения...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        config = TICKET_TYPES[ticket_type]
        button = TicketButton(ticket_type, config)
        await button.callback(interaction)

# --- КОМАНДА: !tickets ---
@bot.command()
@commands.has_permissions(manage_channels=True)  # Только админы могут вызвать панель
async def tickets(ctx):
    """Создает панель управления тикетами"""
    
    embed = discord.Embed(
        title="🎫 СИСТЕМА ПОДДЕРЖКИ NEURO_AI",
        description=(
            "Добро пожаловать в центр поддержки **GTA 5 NeuroAI RolePlay**.\n\n"
            "Выберите категорию вашего обращения, и система автоматически создаст приватный канал для связи с администрацией.\n\n"
            "⚡ **Преимущества системы:**\n"
            "• 🔒 Полная конфиденциальность — тикет видят только вы и администрация\n"
            "• 📊 Быстрая обработка — среднее время ответа: 15 минут\n"
            "• 🤖 Автоматизация — статус тикета отслеживается в реальном времени"
        ),
        color=0x9D00FF,
        timestamp=datetime.utcnow()
    )
    embed.set_image(url="https://i.imgur.com/hbG3hwa.png")  # Баннер из запроса
    embed.set_footer(text="🤖 AI Кардинал | NeuroAI Support System v2.0")
    
    # Создаем View с кнопками
    view = View(timeout=None)
    
    # Добавляем кнопки для каждой категории
    for ticket_type, config in TICKET_TYPES.items():
        view.add_item(TicketButton(ticket_type, config))
    
    # Альтернатива: Select Menu (раскомментируйте, если хотите выпадающий список вместо кнопок)
    # select = TicketSelect()
    # view.add_item(select)
    
    await ctx.send(embed=embed, view=view)

# --- ОБРАБОТЧИК КНОПКИ ЗАКРЫТИЯ (для старых тикетов) ---
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data.get("custom_id") == "close_ticket":
        button = CloseTicketButton()
        await button.callback(interaction)
    elif interaction.data.get("custom_id") == "confirm_close":
        channel = interaction.channel
        user = interaction.user
        await send_log(
            bot, "🔒 ТИКЕТ ЗАКРЫТ",
            f"Тикет {channel.mention} закрыт пользователем {user.mention}",
            0x2ECC71,
            [
                {"name": "📋 Канал", "value": f"`{channel.name}`", "inline": True},
                {"name": "👤 Закрыл", "value": f"`{user.name}`", "inline": True}
            ]
        )
        await interaction.response.defer()
        await channel.delete(reason="Тикет закрыт пользователем")
    elif interaction.data.get("custom_id") == "cancel_close":
        await interaction.response.edit_message(content="✅ Закрытие отменено.", view=None)

# --- СОБЫТИЯ БОТА (приветствия, логи и т.д.) ---
@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name="за симуляцией NeuroAI"))
    print(f"🤖 AI Кардинал подключен...")
    print(f"📡 Имя: {bot.user.name} | 🆔 ID: {bot.user.id}")
    print(f"🎫 Система тикетов: АКТИВНА")
    print("-" * 30)
    await send_log(bot, "🟢 СИСТЕМА ЗАПУЩЕНА", "**AI Кардинал** подключился к нейросети.", 0x2ECC71, [
        {"name": "📡 Статус", "value": "`Онлайн (DND)`", "inline": True},
        {"name": "🎫 Тикеты", "value": "`Активны`", "inline": True}
    ])

@bot.event
async def on_member_join(member):
    # (Код приветствия из предыдущей версии - сокращено для краткости)
    pass

# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ ОШИБКА: Неверный токен бота.")
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
