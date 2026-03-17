import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select, button
from discord.app_commands import CommandTree, describe
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
import re
import asyncio
import aiohttp
import random
import urllib.parse

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
tree = bot.tree

# --- КОНФИГУРАЦИЯ ---
WELCOME_CHANNEL_ID = 1482814888509444298
RULES_CHANNEL_ID = 1482815082437284031
LOGS_CHANNEL_ID = 1482817870164656250
AUTO_ROLE_ID = 1482807093286142083
TICKET_CATEGORY_ID = 1482817236984008714
BOT_OWNER_ID = 314805583788244993
MUTE_ROLE_ID = 1482813904697692360

# ✅ РОЛЬ ПОДДЕРЖКИ
SUPPORT_ROLE_ID = 1483016729172119684

# ✅ РОЛЬ ДЛЯ УПОМИНАНИЯ В ТИКЕТАХ
NOTIFY_ROLE_ID = 1482807077620678949

# ✅ КАНАЛ ДЛЯ ИИ-ГЕНЕРАЦИИ
AI_GENERATION_CHANNEL_ID = 1483021047660806144

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

# --- НАСТРОЙКИ ИИ-ГЕНЕРАЦИИ ---
AI_GENERATION_CONFIG = {
    "cooldown_seconds": 30,
    "max_prompts_per_day": 10,
    "gta_style_prompt": "GTA 5 video game style, cinematic lighting, highly detailed, realistic, 4K, game art, rockstar games style",
    "width": 1024,
    "height": 1024,
}

# --- ХРАНИЛИЩА ДАННЫХ ---
message_cooldown = defaultdict(lambda: deque())
join_cooldown = deque()
warns = defaultdict(int)
mutes = {}
ticket_owners = {}
ai_generation_cooldown = defaultdict(float)
ai_generation_count = defaultdict(int)
ai_generation_date = defaultdict(str)

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

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: ПРОВЕРКА ПРАВ ---
def is_admin(member):
    return any(role.id in ADMIN_ROLE_IDS for role in member.roles) or member.id == BOT_OWNER_ID

def can_manage_tickets(member):
    return (
        any(role.id in ADMIN_ROLE_IDS for role in member.roles) or 
        member.id == BOT_OWNER_ID or
        any(role.id == SUPPORT_ROLE_ID for role in member.roles)
    )

# --- ФУНКЦИЯ: УДАЛЕНИЕ СООБЩЕНИЯ КОМАНДЫ ---
async def delete_command_message(ctx):
    try:
        if hasattr(ctx, 'message') and ctx.message:
            await ctx.message.delete()
    except:
        pass

def delete_command_message_from_interaction(interaction: discord.Interaction):
    asyncio.create_task(_delete_interaction_message(interaction))

async def _delete_interaction_message(interaction: discord.Interaction):
    try:
        await asyncio.sleep(5)
        await interaction.original_response().delete()
    except:
        pass

# ============================================
# 🎨 ИИ-ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ (GTA STYLE)
# ============================================

