#!/usr/bin/env python3.12
"""
Проверка конфигурации XRay VPN бота
"""
import sys
sys.path.insert(0, '/Users/vadim/Desktop/XRay-bot-master/src')

from config import config
from datetime import datetime

print("="*70)
print("🔍 ПРОВЕРКА КОНФИГУРАЦИИ XRAY VPN БОТА")
print("="*70)

print("\n✅ TELEGRAM BOT:")
print(f"  BOT_TOKEN: {config.BOT_TOKEN[:20]}...{config.BOT_TOKEN[-10:]}")
print(f"  ADMINS: {config.ADMINS}")

print("\n✅ 3X-UI PANEL:")
print(f"  API URL: {config.XUI_API_URL}")
print(f"  Username: {config.XUI_USERNAME}")
print(f"  Password: {'*' * len(config.XUI_PASSWORD)}")
print(f"  Host: {config.XUI_HOST}")
print(f"  Server Name: {config.XUI_SERVER_NAME}")
print(f"  Inbound ID: {config.INBOUND_ID}")

print("\n✅ REALITY PROTOCOL:")
print(f"  Public Key: {config.REALITY_PUBLIC_KEY}")
print(f"  Fingerprint: {config.REALITY_FINGERPRINT}")
print(f"  SNI: {config.REALITY_SNI}")
print(f"  Short ID: {config.REALITY_SHORT_ID}")
print(f"  Spider X: {config.REALITY_SPIDER_X}")

print("\n✅ PRICING:")
for months, prices in config.PRICES.items():
    final_price = config.calculate_price(months)
    print(f"  {months} мес: {prices['base_price']} руб → {final_price} руб (скидка {prices['discount_percent']}%)")

print("\n" + "="*70)
print("⚠️  ПРОВЕРКА КРИТИЧЕСКИХ ПАРАМЕТРОВ:")
print("="*70)

errors = []

if not config.BOT_TOKEN or config.BOT_TOKEN == "":
    errors.append("❌ BOT_TOKEN не заполнен")
elif len(config.BOT_TOKEN) < 20:
    errors.append("❌ BOT_TOKEN выглядит некорректно (слишком короткий)")
else:
    print("✅ BOT_TOKEN выглядит корректным")

if not config.ADMINS:
    errors.append("❌ ADMINS не заполнен (нет администраторов)")
else:
    print(f"✅ ADMINS заполнен: {config.ADMINS}")

if config.XUI_HOST and config.XUI_HOST != "your-server.com":
    print(f"✅ XUI_HOST заполнен: {config.XUI_HOST}")
else:
    errors.append("❌ XUI_HOST не заполнен или это значение по умолчанию")

if config.REALITY_PUBLIC_KEY and config.REALITY_PUBLIC_KEY != "":
    print(f"✅ REALITY_PUBLIC_KEY заполнен")
else:
    errors.append("❌ REALITY_PUBLIC_KEY не заполнен")

if config.REALITY_SNI and config.REALITY_SNI != "example.com":
    print(f"✅ REALITY_SNI заполнен: {config.REALITY_SNI}")
else:
    errors.append("❌ REALITY_SNI не заполнен")

if config.REALITY_SHORT_ID and config.REALITY_SHORT_ID != "0":
    print(f"✅ REALITY_SHORT_ID заполнен: {config.REALITY_SHORT_ID}")
else:
    errors.append("⚠️  REALITY_SHORT_ID может быть не заполнен или равен '0'")

if config.INBOUND_ID > 0:
    print(f"✅ INBOUND_ID заполнен: {config.INBOUND_ID}")
else:
    errors.append("❌ INBOUND_ID некорректен")

print("\n" + "="*70)

if errors:
    print("\n⚠️  ПРОБЛЕМЫ НАЙДЕНЫ:\n")
    for error in errors:
        print(f"  {error}")
    
    print("\n" + "="*70)
    print("📝 ДЕЙСТВИЯ:")
    print("  1. Откройте файл: /Users/vadim/Desktop/XRay-bot-master/src/config.py")
    print("  2. Исправьте отмеченные параметры")
    print("  3. Для REALITY_SHORT_ID см. FIND_SHORT_ID.md")
    print("  4. Запустите проверку снова")
else:
    print("\n✅ ВСЕ ПАРАМЕТРЫ КОРРЕКТНО ЗАПОЛНЕНЫ!")
    print("\n🚀 БОТ ГОТОВ К ЗАПУСКУ!")
    print("\nКоманда запуска:")
    print("  /opt/homebrew/bin/python3.12 /Users/vadim/Desktop/XRay-bot-master/src/app.py")

print("\n" + "="*70)
