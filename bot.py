import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
from typing import Optional, List
from waifu_api import WaifuAPI
from config import DISCORD_TOKEN, MAX_IMAGES_PER_REQUEST

# Global cache for tags
ALL_TAGS = []
SFW_TAGS = []
NSFW_TAGS = []
VERSATILE_TAGS = []

async def load_available_tags():
    """Load all available tags from the API and categorize them"""
    global ALL_TAGS, SFW_TAGS, NSFW_TAGS, VERSATILE_TAGS
    
    try:
        async with WaifuAPI() as api:
            result = await api.get_available_tags()
            
            if result and 'versatile' in result and 'nsfw' in result:
                # Get versatile (SFW + some that work in both) tags
                versatile_data = result['versatile']
                nsfw_data = result['nsfw']
                
                # Extract tag names (API может возвращать строки или объекты)
                VERSATILE_TAGS = []
                for tag in versatile_data:
                    if isinstance(tag, dict) and 'name' in tag:
                        VERSATILE_TAGS.append(tag['name'])
                    elif isinstance(tag, str):
                        VERSATILE_TAGS.append(tag)
                
                NSFW_TAGS = []
                for tag in nsfw_data:
                    if isinstance(tag, dict) and 'name' in tag:
                        NSFW_TAGS.append(tag['name'])
                    elif isinstance(tag, str):
                        NSFW_TAGS.append(tag)
                
                # SFW tags are versatile tags that are not explicitly NSFW
                SFW_TAGS = [tag for tag in VERSATILE_TAGS if tag not in NSFW_TAGS]
                
                # All tags combined
                ALL_TAGS = list(set(VERSATILE_TAGS + NSFW_TAGS))
                
                print(f"✅ Загружено тегов: SFW={len(SFW_TAGS)}, NSFW={len(NSFW_TAGS)}, Всего={len(ALL_TAGS)}")
                return True
            else:
                print("❌ Не удалось получить теги с API, используем базовые теги")
                # Fallback to basic tags
                VERSATILE_TAGS = ['waifu', 'maid', 'uniform', 'selfies']
                SFW_TAGS = VERSATILE_TAGS.copy()
                NSFW_TAGS = ['hentai', 'ecchi', 'ero']
                ALL_TAGS = list(set(VERSATILE_TAGS + NSFW_TAGS))
                return False
                
    except Exception as e:
        print(f"❌ Ошибка загрузки тегов: {e}")
        # Fallback to basic tags
        VERSATILE_TAGS = ['waifu', 'maid', 'uniform', 'selfies']
        SFW_TAGS = VERSATILE_TAGS.copy()
        NSFW_TAGS = ['hentai', 'ecchi', 'ero']
        ALL_TAGS = list(set(VERSATILE_TAGS + NSFW_TAGS))
        return False

class WaifuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # Убираем привилегированные интенты, которые не нужны для slash команд
        intents.message_content = False
        intents.members = False
        intents.presences = False
        super().__init__(command_prefix='!', intents=intents)
        self.waifu_api = None
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        self.waifu_api = WaifuAPI()
        await self.waifu_api.__aenter__()
        
        # Load available tags from API
        print("🔄 Загружаем доступные теги...")
        await load_available_tags()
        
        # Настройка команд для работы везде (включая групповые DM)
        for command in self.tree.get_commands():
            # Разрешаем команды в DM и групповых чатах
            command.extras = {"dm_permission": True}
        
        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            print(f"✅ Синхронизировано {len(synced)} команд(ы)")
            for cmd in synced:
                print(f"   • /{cmd.name}")
        except Exception as e:
            print(f"❌ Ошибка синхронизации команд: {e}")
            # Попробуем принудительную синхронизацию
            try:
                self.tree.clear_commands(guild=None)
                synced = await self.tree.sync()
                print(f"✅ Принудительно синхронизировано {len(synced)} команд(ы)")
            except Exception as e2:
                print(f"❌ Критическая ошибка синхронизации: {e2}")
    
    async def on_ready(self):
        print(f'🤖 {self.user} подключился к Discord!')
        print(f'📋 Bot ID: {self.user.id}')
        print(f'🌐 Подключен к {len(self.guilds)} серверам')
        
        # Показываем доступные команды
        commands = [cmd.name for cmd in self.tree.get_commands()]
        print(f'📝 Зарегистрированные команды: {", ".join(commands)}')
        
        # Set bot status
        activity = discord.Activity(type=discord.ActivityType.watching, name="аниме девочек 🌸")
        await self.change_presence(activity=activity)
        
        print("✅ Бот готов к работе!")
        print("💡 Если команды не видны, подождите до 1 часа или перезапустите Discord")
    
    async def close(self):
        """Clean up when bot shuts down"""
        if self.waifu_api:
            await self.waifu_api.close()

