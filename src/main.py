from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.endpoints import router
from src.config import HEADERS
import httpx
import os

# main Kuhi api initialization
app = FastAPI(title="Kuhi API", version="2.0")

# enable CORS for video streaming
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount static files for assets
if os.path.exists("assets"):
    app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# include routes under the /anime prefix for modular future scaling (ex: /movies)
app.include_router(router, prefix="/anime")

from fastapi import Query
from fastapi.responses import Response

@app.get("/proxy_m3u8")
async def proxy_m3u8(url: str, referer: str):
    # acts as a simple header injector to bypass cdn referer checks
    async with httpx.AsyncClient(timeout=10.0) as client:
        h = HEADERS.copy()
        h["Referer"] = referer
        resp = await client.get(url, headers=h)
        
        # rewrite ALL URLs in playlist to go through proxy
        content = resp.text
        base_url = url.rsplit('/', 1)[0] + '/'
        lines = []
        from urllib.parse import quote
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                # handle both relative and absolute URLs
                if stripped.startswith('http'):
                    absolute_url = stripped
                elif not stripped.startswith('/'):
                    absolute_url = base_url + stripped
                else:
                    absolute_url = stripped
                
                # route through appropriate proxy
                if '.m3u8' in stripped:
                    line = f"/proxy_m3u8?url={quote(absolute_url, safe='')}&referer={quote(referer, safe='')}"
                else:
                    line = f"/proxy_segment?url={quote(absolute_url, safe='')}&referer={quote(referer, safe='')}"
            lines.append(line)
        
        return Response(content='\n'.join(lines), media_type="application/vnd.apple.mpegurl")

@app.get("/proxy_segment")
async def proxy_segment(url: str, referer: str):
    # proxy video segments with proper headers
    async with httpx.AsyncClient(timeout=30.0) as client:
        h = HEADERS.copy()
        h["Referer"] = referer
        resp = await client.get(url, headers=h)
        return Response(content=resp.content, media_type="video/mp2t")

