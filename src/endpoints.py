from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import httpx
import base64

from src.queries import MEDIA_LIST_FIELDS, MEDIA_FULL_FIELDS
from src.parser import proxy_deep_images, inject_source_slugs, encode_pipe_request, decode_pipe_response
from src.extractor import anilist_query, fetch_raw_episodes
from src.config import MIRURO_PIPE_URL, HEADERS

# creating router instance to handle api routes
router = APIRouter()

# ─── search & suggestions ───────────────────────────────────────────────────

@router.get("/search")
async def search_anime(
    query: str,
    page: int = Query(1, ge=1, description="page number"),
    per_page: int = Query(20, ge=1, le=50, description="results per page"),
):
    # normal search by keyword mapping to anilist graphql query
    gql = f"""
    query ($search: String, $page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    data = await anilist_query(gql, {"search": query, "page": page, "perPage": per_page})
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    
    # building custom response structure
    response = {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": page_data.get("media", []),
    }
    return proxy_deep_images(response)

@router.get("/suggestions")
async def search_suggestions(
    query: str = Query(..., min_length=1, description="small search query for dropdowns"),
):
    # minimal setup to fetch less load heavy suggestions
    gql = """
    query ($search: String) {
        Page(page: 1, perPage: 8) {
            media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
                id
                title { romaji english }
                coverImage { large }
                format
                status
                startDate { year }
                episodes
            }
        }
    }
    """
    data = await anilist_query(gql, {"search": query})
    results = []
    
    # cleaning up output format
    for item in data.get("Page", {}).get("media", []):
        results.append({
            "id": item["id"],
            "title": item["title"].get("english") or item["title"].get("romaji"),
            "title_romaji": item["title"].get("romaji"),
            "poster": item["coverImage"]["large"],
            "format": item.get("format"),
            "status": item.get("status"),
            "year": (item.get("startDate") or {}).get("year"),
            "episodes": item.get("episodes"),
        })
    return proxy_deep_images({"suggestions": results})

# ─── advanced filter ─────────────────────────────────────────────────────────

SORT_MAP = {
    "SCORE_DESC": "SCORE_DESC",
    "POPULARITY_DESC": "POPULARITY_DESC",
    "TRENDING_DESC": "TRENDING_DESC",
    "START_DATE_DESC": "START_DATE_DESC",
    "FAVOURITES_DESC": "FAVOURITES_DESC",
    "UPDATED_AT_DESC": "UPDATED_AT_DESC",
}

@router.get("/filter")
async def filter_anime(
    genre: Optional[str] = Query(None, description="genre name"),
    tag: Optional[str] = Query(None, description="tag name"),
    year: Optional[int] = Query(None, description="season year"),
    season: Optional[str] = Query(None, description="season time"),
    format: Optional[str] = Query(None, description="media format"),
    status: Optional[str] = Query(None, description="release status"),
    sort: str = Query("POPULARITY_DESC", description="ordering logic"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
):
    # dynamically attaching search params
    args = ["type: ANIME", f"sort: [{SORT_MAP.get(sort, 'POPULARITY_DESC')}]"]
    variables = {"page": page, "perPage": per_page}

    if genre:
        args.append("genre: $genre")
        variables["genre"] = genre
    if tag:
        args.append("tag: $tag")
        variables["tag"] = tag
    if year:
        args.append("seasonYear: $seasonYear")
        variables["seasonYear"] = year
    if season:
        args.append("season: $season")
        variables["season"] = season.upper()
    if format:
        args.append("format: $format")
        variables["format"] = format.upper()
    if status:
        args.append("status: $status")
        variables["status"] = status.upper()

    var_types = ["$page: Int", "$perPage: Int"]
    if genre:
        var_types.append("$genre: String")
    if tag:
        var_types.append("$tag: String")
    if year:
        var_types.append("$seasonYear: Int")
    if season:
        var_types.append("$season: MediaSeason")
    if format:
        var_types.append("$format: MediaFormat")
    if status:
        var_types.append("$status: MediaStatus")

    gql = f"""
    query ({', '.join(var_types)}) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media({', '.join(args)}) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    
    data = await anilist_query(gql, variables)
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    
    response = {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": page_data.get("media", []),
    }
    return proxy_deep_images(response)

