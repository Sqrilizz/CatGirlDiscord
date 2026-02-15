import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
import time

class FurryAPI:
    def __init__(self):
        self.base_url_nsfw = "https://e621.net"
        self.base_url_sfw = "https://e926.net"
        self.session = None
        self.last_request_time = 0
        self.min_request_interval = 1.0
        self.user_agent = "CatGirlDiscordBot/2.0 (by sqrilizz on GitHub)"
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': self.user_agent
        }
    
    async def _wait_for_rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def search_posts(
        self,
        tags: Optional[List[str]] = None,
        limit: int = 1,
        nsfw: bool = False
    ) -> Optional[Dict[str, Any]]:
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        base_url = self.base_url_nsfw if nsfw else self.base_url_sfw
        
        params = {
            'limit': min(limit, 320)
        }
        
        if tags:
            params['tags'] = ' '.join(tags)
        
        await self._wait_for_rate_limit()
        
        try:
            print(f"Furry API Request: {base_url}/posts.json with params: {params}")
            async with self.session.get(
                f'{base_url}/posts.json',
                params=params,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    posts = result.get('posts', [])
                    print(f"Furry API Success: Got {len(posts)} posts")
                    
                    converted_result = {'images': []}
                    
                    for post in posts:
                        file_info = post.get('file', {})
                        
                        if not file_info.get('url'):
                            continue
                        
                        converted_image = {
                            'url': file_info.get('url'),
                            'width': file_info.get('width'),
                            'height': file_info.get('height'),
                            'is_nsfw': nsfw,
                            'tags': [{'name': tag} for tag in post.get('tags', {}).get('general', [])[:5]],
                            'rating': post.get('rating'),
                            'score': post.get('score', {}).get('total', 0)
                        }
                        converted_result['images'].append(converted_image)
                    
                    return converted_result
                elif response.status == 429:
                    error_text = await response.text()
                    print(f"Furry API Rate Limited: {error_text}")
                    
                    retry_after = response.headers.get('Retry-After', '5')
                    try:
                        wait_time = int(retry_after)
                    except:
                        wait_time = 5
                    
                    print(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    
                    async with self.session.get(
                        f'{base_url}/posts.json',
                        params=params,
                        headers=self._get_headers()
                    ) as retry_response:
                        if retry_response.status == 200:
                            result = await retry_response.json()
                            posts = result.get('posts', [])
                            print(f"Furry API Success (retry): Got {len(posts)} posts")
                            
                            converted_result = {'images': []}
                            
                            for post in posts:
                                file_info = post.get('file', {})
                                
                                if not file_info.get('url'):
                                    continue
                                
                                converted_image = {
                                    'url': file_info.get('url'),
                                    'width': file_info.get('width'),
                                    'height': file_info.get('height'),
                                    'is_nsfw': nsfw,
                                    'tags': [{'name': tag} for tag in post.get('tags', {}).get('general', [])[:5]],
                                    'rating': post.get('rating'),
                                    'score': post.get('score', {}).get('total', 0)
                                }
                                converted_result['images'].append(converted_image)
                            
                            return converted_result
                        else:
                            error_text = await retry_response.text()
                            print(f"Furry API Error (retry): {retry_response.status} - {error_text}")
                            return None
                else:
                    error_text = await response.text()
                    print(f"Furry API Error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            print(f"Furry API request failed: {e}")
            return None
    
    async def get_random_furry(self, nsfw: bool = False, count: int = 1) -> Optional[Dict[str, Any]]:
        tags = ['order:random']
        return await self.search_posts(tags=tags, limit=count, nsfw=nsfw)
    
    async def get_furry_by_tags(self, tags: List[str], nsfw: bool = False, count: int = 1) -> Optional[Dict[str, Any]]:
        search_tags = tags + ['order:random']
        return await self.search_posts(tags=search_tags, limit=count, nsfw=nsfw)
    
    async def close(self):
        if self.session:
            await self.session.close()
