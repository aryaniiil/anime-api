# Kuhi API v2.0

> ** DISCLAIMER:** This API is experimental and not reliable. Use at your own risk. No guarantees on uptime or data accuracy. I'M NOT RESPONSIBLE FOR ANY UNETHICAL USAGES OR LEGAL TROUBLES, ONLY FOR EDUCATION PURPOSE.

A anime streaming API built for scale. Kuhi provides a clean REST interface to search, filter, and stream anime content with automatic source extraction and proxy capabilities.

## Features

-  **Smart Search** - Search by anime name or AniList ID
-  **Auto-Extraction** - Automatically finds best streaming sources
-  **Movie Detection** - Automatically handles movies vs episodes
-  **Decryption Pipeline** - Handles encrypted streaming sources
-  **CORS Proxy** - Built-in proxy for bypassing CDN restrictions
-  **HLS Streaming** - Full M3U8 playlist and segment proxying

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/aryaniiil/kuhi-anime-api
cd Kuhi-anime-api
```

2. Install dependencies:
```bash
python -m pip install -r requirements.txt
```

3. Run the server:
```bash
uvicorn api:app --reload
```

4. Access the API:
```
http://127.0.0.1:8000
```

## Project Structure

```
Kuhi/
├── src/
│   ├── __init__.py          # Package initializer
│   ├── main.py              # FastAPI app & proxy endpoints
│   ├── endpoints.py         # Anime API routes
│   ├── extractor.py         # AniList & Miruro data fetchers
│   ├── parser.py            # Data transformation utilities
│   ├── queries.py           # GraphQL query templates
│   └── config.py            # Configuration & constants
├── api.py                   # Alternative entry point
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## API Endpoints

### Search & Discovery

#### `GET /anime/search`
Search anime by keyword with pagination.

**Parameters:**
- `query` (string, required) - Search term
- `page` (int, default: 1) - Page number
- `per_page` (int, default: 20, max: 50) - Results per page

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/search?query=naruto&page=1"
```

#### `GET /anime/suggestions`
Lightweight autocomplete search for dropdowns.

**Parameters:**
- `query` (string, required) - Search term

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/suggestions?query=one%20piece"
```

#### `GET /anime/genres`
List all available genres for filtering.

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/genres"
```

### Collections

#### `GET /anime/spotlight`
Top 10 trending and popular anime.

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/spotlight"
```

#### `GET /anime/trending`
Currently trending anime with pagination.

**Parameters:**
- `page` (int, default: 1)
- `per_page` (int, default: 20, max: 50)

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/trending?page=1&per_page=20"
```

#### `GET /anime/popular`
Most popular anime of all time.

**Parameters:**
- `page` (int, default: 1)
- `per_page` (int, default: 20, max: 50)

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/popular"
```

#### `GET /anime/upcoming`
Upcoming anime releases.

**Parameters:**
- `page` (int, default: 1)
- `per_page` (int, default: 20, max: 50)

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/upcoming"
```

#### `GET /anime/recent`
Recently aired episodes.

**Parameters:**
- `page` (int, default: 1)
- `per_page` (int, default: 20, max: 50)

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/recent"
```

#### `GET /anime/schedule`
Airing schedule for upcoming episodes.

**Parameters:**
- `page` (int, default: 1)
- `per_page` (int, default: 20, max: 50)

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/schedule"
```

### Advanced Filtering

#### `GET /anime/filter`
Filter anime by multiple criteria.

**Parameters:**
- `genre` (string, optional) - Genre name (get from /anime/genres)
- `tag` (string, optional) - Tag name
- `year` (int, optional) - Season year
- `season` (string, optional) - Season (WINTER, SPRING, SUMMER, FALL)
- `format` (string, optional) - Format (TV, MOVIE, OVA, ONA, SPECIAL)
- `status` (string, optional) - Status (RELEASING, FINISHED, NOT_YET_RELEASED)
- `sort` (string, default: POPULARITY_DESC) - Sort order
- `page` (int, default: 1)
- `per_page` (int, default: 20, max: 50)

**Sort Options:**
- `SCORE_DESC` - Highest rated
- `POPULARITY_DESC` - Most popular
- `TRENDING_DESC` - Currently trending
- `START_DATE_DESC` - Recently started
- `FAVOURITES_DESC` - Most favorited
- `UPDATED_AT_DESC` - Recently updated

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/filter?genre=Action&sort=SCORE_DESC&year=2024"
```

### Anime Details