async def generate_gta_image(prompt: str, seed: int = None):
    """Генерация изображения через Pollinations.ai API (БЕСПЛАТНО)"""
    try:
        enhanced_prompt = f"{prompt}, {AI_GENERATION_CONFIG['gta_style_prompt']}"
        
        if seed is None:
            seed = random.randint(1, 999999)
        
        width = AI_GENERATION_CONFIG["width"]
        height = AI_GENERATION_CONFIG["height"]
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&model=flux&nologo=true"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=30) as response:
                if response.status == 200:
                    return {
                        "success": True,
                        "url": image_url,
                        "prompt": enhanced_prompt,
                        "seed": seed
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API вернул статус {response.status}"
                    }
                    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def check_generation_limit(user_id: int):
    """Проверка лимитов генерации"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if ai_generation_date[user_id] != today:
        ai_generation_date[user_id] = today
        ai_generation_count[user_id] = 0
    
    now = datetime.now().timestamp()
    if now - ai_generation_cooldown[user_id] < AI_GENERATION_CONFIG["cooldown_seconds"]:
        remaining = int(AI_GENERATION_CONFIG["cooldown_seconds"] - (now - ai_generation_cooldown[user_id]))
        return False, f"⏱️ Пожалуйста, подождите ещё **{remaining} сек.**"
    
    if ai_generation_count[user_id] >= AI_GENERATION_CONFIG["max_prompts_per_day"]:
        return False, f"📊 Вы исчерпали дневной лимит (**{AI_GENERATION_CONFIG['max_prompts_per_day']}** генераций)"
    
    return True, None

class AIGenerationView(View):
    def __init__(self, user_id: int, prompt: str, seed: int = None):
        super().__init__(timeout=300)  # 5 минут таймаут
        self.user_id = user_id
        self.prompt = prompt
        self.seed = seed if seed else random.randint(1, 999999)
    
    @button(style=discord.ButtonStyle.primary, label="🔄 Перегенерировать", emoji="🔄", custom_id="ai_regenerate")
    async def regenerate_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Только автор может регенерировать.", ephemeral=True)
            return
        
        allowed, error_msg = check_generation_limit(interaction.user.id)
        if not allowed:
            await interaction.response.send_message(error_msg, ephemeral=True)
            return
        
        ai_generation_cooldown[interaction.user.id] = datetime.now().timestamp()
        ai_generation_count[interaction.user.id] += 1
        
        await interaction.response.defer()
        
        new_seed = random.randint(1, 999999)
        result = await generate_gta_image(self.prompt, new_seed)
        
        if result["success"]:
            embed = discord.Embed(
                title="🎨 ИИ-Генерация (Обновлено)",
                description=f"📝 **Промпт:** {self.prompt[:500]}\n🎲 **Seed:** `{new_seed}`",
                color=0x9D00FF,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_image(url=result["url"])
            embed.set_footer(text="🤖 AI Кардинал | GTA 5 NeuroAI | Pollinations.ai")
            
            await interaction.followup.send(embed=embed, view=AIGenerationView(interaction.user.id, self.prompt, new_seed))
        else:
            await interaction.followup.send(f"❌ Ошибка генерации: {result['error']}", ephemeral=True)
    
    @button(style=discord.ButtonStyle.secondary, label="📥 Скачать", emoji="📥", custom_id="ai_download")
    async def download_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("💡 Нажмите правой кнопкой на изображение → Сохранить как", ephemeral=True)

@bot.command(name="ai", aliases=["генерация", "gta", "image"])
async def ai_generate(ctx, *, prompt: str):
    """Генерация изображения в стиле GTA 5"""
    if ctx.channel.id != AI_GENERATION_CHANNEL_ID:
        await ctx.send(f"⚠️ Эта команда доступна только в канале <#{AI_GENERATION_CHANNEL_ID}>", delete_after=10)
        await delete_command_message(ctx)
        return
    
    if len(prompt) < 5:
        await ctx.send("⚠️ Промпт должен быть не менее 5 символов!", delete_after=10)
        await delete_command_message(ctx)
        return
    
    allowed, error_msg = check_generation_limit(ctx.author.id)
    if not allowed:
        await ctx.send(error_msg, delete_after=10)
        await delete_command_message(ctx)
        return
    
    ai_generation_cooldown[ctx.author.id] = datetime.now().timestamp()
    ai_generation_count[ctx.author.id] += 1
    
    loading_embed = discord.Embed(
        title="🎨 ИИ-Генерация...",
        description=f"📝 **Промпт:** {prompt[:500]}\n\n⏳ Пожалуйста, подождите (10-30 сек)...",
        color=0x9D00FF,
        timestamp=datetime.now(timezone.utc)
    )
    loading_embed.set_footer(text="🤖 AI Кардинал | GTA 5 NeuroAI")
    
    loading_msg = await ctx.send(embed=loading_embed)
    await delete_command_message(ctx)
    
    seed = random.randint(1, 999999)
    result = await generate_gta_image(prompt, seed)
    
    if result["success"]:
        embed = discord.Embed(
            title="🎨 ИИ-Генерация завершена",
            description=f"📝 **Промпт:** {prompt[:500]}\n🎲 **Seed:** `{seed}`",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=result["url"])
        embed.set_footer(text="🤖 AI Кардинал | GTA 5 NeuroAI | Pollinations.ai")
        
        view = AIGenerationView(ctx.author.id, prompt, seed)
        await loading_msg.edit(embed=embed, view=view)
        
        await send_log(
            bot, "🎨 ИИ-Генерация",
            f"{ctx.author.mention} сгенерировал изображение.",
            0x9D00FF,
            [
                {"name": "👤 Пользователь", "value": f"`{ctx.author.name}`", "inline": True},
                {"name": "📝 Промпт", "value": f"`{prompt[:50]}`", "inline": True},
                {"name": "📊 Лимит", "value": f"`{ai_generation_count[ctx.author.id]}/{AI_GENERATION_CONFIG['max_prompts_per_day']}`", "inline": True}
            ]
        )
    else:
        error_embed = discord.Embed(
            title="❌ Ошибка генерации",
            description=f"Произошла ошибка при создании изображения.\n\n**Ошибка:** {result['error']}",
            color=0xFF6B6B,
            timestamp=datetime.now(timezone.utc)
        )
        await loading_msg.edit(embed=error_embed)

@tree.command(name="ai", description="Генерация изображения в стиле GTA 5")
@describe(prompt="Описание изображения для генерации")
async def slash_ai_generate(interaction: discord.Interaction, prompt: str):
    """Генерация изображения в стиле GTA 5"""
    if interaction.channel.id != AI_GENERATION_CHANNEL_ID:
        await interaction.response.send_message(f"⚠️ Эта команда доступна только в канале <#{AI_GENERATION_CHANNEL_ID}>", ephemeral=True)
        return
    
    if len(prompt) < 5:
        await interaction.response.send_message("⚠️ Промпт должен быть не менее 5 символов!", ephemeral=True)
        return
    
    allowed, error_msg = check_generation_limit(interaction.user.id)
    if not allowed:
        await interaction.response.send_message(error_msg, ephemeral=True)
        return
    
    ai_generation_cooldown[interaction.user.id] = datetime.now().timestamp()
    ai_generation_count[interaction.user.id] += 1
    
    await interaction.response.defer()
    
    seed = random.randint(1, 999999)
    result = await generate_gta_image(prompt, seed)
    
    if result["success"]:
        embed = discord.Embed(
            title="🎨 ИИ-Генерация завершена",
            description=f"📝 **Промпт:** {prompt[:500]}\n🎲 **Seed:** `{seed}`",
            color=0x2ECC71,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=result["url"])
        embed.set_footer(text="🤖 AI Кардинал | GTA 5 NeuroAI | Pollinations.ai")
        
        view = AIGenerationView(interaction.user.id, prompt, seed)
        await interaction.followup.send(embed=embed, view=view)
        
        await send_log(
            bot, "🎨 ИИ-Генерация",
            f"{interaction.user.mention} сгенерировал изображение.",
            0x9D00FF,
            [
                {"name": "👤 Пользователь", "value": f"`{interaction.user.name}`", "inline": True},
                {"name": "📝 Промпт", "value": f"`{prompt[:50]}`", "inline": True},
                {"name": "📊 Лимит", "value": f"`{ai_generation_count[interaction.user.id]}/{AI_GENERATION_CONFIG['max_prompts_per_day']}`", "inline": True}
            ]
        )
    else:
        await interaction.followup.send(f"❌ Ошибка генерации: {result['error']}", ephemeral=True)

@bot.command(name="aistats")
async def ai_stats(ctx):
    """Проверить статистику использования ИИ-генерации"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if ai_generation_date[ctx.author.id] != today:
        ai_generation_date[ctx.author.id] = today
        ai_generation_count[ctx.author.id] = 0
    
    embed = discord.Embed(
        title="📊 Статистика ИИ-Генерации",
        description=f"Ваша статистика использования генерации изображений.",
        color=0x9D00FF,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📝 Использовано сегодня", value=f"`{ai_generation_count[ctx.author.id]}/{AI_GENERATION_CONFIG['max_prompts_per_day']}`", inline=True)
    embed.add_field(name="⏱️ Кулдаун", value=f"`{AI_GENERATION_CONFIG['cooldown_seconds']} сек.`", inline=True)
    
    remaining = AI_GENERATION_CONFIG["max_prompts_per_day"] - ai_generation_count[ctx.author.id]
    embed.add_field(name="📊 Осталось", value=f"`{remaining}`", inline=True)
    embed.set_footer(text="🤖 AI Кардинал | GTA 5 NeuroAI")
    
    await ctx.send(embed=embed, delete_after=30)
    await delete_command_message(ctx)

# ============================================
# 🎫 СИСТЕМА ТИКЕТОВ
# ============================================

class ConfirmCloseView(View):
    def __init__(self, channel_id: int, user_id: int):
        super().__init__(timeout=60)
        self.channel_id = channel_id
        self.user_id = user_id
    
    @button(style=discord.ButtonStyle.success, label="Да, закрыть", emoji="✅", custom_id="confirm_close_btn")
    async def confirm_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваше действие.", ephemeral=True)
            return
        
        channel = bot.get_channel(self.channel_id)
        if channel is None:
            await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)
            return
        
        await send_log(
            bot, "🔒 Тикет закрыт",
            f"{channel.mention} закрыт пользователем {interaction.user.mention}",
            0x2ECC71,
            [
                {"name": "📋 Канал", "value": f"`{channel.name}`", "inline": True},
                {"name": "👤 Закрыл", "value": f"`{interaction.user.name}`", "inline": True}
            ]
        )
        await interaction.response.defer()
        await channel.delete(reason="Тикет закрыт")
    
    @button(style=discord.ButtonStyle.secondary, label="Отмена", emoji="❌", custom_id="cancel_close_btn")
    async def cancel_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Не ваше действие.", ephemeral=True)
            return
        await interaction.response.edit_message(content="✅ Закрытие отменено.", view=None)

