import json
import asyncio
import logging
import warnings
import coloredlogs
from config import config
from aiogram import Bot, Dispatcher
from aiogram.types import PreCheckoutQuery
from handlers import setup_handlers
from datetime import datetime, timedelta
from functions import delete_client_by_email
from database import Session, User, init_db, get_all_users, delete_user_profile

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Настройка логирования
coloredlogs.install(level='info')
logger = logging.getLogger(__name__)

# Ограничиваем количество одновременных задач
semaphore = asyncio.Semaphore(10)

async def limited_task(coro):
    """
    Ограничивает количество одновременных задач.
    """
    async with semaphore:
        return await coro

async def check_subscriptions(bot: Bot):
    """Проверка статуса подписок"""
    while True:
        try:
            now = datetime.utcnow()
            users = await get_all_users()

            tasks = []
            for user in users:
                # Пропускаем если нет даты подписки
                if not user.subscription_end:
                    continue

                # Проверка за 1 день до окончания
                if user.subscription_end - now < timedelta(days=1) and user.subscription_end >= now and not user.notified:
                    tasks.append(limited_task(notify_user(bot, user)))

                # Проверка истечения подписки
                if user.subscription_end <= now and user.vless_profile_data:
                    tasks.append(limited_task(remove_user_profile(bot, user)))

            await asyncio.gather(*tasks)
        except Exception as e:
            logger.warning(f"⚠️ Subscription check error: {e}")

        await asyncio.sleep(3600)

async def notify_user(bot: Bot, user):
    """
    Уведомляет пользователя о скором окончании подписки.
    """
    try:
        await bot.send_message(
            user.telegram_id,
            "⚠️ Ваша подписка истекает через 24 часа! Продлите подписку, чтобы сохранить доступ."
        )
        with Session() as session:
            db_user = session.query(User).filter_by(telegram_id=user.telegram_id).first()
            if db_user:
                db_user.notified = True
                session.commit()
    except Exception as e:
        logger.warning(f"⚠️ Notification error: {e}")

async def remove_user_profile(bot: Bot, user):
    """
    Удаляет профиль пользователя после окончания подписки.
    """
    try:
        profile = json.loads(user.vless_profile_data)
        success = await delete_client_by_email(profile["email"])
        if success:
            await delete_user_profile(user.telegram_id)
            await bot.send_message(
                user.telegram_id,
                "❌ Ваша подписка истекла! Профиль VPN был удален. Продлите подписку, чтобы создать новый."
            )
    except Exception as e:
        logger.warning(f"⚠️ Deletion error: {e}")

async def update_admins_status():
    """Обновляет статус администраторов в базе данных"""
    with Session() as session:
        # Сбрасываем статус администратора у всех пользователей
        session.query(User).update({User.is_admin: False})

        # Устанавливаем статус администратора для пользователей из config.ADMINS
        for admin_id in config.ADMINS:
            user = session.query(User).filter_by(telegram_id=admin_id).first()
            if user:
                user.is_admin = True
            else:
                # Если администратора нет в базе, создаем запись
                new_admin = User(
                    telegram_id=admin_id,
                    full_name=f"Admin {admin_id}",
                    is_admin=True
                )
                session.add(new_admin)

        session.commit()
    logger.info("✅ Admin status updated in database")

async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    try:
        await init_db()
        logger.info("✅ Database initialized")

        # Обновляем статус администраторов
        await update_admins_status()
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        return

    try:
        setup_handlers(dp)
        logger.info("✅ Handlers registered")
    except Exception as e:
        logger.error(f"❌ Handler registration error: {e}")
        return

    # Обработчик для предварительной проверки платежа
    @dp.pre_checkout_query()
    async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

    # Запускаем фоновую задачу проверки подписок
    try:
        asyncio.create_task(check_subscriptions(bot))
    except Exception as e:
        logger.error(f"❌ Subscription check task failed to start: {e}")

    logger.info("ℹ️  Starting bot...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Bot start error: {e}")
        return

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Stopping bot...")
        exit(0)
    except Exception as e:
        logger.error(f"❌ Main loop error: {e}")
        exit(1)