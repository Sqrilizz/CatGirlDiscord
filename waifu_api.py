import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from config import WAIFU_API_BASE_URL, WAIFU_API_TOKEN
import time

class WaifuAPI:
    def __init__(self):
        self.base_url = WAIFU_API_BASE_URL
        self.token = WAIFU_API_TOKEN
        self.session = None
        self.last_request_time = 0
        self.min_request_interval = 1.0
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'WaifuDiscordBot/2.0 (Python/aiohttp)'
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers
    
    async def _wait_for_rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def search_images(
        self,
        included_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
        is_nsfw: Optional[bool] = None,
        is_animated: Optional[bool] = None,
        orientation: Optional[str] = None,
        page_size: int = 1,
        order_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        params = {}
        
        if included_tags:
            params['tags'] = ','.join(included_tags)
        if excluded_tags:
            params['excludedTags'] = ','.join(excluded_tags)
        if is_nsfw is not None:
            params['isNsfw'] = 'true' if is_nsfw else 'false'
        if is_animated is not None:
            params['isAnimated'] = 'true' if is_animated else 'false'
        if orientation:
            params['orientation'] = orientation
        if order_by:
            params['orderBy'] = order_by
        
        params['pageSize'] = min(page_size, 30)
        
        await self._wait_for_rate_limit()
        
        try:
            print(f"API Request: {self.base_url}/images with params: {params}")
            async with self.session.get(
                f'{self.base_url}/images',
                params=params,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    items = result.get('items', [])
                    print(f"API Success: Got {len(items)} images")
                    
                    converted_result = {'images': []}
                    
                    for item in items:
                        converted_image = {
                            'url': item.get('url'),
                            'width': item.get('width'),
                            'height': item.get('height'),
                            'is_nsfw': item.get('isNsfw'),
                            'dominant_color': item.get('dominantColor'),
                            'tags': [{'name': tag.get('slug')} for tag in item.get('tags', [])],
                            'artist': item.get('artists', [{}])[0] if item.get('artists') else None
                        }
                        converted_result['images'].append(converted_image)
                    
                    return converted_result
                elif response.status == 429:
                    error_text = await response.text()
                    print(f"API Rate Limited: {error_text}")
                    
                    retry_after = response.headers.get('Retry-After', '5')
                    try:
                        wait_time = int(retry_after)
                    except:
                        wait_time = 5
                    
                    print(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    
                    async with self.session.get(
                        f'{self.base_url}/images',
                        params=params,
                        headers=self._get_headers()
                    ) as retry_response:
                        if retry_response.status == 200:
                            result = await retry_response.json()
                            items = result.get('items', [])
                            print(f"API Success (retry): Got {len(items)} images")
                            
                            converted_result = {'images': []}
                            
                            for item in items:
                                converted_image = {
                                    'url': item.get('url'),
                                    'width': item.get('width'),
                                    'height': item.get('height'),
                                    'is_nsfw': item.get('isNsfw'),
                                    'dominant_color': item.get('dominantColor'),
                                    'tags': [{'name': tag.get('slug')} for tag in item.get('tags', [])],
                                    'artist': item.get('artists', [{}])[0] if item.get('artists') else None
                                }
                                converted_result['images'].append(converted_image)
                            
                            return converted_result
                        else:
                            error_text = await retry_response.text()
                            print(f"API Error (retry): {retry_response.status} - {error_text}")
                            return None
                else:
                    error_text = await response.text()
                    print(f"API Error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            print(f"Request failed: {e}")
            return None
    
    async def get_random_waifu(self, nsfw: bool = False) -> Optional[Dict[str, Any]]:
        return await self.search_images(is_nsfw=nsfw)
    
    async def get_waifu_by_tag(self, tag: str, nsfw: bool = False) -> Optional[Dict[str, Any]]:
        return await self.search_images(included_tags=[tag], is_nsfw=nsfw)
    
    async def get_multiple_waifus(self, count: int, nsfw: bool = False, tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        return await self.search_images(
            included_tags=tags,
            is_nsfw=nsfw,
            page_size=min(count, 30)
        )
    
    async def get_available_tags(self) -> Optional[Dict[str, Any]]:
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        await self._wait_for_rate_limit()
        
        try:
            async with self.session.get(
                f'{self.base_url}/tags',
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    items = result.get('items', [])
                    
                    known_nsfw = ['hentai', 'ecchi', 'ero', 'oral', 'paizuri', 'ass', 'milf']
                    known_sfw = ['waifu', 'maid', 'uniform', 'selfies', 'oppai']
                    
                    versatile = []
                    nsfw = []
                    
                    for tag in items:
                        tag_slug = tag.get('slug', tag.get('name', '').lower())
                        
                        if tag_slug in known_nsfw:
                            nsfw.append(tag_slug)
                        elif tag_slug in known_sfw:
                            versatile.append(tag_slug)
                        else:
                            description = tag.get('description', '').lower()
                            if any(word in description for word in ['nsfw', 'explicit', 'sexual', 'erotic', 'nude']):
                                nsfw.append(tag_slug)
                            else:
                                versatile.append(tag_slug)
                    
                    return {
                        'versatile': versatile,
                        'nsfw': nsfw
                    }
                elif response.status == 429:
                    retry_after = response.headers.get('Retry-After', '5')
                    try:
                        wait_time = int(retry_after)
                    except:
                        wait_time = 5
                    
                    print(f"Tags API Rate Limited, waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    
                    async with self.session.get(
                        f'{self.base_url}/tags',
                        headers=self._get_headers()
                    ) as retry_response:
                        if retry_response.status == 200:
                            result = await retry_response.json()
                            items = result.get('items', [])
                            
                            known_nsfw = ['hentai', 'ecchi', 'ero', 'oral', 'paizuri', 'ass', 'milf']
                            known_sfw = ['waifu', 'maid', 'uniform', 'selfies', 'oppai']
                            
                            versatile = []
                            nsfw = []
                            
                            for tag in items:
                                tag_slug = tag.get('slug', tag.get('name', '').lower())
                                
                                if tag_slug in known_nsfw:
                                    nsfw.append(tag_slug)
                                elif tag_slug in known_sfw:
                                    versatile.append(tag_slug)
                                else:
                                    description = tag.get('description', '').lower()
                                    if any(word in description for word in ['nsfw', 'explicit', 'sexual', 'erotic', 'nude']):
                                        nsfw.append(tag_slug)
                                    else:
                                        versatile.append(tag_slug)
                            
                            return {
                                'versatile': versatile,
                                'nsfw': nsfw
                            }
                        else:
                            error_text = await retry_response.text()
                            print(f"Tags API Error (retry): {retry_response.status} - {error_text}")
                            return None
                else:
                    error_text = await response.text()
                    print(f"Tags API Error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            print(f"Tags request failed: {e}")
            return None
    
    async def close(self):
        if self.session:
            await self.session.close()