class TicketView(View):
    def __init__(self, ticket_owner_id: int, ticket_message_id: int = None):
        super().__init__(timeout=None)
        self.ticket_owner_id = ticket_owner_id
        self.ticket_message_id = ticket_message_id
        
    @button(style=discord.ButtonStyle.danger, label="Закрыть тикет", emoji="🔒", custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        try:
            user = interaction.user
            channel = interaction.channel
            
            is_admin = any(role.id in ADMIN_ROLE_IDS for role in user.roles) or user.id == BOT_OWNER_ID
            is_owner = user.id == self.ticket_owner_id
            
            if not is_admin and not is_owner:
                await interaction.response.send_message("⚠️ Нет прав для закрытия.", ephemeral=True)
                return
            
            confirm_view = ConfirmCloseView(channel.id, user.id)
            await interaction.response.send_message("⚠️ Закрыть тикет?", view=confirm_view, ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка кнопки закрытия: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Произошла ошибка. Попробуйте позже.", ephemeral=True)
    
    @button(style=discord.ButtonStyle.primary, label="Взять в работу", emoji="👨‍💼", custom_id="claim_ticket_btn")
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        try:
            user = interaction.user
            channel = interaction.channel
            
            if not can_manage_tickets(user):
                await interaction.response.send_message("⚠️ Только администрация и поддержка могут брать тикеты в работу.", ephemeral=True)
                return
            
            try:
                async for message in channel.history(limit=10):
                    if message.author == bot.user and message.embeds and "ваш тикет успешно создан" in message.embeds[0].description:
                        old_embed = message.embeds[0]
                        new_description = old_embed.description.replace(
                            "• Статус: `🟡 Ожидает ответа`",
                            f"• Статус: `🟢 В работе у {user.display_name}`"
                        )
                        new_embed = discord.Embed(
                            title=old_embed.title,
                            description=new_description,
                            color=0x2ECC71,
                            timestamp=datetime.now(timezone.utc)
                        )
                        new_embed.set_footer(text="🤖 AI кардинал | Система поддержки")
                        await message.edit(embed=new_embed)
                        break
            except Exception as e:
                print(f"⚠️ Не удалось обновить эмбед: {e}")
            
            embed = discord.Embed(
                title="👨‍💼 Тикет взят в работу",
                description=f"{user.mention} начал обработку вашего обращения.\nОжидайте ответа в этом канале.",
                color=0x2ECC71,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text="🤖 AI кардинал")
            await channel.send(embed=embed)
            
            await interaction.response.defer()
            
            await send_log(
                bot, "👨‍💼 Тикет взят в работу",
                f"{user.mention} взял в работу {channel.mention}",
                0x2ECC71,
                [
                    {"name": "👤 Сотрудник", "value": f"`{user.name}`", "inline": True},
                    {"name": "📋 Канал", "value": f"`{channel.name}`", "inline": True}
                ]
            )
        except Exception as e:
            print(f"❌ Ошибка кнопки взятия в работу: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Произошла ошибка. Попробуйте позже.", ephemeral=True)

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
        try:
            ticket_type = self.values[0]
            config = TICKET_TYPES[ticket_type]
            await self.create_ticket(interaction, ticket_type, config)
        except Exception as e:
            print(f"❌ Ошибка выбора категории: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Произошла ошибка при создании тикета.", ephemeral=True)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, config: dict):
        try:
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
            for role_id in ADMIN_ROLE_IDS + [SUPPORT_ROLE_ID]:
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
            embed.set_footer(text="🤖 AI кардинал | Система поддержки")
            
            ticket_owners[new_channel.id] = user.id
            
            view = TicketView(user.id)
            
            await new_channel.send(f"<@&{NOTIFY_ROLE_ID}>")
            await new_channel.send(f"📬 **Новое обращение от** {user.mention}")
            await new_channel.send(embed=embed, view=view)
            
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
        except Exception as e:
            print(f"❌ Ошибка создания тикета: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Произошла ошибка при создании тикета.", ephemeral=True)

class CreateTicketButton(Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Создать обращение",
            emoji="🎫",
            custom_id="create_ticket_btn"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="📋 Выбор категории",
                description="Выберите тип вашего обращения из списка ниже:",
                color=0x9D00FF
            )
            embed.set_footer(text="🤖 AI кардинал")
            
            view = View(timeout=180)
            view.add_item(TicketCategorySelect(interaction.user))
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка кнопки создания тикета: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Произошла ошибка. Попробуйте позже.", ephemeral=True)

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CreateTicketButton())

