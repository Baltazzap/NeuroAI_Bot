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
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

# --- КОНФИГУРАЦИЯ ---
WELCOME_CHANNEL_ID = 1482814888509444298
RULES_CHANNEL_ID = 1482815082437284031
LOGS_CHANNEL_ID = 1482817870164656250
AUTO_ROLE_ID = 1482807093286142083
TICKET_CATEGORY_ID = 1482817236984008714
BOT_OWNER_ID = 314805583788244993

ADMIN_ROLE_IDS = [
    1482807083937169562, 1482807085791182978, 1482807086302760960,
    1482813905293017270, 1482813906085740724,
]

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
        
        # Проверка: есть ли уже открытый тикет
        for channel in interaction.guild.channels:
            if channel.name.startswith(f"ticket-{user.id}-") and channel.category_id == TICKET_CATEGORY_ID:
                await interaction.response.send_message(
                    f"⚠️ У вас уже есть открытый тикет: {channel.mention}",
                    ephemeral=True
                )
                return
        
        # Настройка прав доступа
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_id in ADMIN_ROLE_IDS:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        
        # Создание канала
        channel_name = f"ticket-{user.id}-{ticket_type}"
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
        
        # Приветственное сообщение в тикете
        embed = discord.Embed(
            title=f"{config['emoji']} {config['label']}",
            description=(
                f"{user.mention}, ваш тикет успешно создан!\n\n"
                f"📋 **Детали обращения:**\n"
                f"• Категория: `{config['label']}`\n"
                f"• Описание: {config['description']}\n"
                f"• Создан: <t:{int(datetime.utcnow().timestamp())}:R>\n"
                f"• Статус: `🟡 Ожидает ответа`\n\n"
                f"💬 **Что дальше?**\n"
                f"Опишите вашу ситуацию максимально подробно. Администрация ответит в ближайшее время."
            ),
            color=config["color"],
            timestamp=datetime.utcnow()
        )
        embed.set_image(url="https://i.imgur.com/hbG3hwa.png")
        embed.set_footer(text="🤖 AI Кардинал | Система поддержки")
        
        # Кнопки управления (с классами для правильной обработки)
        view = TicketView(user)
        
        await new_channel.send(embed=embed, view=view)
        await new_channel.send(f"🔔 На связи: {user.mention}")
        
        # Лог создания
        await send_log(
            bot, "🎫 ТИКЕТ СОЗДАН",
            f"{user.mention} создал тикет: {config['label']}",
            config["color"],
            [
                {"name": "📋 Категория", "value": f"`{config['label']}`", "inline": True},
                {"name": "🆔 Канал", "value": f"{new_channel.mention}", "inline": True},
                {"name": "👤 Пользователь", "value": f"`{user.name} ({user.id})`", "inline": False}
            ],
            user.avatar.url if user.avatar else None
        )
        
        await interaction.response.send_message(
            f"✅ Тикет создан: {new_channel.mention}\n📋 Категория: `{config['label']}`",
            ephemeral=True
        )

