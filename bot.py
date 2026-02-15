import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
from typing import Optional, List
from waifu_api import WaifuAPI
from furry_api import FurryAPI
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
                
                print(f"Loaded tags: SFW={len(SFW_TAGS)}, NSFW={len(NSFW_TAGS)}, Total={len(ALL_TAGS)}")
                return True
            else:
                print("Failed to get tags from API, using basic tags")
                # Fallback to basic tags
                VERSATILE_TAGS = ['waifu', 'maid', 'uniform', 'selfies']
                SFW_TAGS = VERSATILE_TAGS.copy()
                NSFW_TAGS = ['hentai', 'ecchi', 'ero']
                ALL_TAGS = list(set(VERSATILE_TAGS + NSFW_TAGS))
                return False
                
    except Exception as e:
        print(f"Error loading tags: {e}")
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
        self.furry_api = None
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        self.waifu_api = WaifuAPI()
        await self.waifu_api.__aenter__()
        
        self.furry_api = FurryAPI()
        await self.furry_api.__aenter__()
        
        # Load available tags from API
        print("Loading available tags...")
        await load_available_tags()
        
        # Настройка команд для работы везде (включая групповые DM)
        for command in self.tree.get_commands():
            # Разрешаем команды в DM и групповых чатах
            command.extras = {"dm_permission": True}
        
        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
            for cmd in synced:
                print(f"   • /{cmd.name}")
        except Exception as e:
            print(f"Error syncing commands: {e}")
            # Попробуем принудительную синхронизацию
            try:
                self.tree.clear_commands(guild=None)
                synced = await self.tree.sync()
                print(f"Force synced {len(synced)} command(s)")
            except Exception as e2:
                print(f"Critical sync error: {e2}")
    
    async def on_ready(self):
        print(f'{self.user} connected to Discord!')
        print(f'Bot ID: {self.user.id}')
        print(f'Connected to {len(self.guilds)} servers')
        
        # Показываем доступные команды
        commands = [cmd.name for cmd in self.tree.get_commands()]
        print(f'Registered commands: {", ".join(commands)}')
        
        # Set bot status
        activity = discord.Activity(type=discord.ActivityType.watching, name="anime girls")
        await self.change_presence(activity=activity)
        
        print("Bot is ready!")
        print("If commands are not visible, wait up to 1 hour or restart Discord")
    
    async def close(self):
        """Clean up when bot shuts down"""
        if self.waifu_api:
            await self.waifu_api.close()
        if self.furry_api:
            await self.furry_api.close()

bot = WaifuBot()