@bot.command()
@commands.has_permissions(manage_channels=True)
async def tickets(ctx):
    """Создает панель управления тикетами"""
    if ctx.author.bot:
        return
    
    await delete_command_message(ctx)
    
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
    embed.set_image(url="https://i.imgur.com/yplKlVx.jpeg")
    embed.set_footer(text="🤖 AI кардинал | NeuroAI support v7.1")
    
    view = TicketPanelView()
    await ctx.send(embed=embed, view=view)

# ============================================
# ⏱️ ПРОВЕРКА МУТОВ
# ============================================

async def check_mutes():
    now = datetime.now(timezone.utc)
    to_remove = []
    
    for user_id, mute_data in mutes.items():
        if mute_data["end_time"] <= now:
            to_remove.append(user_id)
    
    for user_id in to_remove:
        try:
            mute_data = mutes.pop(user_id)
            guild = bot.get_guild(mute_data["guild_id"])
            if guild:
                member = guild.get_member(user_id)
                if member:
                    mute_role = discord.Object(id=MUTE_ROLE_ID)
                    await member.remove_roles(mute_role, reason="Мут истёк")
                    
                    await send_log(
                        bot, "🔊 Мут истёк",
                        f"С пользователя {member.mention} автоматически снят мут.",
                        0x2ECC71,
                        [
                            {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
                            {"name": "⏱️ Длительность", "value": f"`{mute_data['duration']}`", "inline": True}
                        ]
                    )
        except Exception as e:
            print(f"⚠️ Ошибка при снятии мута: {e}")

@tasks.loop(minutes=1)
async def check_mutes_task():
    await check_mutes()

@check_mutes_task.before_loop
async def before_check_mutes_task():
    await bot.wait_until_ready()

# ============================================
# 🛡️ АВТО-МОДЕРАЦИЯ
# ============================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if is_admin(message.author):
        await bot.process_commands(message)
        return
    
    now = datetime.now(timezone.utc)
    
    message_cooldown[message.author.id].append(now)
    while message_cooldown[message.author.id] and now - message_cooldown[message.author.id][0] > timedelta(seconds=AUTO_MOD_CONFIG["spam_time_window"]):
        message_cooldown[message.author.id].popleft()
    
    if len(message_cooldown[message.author.id]) > AUTO_MOD_CONFIG["spam_threshold"]:
        await mute_user(message.author, "Спам", message.channel)
        message_cooldown[message.author.id].clear()
        return
    
    if len(message.mentions) > AUTO_MOD_CONFIG["mention_threshold"]:
        await mute_user(message.author, "Массовые упоминания", message.channel)
        return
    
    if message.channel.id not in AUTO_MOD_CONFIG["link_allowed_channels"]:
        url_pattern = r'https?://\S+|www\.\S+'
        if re.search(url_pattern, message.content):
            await message.delete()
            await mute_user(message.author, "Отправка ссылок", message.channel)
            return
    
    content_lower = message.content.lower()
    for bad_word in AUTO_MOD_CONFIG["bad_words"]:
        if bad_word in content_lower:
            await message.delete()
            await mute_user(message.author, f"Стоп-слово: {bad_word}", message.channel)
            return
    
    if len(message.content) > 10:
        caps_ratio = sum(1 for c in message.content if c.isupper()) / len(message.content)
        if caps_ratio > 0.7:
            await message.delete()
            await mute_user(message.author, "Злоупотребление капсом", message.channel)
            return
    
    await bot.process_commands(message)

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
# 👤 ПРИВЕТСТВИЕ
# ============================================

@bot.event
async def on_member_join(member):
    now = datetime.now(timezone.utc)
    
    join_cooldown.append((member, now))
    
    while join_cooldown and now - join_cooldown[0][1] > timedelta(seconds=AUTO_MOD_CONFIG["raid_time_window"]):
        join_cooldown.popleft()
    
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
    
    account_age = (now - member.created_at).days
    if account_age < AUTO_MOD_CONFIG["new_account_threshold"]:
        try:
            await mute_user(member, f"Новый аккаунт ({account_age} дн.)")
        except Exception as e:
            print(f"⚠️ Ошибка при муте нового аккаунта: {e}")
    
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
                    f"Вам автоматически выдана роль доступа к системе."
                ),
                color=0x9D00FF,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="📜 Ознакомление с протоколами",
                value=f"Внимательно изучите правила в канале <#{RULES_CHANNEL_ID}>\n\n⚠️ **Внимание:** нарушение протоколов приведет к блокировке доступа.",
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
# ⚙️ SLASH КОМАНДЫ (/)
# ============================================