# ─── collections ─────────────────────────────────────────────────────────────

# local helper to easily pull lists from anilist
async def _fetch_collection(sort_type: str, status: str = None, page: int = 1, per_page: int = 20):
    status_filter = f", status: {status}" if status else ""
    gql = f"""
    query ($page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            media(type: ANIME, sort: [{sort_type}]{status_filter}) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    data = await anilist_query(gql, {"page": page, "perPage": per_page})
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    
    response = {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": page_data.get("media", []),
    }
    return proxy_deep_images(response)

@router.get("/spotlight")
async def get_spotlight():
    # nice spot items from hot page
    gql = f"""
    query {{
        Page(page: 1, perPage: 10) {{
            media(sort: [TRENDING_DESC, POPULARITY_DESC], type: ANIME) {{
                {MEDIA_LIST_FIELDS}
            }}
        }}
    }}
    """
    data = await anilist_query(gql)
    media = data.get("Page", {}).get("media", [])
    return proxy_deep_images({"results": media})

@router.get("/trending")
async def get_trending(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    # quick trending endpoint
    return await _fetch_collection("TRENDING_DESC", page=page, per_page=per_page)

@router.get("/popular")
async def get_popular(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    # grab popular animes
    return await _fetch_collection("POPULARITY_DESC", page=page, per_page=per_page)

@router.get("/upcoming")
async def get_upcoming(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    # fetch unreleased games
    return await _fetch_collection("POPULARITY_DESC", "NOT_YET_RELEASED", page=page, per_page=per_page)

@router.get("/recent")
async def get_recent(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    # recently aired shows
    return await _fetch_collection("START_DATE_DESC", "RELEASING", page=page, per_page=per_page)

@router.get("/schedule")
async def get_schedule(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50)):
    # grab timeline format of next eps
    gql = f"""
    query ($page: Int, $perPage: Int) {{
        Page(page: $page, perPage: $perPage) {{
            pageInfo {{ total currentPage lastPage hasNextPage perPage }}
            airingSchedules(notYetAired: true, sort: TIME) {{
                episode
                airingAt
                timeUntilAiring
                media {{
                    {MEDIA_LIST_FIELDS}
                }}
            }}
        }}
    }}
    """
    data = await anilist_query(gql, {"page": page, "perPage": per_page})
    page_data = data.get("Page", {})
    page_info = page_data.get("pageInfo", {})
    
    results = []
    for item in page_data.get("airingSchedules", []):
        entry = item.get("media", {})
        entry["next_episode"] = item.get("episode")
        entry["airingAt"] = item.get("airingAt")
        entry["timeUntilAiring"] = item.get("timeUntilAiring")
        results.append(entry)
        
    response = {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "results": results,
    }
    return proxy_deep_images(response)

# ─── anime details ───────────────────────────────────────────────────────────

@router.get("/info/{anilist_id}")
async def get_anime_info(anilist_id: int):
    # returns absolute big chunk of data for details pages
    gql = f"""
    query ($id: Int) {{
        Media(id: $id, type: ANIME) {{
            {MEDIA_FULL_FIELDS}
        }}
    }}
    """
    data = await anilist_query(gql, {"id": anilist_id})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="anime not found sorry")
    return proxy_deep_images(media)

@router.get("/anime/{anilist_id}/characters")
async def get_anime_characters(
    anilist_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=50),
):
    # specific chars mapping for single pages
    gql = """
    query ($id: Int, $page: Int, $perPage: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            characters(sort: [ROLE, RELEVANCE], page: $page, perPage: $perPage) {
                pageInfo { total currentPage lastPage hasNextPage perPage }
                edges {
                    role
                    node {
                        id
                        name { full native userPreferred }
                        image { large medium }
                        description
                        gender
                        dateOfBirth { year month day }
                        age
                        favourites
                        siteUrl
                    }
                    voiceActors {
                        id
                        name { full native }
                        image { large }
                        languageV2
                    }
                }
            }
        }
    }
    """
    data = await anilist_query(gql, {"id": anilist_id, "page": page, "perPage": per_page})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="couldnt locate anime")
        
    chars = media.get("characters", {})
    page_info = chars.get("pageInfo", {})
    
    response = {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "characters": chars.get("edges", []),
    }
    return proxy_deep_images(response)

@router.get("/anime/{anilist_id}/relations")
async def get_anime_relations(anilist_id: int):
    # connecting nodes of anime sequels prequels
    gql = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            relations {
                edges {
                    relationType(version: 2)
                    node {
                        id
                        title { romaji english native }
                        coverImage { large }
                        bannerImage
                        format
                        type
                        status
                        episodes
                        chapters
                        meanScore
                        averageScore
                        popularity
                        startDate { year month day }
                    }
                }
            }
        }
    }
    """
    data = await anilist_query(gql, {"id": anilist_id})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="not found")
    
    response = {
        "id": media["id"],
        "title": media["title"],
        "relations": media.get("relations", {}).get("edges", []),
    }
    return proxy_deep_images(response)

