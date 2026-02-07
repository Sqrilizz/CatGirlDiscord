# API v5 Update

## Changes Made

### API Endpoints
- `/search` → `/images`
- New parameters: `pageSize`, `tags`, `isNsfw`, `excludedTags`
- New response structure: `items` instead of `images`

### Required Changes
- **API token is now required** - add to `.env`:
  ```
  WAIFU_API_TOKEN=j6UBBh8ljk3HTVdz7kPLloZNbqhXOPmpGurtNtMiPs0
  ```

### Code Updates
- `waifu_api.py` - completely rewritten for v5
- Added User-Agent header
- Automatic response conversion for backward compatibility
- Improved tag handling
- Updated `.env.example`
- Removed all comments and emojis
- Translated all messages to English

### Testing
```bash
# Test via curl
curl -H "Authorization: Bearer j6UBBh8ljk3HTVdz7kPLloZNbqhXOPmpGurtNtMiPs0" \
  "https://api.waifu.im/images?pageSize=1&isNsfw=false"

# Run bot
python3 bot.py
```

## Test Results
- Tags retrieval works (17 tags)
- SFW images work
- NSFW images work
- Tag filtering works
- Multiple images work

**Update date**: 2026-02-07