@bot.event
async def on_ready():
    # ✅ РЕГИСТРАЦИЯ ТОЛЬКО PERSISTENT VIEWS (без timeout)
    bot.add_view(TicketPanelView())
    # ❌ AIGenerationView НЕ регистрируем - у него есть timeout=300
    
    @tree.command(name="mute", description="Заглушить пользователя на указанное время")
    @describe(member="Пользователь для мута", duration="Длительность в минутах", reason="Причина мута")
    @discord.app_commands.checks.has_permissions(manage_roles=True)
    async def slash_mute(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "Нарушение правил"):
        if not is_admin(interaction.user):
            await interaction.response.send_message("⚠️ Недостаточно прав.", ephemeral=True)
            return
        
        mute_role = discord.Object(id=MUTE_ROLE_ID)
        await member.add_roles(mute_role, reason=f"Moderator: {reason}")
        
        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)
        mutes[member.id] = {
            "end_time": end_time,
            "guild_id": interaction.guild.id,
            "duration": f"{duration} мин."
        }
        
        await send_log(
            bot, "🔇 Пользователь заглушен",
            f"{member.mention} получил мут от {interaction.user.mention}.",
            0xFF6B6B,
            [
                {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
                {"name": "👮 Модератор", "value": f"`{interaction.user.name}`", "inline": True},
                {"name": "📋 Причина", "value": f"`{reason}`", "inline": True},
                {"name": "⏱️ Длительность", "value": f"`{duration} мин.`", "inline": True}
            ]
        )
        
        await interaction.response.send_message(f"✅ {member.mention} заглушен на {duration} мин. Причина: {reason}")
        delete_command_message_from_interaction(interaction)
    
    @tree.command(name="unmute", description="Разглушить пользователя")
    @describe(member="Пользователь для размута")
    @discord.app_commands.checks.has_permissions(manage_roles=True)
    async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
        if not is_admin(interaction.user):
            await interaction.response.send_message("⚠️ Недостаточно прав.", ephemeral=True)
            return
        
        mute_role = discord.utils.get(interaction.guild.roles, id=MUTE_ROLE_ID)
        if mute_role in member.roles:
            await member.remove_roles(mute_role, reason=f"Moderator: {interaction.user.name}")
            
            if member.id in mutes:
                mutes.pop(member.id)
            
            await send_log(
                bot, "🔊 Пользователь разглушен",
                f"{member.mention} разглушен пользователем {interaction.user.mention}.",
                0x2ECC71,
                [
                    {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
                    {"name": "👮 Модератор", "value": f"`{interaction.user.name}`", "inline": True}
                ]
            )
            await interaction.response.send_message(f"✅ {member.mention} разглушен.")
        else:
            await interaction.response.send_message("⚠️ У пользователя нет роли мута.", ephemeral=True)
        
        delete_command_message_from_interaction(interaction)
    
    @tree.command(name="warn", description="Выдать предупреждение пользователю")
    @describe(member="Пользователь для предупреждения", reason="Причина предупреждения")
    @discord.app_commands.checks.has_permissions(manage_roles=True)
    async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Нарушение правил"):
        if not is_admin(interaction.user):
            await interaction.response.send_message("⚠️ Недостаточно прав.", ephemeral=True)
            return
        
        warns[member.id] += 1
        await send_log(
            bot, "⚠️ Пользователь предупреждён",
            f"{member.mention} получил предупреждение от {interaction.user.mention}.",
            0xFFA500,
            [
                {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
                {"name": "👮 Модератор", "value": f"`{interaction.user.name}`", "inline": True},
                {"name": "📋 Причина", "value": f"`{reason}`", "inline": False},
                {"name": "⚠️ Предупреждений", "value": f"`{warns[member.id]}`", "inline": True}
            ]
        )
        await interaction.response.send_message(f"⚠️ {member.mention} предупреждён. Причина: {reason}\nВсего предупреждений: {warns[member.id]}/3")
        
        if warns[member.id] >= 3:
            mute_role = discord.Object(id=MUTE_ROLE_ID)
            await member.add_roles(mute_role, reason="3 предупреждения")
            warns[member.id] = 0
            await interaction.followup.send(f"🔇 {member.mention} получил мут за 3 предупреждения.")
        
        delete_command_message_from_interaction(interaction)
    
    @tree.command(name="warns", description="Проверить предупреждения пользователя")
    @describe(member="Пользователь для проверки")
    @discord.app_commands.checks.has_permissions(manage_roles=True)
    async def slash_warns(interaction: discord.Interaction, member: discord.Member):
        if not is_admin(interaction.user):
            await interaction.response.send_message("⚠️ Недостаточно прав.", ephemeral=True)
            return
        
        await interaction.response.send_message(f"📋 У {member.mention} **{warns[member.id]}** предупреждений из 3.")
        delete_command_message_from_interaction(interaction)
    
    @tree.command(name="raidmode", description="Включить/выключить режим защиты от рейдов")
    @describe(status="on - включить, off - выключить")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def slash_raidmode(interaction: discord.Interaction, status: str):
        if not is_admin(interaction.user):
            await interaction.response.send_message("⚠️ Недостаточно прав.", ephemeral=True)
            return
        
        if status.lower() in ["on", "вкл", "true"]:
            AUTO_MOD_CONFIG["raid_threshold"] = 3
            await interaction.response.send_message("🚨 Режим защиты от рейдов: **ВКЛЮЧЕН**")
            await send_log(bot, "🚨 Режим защиты от рейдов", "Активирован администратором.", 0xFF0000)
        else:
            AUTO_MOD_CONFIG["raid_threshold"] = 10
            await interaction.response.send_message("✅ Режим защиты от рейдов: **ВЫКЛЮЧЕН**")
            await send_log(bot, "🚨 Режим защиты от рейдов", "Деактивирован администратором.", 0x2ECC71)
        
        delete_command_message_from_interaction(interaction)
    
    @tree.command(name="clear", description="Очистить сообщения в канале")
    @describe(amount="Количество сообщений для удаления (1-100)")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def slash_clear(interaction: discord.Interaction, amount: int):
        if not is_admin(interaction.user):
            await interaction.response.send_message("⚠️ Недостаточно прав.", ephemeral=True)
            return
        
        if amount < 1 or amount > 100:
            await interaction.response.send_message("⚠️ Количество должно быть от 1 до 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Удалено {len(deleted)} сообщений.", ephemeral=True)
        
        await send_log(
            bot, "🗑️ Сообщения очищены",
            f"{interaction.user.mention} очистил {len(deleted)} сообщений в {interaction.channel.mention}.",
            0xFF6B6B,
            [
                {"name": "👮 Модератор", "value": f"`{interaction.user.name}`", "inline": True},
                {"name": "📊 Удалено", "value": f"`{len(deleted)}`", "inline": True}
            ]
        )
    
    try:
        await tree.sync()
        print(f"✅ Slash команды синхронизированы (7 команд)")
    except Exception as e:
        print(f"⚠️ Ошибка синхронизации команд: {e}")
    
    check_mutes_task.start()
    
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.watching, name="за симуляцией NeuroAI")
    )
    print(f"🤖 AI кардинал подключен...")
    print(f"📡 {bot.user.name} | 🆔 {bot.user.id}")
    print(f"🎫 Система тикетов: активна")
    print(f"🎨 ИИ-Генерация: активна (Pollinations.ai)")
    print(f"🛡️ Авто-модерация: активна")
    print(f"🔇 Роль мута: {MUTE_ROLE_ID}")
    print(f"👋 Канал приветствий: {WELCOME_CHANNEL_ID}")
    print(f"🎭 Авто-роль: {AUTO_ROLE_ID}")
    print(f"👨‍💼 Support роль: {SUPPORT_ROLE_ID}")
    print(f"📬 Notify роль: {NOTIFY_ROLE_ID}")
    print(f"🎨 AI канал: {AI_GENERATION_CHANNEL_ID}")
    print(f"⚙️ Команды: / и !")
    print("-" * 30)
    await send_log(bot, "🟢 Система запущена", "**AI кардинал** подключился.", 0x2ECC71, [
        {"name": "📡 Статус", "value": "`Онлайн (DND)`", "inline": True},
        {"name": "🎫 Тикеты", "value": "`Активны`", "inline": True},
        {"name": "🛡️ Авто-мод", "value": "`Активен`", "inline": True},
        {"name": "🎨 ИИ", "value": "`Активен`", "inline": True}
    ])

# ============================================
# ⚙️ PREFIX КОМАНДЫ (!)
# ============================================

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def prefix_mute(ctx, member: discord.Member, duration: int, *, reason: str = "Нарушение правил"):
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", delete_after=5)
        return
    
    mute_role = discord.Object(id=MUTE_ROLE_ID)
    await member.add_roles(mute_role, reason=f"Moderator: {reason}")
    
    end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)
    mutes[member.id] = {
        "end_time": end_time,
        "guild_id": ctx.guild.id,
        "duration": f"{duration} мин."
    }
    
    await send_log(
        bot, "🔇 Пользователь заглушен",
        f"{member.mention} получил мут от {ctx.author.mention}.",
        0xFF6B6B,
        [
            {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
            {"name": "👮 Модератор", "value": f"`{ctx.author.name}`", "inline": True},
            {"name": "📋 Причина", "value": f"`{reason}`", "inline": True},
            {"name": "⏱️ Длительность", "value": f"`{duration} мин.`", "inline": True}
        ]
    )
    
    await ctx.send(f"✅ {member.mention} заглушен на {duration} мин. Причина: {reason}", delete_after=10)
    await delete_command_message(ctx)

@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def prefix_unmute(ctx, member: discord.Member):
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", delete_after=5)
        return
    
    mute_role = discord.utils.get(ctx.guild.roles, id=MUTE_ROLE_ID)
    if mute_role in member.roles:
        await member.remove_roles(mute_role, reason=f"Moderator: {ctx.author.name}")
        
        if member.id in mutes:
            mutes.pop(member.id)
        
        await send_log(
            bot, "🔊 Пользователь разглушен",
            f"{member.mention} разглушен пользователем {ctx.author.mention}.",
            0x2ECC71,
            [
                {"name": "👤 Пользователь", "value": f"`{member.name}`", "inline": True},
                {"name": "👮 Модератор", "value": f"`{ctx.author.name}`", "inline": True}
            ]
        )
        await ctx.send(f"✅ {member.mention} разглушен.", delete_after=10)
    else:
        await ctx.send("⚠️ У пользователя нет роли мута.", delete_after=5)
    
    await delete_command_message(ctx)

@bot.command(name="warn")
@commands.has_permissions(manage_roles=True)
async def prefix_warn(ctx, member: discord.Member, *, reason: str = "Нарушение правил"):
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", delete_after=5)
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
    await ctx.send(f"⚠️ {member.mention} предупреждён. Причина: {reason}\nВсего предупреждений: {warns[member.id]}/3", delete_after=10)
    
    if warns[member.id] >= 3:
        mute_role = discord.Object(id=MUTE_ROLE_ID)
        await member.add_roles(mute_role, reason="3 предупреждения")
        warns[member.id] = 0
        await ctx.send(f"🔇 {member.mention} получил мут за 3 предупреждения.", delete_after=10)
    
    await delete_command_message(ctx)

@bot.command(name="warns")
@commands.has_permissions(manage_roles=True)
async def prefix_warns(ctx, member: discord.Member):
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", delete_after=5)
        return
    
    await ctx.send(f"📋 У {member.mention} **{warns[member.id]}** предупреждений из 3.", delete_after=10)
    await delete_command_message(ctx)

@bot.command(name="raidmode")
@commands.has_permissions(administrator=True)
async def prefix_raidmode(ctx, status: str):
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", delete_after=5)
        return
    
    if status.lower() in ["on", "вкл", "true"]:
        AUTO_MOD_CONFIG["raid_threshold"] = 3
        await ctx.send("🚨 Режим защиты от рейдов: **ВКЛЮЧЕН**", delete_after=10)
        await send_log(bot, "🚨 Режим защиты от рейдов", "Активирован администратором.", 0xFF0000)
    else:
        AUTO_MOD_CONFIG["raid_threshold"] = 10
        await ctx.send("✅ Режим защиты от рейдов: **ВЫКЛЮЧЕН**", delete_after=10)
        await send_log(bot, "🚨 Режим защиты от рейдов", "Деактивирован администратором.", 0x2ECC71)
    
    await delete_command_message(ctx)

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def prefix_clear(ctx, amount: int):
    if not is_admin(ctx.author):
        await ctx.send("⚠️ Недостаточно прав.", delete_after=5)
        return
    
    if amount < 1 or amount > 100:
        await ctx.send("⚠️ Количество должно быть от 1 до 100.", delete_after=5)
        return
    
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"🗑️ Удалено {len(deleted)} сообщений.", delete_after=10)
    
    await send_log(
        bot, "🗑️ Сообщения очищены",
        f"{ctx.author.mention} очистил {len(deleted)} сообщений в {ctx.channel.mention}.",
        0xFF6B6B,
        [
            {"name": "👮 Модератор", "value": f"`{ctx.author.name}`", "inline": True},
            {"name": "📊 Удалено", "value": f"`{len(deleted)}`", "inline": True}
        ]
    )
    
    await delete_command_message(ctx)

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