async def process_waifu_request(interaction: discord.Interaction, nsfw: bool = False, tag: Optional[str] = None, count: int = 1):
    """Common function to process waifu requests"""
    # Check NSFW permissions
    if nsfw:
        # В серверных каналах проверяем NSFW статус
        if hasattr(interaction.channel, 'is_nsfw') and not interaction.channel.is_nsfw():
            await interaction.response.send_message(
                "NSFW content is only available in NSFW channels!",
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
                error_msg = f"Unknown tag: `{tag}`"
                if similar_tags:
                    error_msg += f"\nDid you mean: {', '.join(similar_tags)}"
                error_msg += f"\nUse `/tags` to view all available tags"
                
                await interaction.followup.send(error_msg, ephemeral=True)
                return
            
            result = await bot.waifu_api.get_multiple_waifus(count, nsfw, [tag])
        else:
            result = await bot.waifu_api.get_multiple_waifus(count, nsfw)
        
        if not result:
            await interaction.followup.send(
                "Failed to get response from API.\n" +
                "Possible reasons:\n" +
                "- API temporarily unavailable\n" +
                "- Rate limit exceeded\n" +
                "- Internet connection issues\n\n" +
                "Try again in a few seconds."
            )
            return
            
        if 'images' not in result:
            await interaction.followup.send("API returned invalid response. Try again later.")
            return
            
        if not result['images']:
            await interaction.followup.send("No images found for your request. Try different parameters.")
            return
        
        images = result['images']
        
        # Create embeds for each image
        embeds = []
        for i, image in enumerate(images):
            embed = discord.Embed(
                title=f"Waifu #{i+1}" + (f" - {tag}" if tag else ""),
                color=discord.Color.from_str(image.get('dominant_color', '#FF69B4'))
            )
            embed.set_image(url=image.get('url', ''))
            
            # Add image info
            tags = image.get('tags') or []
            tags_str = ', '.join([t.get('name', '') for t in tags if t and isinstance(t, dict)])
            embed.add_field(name="Tags", value=tags_str or "None", inline=True)
            embed.add_field(name="Size", value=f"{image.get('width', '?')}x{image.get('height', '?')}", inline=True)
            embed.add_field(name="NSFW", value="Yes" if image.get('is_nsfw') else "No", inline=True)
            
            artist = image.get('artist')
            if artist and isinstance(artist, dict) and artist.get('name'):
                embed.set_footer(text=f"Artist: {artist['name']}")
            
            embeds.append(embed)
        
        # Send embeds (Discord allows up to 10 embeds per message)
        await interaction.followup.send(embeds=embeds)
        
    except Exception as e:
        print(f"Error in waifu command: {e}")
        await interaction.followup.send("An error occurred while fetching the image.")

@bot.tree.command(name="waifu", description="Get random anime girl picture")
@app_commands.describe(
    nsfw="Include NSFW content (NSFW channels only)",
    tag="Select specific tag",
    count="Number of pictures (1-5)"
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

@bot.tree.command(name="nsfw", description="Get NSFW anime girl picture")
@app_commands.describe(
    tag="Select specific NSFW tag",
    count="Number of pictures (1-5)"
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
            "This command is only available in NSFW channels or DMs!",
            ephemeral=True
        )
        return
    
    # Use the common function with NSFW enabled
    await process_waifu_request(interaction, nsfw=True, tag=tag, count=count)

@bot.tree.command(name="tags", description="Show available tags")
@app_commands.describe(
    nsfw="Show NSFW tags",
    search="Search by tag name"
)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def tags_command(interaction: discord.Interaction, nsfw: bool = False, search: Optional[str] = None):
    if nsfw and hasattr(interaction.channel, 'is_nsfw') and not interaction.channel.is_nsfw():
        await interaction.response.send_message(
            "NSFW tags can only be viewed in NSFW channels or DMs!",
            ephemeral=True
        )
        return
    
    # Determine which tags to show
    if nsfw:
        available_tags = NSFW_TAGS
        title = "NSFW Tags"
        color = discord.Color.red()
    else:
        available_tags = SFW_TAGS + VERSATILE_TAGS
        title = "SFW Tags"
        color = discord.Color.blue()
    
    # Filter tags if search is provided
    if search:
        available_tags = [tag for tag in available_tags if search.lower() in tag.lower()]
        title += f" (поиск: '{search}')"
    
    if not available_tags:
        await interaction.response.send_message(
            f"No tags found for query '{search}'",
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
        description=f"Total found: **{len(available_tags)}** tags",
        color=color
    )
    
    # Add tag chunks as fields
    for i, chunk in enumerate(tag_chunks[:5]):  # Limit to 5 fields max
        field_name = f"Tags (part {i+1})" if len(tag_chunks) > 1 else "Available tags"
        field_value = ", ".join(chunk)
        embed.add_field(name=field_name, value=field_value, inline=False)
    
    if len(tag_chunks) > 5:
        embed.add_field(
            name="Warning", 
            value=f"Only first 5 tag groups shown. Use search to filter.",
            inline=False
        )
    
    embed.set_footer(text="Use /waifu tag:<tag> to search by tag")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show bot commands help")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Commands Help",
        description="Bot for getting anime girl pictures",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="/waifu",
        value="Get random anime picture\n`nsfw:` include NSFW (NSFW channels only)\n`tag:` select tag\n`count:` number (1-5)",
        inline=False
    )
    
    embed.add_field(
        name="/nsfw",
        value="Get NSFW anime picture (NSFW channels only)\n`tag:` select NSFW tag\n`count:` number (1-5)",
        inline=False
    )
    
    embed.add_field(
        name="/furry",
        value="Get random furry picture\n`nsfw:` include NSFW (NSFW channels only)\n`tags:` search tags\n`count:` number (1-5)",
        inline=False
    )
    
    embed.add_field(
        name="/tags",
        value="Show available tags\n`nsfw:` show NSFW tags",
        inline=False
    )
    
    embed.add_field(
        name="/help",
        value="Show this help",
        inline=False
    )
    
    embed.set_footer(text="Created using Waifu.im API")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reload_tags", description="Обновить список доступных тегов с API (только для администраторов)")
async def reload_tags_command(interaction: discord.Interaction):
    # Специальный пользователь с правами администратора
    SUPER_ADMIN_ID = 1401591841115078862
    
    # Debug info
    print(f"reload_tags called by user ID: {interaction.user.id}")
    print(f"Is super admin: {interaction.user.id == SUPER_ADMIN_ID}")
    print(f"Has guild: {interaction.guild is not None}")
    if interaction.guild:
        print(f"Guild permissions: {interaction.user.guild_permissions.administrator}")
    
    # Супер-админ всегда имеет доступ, независимо от контекста
    if interaction.user.id == SUPER_ADMIN_ID:
        is_admin = True
    elif interaction.guild:
        # На сервере проверяем права администратора
        is_admin = interaction.user.guild_permissions.administrator
    else:
        # В других контекстах (DM, User Install) без супер-админа - нет доступа
        is_admin = False
    
    if not is_admin:
        await interaction.response.send_message(
            f"❌ Эта команда доступна только администраторам сервера!\nВаш ID: {interaction.user.id}",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        print("Administrator requested tags reload...")
        success = await load_available_tags()
        
        if success:
            embed = discord.Embed(
                title="Tags successfully updated!",
                description=f"Loaded tags:\n- SFW: **{len(SFW_TAGS)}**\n- NSFW: **{len(NSFW_TAGS)}**\n- Total: **{len(ALL_TAGS)}**",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Tags updated with errors",
                description="Using basic tags. Check API connection.",
                color=discord.Color.orange()
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error updating tags: {e}")
        await interaction.followup.send(
            "An error occurred while updating tags. Check bot logs.",
            ephemeral=True
        )

@bot.tree.command(name="sync", description="Принудительно синхронизировать команды (только для администраторов)")
async def sync_command(interaction: discord.Interaction):
    # Специальный пользователь с правами администратора
    SUPER_ADMIN_ID = 1401591841115078862
    
    # Debug info
    print(f"sync called by user ID: {interaction.user.id}")
    print(f"Is super admin: {interaction.user.id == SUPER_ADMIN_ID}")
    print(f"Has guild: {interaction.guild is not None}")
    if interaction.guild:
        print(f"Guild permissions: {interaction.user.guild_permissions.administrator}")
    
    # Супер-админ всегда имеет доступ, независимо от контекста
    if interaction.user.id == SUPER_ADMIN_ID:
        is_admin = True
    elif interaction.guild:
        # На сервере проверяем права администратора
        is_admin = interaction.user.guild_permissions.administrator
    else:
        # В других контекстах (DM, User Install) без супер-админа - нет доступа
        is_admin = False
    
    if not is_admin:
        await interaction.response.send_message(
            f"❌ Эта команда доступна только администраторам сервера!\nВаш ID: {interaction.user.id}",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        print("Administrator requested command sync...")
        synced = await bot.tree.sync()
        
        embed = discord.Embed(
            title="Commands synced!",
            description=f"Synced **{len(synced)}** command(s):\n" + 
                       "\n".join([f"• `/{cmd.name}`" for cmd in synced]),
            color=discord.Color.green()
        )
        embed.set_footer(text="Commands may appear in Discord after a few minutes")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error syncing commands: {e}")
        await interaction.followup.send(
            f"An error occurred while syncing commands: {e}",
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

@bot.tree.command(name="furry", description="Get random furry picture")
@app_commands.describe(
    nsfw="Include NSFW content (NSFW channels only)",
    tags="Search tags (space separated)",
    count="Number of pictures (1-5)"
)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def furry_command(
    interaction: discord.Interaction,
    nsfw: bool = False,
    tags: Optional[str] = None,
    count: int = 1
):
    if nsfw and hasattr(interaction.channel, 'is_nsfw') and not interaction.channel.is_nsfw():
        await interaction.response.send_message(
            "NSFW content is only available in NSFW channels!",
            ephemeral=True
        )
        return
    
    count = max(1, min(count, 5))
    
    await interaction.response.defer()
    
    try:
        tag_list = tags.split() if tags else None
        result = await bot.furry_api.get_furry_by_tags(tag_list, nsfw=nsfw, count=count) if tag_list else await bot.furry_api.get_random_furry(nsfw=nsfw, count=count)
        
        if not result or not result.get('images'):
            await interaction.followup.send("No furry images found. Try different tags or parameters.")
            return
        
        images = result['images']
        
        embeds = []
        for i, image in enumerate(images):
            embed = discord.Embed(
                title=f"Furry #{i+1}" + (f" - {tags}" if tags else ""),
                color=discord.Color.purple()
            )
            embed.set_image(url=image.get('url', ''))
            
            tags_list = image.get('tags') or []
            tags_str = ', '.join([t.get('name', '') for t in tags_list if t and isinstance(t, dict)])
            embed.add_field(name="Tags", value=tags_str[:100] + "..." if len(tags_str) > 100 else tags_str or "None", inline=False)
            embed.add_field(name="Size", value=f"{image.get('width', '?')}x{image.get('height', '?')}", inline=True)
            embed.add_field(name="Rating", value=image.get('rating', 'Unknown').upper(), inline=True)
            embed.add_field(name="Score", value=str(image.get('score', 0)), inline=True)
            
            embed.set_footer(text="Powered by e621.net" if nsfw else "Powered by e926.net")
            
            embeds.append(embed)
        
        await interaction.followup.send(embeds=embeds)
        
    except Exception as e:
        print(f"Error in furry command: {e}")
        await interaction.followup.send("An error occurred while fetching furry images.")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("DISCORD_TOKEN not found in environment variables!")
        print("Create .env file based on .env.example")
        exit(1)
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Bot startup error: {e}")
