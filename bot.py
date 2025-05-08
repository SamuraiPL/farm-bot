import discord
from discord import ui, ButtonStyle, app_commands
import time
import asyncio
import sqlite3
import os

# --- Discord ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# --- Настройки кулдаунов ---
custom_cooldowns = {
    "Схемы": 14400,
    "Швейка": 14400,
    "Волонтёрка": 10800,
    "Скользкая": 10800,
    "Питомец": 900,
    "Организация": 7200,
    "Релог": 900,

    # Задания клуба
    "Moto": 7200,
    "Car Meet": 7200,
    "Rednecks": 7200,
    "The Epsilon Program": 7200,
    "Merryweather": 7200,

    # Оплата имущества
    "Оплата на 6 дней": 5 * 86400,
    "Оплата на 29 дней": 29 * 86400
}

COOLDOWN_DEFAULT = 1800  # 30 минут

def get_cooldown(action_name):
    return custom_cooldowns.get(action_name, COOLDOWN_DEFAULT)

# --- SQLite ---
conn = sqlite3.connect('farm_bot.db', check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_timers (
            user_id INTEGER,
            action TEXT,
            last_used REAL,
            PRIMARY KEY (user_id, action)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            user_id INTEGER,
            action_name TEXT,
            message TEXT
        )
    ''')
    conn.commit()

def load_data_from_db():
    cursor.execute("SELECT user_id, action, last_used FROM user_timers")
    for row in cursor.fetchall():
        user_id, action, timestamp = row
        if user_id not in last_used:
            last_used[user_id] = {}
        last_used[user_id][action] = timestamp

def save_timer_to_db(user_id, action_name):
    cursor.execute('''
        INSERT OR REPLACE INTO user_timers (user_id, action, last_used)
        VALUES (?, ?, ?)
    ''', (user_id, action_name, time.time()))
    conn.commit()
    log_event("Использование действия", user_id, action_name, "Записано в БД")

# --- Хранилище времени использования ---
last_used = {}  # user_id -> {action -> last_used_time}
pending_notifications = []  # {user_id, action_name, end_time, message}

# --- Логирование ---
def log_event(event_type: str, user_id: int, action_name: str = None, message: str = None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    cursor.execute('''
        INSERT INTO logs (timestamp, event_type, user_id, action_name, message)
        VALUES (?, ?, ?, ?, ?)
    ''', (timestamp, event_type, user_id, action_name, message))
    conn.commit()
    print(f"[{event_type}] Пользователь {user_id}, действие: {action_name or 'N/A'} → {message or ''}")

# --- Меню фарма ---
class FarmMenu(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def handle_button_click(self, interaction: discord.Interaction, action_name: str):
        user_id = interaction.user.id

        if not is_action_available(user_id, action_name):
            await self.show_countdown(interaction, action_name)
            return

        last_used.setdefault(user_id, {})[action_name] = time.time()
        save_timer_to_db(user_id, action_name)

        pending_notifications.append({
            "user_id": user_id,
            "action_name": action_name,
            "end_time": time.time() + get_cooldown(action_name),
            "message": None
        })

        await interaction.response.send_message(f"✅ Вы начали: **{action_name}**", ephemeral=True)

    async def show_countdown(self, interaction: discord.Interaction, action_name: str):
        user_id = interaction.user.id
        cooldown = get_cooldown(action_name)
        end_time = last_used.get(user_id, {}).get(action_name, 0) + cooldown
        remaining = max(0, int(end_time - time.time()))

        embed = discord.Embed(
            title=f"⏳ Ожидание: {action_name}",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        while remaining > 0:
            hours, remainder = divmod(remaining, 3600)
            mins, secs = divmod(remainder, 60)
            timer_text = f"{hours} ч {mins} мин {secs} сек"

            bar_length = 20
            progress = 1 - (remaining / cooldown)
            filled = int(bar_length * progress)
            bar = '🟩' * filled + '🟥' * (bar_length - filled)

            embed.description = f"```\n{bar}\n```\nОсталось: **{timer_text}**"
            try:
                await interaction.edit_original_response(embed=embed)
            except discord.NotFound:
                return

            await asyncio.sleep(10)
            remaining = max(0, int(end_time - time.time()))

        embed.title = "✅ Теперь доступно!"
        embed.description = f"Вы можете снова использовать: **{action_name}**"
        embed.color = discord.Color.green()
        await interaction.edit_original_response(embed=embed)

    @ui.button(label="Схемы", style=ButtonStyle.primary, emoji="📘")
    async def schemes(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_button_click(interaction, "Схемы")

    @ui.button(label="Швейка", style=ButtonStyle.primary, emoji="🧵")
    async def sewing(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_button_click(interaction, "Швейка")

    @ui.button(label="Волонтёрка", style=ButtonStyle.success, emoji="⛑️")
    async def volunteer(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_button_click(interaction, "Волонтёрка")

    @ui.button(label="Скользкая", style=ButtonStyle.danger, emoji="🛢️")
    async def slippery(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_button_click(interaction, "Скользкая")

    @ui.button(label="Питомец", style=ButtonStyle.secondary, emoji="🐾")
    async def pet(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_button_click(interaction, "Питомец")

    @ui.button(label="Организация", style=ButtonStyle.primary, emoji="🏢")
    async def organization(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_button_click(interaction, "Организация")

    @ui.button(label="Релог", style=ButtonStyle.danger, emoji="🔄")
    async def relog(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_button_click(interaction, "Релог")

    @ui.button(label="Задание клуба", style=ButtonStyle.primary, emoji="🎯")
    async def club_task_button(self, interaction: discord.Interaction, button: ui.Button):
        view = ClubTaskMenu(farm_view=self)
        embed = discord.Embed(
            title="🎯 Задание клуба",
            description="Выберите задание:",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Оплата имущества", style=ButtonStyle.success, emoji="💰")
    async def property_payment_button(self, interaction: discord.Interaction, button: ui.Button):
        view = PaymentMenu(farm_view=self)
        embed = discord.Embed(
            title="💰 Оплата имущества",
            description="Выберите срок оплаты:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Кастомный таймер", style=ButtonStyle.secondary, emoji="⏱️")
    async def custom_timer_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CustomTimerModal())

    @ui.button(label="Посмотреть таймеры", style=ButtonStyle.secondary, emoji="⏱️")
    async def show_timers_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_current_timers(interaction)

    async def show_current_timers(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id not in last_used or not last_used[user_id]:
            await interaction.response.send_message("✅ У вас нет активных таймеров.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⏱️ Ваши активные таймеры",
            description="Используйте ❌ рядом с действием, чтобы отключить его",
            color=discord.Color.orange()
        )

        view = TimerMenu(farm_view=self)

        for action_name, timestamp in last_used[user_id].items():
            cooldown = get_cooldown(action_name)
            remaining = max(0, int(timestamp + cooldown - time.time()))
            if remaining > 0:
                hours, remainder = divmod(remaining, 3600)
                mins, secs = divmod(remainder, 60)
                timer_text = f"{hours} ч {mins} мин {secs} сек"
                embed.add_field(
                    name=f"⏳ {action_name}",
                    value=f"Доступно через: `{timer_text}`",
                    inline=False
                )
                view.add_delete_button(action_name)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# --- CustomTimerModal ---
class CustomTimerModal(ui.Modal, title="⏰ Настройте кастомный таймер"):
    days = ui.TextInput(label="Дни", placeholder="Например: 2", required=False, default="0")
    hours = ui.TextInput(label="Часы", placeholder="Например: 5", required=False, default="0")
    minutes = ui.TextInput(label="Минуты", placeholder="Например: 30", required=False, default="0")

    def __init__(self):
        super().__init__()
        self.view = None

    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = int(self.days.value or 0)
            h = int(self.hours.value or 0)
            m = int(self.minutes.value or 0)

            total_seconds = d * 86400 + h * 3600 + m * 60

            if total_seconds <= 0:
                await interaction.response.send_message("❌ Укажите время больше нуля.", ephemeral=True)
                return

            action_name = f"Кастомный таймер ({d} дн {h} ч {m} мин)"
            user_id = interaction.user.id

            last_used.setdefault(user_id, {})[action_name] = time.time()
            save_timer_to_db(user_id, action_name)

            pending_notifications.append({
                "user_id": user_id,
                "action_name": action_name,
                "end_time": time.time() + total_seconds
            })

            log_event("Кастомный таймер", user_id, action_name, "Активировано")

            embed = discord.Embed(
                title=f"⏱️ {action_name}",
                description=f"Таймер запущен на: {d} дней, {h} часов, {m} минут",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Введите числа в полях", ephemeral=True)


# --- Таймеры с кнопкой ❌ ---
class TimerMenu(ui.View):
    def __init__(self, farm_view):
        super().__init__(timeout=None)
        self.farm_view = farm_view

    def add_delete_button(self, action_name: str):
        button = ui.Button(
            label=f"❌ {action_name}",
            style=ButtonStyle.danger,
            custom_id=f"delete_{action_name}"
        )
        async def delete_callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            if user_id in last_used and action_name in last_used[user_id]:
                del last_used[user_id][action_name]
                cursor.execute("DELETE FROM user_timers WHERE user_id=? AND action=?", (user_id, action_name))
                conn.commit()
                log_event("Таймер удалён", user_id, action_name, "Таймер отключён вручную")
                await interaction.response.send_message(f"✅ Таймер `{action_name}` отключён.", ephemeral=True)
                await self.update_timer_embed(interaction)
            else:
                await interaction.response.send_message("❌ Это действие уже удалено.", ephemeral=True)
        button.callback = delete_callback
        self.add_item(button)

    @ui.button(label="⬅️ Вернуться", style=ButtonStyle.secondary, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🌾 Фарм GTA V RP",
            description="Выберите тип фарма:",
            color=discord.Color.green()
        )
        view = self.farm_view
        await interaction.response.edit_message(embed=embed, view=view)

    async def update_timer_embed(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = time.time()

        embed = discord.Embed(
            title="⏱️ Ваши активные таймеры",
            description="Используйте ❌ рядом с действием, чтобы отключить его",
            color=discord.Color.orange()
        )

        has_active = False

        for action_name, timestamp in last_used.get(user_id, {}).items():
            cooldown = get_cooldown(action_name)
            remaining = max(0, int(timestamp + cooldown - current_time))

            if remaining > 0:
                hours, remainder = divmod(remaining, 3600)
                mins, secs = divmod(remainder, 60)
                timer_text = f"{hours} ч {mins} мин {secs} сек"
                embed.add_field(
                    name=f"⏳ {action_name}",
                    value=f"Доступно через: `{timer_text}`",
                    inline=False
                )
                has_active = True

        if not has_active:
            embed.title = "✅ Все действия доступны"
            embed.description = ""
            embed.add_field(name="🎉", value="Нет активных таймеров.")
            embed.color = discord.Color.green()

        new_view = TimerMenu(farm_view=self.farm_view)
        for act, ts in last_used.get(user_id, {}).items():
            cooldown = get_cooldown(act)
            if ts + cooldown > time.time():
                new_view.add_delete_button(act)

        try:
            await interaction.edit_original_response(embed=embed, view=new_view)
        except discord.NotFound:
            return

        while True:
            if not self.is_message_valid(interaction):
                return

            updated_embed = discord.Embed(
                title="⏱️ Ваши активные таймеры",
                description="Используйте ❌ рядом с действием, чтобы отключить его",
                color=discord.Color.orange()
            )

            for action_name, timestamp in list(last_used.get(user_id, {}).items()):
                cooldown = get_cooldown(action_name)
                remaining = max(0, int(timestamp + cooldown - time.time()))

                if remaining > 0:
                    hours, remainder = divmod(remaining, 3600)
                    mins, secs = divmod(remainder, 60)
                    timer_text = f"{hours} ч {mins} мин {secs} сек"
                    updated_embed.add_field(
                        name=f"⏳ {action_name}",
                        value=f"Доступно через: `{timer_text}`",
                        inline=False
                    )

            try:
                await interaction.edit_original_response(embed=updated_embed, view=new_view)
            except discord.NotFound:
                return

            await asyncio.sleep(1)

    def is_message_valid(self, interaction: discord.Interaction):
        try:
            message = interaction.message or interaction.original_response()
            return message is not None
        except Exception as e:
            return False


# --- Уведомления с кнопкой 🗑️ ---
class NotificationView(ui.View):
    def __init__(self, user_id, action_name):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.action_name = action_name

    @ui.button(label="🗑️ Удалить", style=ButtonStyle.danger)
    async def delete_notification(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()

        for notify in pending_notifications:
            if notify.get("user_id") == self.user_id and notify.get("action_name") == self.action_name:
                pending_notifications.remove(notify)
                break

        print(f"[LOG] Уведомление `{self.action_name}` удалено пользователем {self.user_id}")
        print(f"[LOG] Уведомление скрыто игроком")


# --- Подменю "Задание клуба" ---
class ClubTaskMenu(ui.View):
    def __init__(self, farm_view):
        super().__init__(timeout=None)
        self.farm_view = farm_view

    async def handle_task_click(self, interaction: discord.Interaction, task_name: str):
        user_id = interaction.user.id

        if not is_action_available(user_id, task_name):
            remaining = get_remaining_time(user_id, task_name)
            hours, remainder = divmod(remaining, 3600)
            mins, secs = divmod(remainder, 60)
            await interaction.response.send_message(
                f"⏳ Следующее использование \"{task_name}\" доступно через {hours} ч {mins} мин.",
                ephemeral=True
            )
            return

        last_used.setdefault(user_id, {})[task_name] = time.time()
        save_timer_to_db(user_id, task_name)

        pending_notifications.append({
            "user_id": user_id,
            "action_name": task_name,
            "end_time": time.time() + 7200  # 2 часа для всех заданий клуба
        })
        log_event("Использование задания", user_id, task_name, "Начато")
        await interaction.response.send_message(f"✅ Вы начали задание: **{task_name}**", ephemeral=True)

    @ui.button(label="Moto", style=ButtonStyle.primary, emoji="🏍️")
    async def moto(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_task_click(interaction, "Moto")

    @ui.button(label="Car Meet", style=ButtonStyle.primary, emoji="🚗")
    async def car_meet(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_task_click(interaction, "Car Meet")

    @ui.button(label="Rednecks", style=ButtonStyle.primary, emoji="🤠")
    async def rednecks(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_task_click(interaction, "Rednecks")

    @ui.button(label="The Epsilon Program", style=ButtonStyle.success, emoji="🌀")
    async def epsilon(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_task_click(interaction, "The Epsilon Program")

    @ui.button(label="Merryweather", style=ButtonStyle.danger, emoji="👮‍♂️")
    async def merryweather(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_task_click(interaction, "Merryweather")

    @ui.button(label="⬅️ Назад", style=ButtonStyle.secondary, emoji="⬅️")
    async def back_to_farm(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🌾 Фарм GTA V RP",
            description="Выберите тип фарма:",
            color=discord.Color.green()
        )
        view = self.farm_view
        await interaction.response.edit_message(embed=embed, view=view)


# --- Подменю "Оплата имущества" ---
class PaymentMenu(ui.View):
    def __init__(self, farm_view):
        super().__init__(timeout=None)
        self.farm_view = farm_view

    async def handle_payment_click(self, interaction: discord.Interaction, payment_name: str, cooldown: int):
        user_id = interaction.user.id

        if not is_action_available(user_id, payment_name):
            remaining = get_remaining_time(user_id, payment_name)
            hours, remainder = divmod(remaining, 3600)
            mins, secs = divmod(remainder, 60)
            await interaction.response.send_message(
                f"⏳ Следующее использование \"{payment_name}\" доступно через {hours} ч {mins} мин.",
                ephemeral=True
            )
            return

        last_used.setdefault(user_id, {})[payment_name] = time.time()
        save_timer_to_db(user_id, payment_name)

        pending_notifications.append({
            "user_id": user_id,
            "action_name": payment_name,
            "end_time": time.time() + cooldown
        })
        log_event("Оплата имущества", user_id, payment_name, "Активировано")

        await interaction.response.send_message(f"✅ Вы начали: **{payment_name}**", ephemeral=True)

    @ui.button(label="Оплата на 6 дней", style=ButtonStyle.primary, emoji="📆")
    async def pay_6(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_payment_click(interaction, "Оплата на 6 дней", 5 * 86400)  # 5 дней (оплачено на 6)

    @ui.button(label="Оплата на 29 дней", style=ButtonStyle.success, emoji="📅")
    async def pay_29(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_payment_click(interaction, "Оплата на 29 дней", 29 * 86400)

    @ui.button(label="⬅️ Назад", style=ButtonStyle.secondary, emoji="⬅️")
    async def back_to_farm(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🌾 Фарм GTA V RP",
            description="Выберите тип фарма:",
            color=discord.Color.green()
        )
        view = self.farm_view
        await interaction.response.edit_message(embed=embed, view=view)


# --- Команды ---
@tree.command(name="фарм", description="Открыть интерактивное меню фарма")
async def farm_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌾 Фарм GTA V RP",
        description="Выберите тип фарма:",
        color=discord.Color.green()
    )
    view = FarmMenu()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


@tree.command(name="таймеры", description="Показывает оставшееся время по всем вашим действиям")
async def show_timers(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id not in last_used or not last_used[user_id]:
        await interaction.response.send_message("✅ У вас нет активных таймеров.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⏱️ Ваши активные таймеры",
        description="Используйте ❌ рядом с действием, чтобы отключить его",
        color=discord.Color.orange()
    )

    view = TimerMenu(farm_view=FarmMenu())

    for action_name, timestamp in last_used[user_id].items():
        cooldown = get_cooldown(action_name)
        remaining = max(0, int(timestamp + cooldown - time.time()))
        if remaining > 0:
            hours, remainder = divmod(remaining, 3600)
            mins, secs = divmod(remainder, 60)
            timer_text = f"{hours} ч {mins} мин {secs} сек"
            embed.add_field(
                name=f"⏳ {action_name}",
                value=f"Доступно через: `{timer_text}`",
                inline=False
            )
            view.add_delete_button(action_name)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# --- Уведомления по истечении ---
@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен!')
    await tree.sync()
    init_db()
    load_data_from_db()
    asyncio.create_task(check_notifications())


async def check_notifications():
    while True:
        current_time = time.time()
        to_remove = []

        for notify in pending_notifications:
            if notify["end_time"] <= current_time:
                user_id = notify["user_id"]
                action_name = notify["action_name"]

                try:
                    user = await bot.fetch_user(user_id)
                    msg_text = {
                        "Оплата на 29 дней": "🔔 Ваша оплата имущества на 29 дней завершена. Пора продлить!",
                        "Оплата на 6 дней": "🔔 Ваша оплата имущества на 6 дней завершена. Пора продлить!"
                    }.get(action_name, f"🔔 Задание \"{action_name}\" снова доступно!")

                    view = NotificationView(user_id, action_name)
                    message = await user.send(msg_text, view=view)
                    notify["message"] = message

                except Exception as e:
                    print(f"[Ошибка] Не удалось отправить уведомление: {e}")

                to_remove.append(notify)

        for item in to_remove:
            pending_notifications.remove(item)

        await asyncio.sleep(60)


# --- Вспомогательные функции ---
def is_action_available(user_id, action_name):
    current_time = time.time()
    cooldown = get_cooldown(action_name)
    if user_id in last_used and action_name in last_used[user_id]:
        elapsed = current_time - last_used[user_id][action_name]
        return elapsed >= cooldown
    return True

def get_remaining_time(user_id, action_name):
    current_time = time.time()
    cooldown = get_cooldown(action_name)
    if user_id in last_used and action_name in last_used[user_id]:
        return max(0, int(cooldown - (current_time - last_used[user_id][action_name])))
    return 0

def get_cooldown(action_name):
    return custom_cooldowns.get(action_name, COOLDOWN_DEFAULT)


# --- Приветствие новых участников ---
class StartMenu(ui.View):
    def __init__(self, farm_view):
        super().__init__(timeout=None)
        self.farm_view = farm_view

    @ui.button(label="Открыть Фарм", style=ButtonStyle.green)
    async def open_farm(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="🌾 Фарм GTA V RP",
            description="Выберите тип фарма:",
            color=discord.Color.green()
        )
        view = self.farm_view
        await interaction.response.edit_message(embed=embed, view=view)


@bot.event
async def on_member_join(member: discord.Member):
    try:
        embed_dm = discord.Embed(
            title="👋 Добро пожаловать в GTA V RP!",
            description="Этот бот поможет вам следить за таймерами.\n\n🔹 Нажмите кнопку ниже, чтобы начать!\n🔹 Бот работает с FiveM / RAGE.MP серверами",
            color=discord.Color.green()
        )
        view = StartMenu(farm_view=FarmMenu())
        await member.send(embed=embed_dm, view=view)
    except discord.Forbidden:
        print(f"[Ошибка] Не могу отправить ЛС пользователю {member.name} — закрытые сообщения отключены.")


# --- Обработка текстовых команд ---
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if message.content.lower() in ["меню", "!фарм"]:
        embed = discord.Embed(
            title="🌾 Фарм GTA V RP",
            description="Выберите тип фарма:",
            color=discord.Color.green()
        )
        view = FarmMenu()
        await message.channel.send(embed=embed, view=view)


# --- Запуск бота ---
if __name__ == "__main__":
    # Для локального запуска
    bot.run("Твой_токен")
else:
    # Для Replit / Railway
    import os
    bot.run(os.getenv("DISCORD_TOKEN"))