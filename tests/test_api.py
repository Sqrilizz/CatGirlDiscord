#!/usr/bin/env python3
"""
Test script for Waifu.im API
Run this to test API connectivity before running the bot
"""

import asyncio
import json
from waifu_api import WaifuAPI

async def test_api():
    """Test the Waifu.im API functionality"""
    print("🧪 Тестирование Waifu.im API...")
    
    async with WaifuAPI() as api:
        # Test 1: Get random waifu
        print("\n1️⃣ Тест: Случайная waifu...")
        result = await api.get_random_waifu()
        if result and 'images' in result:
            image = result['images'][0]
            print(f"✅ Успешно! URL: {image['url']}")
            print(f"   Размер: {image['width']}x{image['height']}")
            print(f"   NSFW: {image['is_nsfw']}")
        else:
            print("❌ Ошибка получения случайной waifu")
            return False
        
        # Test 2: Get waifu by tag
        print("\n2️⃣ Тест: Waifu с тегом 'maid'...")
        result = await api.get_waifu_by_tag('maid')
        if result and 'images' in result:
            image = result['images'][0]
            tags = [tag['name'] for tag in image.get('tags', [])]
            print(f"✅ Успешно! URL: {image['url']}")
            print(f"   Теги: {', '.join(tags)}")
        else:
            print("❌ Ошибка получения waifu с тегом")
            return False
        
        # Test 3: Get multiple waifus
        print("\n3️⃣ Тест: Несколько waifu (3 штуки)...")
        result = await api.get_multiple_waifus(3)
        if result and 'images' in result:
            print(f"✅ Успешно! Получено {len(result['images'])} изображений")
            for i, image in enumerate(result['images'], 1):
                print(f"   {i}. {image['url']}")
        else:
            print("❌ Ошибка получения нескольких waifu")
            return False
        
        # Test 4: NSFW test (optional)
        print("\n4️⃣ Тест: NSFW waifu...")
        result = await api.get_random_waifu(nsfw=True)
        if result and 'images' in result:
            image = result['images'][0]
            print(f"✅ Успешно! NSFW: {image['is_nsfw']}")
        else:
            print("❌ Ошибка получения NSFW waifu")
            return False
        
        # Test 5: Get available tags
        print("\n5️⃣ Тест: Получение доступных тегов...")
        result = await api.get_available_tags()
        if result and ('versatile' in result or 'nsfw' in result):
            versatile_count = len(result.get('versatile', []))
            nsfw_count = len(result.get('nsfw', []))
            print(f"✅ Успешно! Versatile тегов: {versatile_count}, NSFW тегов: {nsfw_count}")
            
            # Show some example tags
            if result.get('versatile'):
                example_versatile = []
                for tag in result['versatile'][:5]:
                    if isinstance(tag, dict):
                        example_versatile.append(tag.get('name', 'Unknown'))
                    elif isinstance(tag, str):
                        example_versatile.append(tag)
                print(f"   Примеры versatile тегов: {', '.join(example_versatile)}")
            if result.get('nsfw'):
                example_nsfw = []
                for tag in result['nsfw'][:3]:
                    if isinstance(tag, dict):
                        example_nsfw.append(tag.get('name', 'Unknown'))
                    elif isinstance(tag, str):
                        example_nsfw.append(tag)
                print(f"   Примеры NSFW тегов: {', '.join(example_nsfw)}")
        else:
            print("❌ Ошибка получения тегов")
            return False
    
    print("\n🎉 Все тесты пройдены успешно!")
    print("🚀 API готов к использованию в Discord боте")
    return True

async def test_detailed_search():
    """Test advanced search features"""
    print("\n🔍 Тест расширенного поиска...")
    
    async with WaifuAPI() as api:
        # Test with multiple parameters
        result = await api.search_images(
            included_tags=['waifu'],
            is_nsfw='false',
            limit=2,
            height='>=1080'
        )
        
        if result and 'images' in result:
            print(f"✅ Расширенный поиск: найдено {len(result['images'])} изображений")
            for image in result['images']:
                print(f"   - {image['width']}x{image['height']} px, NSFW: {image['is_nsfw']}")
        else:
            print("❌ Ошибка расширенного поиска")

if __name__ == "__main__":
    print("🌸 CatGirl Discord Bot - Тест API")
    print("=" * 50)
    
    try:
        # Run basic tests
        success = asyncio.run(test_api())
        
        if success:
            # Run advanced tests
            asyncio.run(test_detailed_search())
            
            print("\n" + "=" * 50)
            print("✅ Все тесты завершены успешно!")
            print("💡 Теперь вы можете запустить бота: python bot.py")
        else:
            print("\n❌ Некоторые тесты не прошли")
            print("🔧 Проверьте подключение к интернету и доступность API")
            
    except KeyboardInterrupt:
        print("\n👋 Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка тестирования: {e}")
        print("🔧 Проверьте установку зависимостей: pip install -r requirements.txt")