#### `GET /anime/info/{anilist_id}`
Complete anime information including characters, relations, staff, and recommendations.

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/info/21"
```

#### `GET /anime/anime/{anilist_id}/characters`
Character list with voice actors.

**Parameters:**
- `page` (int, default: 1)
- `per_page` (int, default: 25, max: 50)

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/anime/21/characters"
```

#### `GET /anime/anime/{anilist_id}/relations`
Related anime (sequels, prequels, spin-offs).

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/anime/21/relations"
```

#### `GET /anime/anime/{anilist_id}/recommendations`
Recommended similar anime.

**Parameters:**
- `page` (int, default: 1)
- `per_page` (int, default: 10, max: 25)

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/anime/21/recommendations"
```

### Streaming

#### `GET /anime/episodes/{anilist_id}`
Get episode list with provider mappings.

**Example:**
```bash
curl "http://127.0.0.1:8000/anime/episodes/21"
```

#### `GET /anime/extract/{query}` 
**Magic endpoint** - Automatically extracts streaming sources from anime name or ID.

**Parameters:**
- `query` (string, required) - AniList ID (21) or anime name (violet evergarden)
- `e` (int, default: 1) - Episode number

**Features:**
- Accepts both numeric IDs and full anime names with spaces
- Automatically searches AniList if name is provided
- Auto-detects movies and plays them regardless of episode parameter
- Prioritizes best quality providers (zoro → bee → kiwi → telli → arc → yugen → jet → neo)
- Returns HLS streams with referer headers

**Examples:**
```bash
# Using AniList ID
curl "http://127.0.0.1:8000/anime/extract/21?e=1"

# Using anime name (spaces work)
curl "http://127.0.0.1:8000/anime/extract/violet%20evergarden?e=1"

# Using hyphenated name
curl "http://127.0.0.1:8000/anime/extract/my-hero-academia?e=5"

# Movie (episode param ignored)
curl "http://127.0.0.1:8000/anime/extract/a-silent-voice"
```

**Tip:** If search by name fails, use `/anime/search?query=<name>` to get the exact AniList ID first.

### Proxy Endpoints

#### `GET /proxy_m3u8`
Proxy M3U8 playlists with referer injection and URL rewriting.

**Parameters:**
- `url` (string, required) - M3U8 playlist URL
- `referer` (string, required) - Referer header value

#### `GET /proxy_segment`
Proxy video segments with referer injection.

**Parameters:**
- `url` (string, required) - Segment URL
- `referer` (string, required) - Referer header value

## Usage Examples

### Basic Workflow

1. **Search for anime:**
```bash
curl "http://127.0.0.1:8000/anime/search?query=demon%20slayer"
```

2. **Get anime info (use ID from search):**
```bash
curl "http://127.0.0.1:8000/anime/info/101922"
```

3. **Get episodes:**
```bash
curl "http://127.0.0.1:8000/anime/episodes/101922"
```

4. **Extract streaming source:**
```bash
curl "http://127.0.0.1:8000/anime/extract/101922?e=1"
```

### Quick Extraction

Skip all steps and directly extract:
```bash
# By name
curl "http://127.0.0.1:8000/anime/extract/demon%20slayer?e=1"

# By ID
curl "http://127.0.0.1:8000/anime/extract/101922?e=1"
```

## Response Format

All endpoints return JSON with consistent structure:

### Search/Filter/Collections Response
```json
{
  "page": 1,
  "perPage": 20,
  "total": 1000,
  "hasNextPage": true,
  "results": [...]
}
```

### Streaming Source Response
```json
{
  "streams": [
    {
      "type": "hls",
      "url": "https://..../master.m3u8",
      "referer": "https://..."
    }
  ],
  "subtitles": [...]
}
```

## Configuration

Edit `src/config.py` to customize:
- AniList API URL
- Miruro pipe URL
- Request headers
- Timeouts

## Tech Stack

- **FastAPI** - Modern async web framework
- **httpx** - Async HTTP client
- **HLS.js** - Video player for web interface
- **AniList GraphQL API** - Anime metadata
- **Miruro Pipe** - Encrypted streaming sources

## Development

Run in development mode with auto-reload:
```bash
uvicorn api:app --reload
```

## Notes

- All image URLs are automatically proxied through serveproxy.com
- Provider priority: zoro > bee > kiwi > telli > arc > yugen > jet > neo
- Movies automatically default to episode 1
- M3U8 playlists and segments are proxied to bypass referer checks
- CORS is enabled for all origins

## License

Educational purposes only. Respect content creators and copyright laws.

---

**Built with ❤️ for the anime community**