bot = WaifuBot()

async def process_waifu_request(interaction: discord.Interaction, nsfw: bool = False, tag: Optional[str] = None, count: int = 1):
    """Common function to process waifu requests"""
    # Check NSFW permissions
    if nsfw:
        # В серверных каналах проверяем NSFW статус
        if hasattr(interaction.channel, 'is_nsfw') and not interaction.channel.is_nsfw():
            await interaction.response.send_message(
                "❌ NSFW контент доступен только в NSFW каналах!",
                ephemeral=True
            )
            return
        # В DM разрешаем NSFW (пользователь сам решает)
    
    # Validate count
    count = max(1, min(count, 5))
    
    await interaction.response.defer()
    
    try:
        # Get images from API
        if tag:
            # Validate tag against all available tags
            if nsfw:
                available_tags = list(set(SFW_TAGS + VERSATILE_TAGS + NSFW_TAGS))
            else:
                available_tags = list(set(SFW_TAGS + VERSATILE_TAGS))
            
            if tag not in available_tags:
                # Show a more helpful error message with suggestions
                similar_tags = [t for t in available_tags if tag.lower() in t.lower() or t.lower() in tag.lower()][:5]
                error_msg = f"❌ Неизвестный тег: `{tag}`"
                if similar_tags:
                    error_msg += f"\n💡 Возможно, вы имели в виду: {', '.join(similar_tags)}"
                error_msg += f"\n📝 Используйте `/tags` для просмотра всех доступных тегов"
                
                await interaction.followup.send(error_msg, ephemeral=True)
                return
            
            result = await bot.waifu_api.get_multiple_waifus(count, nsfw, [tag])
        else:
            result = await bot.waifu_api.get_multiple_waifus(count, nsfw)
        
        if not result:
            await interaction.followup.send(
                "❌ Не удалось получить ответ от API.\n" +
                "💡 Возможные причины:\n" +
                "• API временно недоступен\n" +
                "• Превышен лимит запросов\n" +
                "• Проблемы с интернетом\n\n" +
                "Попробуйте через несколько секунд."
            )
            return
            
        if 'images' not in result:
            await interaction.followup.send("❌ API вернул некорректный ответ. Попробуйте позже.")
            return
            
        if not result['images']:
            await interaction.followup.send("❌ Не найдено изображений по вашему запросу. Попробуйте другие параметры.")
            return
        
        images = result['images']
        
        # Create embeds for each image
        embeds = []
        for i, image in enumerate(images):
            embed = discord.Embed(
                title=f"🌸 Waifu #{i+1}" + (f" - {tag}" if tag else ""),
                color=discord.Color.from_str(image.get('dominant_color', '#FF69B4'))
            )
            embed.set_image(url=image.get('url', ''))
            
            # Add image info
            tags = image.get('tags') or []
            tags_str = ', '.join([t.get('name', '') for t in tags if t and isinstance(t, dict)])
            embed.add_field(name="Теги", value=tags_str or "Нет", inline=True)
            embed.add_field(name="Размер", value=f"{image.get('width', '?')}x{image.get('height', '?')}", inline=True)
            embed.add_field(name="NSFW", value="Да" if image.get('is_nsfw') else "Нет", inline=True)
            
            artist = image.get('artist')
            if artist and isinstance(artist, dict) and artist.get('name'):
                embed.set_footer(text=f"Художник: {artist['name']}")
            
            embeds.append(embed)
        
        # Send embeds (Discord allows up to 10 embeds per message)
        await interaction.followup.send(embeds=embeds)
        
    except Exception as e:
        print(f"Error in waifu command: {e}")
        await interaction.followup.send("❌ Произошла ошибка при получении изображения.")

@bot.tree.command(name="waifu", description="Получить случайную картинку аниме девочки")
@app_commands.describe(
    nsfw="Включить NSFW контент (только в NSFW каналах)",
    tag="Выбрать конкретный тег",
    count="Количество картинок (1-5)"
)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def waifu_command(
    interaction: discord.Interaction,
    nsfw: bool = False,
    tag: Optional[str] = None,
    count: int = 1
):
    await process_waifu_request(interaction, nsfw, tag, count)

