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
        self.min_request_interval = 1.0  # Минимум 1 секунда между запросами
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers
    
    async def _wait_for_rate_limit(self):
        """Ждем чтобы не превысить rate limit"""
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
        is_nsfw: Optional[str] = None,
        gif: Optional[bool] = None,
        orientation: Optional[str] = None,
        limit: int = 1,
        width: Optional[str] = None,
        height: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for waifu images using the Waifu.im API
        
        Args:
            included_tags: Tags that must be present
            excluded_tags: Tags that must not be present
            is_nsfw: 'true', 'false', or 'null' for random
            gif: True/False to include/exclude GIFs
            orientation: 'LANDSCAPE', 'PORTRAIT', or 'SQUARE'
            limit: Number of images to return (1-30, default 1)
            width: Width filter (e.g., '>=1920')
            height: Height filter (e.g., '>=1080')
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        params = {}
        
        if included_tags:
            params['included_tags'] = included_tags
        if excluded_tags:
            params['excluded_tags'] = excluded_tags
        if is_nsfw is not None:
            params['is_nsfw'] = is_nsfw
        if gif is not None:
            params['gif'] = gif
        if orientation:
            params['orientation'] = orientation
        if width:
            params['width'] = width
        if height:
            params['height'] = height
        
        # API требует limit > 1, но если нужно 1 изображение, не передаем параметр
        if limit > 1:
            params['limit'] = min(limit, 30)  # API limit
        
        # Ждем чтобы не превысить rate limit
        await self._wait_for_rate_limit()
        
        try:
            print(f"API Request: {self.base_url}/search with params: {params}")
            async with self.session.get(
                f'{self.base_url}/search',
                params=params,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"API Success: Got {len(result.get('images', []))} images")
                    return result
                elif response.status == 429:
                    # Rate limit exceeded
                    error_text = await response.text()
                    print(f"API Rate Limited: {error_text}")
                    
                    # Попробуем подождать и повторить запрос
                    retry_after = response.headers.get('Retry-After', '5')
                    try:
                        wait_time = int(retry_after)
                    except:
                        wait_time = 5
                    
                    print(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    
                    # Повторный запрос
                    async with self.session.get(
                        f'{self.base_url}/search',
                        params=params,
                        headers=self._get_headers()
                    ) as retry_response:
                        if retry_response.status == 200:
                            result = await retry_response.json()
                            print(f"API Success (retry): Got {len(result.get('images', []))} images")
                            return result
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
        """Get a random waifu image"""
        is_nsfw = 'true' if nsfw else 'false'
        return await self.search_images(is_nsfw=is_nsfw)
    
    async def get_waifu_by_tag(self, tag: str, nsfw: bool = False) -> Optional[Dict[str, Any]]:
        """Get a waifu image with specific tag"""
        is_nsfw = 'true' if nsfw else 'false'
        return await self.search_images(included_tags=[tag], is_nsfw=is_nsfw)
    
    async def get_multiple_waifus(self, count: int, nsfw: bool = False, tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Get multiple waifu images"""
        is_nsfw = 'true' if nsfw else 'false'
        return await self.search_images(
            included_tags=tags,
            is_nsfw=is_nsfw,
            limit=min(count, 30)
        )
    
    async def get_available_tags(self) -> Optional[Dict[str, Any]]:
        """Get all available tags from the API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # Ждем чтобы не превысить rate limit
        await self._wait_for_rate_limit()
        
        try:
            async with self.session.get(
                f'{self.base_url}/tags',
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                elif response.status == 429:
                    # Rate limit exceeded
                    retry_after = response.headers.get('Retry-After', '5')
                    try:
                        wait_time = int(retry_after)
                    except:
                        wait_time = 5
                    
                    print(f"Tags API Rate Limited, waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    
                    # Повторный запрос
                    async with self.session.get(
                        f'{self.base_url}/tags',
                        headers=self._get_headers()
                    ) as retry_response:
                        if retry_response.status == 200:
                            result = await retry_response.json()
                            return result
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
        """Close the session"""
        if self.session:
            await self.session.close()
