import asyncio
import logging
import json
from datetime import datetime, timedelta
from aiogram import Dispatcher, Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import config
from database import (
    StaticProfile, get_user, create_user, update_subscription, 
    get_all_users, create_static_profile, get_static_profiles, 
    User, Session, get_user_stats as db_user_stats, delete_user_profile, 
    get_user_profiles, save_vless_profile, VLESSProfile
)
from functions import create_vless_profile, delete_client_by_email, delete_vless_profile, generate_vless_url, get_user_stats, create_static_client, get_global_stats, get_online_users

logger = logging.getLogger(__name__)

router = Router()

MAX_MESSAGE_LENGTH = 4096

class AdminStates(StatesGroup):
    ADD_TIME = State()
    REMOVE_TIME = State()
    CREATE_STATIC_PROFILE = State()
    SEND_MESSAGE = State()
    ADD_TIME_USER = State()
    REMOVE_TIME_USER = State()
    ADD_TIME_AMOUNT = State()
    REMOVE_TIME_AMOUNT = State()
    SEND_MESSAGE_TARGET = State()

class UserStates(StatesGroup):
    device_name = State()

def split_text(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list:
    """Разбивает текст на части указанной максимальной длины"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        part = text[:max_length]
        last_newline = part.rfind('\n')
        if last_newline != -1:
            part = part[:last_newline]
        parts.append(part)
        text = text[len(part):].lstrip()
    return parts

async def show_menu(bot: Bot, chat_id: int, message_id: int = None):
    """
    Функция для отображения меню (может как редактировать существующее сообщение, так и отправлять новое).
    """
    user = await get_user(chat_id)
    if not user:
        return

    text = (
        f"👋 Привет, {user.full_name}!\n\n"
        f"🔐 Ваш профиль подключён к учебной сети **Кодики**.\n"
        f"Статус подключения: ✅ Всё работает отлично!\n\n"
        f"Если нужна помощь или появились вопросы — нажмите кнопку ниже или введите команду /help.\n"
        f"Мы всегда на связи и готовы помочь 😊💡"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Сгенерировать ключ", callback_data="connect")
    builder.button(text="📊 Статистика", callback_data="stats")
    builder.button(text="🔑 Мои ключи", callback_data="manage_keys")
    builder.button(text="ℹ️ Помощь", callback_data="help")
    builder.button(text="📥 Приложения для работы VPN", callback_data="apps")
    builder.button(text="📖 Инструкция", url="https://telegra.ph/Nastrojka-obhoda-blokirovki-dlya-zapuska-programm-11-25")

    if user.is_admin:
        builder.button(text="⚠️ Админ. меню", callback_data="admin_menu")

    builder.adjust(2, 2, 1)

    if message_id:
        # Редактируем существующее сообщение
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode='Markdown'
        )
    else:
        # Отправляем новое сообщение
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode='Markdown'
        )

@router.message(Command("start"))
async def start_cmd(message: Message, bot: Bot):
    logger.info(f"ℹ️  Start command from {message.from_user.id}")
    user = await get_user(message.from_user.id)
    
    # Обновляем данные пользователя если они изменились
    update_data = {}
    if user:
        if user.full_name != message.from_user.full_name:
            update_data["full_name"] = message.from_user.full_name
        if user.username != message.from_user.username:
            update_data["username"] = message.from_user.username
    else:
        is_admin = message.from_user.id in config.ADMINS
        user = await create_user(
            telegram_id=message.from_user.id, 
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            is_admin=is_admin
        )
        # Отправляем инструкцию при первом запуске
        instruction = (
            f"🎉 Добро пожаловать в VPN бота `{(await bot.get_me()).full_name}`!\n\n"
            f"**Быстрый старт:**\n"
            f"1️⃣ Нажмите 🔑 **Сгенерировать ключ**\n"
            f"2️⃣ Введите название устройства (iPhone, PC и т.д.)\n"
            f"3️⃣ Получите VLESS URL\n"
            f"4️⃣ Импортируйте в приложение VPN\n\n"
            f"**Важно:** У вас может быть только 1 активный ключ одновременно. При создании нового ключа старый будет удален.\n\n"
            f"Нужна помощь? Нажмите ℹ️ **Помощь** в меню."
        )
        await message.answer(instruction, parse_mode='Markdown')
        await asyncio.sleep(2)
    
    # Обновляем данные если есть изменения
    if update_data:
        with Session() as session:
            db_user = session.query(User).get(user.id)
            for key, value in update_data.items():
                setattr(db_user, key, value)
            session.commit()
            logger.info(f"🔄 Updated user data: {message.from_user.id}")
    
    await show_menu(bot, message.from_user.id)

@router.message(Command("menu"))
async def menu_cmd(message: Message, bot: Bot):
    user = await get_user(message.from_user.id)
    if not user:
        await start_cmd(message, bot)
        return
    
    # Проверяем изменения данных
    update_data = {}
    if user.full_name != message.from_user.full_name:
        update_data["full_name"] = message.from_user.full_name
    if user.username != message.from_user.username:
        update_data["username"] = message.from_user.username
    
    # Обновляем данные если есть изменения
    if update_data:
        with Session() as session:
            db_user = session.query(User).get(user.id)
            for key, value in update_data.items():
                setattr(db_user, key, value)
            session.commit()
            logger.info(f"🔄 Updated user data in menu: {message.from_user.id}")
    
    await show_menu(bot, message.from_user.id)

@router.callback_query(F.data == "help")
async def help_msg(callback: CallbackQuery):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="Поддержка", url="https://t.me/vadimkulishov")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    text = (
        f"📞 Служба поддержки:\n"
        f"<a href='https://t.me/vadimkulishov'>Написать @vadimkulishov</a>\n\n"
    )
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=builder.as_markup())


@router.callback_query(F.data == "apps")
async def apps_menu(callback: CallbackQuery):
    """Показывает список приложений по ОС для скачивания"""
    await callback.answer()
    builder = InlineKeyboardBuilder()
    # Основные клиенты для разных ОС
    builder.button(text='🖥️ Windows [Nekoray]', url='https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-windows64.zip')
    builder.button(text='🖥️ Windows [Happ]', url='https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe')
    builder.button(text='🐧 Linux [NekoBox]', url='https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-debian-x64.deb')
    builder.button(text='🍎 Mac [V2RayU]', url='https://github.com/yanue/V2rayU/releases/download/v4.2.6/V2rayU-64.dmg')
    builder.button(text='🍏 iOS [V2RayTun]', url='https://apps.apple.com/ru/app/v2raytun/id6476628951')
    builder.button(text='🤖 Android [V2RayNG]', url='https://github.com/2dust/v2rayNG/releases/download/1.10.16/v2rayNG_1.10.16_arm64-v8a.apk')
    builder.button(text='📖 Инструкция', url='https://telegra.ph/Nastrojka-obhoda-blokirovki-dlya-zapuska-programm-11-25')
    builder.button(text='⬅️ Назад', callback_data='back_to_menu')
    builder.adjust(2, 2, 2, 1)

    await callback.message.edit_text(
        "📥 Приложения для работы VPN — выберите вашу ОС:",
        reply_markup=builder.as_markup(),
        parse_mode='Markdown'
    )

@router.message(Command("help"))
async def help_cmd(message: Message):
    """
    Обработчик команды /help. Отправляет информацию о боте и инструкцию.
    """
    bot = message.bot

    help_text = (
        "\u2139\ufe0f **Помощь**\n\n"
        "Этот бот помогает управлять VPN-профилями.\n\n"
        "**Основные команды:**\n"
        "/start - Перезапустить бота\n"
        "/menu - Открыть меню\n"
        "/help - Показать это сообщение\n\n"
        "[Инструкция по настройке приложений](https://telegra.ph/Nastrojka-obhoda-blokirovki-dlya-zapuska-programm-11-25)"
    )
    try:
        await message.answer(help_text, parse_mode="Markdown")
    except TelegramForbiddenError:
        logger.warning(f"User {message.from_user.id} blocked the bot")
        return

    await show_menu(bot, message.from_user.id)
@router.callback_query(F.data == "renew_sub")
async def renew_subscription(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для каждого варианта подписки (бесплатная)
    for months in sorted(config.PRICES.keys()):
        button_text = f"{months} мес. - БЕСПЛАТНО ✨"
        builder.button(text=button_text, callback_data=f"pay_{months}")
    
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🎉 **Выберите период подписки (бесплатно):**",
        reply_markup=builder.as_markup(),
        parse_mode='Markdown'
    )

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    
    try:
        months = int(callback.data.split("_")[1])
        if months not in config.PRICES:
            await callback.message.answer("❌ Неверный период подписки")
            return
            
        suffix = "месяц" if months == 1 else "месяца" if months in (2,3,4) else "месяцев"
        
        # Бесплатная подписка - просто обновляем без платежа
        user = await get_user(callback.from_user.id)
        if not user:
            await callback.message.answer("❌ Ошибка: пользователь не найден")
            return
        
        # Определяем тип действия
        now = datetime.utcnow()
        action_type = "продлена" if user.subscription_end and user.subscription_end > now else "активирована"
        
        # Обновляем подписку
        success = await update_subscription(callback.from_user.id, months)
        
        if success:
            await callback.message.answer(
                f"✅ Подписка {action_type}! Вы получили бесплатный доступ на {months} {suffix}! 🎉",
                parse_mode='Markdown'
            )
            
            # Отправляем уведомление администраторам
            admin_message = (
                f"🎉 {action_type.capitalize()} бесплатная подписка пользователем\n"
                f"`{user.full_name}` | `{user.telegram_id}`\n"
                f"на {months} {suffix}"
            )
            
            for admin_id in config.ADMINS:
                try:
                    await bot.send_message(admin_id, admin_message, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"🛑 Failed to send notification to admin {admin_id}: {e}")
        else:
            await callback.message.answer("❌ Ошибка при активации подписки")
    except Exception as e:
        logger.error(f"🛑 Free subscription error: {e}")
        await callback.message.answer("❌ Ошибка при активации подписки")

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: Message, bot: Bot):
    # Эта функция больше не используется так как подписка бесплатная
    await message.answer("ℹ️ Подписка выдается бесплатно. Используйте меню бота.")

@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user or not user.is_admin:
        await callback.answer("🛑 Доступ запрещен!")
        return
    
    total, with_sub, without_sub = await db_user_stats()
    online_count = await get_online_users()
    
    text = (
        "**Административное меню**\n\n"
        f"**Всего пользователей**: `{total}`\n"
        f"**С подпиской/Без подписки**: `{with_sub}`/`{without_sub}`\n"
        f"**Онлайн**: `{online_count}` | **Офлайн**: `{with_sub - online_count}`"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="+ время", callback_data="admin_add_time")
    builder.button(text="- время", callback_data="admin_remove_time")
    builder.button(text="📋 Список пользователей", callback_data="admin_user_list")
    builder.button(text="📊 Статистика исп. сети", callback_data="admin_network_stats")
    builder.button(text="📢 Рассылка", callback_data="admin_send_message")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(2, 1, 1, 1, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode='Markdown')

# Обработчики для управления временем подписки
@router.callback_query(F.data == "admin_add_time")
async def admin_add_time_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # Снимаем анимацию
    await callback.message.answer("Введите Telegram ID пользователя:")
    await state.set_state(AdminStates.ADD_TIME_USER)

@router.message(AdminStates.ADD_TIME_USER)
async def admin_add_time_user(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer("Введите количество времени в формате:\nМесяцы Дни Часы Минуты\nПример: 1 0 0 0")
        await state.set_state(AdminStates.ADD_TIME_AMOUNT)
    except ValueError:
        await message.answer("Ошибка: ID должен быть числом")

@router.message(AdminStates.ADD_TIME_AMOUNT)
async def admin_add_time_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']
    parts = message.text.split()
    
    if len(parts) != 4:
        await message.answer("Ошибка: нужно ввести 4 числа")
        return
    
    try:
        months, days, hours, minutes = map(int, parts)
        total_seconds = (
            months * 30 * 24 * 60 * 60 +
            days * 24 * 60 * 60 +
            hours * 60 * 60 +
            minutes * 60
        )
        
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if user:
                if user.subscription_end and user.subscription_end > datetime.utcnow():
                    user.subscription_end += timedelta(seconds=total_seconds)
                else:
                    user.subscription_end = datetime.utcnow() + timedelta(seconds=total_seconds)
                session.commit()
                await message.answer(f"✅ Добавлено время пользователю {user_id}")
            else:
                await message.answer("❌ Пользователь не найден")
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")
    finally:
        await state.clear()

@router.callback_query(F.data == "admin_remove_time")
async def admin_remove_time_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # Снимаем анимацию
    await callback.message.answer("Введите Telegram ID пользователя:")
    await state.set_state(AdminStates.REMOVE_TIME_USER)

@router.message(AdminStates.REMOVE_TIME_USER)
async def admin_remove_time_user(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer("Введите количество времени в формате:\nМесяцы Дни Часы Минуты\nПример: 1 0 0 0")
        await state.set_state(AdminStates.REMOVE_TIME_AMOUNT)
    except ValueError:
        await message.answer("Ошибка: ID должен быть числом")

@router.message(AdminStates.REMOVE_TIME_AMOUNT)
async def admin_remove_time_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']
    parts = message.text.split()
    
    if len(parts) != 4:
        await message.answer("Ошибка: нужно ввести 4 числа")
        return
    
    try:
        months, days, hours, minutes = map(int, parts)
        total_seconds = (
            months * 30 * 24 * 60 * 60 +
            days * 24 * 60 * 60 +
            hours * 60 * 60 +
            minutes * 60
        )
        
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if user:
                new_end = user.subscription_end - timedelta(seconds=total_seconds) if user.subscription_end else datetime.utcnow() - timedelta(seconds=total_seconds)
                # Проверяем, чтобы не ушло в прошлое
                if new_end < datetime.utcnow():
                    new_end = datetime.utcnow()
                user.subscription_end = new_end
                session.commit()
                await message.answer(f"✅ Удалено время у пользователя {user_id}")
            else:
                await message.answer("❌ Пользователь не найден")
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")
    finally:
        await state.clear()

# Обработчики для вывода списка пользователей
@router.callback_query(F.data == "admin_user_list")
async def admin_user_list(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ С подпиской", callback_data="user_list_active")
    builder.button(text="🛑 Без подписки", callback_data="user_list_inactive")
    builder.button(text="⏱️ Статические профили", callback_data="static_profiles_menu")
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(1, 1, 1)
    await callback.message.edit_text("**Выберите фильтр**", reply_markup=builder.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == "user_list_active")
async def handle_user_list_active(callback: CallbackQuery):
    users = await get_all_users(with_subscription=True)
    await callback.answer()
    if not users:
        await callback.answer("Нет пользователей с активной подпиской")
        return
    
    text = "👤 <b>Пользователи с активной подпиской:</b>\n\n"
    for user in users:
        expire_date = user.subscription_end.strftime("%d.%m.%Y %H:%M")
        username = f"@{user.username}" if user.username else "none"
        user_line = f"• {user.full_name} ({username} | <code>{user.telegram_id}</code>) - до <code>{expire_date}</code>\n"
        
        # Если текст становится слишком длинным, отправляем текущую часть и начинаем новую
        if len(text) + len(user_line) > MAX_MESSAGE_LENGTH:
            await callback.message.answer(text, parse_mode="HTML")
            text = "👤 <b>Пользователи с активной подпиской (продолжение):</b>\n\n"
        
        text += user_line
    
    # Отправляем оставшуюся часть текста
    await callback.message.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "user_list_inactive")
async def handle_user_list_inactive(callback: CallbackQuery):
    await callback.answer()
    users = await get_all_users(with_subscription=False)
    if not users:
        await callback.answer("Нет пользователей без подписки")
        return
    
    text = "👤 <b>Пользователи без подписки:</b>\n\n"
    for user in users:
        username = f"@{user.username}" if user.username else "none"
        user_line = f"• {user.full_name} ({username} | <code>{user.telegram_id}</code>)\n"
        
        # Если текст становится слишком длинным, отправляем текущую часть и начинаем новую
        if len(text) + len(user_line) > MAX_MESSAGE_LENGTH:
            await callback.message.answer(text, parse_mode="HTML")
            text = "👤 <b>Пользователи без подписки (продолжение):</b>\n\n"
        
        text += user_line
    
    # Отправляем оставшуюся часть текста
    await callback.message.answer(text, parse_mode="HTML")

# Обработчики для рассылки сообщений
@router.callback_query(F.data == "admin_send_message")
async def admin_send_message_start(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ С подпиской", callback_data="target_active")
    builder.button(text="🛑 Без подписки", callback_data="target_inactive")
    builder.button(text="👥 Всем пользователям", callback_data="target_all")
    builder.button(text="↩️ Назад", callback_data="admin_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Выберите целевую аудиторию для рассылки:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("target_"))
async def admin_send_message_target(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # Снимаем анимацию
    target = callback.data.split("_")[1]
    await state.update_data(target=target)
    await callback.message.answer("Введите сообщение для рассылки:")
    await state.set_state(AdminStates.SEND_MESSAGE)

@router.message(AdminStates.SEND_MESSAGE)
async def admin_send_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target = data['target']
    text = message.text

    users = []
    if target == "active":
        users = await get_all_users(with_subscription=True)
    elif target == "inactive":
        users = await get_all_users(with_subscription=False)
    else:  # all
        users = await get_all_users()

    success = 0
    failed = 0

    for user in users:
        try:
            await bot.send_message(user.telegram_id, text)
            success += 1
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения {user.telegram_id}: {e}")
            failed += 1

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")

    await message.answer(
        f"📨 Результаты рассылки:\n\n"
        f"• Успешно: {success}\n"
        f"• Не удалось: {failed}\n"
        f"• Всего: {len(users)}",
        reply_markup=builder.as_markup()
    )
    await state.clear()

# Остальные обработчики остаются без изменений
@router.callback_query(F.data == "static_profiles_menu")
async def static_profiles_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Добавить статический профиль", callback_data="static_profile_add")
    builder.button(text="📋 Вывести статические профили", callback_data="static_profile_list")
    builder.button(text="⬅️ Назад", callback_data="admin_user_list")
    builder.adjust(1)
    await callback.message.edit_text("**Выберите действие**", reply_markup=builder.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == "static_profile_add")
async def static_profile_add(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # Снимаем анимацию
    await callback.message.answer("Введите имя для статического профиля:")
    await state.set_state(AdminStates.CREATE_STATIC_PROFILE)

@router.message(AdminStates.CREATE_STATIC_PROFILE)
async def process_static_profile_name(message: Message, state: FSMContext):
    profile_name = message.text
    profile_data = await create_static_client(profile_name)
    
    if profile_data:
        vless_url = generate_vless_url(profile_data)
        await create_static_profile(profile_name, vless_url)
        profiles = await get_static_profiles()
        for profile in profiles:
            if profile.name == profile_name:
                id = profile.id
        builder = InlineKeyboardBuilder()
        builder.button(text="🗑️ Удалить", callback_data=f"delete_static_{id}")
        await message.answer(f"Профиль создан!\n\n`{vless_url}`", reply_markup=builder.as_markup(), parse_mode='Markdown')
    else:
        await message.answer("Ошибка при создании профиля")
    
    await state.clear()

@router.callback_query(F.data == "static_profile_list")
async def static_profile_list(callback: CallbackQuery):
    profiles = await get_static_profiles()
    if not profiles:
        await callback.answer("Нет статических профилей")
        return
    
    for profile in profiles:
        builder = InlineKeyboardBuilder()
        builder.button(text="🗑️ Удалить", callback_data=f"delete_static_{profile.id}")
        await callback.message.answer(
            f"**{profile.name}**\n`{profile.vless_url}`", 
            reply_markup=builder.as_markup(), parse_mode='Markdown'
        )

@router.callback_query(F.data.startswith("delete_static_"))
async def handle_delete_static_profile(callback: CallbackQuery):
    try:
        profile_id = int(callback.data.split("_")[-1])
        
        with Session() as session:
            profile = session.query(StaticProfile).filter_by(id=profile_id).first()
            if not profile:
                await callback.answer("⚠️ Профиль не найден")
                return
            
            success = await delete_client_by_email(profile.name)
            if not success:
                logger.error(f"🛑 Ошибка удаления клиента из инбаунда: {profile.name}")
            
            session.delete(profile)
            session.commit()
        
        await callback.answer("✅ Профиль удален!")
        await callback.message.delete()
    except Exception as e:
        logger.error(f"🛑 Ошибка при удалении статического профиля: {e}")
        await callback.answer("⚠️ Ошибка при удалении профиля")

@router.callback_query(F.data == "connect")
async def connect_profile(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("⚠️ Ошибка профиля")
        return

    # Если подписка истекла, даём 3 дня бесплатно
    if not user.subscription_end or user.subscription_end < datetime.utcnow():
        await callback.message.edit_text("⏳ Активируем подписку...")
        success = await update_subscription(callback.from_user.id, 3)
        if not success:
            await callback.answer("❌ Ошибка при активации подписки")
            return
        await callback.message.edit_text("✅ Подписка активирована на 3 дня! Теперь создаём ключ...")
        await asyncio.sleep(1)
    
    # Показываем кнопки выбора устройства
    builder = InlineKeyboardBuilder()
    devices = [
        ("🍎 iPhone", "device_iphone"),
        ("🤖 Android", "device_android"),
        ("🖥️ Windows", "device_windows"),
        ("🐧 Linux", "device_linux"),
        ("🍏 macOS", "device_macos"),
        ("⚙️ Другое", "device_other"),
    ]

    for label, callback_data in devices:
        builder.button(text=label, callback_data=callback_data)

    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(2, 2, 2, 1)

    await callback.message.edit_text(
        "📱 **Выберите ваше устройство:**",
        reply_markup=builder.as_markup(),
        parse_mode='Markdown'
    )

@router.callback_query(F.data.startswith("device_"))
async def select_device(callback: CallbackQuery):
    device_map = {
        "device_iphone": "iPhone",
        "device_android": "Android",
        "device_windows": "Windows PC",
        "device_linux": "Linux",
        "device_macos": "macOS",
        "device_other": "Другое",
    }
    
    device_name = device_map.get(callback.data, "Неизвестное")
    
    user = await get_user(callback.from_user.id)
    if not user or not user.subscription_end or user.subscription_end < datetime.utcnow():
        await callback.answer("⚠️ Подписка истекла!")
        return
    
    await callback.message.edit_text(f"⚙️ Создаем ваш VPN профиль для {device_name}...")
    profile_data = await create_vless_profile(user.telegram_id, device_name)
    
    if profile_data:
        await save_vless_profile(
            telegram_id=user.telegram_id,
            profile_id=profile_data["profile_id"],
            vless_url=profile_data["vless_url"],
            email=profile_data["email"],
            device_name=device_name
        )
        logger.info(f"✅ Profile created for {user.telegram_id} on device {device_name}")
    else:
        await callback.message.answer("🛑 Ошибка при создании профиля. Попробуйте позже.")
        return
    
    vless_url = profile_data["vless_url"]
    text = (
        "🎉 **Ваш VPN профиль готов!**\n\n"
        "ℹ️ **Инструкция по подключению:**\n"
        "1. Скачайте приложение для вашей платформы\n"
        "2. Скопируйте эту ссылку и импортируйте в приложение:\n\n"
        f"`{vless_url}`\n\n"
        "3. Активируйте соединение в приложении."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text='🖥️ Windows [Nekoray]', url='https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-windows64.zip')
    builder.button(text='🖥️ Windows [Happ]', url='https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe')
    builder.button(text='🐧 Linux [NekoBox]', url='https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-debian-x64.deb')
    builder.button(text='🍎 Mac [V2RayU]', url='https://github.com/yanue/V2rayU/releases/download/v4.2.6/V2rayU-64.dmg ')
    builder.button(text='🍏 iOS [V2RayTun]', url='https://apps.apple.com/ru/app/v2raytun/id6476628951')
    builder.button(text='🤖 Android [V2RayNG]', url='https://github.com/2dust/v2rayNG/releases/download/1.10.16/v2rayNG_1.10.16_arm64-v8a.apk')
    builder.button(text="📖 Инструкция", url="https://telegra.ph/Nastrojka-obhoda-blokirovki-dlya-zapuska-programm-11-25")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(2, 2, 1, 1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode='Markdown')
    await callback.answer()

@router.callback_query(F.data == "stats")
async def user_stats(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("⚠️ Профиль не создан")
        return

    profiles = await get_user_profiles(callback.from_user.id)
    if not profiles:
        await callback.answer("⚠️ У вас нет созданных профилей")
        return

    await callback.message.edit_text("⚙️ Загружаем вашу статистику...")
    
    # Собираем статистику по всем профилям
    total_upload = 0
    total_download = 0
    
    for profile in profiles:
        stats = await get_user_stats(profile.email)
        total_upload += stats.get('upload', 0)
        total_download += stats.get('download', 0)
    
    upload = f"{total_upload / 1024 / 1024:.2f}"
    upload_size = 'MB' if int(float(upload)) < 1024 else 'GB'
    if upload_size == "GB":
        upload = f"{int(float(upload) / 1024):.2f}"

    download = f"{total_download / 1024 / 1024:.2f}"
    download_size = 'MB' if int(float(download)) < 1024 else 'GB'
    if download_size == "GB":
        download = f"{int(float(download) / 1024):.2f}"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")

    # Показываем информацию по каждому ключу
    text = "📊 **Ваша статистика:**\n\n"
    for i, profile in enumerate(profiles, 1):
        text += f"**{i}. {profile.device_name}**\n"
        stats = await get_user_stats(profile.email)
        prof_upload = f"{stats.get('upload', 0) / 1024 / 1024:.2f}"
        prof_upload_size = 'MB' if int(float(prof_upload)) < 1024 else 'GB'
        if prof_upload_size == "GB":
            prof_upload = f"{int(float(prof_upload) / 1024):.2f}"
        
        prof_download = f"{stats.get('download', 0) / 1024 / 1024:.2f}"
        prof_download_size = 'MB' if int(float(prof_download)) < 1024 else 'GB'
        if prof_download_size == "GB":
            prof_download = f"{int(float(prof_download) / 1024):.2f}"
        
        text += f"  ⬆️ Загружено: `{prof_upload} {prof_upload_size}`\n"
        text += f"  ⬇️ Скачано: `{prof_download} {prof_download_size}`\n\n"
    
    text += f"**Всего:**\n"
    text += f"⬆️ Загружено: `{upload} {upload_size}`\n"
    text += f"⬇️ Скачано: `{download} {download_size}`\n"
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == "admin_network_stats")
async def network_stats(callback: CallbackQuery):
    stats = await get_global_stats()

    upload = f"{stats.get('upload', 0) / 1024 / 1024:.2f}"
    upload_size = 'MB' if int(float(upload)) < 1024 else 'GB'
    if upload_size == "GB":
        upload = f"{int(float(upload) / 1024):.2f}"

    download = f"{stats.get('download', 0) / 1024 / 1024:.2f}"
    download_size = 'MB' if int(float(download)) < 1024 else 'GB'
    if download_size == "GB":
        download = f"{int(float(download) / 1024):.2f}"
    
    await callback.answer()
    text = (
        "📊 **Статистика использования сети:**\n\n"
        f"🔼 Upload - `{upload} {upload_size}` | 🔽 Download - `{download} {download_size}`"
    )
    await callback.message.edit_text(text, parse_mode='Markdown')

@router.callback_query(F.data == "manage_keys")
async def manage_keys(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("🛑 Ошибка профиля")
        return
    
    profiles = await get_user_profiles(callback.from_user.id)
    if not profiles:
        await callback.answer("⚠️ У вас нет созданных профилей")
        return
    
    text = "🔑 **Ваши VPN ключи:**\n\n"
    
    builder = InlineKeyboardBuilder()
    for profile in profiles:
        created = profile.created_at.strftime("%d-%m-%Y") if hasattr(profile.created_at, 'strftime') else "неизв."
        text += f"• **{profile.device_name}** (создан {created})\n"
        builder.button(
            text=f"🗑️ Удалить {profile.device_name}",
            callback_data=f"delete_key:{profile.id}"
        )
    
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data.startswith("delete_key:"))
async def delete_key(callback: CallbackQuery):
    profile_id_str = callback.data.split(":")[1]
    
    try:
        profile_id = int(profile_id_str)
    except ValueError:
        await callback.answer("⚠️ Неверный ID профиля")
        return
    
    # Проверяем что профиль принадлежит пользователю
    with Session() as session:
        profile = session.query(VLESSProfile).filter_by(id=profile_id).first()
        if not profile or profile.telegram_id != callback.from_user.id:
            await callback.answer("⚠️ Этот профиль не принадлежит вам")
            return
        
        device_name = profile.device_name
        session.delete(profile)
        session.commit()
    
    # Удаляем профиль с 3X-UI
    try:
        await delete_vless_profile(profile.email)
        logger.info(f"✅ Profile {device_name} deleted for user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"⚠️ Error deleting profile from 3X-UI: {e}")
    
    # Возвращаемся в меню управления ключами
    await callback.answer(f"✅ Ключ '{device_name}' успешно удален!")
    
    profiles = await get_user_profiles(callback.from_user.id)
    if not profiles:
        text = "🔑 **Ваши VPN ключи:**\n\nУ вас еще нет ключей. Создайте новый!"
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Создать ключ", callback_data="connect")
        builder.button(text="⬅️ Назад", callback_data="back_to_menu")
        builder.adjust(2)
    else:
        text = "🔑 **Ваши VPN ключи:**\n\n"
        builder = InlineKeyboardBuilder()
        for profile in profiles:
            created = profile.created_at.strftime("%d-%m-%Y") if hasattr(profile.created_at, 'strftime') else "неизв."
            text += f"• **{profile.device_name}** (создан {created})\n"
            builder.button(
                text=f"🗑️ Удалить {profile.device_name}",
                callback_data=f"delete_key:{profile.id}"
            )
        builder.button(text="⬅️ Назад", callback_data="back_to_menu")
        builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_menu(bot, callback.from_user.id)

def setup_handlers(dp: Dispatcher):
    dp.include_router(router)
    logger.info("✅ Handlers setup completed")

def safe_json_loads(data, default=None):
    if not data:
        return default
    try:
        return json.loads(data)
    except Exception:
        return default
