#!/usr/bin/env python3
"""
Скрипт для получения информации из панели 3X-UI (простая версия)
"""
import urllib.request
import urllib.error
import json
import http.cookiejar
import urllib.parse

def get_panel_info():
    """Получает информацию о панели 3X-UI"""
    
    # Ваши данные
    panel_url = "http://85.192.26.36:8080/eWaOoqgUCezndPKXkz"
    username = "Nck4vyaD6R"
    password = "uIQ1pwQWFU"
    inbound_id = 1
    
    # Создаем cookie jar для сохранения сессии
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    urllib.request.install_opener(opener)
    
    try:
        # Логин
        print("🔐 Авторизация в панели...")
        login_url = f"{panel_url}/login"
        auth_data = urllib.parse.urlencode({
            "username": username,
            "password": password
        }).encode('utf-8')
        
        req = urllib.request.Request(login_url, data=auth_data)
        with opener.open(req) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            if not resp_data.get("success"):
                print(f"❌ Авторизация не удалась: {resp_data.get('msg')}")
                return
            
            print("✅ Авторизация успешна")
        
        # Получение данных инбаунда
        print(f"\n📡 Получение данных инбаунда (ID: {inbound_id})...")
        # Пробуем разные варианты URL
        urls_to_try = [
            f"{panel_url}/api/inbounds/get/{inbound_id}",
            f"{panel_url.rsplit('/', 1)[0]}/api/inbounds/get/{inbound_id}",
            f"http://85.192.26.36:8080/api/inbounds/get/{inbound_id}",
        ]
        
        inbound = None
        for inbound_url in urls_to_try:
            try:
                print(f"  Пытаемся: {inbound_url}")
                with opener.open(inbound_url) as resp:
                    inbound_data = json.loads(resp.read().decode('utf-8'))
                    if inbound_data.get("success"):
                        inbound = inbound_data.get("obj")
                        print(f"✅ Инбаунд получен!")
                        break
            except urllib.error.URLError as e:
                print(f"  ❌ Не подходит: {e}")
                continue
        
        if not inbound:
            print("❌ Не удалось получить инбаунд ни с одного URL")
            return
        
        # Вывод информации
        print("\n" + "="*60)
        print("📋 ИНФОРМАЦИЯ ДЛЯ КОНФИГУРАЦИИ")
        print("="*60)
        
        print(f"\n🔧 Основные параметры:")
        print(f"  Port: {inbound.get('port')}")
        print(f"  Protocol: {inbound.get('protocol')}")
        print(f"  Remark: {inbound.get('remark')}")
        
        # Parsing streamSettings для получения Reality параметров
        try:
            stream_settings = json.loads(inbound.get('streamSettings', '{}'))
            print(f"\n🔐 Stream Settings (первые 500 символов):")
            stream_str = json.dumps(stream_settings, indent=2, ensure_ascii=False)
            print(stream_str[:500])
            
            if 'realitySettings' in stream_settings:
                reality = stream_settings['realitySettings']
                print(f"\n✨ Reality параметры найдены:")
                print(f"  Public Key: {reality.get('publicKey', 'НЕ НАЙДЕН')}")
                print(f"  Short IDs: {reality.get('shortIds', [])}")
                
                if reality.get('shortIds'):
                    print(f"\n⚠️  IMPORTANT: REALITY_SHORT_ID:")
                    for i, sid in enumerate(reality.get('shortIds')):
                        print(f"    [{i}] {sid}")
        except Exception as e:
            print(f"⚠️  Ошибка при парсинге streamSettings: {e}")
        
        # Информация о клиентах
        try:
            settings = json.loads(inbound.get('settings', '{}'))
            clients = settings.get('clients', [])
            print(f"\n👥 Количество клиентов: {len(clients)}")
        except Exception as e:
            print(f"⚠️  Ошибка при парсинге клиентов: {e}")
        
        print("\n" + "="*60)
        print("📝 РЕКОМЕНДУЕМЫЕ ЗНАЧЕНИЯ ДЛЯ config.py:")
        print("="*60)
        
        try:
            stream_settings = json.loads(inbound.get('streamSettings', '{}'))
            reality = stream_settings.get('realitySettings', {})
            short_ids = reality.get('shortIds', ['UNKNOWN'])
            
            print(f"""
# Скопируйте эти значения в config.py:

XUI_API_URL = "http://85.192.26.36:8080/eWaOoqgUCezndPKXkz"
XUI_USERNAME = "Nck4vyaD6R"
XUI_PASSWORD = "uIQ1pwQWFU"
XUI_HOST = "85.192.26.36"  # или ваш домен
XUI_SERVER_NAME = "web.max.ru"
INBOUND_ID = {inbound_id}
REALITY_PUBLIC_KEY = "{reality.get('publicKey', 'UNKNOWN')}"
REALITY_SNI = "web.max.ru"
REALITY_SHORT_ID = "{short_ids[0]}"  # <- Вот это значение!
REALITY_FINGERPRINT = "chrome"
REALITY_SPIDER_X = "/"
""")
        except Exception as e:
            print(f"❌ Ошибка при формировании значений: {e}")
    
    except urllib.error.URLError as e:
        print(f"❌ Ошибка подключения: {e}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    get_panel_info()
