from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, func, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta
import logging
from functools import lru_cache
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    full_name = Column(String)
    username = Column(String)
    registration_date = Column(DateTime, default=datetime.utcnow)
    subscription_end = Column(DateTime)
    is_admin = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    
    # Связь с профилями
    profiles = relationship("VLESSProfile", back_populates="user", cascade="all, delete-orphan")

class VLESSProfile(Base):
    __tablename__ = 'vless_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    telegram_id = Column(Integer)
    vless_profile_id = Column(String, unique=True)
    vless_url = Column(String)
    email = Column(String, unique=True)
    device_name = Column(String)  # Имя устройства
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="profiles")

class StaticProfile(Base):
    __tablename__ = 'static_profiles'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    vless_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

engine = create_engine('sqlite:///users.db', echo=False)
Session = sessionmaker(bind=engine)

async def init_db():
    Base.metadata.create_all(engine)
    logger.info("✅ Database tables created")

@lru_cache(maxsize=128)
def get_cached_user(telegram_id: int):
    """
    Кэширует данные пользователя для уменьшения нагрузки на базу данных.
    """
    with Session() as session:
        return session.query(User).filter_by(telegram_id=telegram_id).first()

async def get_user(telegram_id: int):
    """
    Получает пользователя из кэша или базы данных.
    """
    return get_cached_user(telegram_id)

async def create_user(telegram_id: int, full_name: str, username: str = None, is_admin: bool = False):
    with Session() as session:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            subscription_end=datetime.utcnow() + timedelta(days=3),
            is_admin=is_admin
        )
        session.add(user)
        try:
            session.commit()
            logger.info(f"✅ New user created: {telegram_id}")
            try:
                get_cached_user.cache_clear()
            except Exception:
                pass
            return user
        except IntegrityError:
            # Возможно конкурентное создание — откатываем транзакцию и возвращаем существующего пользователя
            session.rollback()
            existing = session.query(User).filter_by(telegram_id=telegram_id).first()
            if existing:
                logger.info(f"ℹ️ User already exists (race): {telegram_id}")
                try:
                    get_cached_user.cache_clear()
                except Exception:
                    pass
                return existing
            # Если по какой-то причине пользователь всё ещё не найден, пробрасываем ошибку
            raise

async def delete_user_profile(telegram_id: int, profile_id: int = None):
    """Удаляет профиль пользователя"""
    with Session() as session:
        if profile_id:
            # Удаляем конкретный профиль
            profile = session.query(VLESSProfile).filter_by(id=profile_id, telegram_id=telegram_id).first()
            if profile:
                session.delete(profile)
                session.commit()
                logger.info(f"✅ Profile deleted for {telegram_id}: {profile_id}")
                return True
        else:
            # Удаляем все профили пользователя
            session.query(VLESSProfile).filter_by(telegram_id=telegram_id).delete()
            session.commit()
            logger.info(f"✅ All profiles deleted for {telegram_id}")
        return False

async def get_user_profiles(telegram_id: int):
    """Получает все профили пользователя"""
    with Session() as session:
        return session.query(VLESSProfile).filter_by(telegram_id=telegram_id).all()

async def save_vless_profile(telegram_id: int, profile_id: str, vless_url: str, email: str, device_name: str = "Device 1"):
    """Сохраняет новый VLESS профиль"""
    with Session() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            # Проверяем лимит устройств (максимум 1 активное устройство)
            active_profiles = session.query(VLESSProfile).filter_by(telegram_id=telegram_id).all()
            
            # Если уже есть профиль, удаляем его перед созданием нового
            if active_profiles:
                for prof in active_profiles:
                    session.delete(prof)
            
            # Создаем новый профиль
            new_profile = VLESSProfile(
                user_id=user.id,
                telegram_id=telegram_id,
                vless_profile_id=profile_id,
                vless_url=vless_url,
                email=email,
                device_name=device_name
            )
            session.add(new_profile)
            session.commit()
            logger.info(f"✅ VLESS profile saved for {telegram_id}")
            return new_profile
        return None

async def update_subscription(telegram_id: int, months: int):
    """Обновляет подписку с учетом текущего состояния"""
    with Session() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            now = datetime.utcnow()
            # Если подписка активна, добавляем к текущей дате окончания
            if user.subscription_end and user.subscription_end > now:
                user.subscription_end += timedelta(days=months * 30)
            else:
                # Если подписка истекла или не установлена, начинаем с текущей даты
                user.subscription_end = now + timedelta(days=months * 30)
            
            # Сбрасываем флаг уведомления
            user.notified = False
            session.commit()
            logger.info(f"✅ Subscription updated for {telegram_id}: +{months} months")
            return True
        return False

async def get_all_users(with_subscription: bool = None):
    """
    Оптимизированный запрос для получения всех пользователей с фильтрацией.
    """
    with Session() as session:
        query = session.query(User)
        if with_subscription is not None:
            if with_subscription:
                query = query.filter(User.subscription_end.isnot(None), User.subscription_end > datetime.utcnow())
            else:
                query = query.filter((User.subscription_end.is_(None)) | (User.subscription_end <= datetime.utcnow()))
        return query.limit(100).all()  # Ограничиваем количество записей для уменьшения нагрузки

async def create_static_profile(name: str, vless_url: str):
    with Session() as session:
        profile = StaticProfile(name=name, vless_url=vless_url)
        session.add(profile)
        session.commit()
        logger.info(f"✅ Static profile created: {name}")
        return profile

async def get_static_profiles():
    with Session() as session:
        return session.query(StaticProfile).all()

async def get_user_stats():
    with Session() as session:
        total = session.query(func.count(User.id)).scalar()
        with_sub = session.query(func.count(User.id)).filter(User.subscription_end.isnot(None), User.subscription_end > datetime.utcnow()).scalar()
        without_sub = total - with_sub
        return total, with_sub, without_sub