@bot.tree.command(name="nsfw", description="Получить NSFW картинку аниме девочки")
@app_commands.describe(
    tag="Выбрать конкретный NSFW тег",
    count="Количество картинок (1-5)"
)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def nsfw_command(
    interaction: discord.Interaction,
    tag: Optional[str] = None,
    count: int = 1
):
    # Check if command is used in NSFW channel (не проверяем в DM)
    if hasattr(interaction.channel, 'is_nsfw') and not interaction.channel.is_nsfw():
        await interaction.response.send_message(
            "❌ Эта команда доступна только в NSFW каналах или личных сообщениях!",
            ephemeral=True
        )
        return
    
    # Use the common function with NSFW enabled
    await process_waifu_request(interaction, nsfw=True, tag=tag, count=count)

@bot.tree.command(name="tags", description="Показать доступные теги")
@app_commands.describe(
    nsfw="Показать NSFW теги",
    search="Поиск по названию тега"
)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def tags_command(interaction: discord.Interaction, nsfw: bool = False, search: Optional[str] = None):
    if nsfw and hasattr(interaction.channel, 'is_nsfw') and not interaction.channel.is_nsfw():
        await interaction.response.send_message(
            "❌ NSFW теги можно просматривать только в NSFW каналах или личных сообщениях!",
            ephemeral=True
        )
        return
    
    # Determine which tags to show
    if nsfw:
        available_tags = NSFW_TAGS
        title = "🔞 NSFW теги"
        color = discord.Color.red()
    else:
        available_tags = SFW_TAGS + VERSATILE_TAGS
        title = "🏷️ SFW теги"
        color = discord.Color.blue()
    
    # Filter tags if search is provided
    if search:
        available_tags = [tag for tag in available_tags if search.lower() in tag.lower()]
        title += f" (поиск: '{search}')"
    
    if not available_tags:
        await interaction.response.send_message(
            f"❌ Не найдено тегов по запросу '{search}'",
            ephemeral=True
        )
        return
    
    # Split tags into chunks for pagination (Discord embed field limit is 1024 chars)
    def chunk_tags(tags, max_length=900):
        chunks = []
        current_chunk = []
        current_length = 0
        
        for tag in sorted(tags):
            tag_with_comma = tag + ", "
            if current_length + len(tag_with_comma) > max_length and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [tag]
                current_length = len(tag_with_comma)
            else:
                current_chunk.append(tag)
                current_length += len(tag_with_comma)
        
        if current_chunk:
            chunks.append(current_chunk)
        return chunks
    
    tag_chunks = chunk_tags(available_tags)
    
    embed = discord.Embed(
        title=title,
        description=f"Всего найдено: **{len(available_tags)}** тегов",
        color=color
    )
    
    # Add tag chunks as fields
    for i, chunk in enumerate(tag_chunks[:5]):  # Limit to 5 fields max
        field_name = f"Теги (часть {i+1})" if len(tag_chunks) > 1 else "Доступные теги"
        field_value = ", ".join(chunk)
        embed.add_field(name=field_name, value=field_value, inline=False)
    
    if len(tag_chunks) > 5:
        embed.add_field(
            name="⚠️ Внимание", 
            value=f"Показано только первые 5 групп тегов. Используйте поиск для фильтрации.",
            inline=False
        )
    
    embed.set_footer(text="Используйте /waifu tag:<тег> для поиска по тегу")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Показать справку по командам бота")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Справка по командам",
        description="Бот для получения картинок аниме девочек",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="/waifu",
        value="Получить случайную картинку\n`nsfw:` включить NSFW (только в NSFW каналах)\n`tag:` выбрать тег\n`count:` количество (1-5)",
        inline=False
    )
    
    embed.add_field(
        name="/nsfw",
        value="Получить NSFW картинку (только в NSFW каналах)\n`tag:` выбрать NSFW тег\n`count:` количество (1-5)",
        inline=False
    )
    
    embed.add_field(
        name="/tags",
        value="Показать доступные теги\n`nsfw:` показать NSFW теги",
        inline=False
    )
    
    embed.add_field(
        name="/help",
        value="Показать эту справку",
        inline=False
    )
    
    embed.set_footer(text="Создано на основе Waifu.im API")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reload_tags", description="Обновить список доступных тегов с API (только для администраторов)")