@router.get("/anime/{anilist_id}/recommendations")
async def get_anime_recommendations(
    anilist_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=25),
):
    # shows what else might be good based on user likes
    gql = """
    query ($id: Int, $page: Int, $perPage: Int) {
        Media(id: $id, type: ANIME) {
            id
            title { romaji english }
            recommendations(sort: RATING_DESC, page: $page, perPage: $perPage) {
                pageInfo { total currentPage lastPage hasNextPage perPage }
                nodes {
                    rating
                    mediaRecommendation {
                        id
                        title { romaji english native }
                        coverImage { large extraLarge }
                        bannerImage
                        format
                        episodes
                        status
                        meanScore
                        averageScore
                        popularity
                        genres
                        startDate { year }
                    }
                }
            }
        }
    }
    """
    data = await anilist_query(gql, {"id": anilist_id, "page": page, "perPage": per_page})
    media = data.get("Media")
    if not media:
        raise HTTPException(status_code=404, detail="where the anime at")
        
    recs = media.get("recommendations", {})
    page_info = recs.get("pageInfo", {})
    
    response = {
        "page": page_info.get("currentPage", page),
        "perPage": page_info.get("perPage", per_page),
        "total": page_info.get("total", 0),
        "hasNextPage": page_info.get("hasNextPage", False),
        "recommendations": recs.get("nodes", []),
    }
    return proxy_deep_images(response)

# ─── streaming data logic ───────────────────────────────────────────────────

@router.get("/episodes/{anilist_id}")
async def get_episodes(anilist_id: int):
    # get the full list of eps mapped to providers
    data = await fetch_raw_episodes(anilist_id)
    return proxy_deep_images(inject_source_slugs(data, anilist_id))

@router.get("/genres")
async def get_genres():
    # list all available genres for filtering
    gql = """
    query {
        GenreCollection
    }
    """
    data = await anilist_query(gql)
    return {"genres": data.get("GenreCollection", [])}

@router.get("/sources")
async def get_sources(
    episodeId: str = Query(..., description="episode tracking string"),
    provider: str = Query(..., description="video provider host"),
    anilistId: int = Query(..., description="anime db identification code"),
    category: str = Query("sub", description="dubbed or subbed version"),
):
    # grabs video sources using encrypted payload pipe
    enc_id = base64.urlsafe_b64encode(episodeId.encode()).decode().rstrip('=')
    payload = {
        "path": "sources",
        "method": "GET",
        "query": {
            "episodeId": enc_id,
            "provider": provider,
            "category": category,
            "anilistId": anilistId,
        },
        "body": None,
        "version": "0.1.0",
    }
    encoded_req = encode_pipe_request(payload)
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        pipe_target = f"{MIRURO_PIPE_URL}?e={encoded_req}"
        print(f"\n[KUHI API] extracting stream sources pipe targeting:", pipe_target)
        res = await client.get(pipe_target, headers=HEADERS)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="fetching pipe failed real bad")
        return proxy_deep_images(decode_pipe_response(res.text.strip()))

