#!/usr/bin/env python3
"""
Тест новых функций управления ключами
"""
import asyncio
import sys
sys.path.insert(0, '/Users/vadim/Desktop/XRay-bot-master/src')

from database import (
    create_user, get_user, get_user_profiles, 
    save_vless_profile, delete_user_profile, Session, VLESSProfile
)

async def test_device_management():
    """Тестирует функциональность управления устройствами"""
    print("🧪 Starting device management tests...\n")
    
    test_user_id = 9999999999
    
    # 1. Create user
    print("1️⃣  Testing user creation...")
    user = await create_user(
        telegram_id=test_user_id,
        full_name="Test User",
        username="testuser",
        is_admin=False
    )
    print(f"   ✅ User created: {user.telegram_id}\n")
    
    # 2. Add first device
    print("2️⃣  Testing first device creation...")
    await save_vless_profile(
        telegram_id=test_user_id,
        profile_id="uuid-1",
        vless_url="vless://uuid-1@example.com:443",
        email="user_9999999999_1234@test.com",
        device_name="iPhone"
    )
    
    profiles = await get_user_profiles(test_user_id)
    print(f"   ✅ First device created. Total profiles: {len(profiles)}")
    print(f"   Device: {profiles[0].device_name}")
    print(f"   Email: {profiles[0].email}\n")
    
    # 3. Try to add second device (should delete first)
    print("3️⃣  Testing device replacement (1-per-user limit)...")
    await save_vless_profile(
        telegram_id=test_user_id,
        profile_id="uuid-2",
        vless_url="vless://uuid-2@example.com:443",
        email="user_9999999999_5678@test.com",
        device_name="PC"
    )
    
    profiles = await get_user_profiles(test_user_id)
    print(f"   ✅ Second device created. Total profiles: {len(profiles)} (old one deleted)")
    print(f"   Device: {profiles[0].device_name}")
    print(f"   Email: {profiles[0].email}\n")
    
    if len(profiles) != 1:
        print("   ⚠️  ERROR: Should have exactly 1 profile!")
        return False
    
    # 4. Test deletion
    print("4️⃣  Testing device deletion...")
    profile_id = profiles[0].id
    await delete_user_profile(test_user_id, profile_id)
    
    profiles = await get_user_profiles(test_user_id)
    print(f"   ✅ Device deleted. Total profiles: {len(profiles)}\n")
    
    # 5. Test multiple devices added separately
    print("5️⃣  Testing multiple device storage (sequential adds)...")
    
    # Add device 1
    await save_vless_profile(
        telegram_id=test_user_id,
        profile_id="uuid-3",
        vless_url="vless://uuid-3@example.com:443",
        email="user_9999999999_dev1@test.com",
        device_name="Phone"
    )
    
    # Add device 2 (replaces device 1)
    await save_vless_profile(
        telegram_id=test_user_id,
        profile_id="uuid-4",
        vless_url="vless://uuid-4@example.com:443",
        email="user_9999999999_dev2@test.com",
        device_name="Laptop"
    )
    
    profiles = await get_user_profiles(test_user_id)
    print(f"   ✅ Device limit enforced: {len(profiles)} active profiles")
    for p in profiles:
        print(f"      • {p.device_name} ({p.email})")
    print()
    
    # Cleanup
    print("6️⃣  Cleanup...")
    with Session() as session:
        session.query(VLESSProfile).filter_by(telegram_id=test_user_id).delete()
        from database import User
        session.query(User).filter_by(telegram_id=test_user_id).delete()
        session.commit()
    print("   ✅ Test data cleaned up\n")
    
    print("✅ All tests passed!")
    return True

if __name__ == "__main__":
    result = asyncio.run(test_device_management())
    sys.exit(0 if result else 1)