async def reload_tags_command(interaction: discord.Interaction):
    # Check if user has administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Эта команда доступна только администраторам сервера!",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        print("🔄 Администратор запросил обновление тегов...")
        success = await load_available_tags()
        
        if success:
            embed = discord.Embed(
                title="✅ Теги успешно обновлены!",
                description=f"Загружено тегов:\n• SFW: **{len(SFW_TAGS)}**\n• NSFW: **{len(NSFW_TAGS)}**\n• Всего: **{len(ALL_TAGS)}**",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="⚠️ Теги обновлены с ошибками",
                description="Используются базовые теги. Проверьте подключение к API.",
                color=discord.Color.orange()
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"❌ Ошибка обновления тегов: {e}")
        await interaction.followup.send(
            "❌ Произошла ошибка при обновлении тегов. Проверьте логи бота.",
            ephemeral=True
        )

@bot.tree.command(name="sync", description="Принудительно синхронизировать команды (только для администраторов)")
async def sync_command(interaction: discord.Interaction):
    # Check if user has administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Эта команда доступна только администраторам сервера!",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        print("🔄 Администратор запросил синхронизацию команд...")
        synced = await bot.tree.sync()
        
        embed = discord.Embed(
            title="✅ Команды синхронизированы!",
            description=f"Синхронизировано **{len(synced)}** команд(ы):\n" + 
                       "\n".join([f"• `/{cmd.name}`" for cmd in synced]),
            color=discord.Color.green()
        )
        embed.set_footer(text="Команды могут появиться в Discord через несколько минут")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"❌ Ошибка синхронизации команд: {e}")
        await interaction.followup.send(
            f"❌ Произошла ошибка при синхронизации команд: {e}",
            ephemeral=True
        )

# Autocomplete for tags
@waifu_command.autocomplete('tag')
async def waifu_tag_autocomplete(interaction: discord.Interaction, current: str):
    # Determine available tags based on NSFW channel or DM
    if not hasattr(interaction.channel, 'is_nsfw') or interaction.channel.is_nsfw():
        # In NSFW channels or DM, show all tags
        available_tags = list(set(SFW_TAGS + VERSATILE_TAGS + NSFW_TAGS))
    else:
        # In SFW channels, only show SFW and versatile tags
        available_tags = list(set(SFW_TAGS + VERSATILE_TAGS))
    
    # Filter tags based on current input and sort by relevance
    if current:
        # Prioritize exact matches and starts-with matches
        exact_matches = [tag for tag in available_tags if tag.lower() == current.lower()]
        starts_with = [tag for tag in available_tags if tag.lower().startswith(current.lower()) and tag not in exact_matches]
        contains = [tag for tag in available_tags if current.lower() in tag.lower() and tag not in exact_matches and tag not in starts_with]
        
        filtered_tags = exact_matches + starts_with + contains
    else:
        # If no input, show popular tags first
        popular_tags = ['waifu', 'maid', 'uniform', 'selfies', 'oppai', 'ass']
        filtered_tags = [tag for tag in popular_tags if tag in available_tags] + \
                       [tag for tag in available_tags if tag not in popular_tags]
    
    # Convert to choices
    choices = [
        app_commands.Choice(name=tag, value=tag)
        for tag in filtered_tags[:25]  # Discord limit
    ]
    
    return choices

@nsfw_command.autocomplete('tag')
async def nsfw_tag_autocomplete(interaction: discord.Interaction, current: str):
    # Filter NSFW tags based on current input
    if current:
        exact_matches = [tag for tag in NSFW_TAGS if tag.lower() == current.lower()]
        starts_with = [tag for tag in NSFW_TAGS if tag.lower().startswith(current.lower()) and tag not in exact_matches]
        contains = [tag for tag in NSFW_TAGS if current.lower() in tag.lower() and tag not in exact_matches and tag not in starts_with]
        
        filtered_tags = exact_matches + starts_with + contains
    else:
        # Show popular NSFW tags first
        popular_nsfw = ['hentai', 'ecchi', 'ero', 'ass', 'oppai']
        filtered_tags = [tag for tag in popular_nsfw if tag in NSFW_TAGS] + \
                       [tag for tag in NSFW_TAGS if tag not in popular_nsfw]
    
    choices = [
        app_commands.Choice(name=tag, value=tag)
        for tag in filtered_tags[:25]
    ]
    
    return choices

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN не найден в переменных окружения!")
        print("Создайте файл .env на основе .env.example")
        exit(1)
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