# --- VIEW ДЛЯ ТИКЕТА (с кнопками) ---
class TicketView(View):
    def __init__(self, ticket_owner: discord.Member):
        super().__init__(timeout=None)  # Persistent view
        self.ticket_owner = ticket_owner
        
    @discord.ui.button(style=discord.ButtonStyle.danger, label="Закрыть тикет", emoji="🔒", custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        channel = interaction.channel
        
        is_admin = any(role.id in ADMIN_ROLE_IDS for role in user.roles) or user.id == BOT_OWNER_ID
        is_owner = channel.name.startswith(f"ticket-{self.ticket_owner.id}-")
        
        if not is_admin and not is_owner:
            await interaction.response.send_message("⚠️ Нет прав для закрытия.", ephemeral=True)
            return
        
        # Подтверждение закрытия
        confirm_view = View(timeout=60)
        
        @discord.ui.button(style=discord.ButtonStyle.success, label="✅ Да, закрыть", custom_id="confirm_close_btn")
        async def confirm_callback(inter: discord.Interaction, btn: Button):
            if inter.user.id != user.id:
                await inter.response.send_message("❌ Не ваше действие.", ephemeral=True)
                return
            await send_log(
                bot, "🔒 ТИКЕТ ЗАКРЫТ",
                f"{channel.mention} закрыт пользователем {user.mention}",
                0x2ECC71,
                [
                    {"name": "📋 Канал", "value": f"`{channel.name}`", "inline": True},
                    {"name": "👤 Закрыл", "value": f"`{user.name}`", "inline": True}
                ]
            )
            await inter.response.defer()
            await channel.delete(reason="Тикет закрыт")
        
        @discord.ui.button(style=discord.ButtonStyle.secondary, label="❌ Отмена", custom_id="cancel_close_btn")
        async def cancel_callback(inter: discord.Interaction, btn: Button):
            if inter.user.id != user.id:
                await inter.response.send_message("❌ Не ваше действие.", ephemeral=True)
                return
            await inter.response.edit_message(content="✅ Закрытие отменено.", view=None)
        
        confirm_view.add_item(confirm_callback)
        confirm_view.add_item(cancel_callback)
        
        await interaction.response.send_message("⚠️ Закрыть тикет?", view=confirm_view, ephemeral=True)
    
    @discord.ui.button(style=discord.ButtonStyle.primary, label="👨‍💼 Взять в работу", emoji="👨‍💼", custom_id="claim_ticket_btn")
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if not any(role.id in ADMIN_ROLE_IDS for role in user.roles):
            await interaction.response.send_message("⚠️ Только администрация может брать тикеты в работу.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="👨‍💼 ТИКЕТ ВЗЯТ В РАБОТУ",
            description=f"{user.mention} начал обработку вашего обращения.\nОжидайте ответа в этом канале.",
            color=0x2ECC71,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="🤖 AI Кардинал")
        await interaction.channel.send(embed=embed)
        await interaction.response.defer()
        
        await send_log(
            bot, "👨‍💼 ТИКЕТ ВЗЯТ В РАБОТУ",
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
            title="📋 ВЫБОР КАТЕГОРИИ",
            description="Выберите тип вашего обращения из списка ниже:",
            color=0x9D00FF
        )
        embed.set_footer(text="🤖 AI Кардинал")
        
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
        title="🎫 СИСТЕМА ПОДДЕРЖКИ NEURO_AI",
        description=(
            f"Добро пожаловать в центр поддержки **GTA 5 NeuroAI RolePlay**.\n\n"
            f"Нажмите на кнопку ниже, чтобы создать обращение. Выберите категорию, и система автоматически создаст приватный канал для связи с администрацией.\n\n"
            f"📋 **Доступные категории:**\n{categories_text}\n\n"
            f"⚡ **Преимущества:**\n"
            f"• 🔒 Конфиденциальность — тикет видят только вы и администрация\n"
            f"• 📊 Быстрый ответ — среднее время: 15 минут\n"
            f"• 🤖 Прозрачность — статус отслеживается в реальном времени"
        ),
        color=0x9D00FF,
        timestamp=datetime.utcnow()
    )
    embed.set_image(url="https://i.imgur.com/hbG3hwa.png")
    embed.set_footer(text="🤖 AI Кардинал | NeuroAI Support v2.2")
    
    view = TicketPanelView()
    
    await ctx.send(embed=embed, view=view)

# --- СОБЫТИЯ БОТА ---
@bot.event
async def on_ready():
    # Регистрация постоянных видов (persistent views)
    bot.add_view(TicketPanelView())
    bot.add_view(TicketView(bot.user))  # Placeholder, ticket_owner не важен для регистрации
    
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.watching, name="за симуляцией NeuroAI")
    )
    print(f"🤖 AI Кардинал подключен...")
    print(f"📡 {bot.user.name} | 🆔 {bot.user.id}")
    print(f"🎫 Система тикетов: АКТИВНА")
    print("-" * 30)
    await send_log(bot, "🟢 СИСТЕМА ЗАПУЩЕНА", "**AI Кардинал** подключился.", 0x2ECC71, [
        {"name": "📡 Статус", "value": "`Онлайн (DND)`", "inline": True},
        {"name": "🎫 Тикеты", "value": "`Активны`", "inline": True}
    ])

@bot.event
async def on_member_join(member):
    # (Код приветствия - сокращено)
    pass

# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ ОШИБКА: Неверный токен.")
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