@router.get("/extract/{query}")
async def extract_simple(query: str, episode: int = Query(1, alias="e")):
    # simplified extraction with auto-search: /anime/extract/21?e=1 or /anime/extract/violet-evergarden?e=1
    # handles both anilist IDs and search queries
    
    # check if query is numeric (anilist ID) or text (search query)
    if query.isdigit():
        anilist_id = int(query)
        # fetch format to check if movie
        gql = """
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                id
                format
            }
        }
        """
        media_data = await anilist_query(gql, {"id": anilist_id})
        media = media_data.get("Media")
        if not media:
            raise HTTPException(status_code=404, detail="anime not found")
        
        # if it's a movie, force episode to 1
        if media.get("format") == "MOVIE":
            episode = 1
    else:
        # search for anime and get first result
        gql = f"""
        query ($search: String) {{
            Page(page: 1, perPage: 1) {{
                media(search: $search, type: ANIME, sort: SEARCH_MATCH) {{
                    id
                    format
                }}
            }}
        }}
        """
        search_data = await anilist_query(gql, {"search": query.replace("-", " ")})
        media_list = search_data.get("Page", {}).get("media", [])
        if not media_list:
            raise HTTPException(status_code=404, detail="anime not found")
        
        anilist_id = media_list[0]["id"]
        media_format = media_list[0].get("format")
        
        # if it's a movie, force episode to 1
        if media_format == "MOVIE":
            episode = 1
    
    data = await fetch_raw_episodes(anilist_id)
    providers = data.get("providers", {})
    
    if not providers:
        raise HTTPException(status_code=404, detail="no providers available for this anime")
    
    # smart resolve best provider source
    target_episode_id = None
    target_provider = None
    target_cat = None
    
    ranking = ["zoro", "bee", "telli", "arc", "yugen", "jet", "neo", "kiwi"]
    
    for prov in ranking:
        if prov in providers:
            prov_data = providers[prov]
            eps = prov_data.get("episodes", {})
            for cat in ["sub", "dub", "raw"]:
                if cat in eps:
                    cat_eps = eps[cat]
                    if isinstance(cat_eps, list):
                        for ep in cat_eps:
                            if ep.get("number") == episode:
                                target_episode_id = ep.get("id")
                                target_provider = prov
                                target_cat = cat
                                break
                if target_episode_id:
                    break
        if target_episode_id:
            break
            
    if not target_episode_id:
        raise HTTPException(status_code=404, detail=f"episode {episode} not found in any provider")
        
    # try multiple providers if one fails
    last_error = None
    providers_to_try = [(target_provider, target_cat, target_episode_id)]
    
    # add fallback providers
    for prov in ranking:
        if prov != target_provider and prov in providers:
            prov_data = providers[prov]
            eps = prov_data.get("episodes", {})
            for cat in ["sub", "dub", "raw"]:
                if cat in eps:
                    cat_eps = eps[cat]
                    if isinstance(cat_eps, list):
                        for ep in cat_eps:
                            if ep.get("number") == episode:
                                providers_to_try.append((prov, cat, ep.get("id")))
                                break
    
    # try each provider until one works
    for try_provider, try_cat, try_ep_id in providers_to_try:
        try:
            enc_id = base64.urlsafe_b64encode(try_ep_id.encode()).decode().rstrip('=')
            payload = {
                "path": "sources",
                "method": "GET",
                "query": {
                    "episodeId": enc_id,
                    "provider": try_provider,
                    "category": try_cat,
                    "anilistId": anilist_id,
                },
                "body": None,
                "version": "0.1.0",
            }
            encoded_req = encode_pipe_request(payload)
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                pipe_target = f"{MIRURO_PIPE_URL}?e={encoded_req}"
                print(f"\n[KUHI API] trying provider {try_provider}: {pipe_target}")
                res = await client.get(pipe_target, headers=HEADERS)
                
                if res.status_code == 200:
                    result = decode_pipe_response(res.text.strip())
                    print(f"[KUHI API] success with provider {try_provider}")
                    return proxy_deep_images(result)
                else:
                    last_error = f"{try_provider} failed: {res.status_code}"
                    print(f"[KUHI API] {last_error}")
        except Exception as e:
            last_error = f"{try_provider} error: {str(e)}"
            print(f"[KUHI API] {last_error}")
            continue
    
    raise HTTPException(status_code=500, detail=f"all providers failed. last error: {last_error}")