@app.get("/", response_class=HTMLResponse)
async def home():
    # minimalist black and white interactive page for Kuhi API
    # updated playground with editable input fields for custom params
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>kuhi native api</title>
    <link rel="icon" type="image/png" href="/assets/imgs/logo.png">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #000000;
            --fg: #ffffff;
            --accent: #262626;
            --muted: #1a1a1a;
            --border: #262626;
            --text-muted: #a1a1aa;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
            scrollbar-width: thin;
            scrollbar-color: var(--accent) var(--bg);
        }

        body {
            background-color: var(--bg);
            color: var(--fg);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 80px 24px;
        }

        header { margin-bottom: 60px; text-align: left; }
        
        .warning-box {
            background: rgba(220, 38, 38, 0.1);
            border: 1px solid rgba(220, 38, 38, 0.3);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 40px;
            color: #fca5a5;
            font-size: 0.9rem;
            font-weight: 500;
        }
        .warning-box strong { color: #ef4444; }
        
        .logo-box { width: 48px; height: 48px; border: 2px solid #fff; border-radius: 8px; margin-bottom: 24px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.5rem; }

        h1 { font-size: 3.5rem; font-weight: 700; letter-spacing: -0.05em; line-height: 1; }
        .subtitle { font-size: 1.1rem; color: var(--text-muted); font-weight: 300; margin: 12px 0 20px; }
        .v-badge { display: inline-block; background: var(--muted); border: 1px solid var(--border); padding: 4px 12px; border-radius: 99px; font-size: 0.8rem; color: var(--fg); }

        .lbl {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            color: var(--text-muted);
            margin: 60px 0 24px;
            display: block;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }

        .card {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 24px;
            padding: 24px;
            transition: border-color 0.2s;
        }
        .card:hover { border-color: #404040; }

        .meta { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 12px; }
        .method { font-size: 0.75rem; font-weight: 700; padding: 4px 8px; background: var(--muted); border: 1px solid var(--border); border-radius: 4px; display: flex; align-items: center; gap: 8px; }
        .tag { border: 1px solid var(--border); padding: 1px 6px; border-radius: 4px; font-size: 0.6rem; text-transform: uppercase; color: var(--text-muted); }
        .path { font-family: monospace; font-size: 0.95rem; }

        .desc { font-size: 0.9rem; color: var(--text-muted); margin-bottom: 20px; }

        /* playground interactive elements */
        .sandbox { display: flex; gap: 8px; margin-bottom: 12px; }
        .in-url {
            flex: 1;
            background: var(--muted);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px 12px;
            color: var(--fg);
            font-family: monospace;
            font-size: 0.85rem;
            outline: none;
        }
        .in-url:focus { border-color: #555; }

        .try-btn { background: var(--fg); color: var(--bg); border: none; padding: 8px 16px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: opacity 0.2s; white-space: nowrap; }
        .try-btn:hover { opacity: 0.8; }

        pre { font-family: monospace; font-size: 0.75rem; color: var(--text-muted); background: var(--muted); padding: 16px; border-radius: 6px; border: 1px solid var(--border); margin-top: 16px; white-space: pre-wrap; word-break: break-all; }
        
        .res-box { margin-top: 20px; display: none; max-height: 400px; overflow-y: auto; }
        .loading { font-size: 0.8rem; color: var(--text-muted); display: none; margin-top: 10px; }

        .player-wrap { margin-top: 24px; display: none; background: #000; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); aspect-ratio: 16/9; position: relative; }
        video { width: 100%; height: 100%; display: block; }
        
        .curl-box { margin-top: 16px; display: none; background: var(--muted); border: 1px solid var(--border); border-radius: 6px; padding: 12px; position: relative; }
        .curl-box code { font-family: monospace; font-size: 0.75rem; color: var(--fg); word-break: break-all; display: block; }
        .copy-curl { position: absolute; top: 8px; right: 8px; background: var(--fg); color: var(--bg); border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.7rem; cursor: pointer; font-weight: 600; }
        .copy-curl:hover { opacity: 0.8; }

        footer { margin-top: 100px; padding: 40px 0; border-top: 1px solid var(--border); font-size: 0.8rem; color: var(--text-muted); line-height: 1.8; text-align: center; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-box">K</div>
            <h1>kuhi api</h1>
            <p class="subtitle">revamped and decrypted streaming server built for scale.</p>
            <div class="v-badge">v2.0 — live testing enabled</div>
        </header>

        <div class="warning-box">
            <strong>⚠ disclaimer:</strong> this api is experimental and not reliable. use at your own risk. no guarantees on uptime or data accuracy. i'm not responsible for any legal troubles
        </div>

        <span class="lbl">anime endpoints explorer</span>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">search</span></div>
                <div class="tag">full metadata</div>
            </div>
            <div class="desc">global anime search. returns full metadata titles and covers.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/search?query=violet evergarden&page=1">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">suggestions</span> <span class="tag">lite</span></div>
            </div>
            <div class="desc">lightweight autocomplete search. minimal data footprint.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/suggestions?query=violet evergarden">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">spotlight</span> <span class="tag">hot</span></div>
            </div>
            <div class="desc">curated hot list of top trending shows in focus.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/spotlight">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">filter</span></div>
            </div>
            <div class="desc">advanced logic to combine genres, years, formats and sorting.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/filter?genre=Action&sort=SCORE_DESC">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">genres</span></div>
            </div>
            <div class="desc">list all available genres for filtering.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/genres">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">info/{id}</span></div>
                <div class="tag">full info</div>
            </div>
            <div class="desc">complete anime page chunk — characters, relations, staff, and recs.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/info/21827">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">anime/{id}/characters</span></div>
            </div>
            <div class="desc">character list with voice actors.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/anime/21827/characters">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">anime/{id}/relations</span></div>
            </div>
            <div class="desc">related anime (sequels, prequels, spin-offs).</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/anime/21827/relations">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">anime/{id}/recommendations</span></div>
            </div>
            <div class="desc">recommended similar anime.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/anime/21827/recommendations">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">trending</span></div>
            </div>
            <div class="desc">currently trending anime.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/trending?page=1">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">popular</span></div>
            </div>
            <div class="desc">most popular anime of all time.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/popular?page=1">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">upcoming</span></div>
            </div>
            <div class="desc">upcoming anime releases.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/upcoming?page=1">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">recent</span></div>
            </div>
            <div class="desc">recently aired episodes.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/recent?page=1">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">schedule</span></div>
            </div>
            <div class="desc">airing schedule for upcoming episodes.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/schedule?page=1">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">episodes/{id}</span></div>
            </div>
            <div class="desc">grabs internal mappings and episode lists.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/episodes/178005">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <div class="card">
            <div class="meta">
                <div><span class="method">GET</span> <span class="path">episodes/{id}</span></div>
            </div>
            <div class="desc">grabs internal mappings and episode lists.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/episodes/21827">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="res-box"><pre></pre></div>
        </div>

        <span class="lbl">all-in-one automation</span>
        
        <div class="card">
            <div class="meta">
                <div><span class="method" style="background:#fff;color:#000">GET</span> <span class="path">extract</span> <span class="tag">magic</span></div>
            </div>
            <div class="desc">use anilist id (21827) or full anime name (violet evergarden). get id from /anime/search if needed. movies auto-detect.</div>
            <div class="sandbox">
                <input type="text" class="in-url" value="/anime/extract/violet-evergarden?e=1">
                <button class="try-btn" onclick="test(this)">execute</button>
            </div>
            <div class="loading">working...</div>
            <div class="player-wrap"><video id="hls-player" controls @play="refreshReferer"></video></div>
            <div class="curl-box">
                <button class="copy-curl" onclick="copyCurl(this)">copy</button>
                <code></code>
            </div>
            <div class="res-box"><pre></pre></div>
        </div>

        <footer>
            kuhi native 2.0 interface — miruro
        </footer>
    </div>

    <script>
        async function test(btn) {
            const card = btn.closest('.card');
            const input = card.querySelector('.in-url');
            const endpoint = input.value;
            const resBox = card.querySelector('.res-box');
            const pre = resBox.querySelector('pre');
            const loader = card.querySelector('.loading');

            resBox.style.display = 'none';
            loader.style.display = 'block';

            try {
                const response = await fetch(endpoint);
                const data = await response.json();
                pre.textContent = JSON.stringify(data, null, 2);
                resBox.style.display = 'block';

                // init player if streams exist in extraction
                if (data.streams && data.streams.length > 0) {
                    const hlsStream = data.streams.find(s => s.type === 'hls');
                    if (hlsStream && Hls.isSupported()) {
                        const video = document.getElementById('hls-player');
                        const hls = new Hls({
                            xhrSetup: function(xhr, url) {
                                // force all requests through our server
                                if (url.startsWith('http') && !url.includes('127.0.0.1') && !url.includes('localhost')) {
                                    return;
                                }
                            }
                        });
                        // we use an internal proxy to inject the required referer per stream response
                        const proxyUrl = `/proxy_m3u8?url=${encodeURIComponent(hlsStream.url)}&referer=${encodeURIComponent(hlsStream.referer)}`;
                        hls.loadSource(proxyUrl);
                        hls.attachMedia(video);
                        card.querySelector('.player-wrap').style.display = 'block';
                        
                        // add curl command for m3u8
                        const curlCmd = `curl -H "Referer: ${hlsStream.referer}" "${hlsStream.url}"`;
                        const curlBox = card.querySelector('.curl-box');
                        if (curlBox) {
                            curlBox.querySelector('code').textContent = curlCmd;
                            curlBox.style.display = 'block';
                        }
                    }
                }
            } catch (err) {
                pre.textContent = 'error: ' + err.message;
                resBox.style.display = 'block';
            } finally {
                loader.style.display = 'none';
            }
        }
        
        function copyCurl(btn) {
            const code = btn.parentElement.querySelector('code').textContent;
            navigator.clipboard.writeText(code);
            btn.textContent = 'copied!';
            setTimeout(() => btn.textContent = 'copy', 2000);
        }
    </script>
</body>
</html>"""
