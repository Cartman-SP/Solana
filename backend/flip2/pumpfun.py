# pip install websockets aiohttp base58 colorama
# (optional) pip install orjson uvloop

import asyncio, re, base64, json
import websockets, aiohttp
from base58 import b58encode, b58decode
from colorama import init as colorama_init, Fore, Style

# -------- fast JSON (orjson if available) --------
try:
    import orjson
    def jloads(b: bytes | str):
        if isinstance(b, str): b = b.encode()
        return orjson.loads(b)
    def jdumps(o): return orjson.dumps(o).decode()
except Exception:
    def jloads(b: bytes | str):
        if isinstance(b, bytes): b = b.decode("utf-8", "ignore")
        return json.loads(b.lstrip("\ufeff").strip())
    def jdumps(o): return json.dumps(o, separators=(",", ":"))

# ===================== CONFIG =====================
HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMP_FUN = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

# Веб-сокет сервер для отправки данных
WEBSOCKET_SERVER_URL = "ws://localhost:9393"

# Скорость vs чистота:
# - "fast": мгновенно печатает по Create (commitment=processed), без явных ошибок
# - "strict": только реально "Complete" + успех программы (медленнее, может пропускать)
MODE = "fast"

# Доп. тумблеры
COMMITMENT = "processed" if MODE == "fast" else "finalized"
STRICT_COMPLETE_SUCCESS = True
REQUIRE_METADATA_ON_CREATE = (MODE != "fast")
DEBUG_SUB = False   # True -> печатаем первые 3 необработанных сырых лога для диагностики

IPFS_PER_REQ_MS  = 900
MAX_IPFS_TRIES   = 2
RETRY_DELAYS_SEC = [0.0, 0.4]
IPFS_GATEWAYS = [
    "https://cloudflare-ipfs.com/ipfs/",
    "https://ipfs.io/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
    "https://ipfs.mogtech.dev/ipfs/",
]

# X/Twitter community helpers
COMMUNITY_ID_RE = re.compile(r"/communities/(\d+)", re.IGNORECASE)
TW_API_KEY = "8879aa53d815484ebea0313718172fea"
TW_BASE    = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}
TW_TIMEOUT_SEC = 5.0

# state
SEEN_SIGS, SEEN_MINTS = set(), set()
URI_META_CACHE: dict[str, dict] = {}
COMMUNITY_INFO_CACHE: dict[str, tuple[str|None, int|None, str|None]] = {}
_debug_left = 3

# ================= WebSocket subscription =================
def build_logs_sub():
    return {
        "jsonrpc": "2.0",
        "id": "logs-pump",
        "method": "logsSubscribe",
        "params": [
            {"mentions": [PUMP_FUN]},
            {"commitment": COMMITMENT}
        ]
    }

def unpack_logs_notification(msg):
    params = msg.get("params") or {}
    res    = params.get("result") or {}
    value  = res.get("value") or {}
    ctx    = res.get("context") or {}
    logs   = value.get("logs") or res.get("logs") or []
    sig    = value.get("signature") or res.get("signature")
    slot   = ctx.get("slot") or res.get("slot")
    return logs, sig, slot

# ================= Log filters =================
def _low_logs(logs):
    return [str(l).lower() for l in (logs or [])]

def pump_program_succeeded(logs: list[str]) -> bool:
    tgt = f"program {PUMP_FUN.lower()}"
    for l in _low_logs(logs):
        if tgt in l and " success" in l:
            return True
    return False

def has_program_error(logs: list[str]) -> bool:
    for l in _low_logs(logs):
        if "failed:" in l or "custom program error" in l:
            return True
    return False

def looks_like_create(logs: list[str]) -> bool:
    for l in _low_logs(logs):
        if "instruction" in l and "create" in l:
            return True
    return False

def looks_like_complete(logs: list[str]) -> bool:
    for l in _low_logs(logs):
        if "instruction" in l and "complete" in l:
            return True
    return False

def complete_was_successful(logs: list[str]) -> bool:
    low = _low_logs(logs)
    tgt = f"program {PUMP_FUN.lower()}"
    saw_complete = False
    for l in low:
        if "instruction" in l and "complete" in l:
            saw_complete = True
        if saw_complete and (tgt in l) and (" success" in l):
            return True
    return False

def looks_like_metadata_created(logs: list[str]) -> bool:
    low = _low_logs(logs)
    return any(("createmetadata" in l) or ("create metadata" in l) or ("metaplex token metadata" in l) for l in low)

# ================= Program data parsing =================
PROGDATA_RE = re.compile(r"Program data:\s*([A-Za-z0-9+/=]+)")

def collect_progdata_bytes_after_create(logs):
    chunks, after = [], False
    for line in logs:
        low = str(line).lower()
        if "instruction" in low and "create" in low:
            after = True
            continue
        if not after:
            continue
        m = PROGDATA_RE.search(str(line))
        if m:
            chunks.append(m.group(1))
        elif chunks:
            break
    if not chunks:
        return None

    out = bytearray()
    for c in chunks:
        try:
            out += base64.b64decode(c, validate=True)
        except Exception:
            try:
                out += b58decode(c)
            except Exception:
                return None
    return bytes(out)

def _read_borsh_string(buf: memoryview, off: int):
    if off + 4 > len(buf): return None, off
    ln = int.from_bytes(buf[off:off+4], "little"); off += 4
    if ln < 0 or off + ln > len(buf): return None, off
    try:
        s = bytes(buf[off:off+ln]).decode("utf-8", "ignore")
    except Exception:
        s = ""
    off += ln
    return s, off

def _take_pk(buf: memoryview, off: int):
    if off + 32 > len(buf): return None, off
    return b58encode(bytes(buf[off:off+32])).decode(), off + 32

def parse_pump_create(raw: bytes):
    if not raw or len(raw) < 8: return None
    mv = memoryview(raw)
    off = 8
    name, off   = _read_borsh_string(mv, off)
    symbol, off = _read_borsh_string(mv, off)
    uri, off    = _read_borsh_string(mv, off)
    mint, off          = _take_pk(mv, off)
    bonding_curve, off = _take_pk(mv, off)
    creator, off       = _take_pk(mv, off)
    return {
        "name": name or "", "symbol": symbol or "", "uri": uri or "",
        "mint": mint or "", "bondingCurve": bonding_curve or "", "creator": creator or "",
        "decimals": 6,
    }

# ================= Metadata fetching =================
def normalize_uri_candidates(u: str) -> list[str]:
    if not u: return []
    u = u.strip(); low = u.lower()
    if low.startswith(("http://","https://")): return [u]
    if low.startswith("ipfs://"):
        path = u[7:]
        if path.startswith("ipfs/"): path = path[5:]
        return [g + path for g in IPFS_GATEWAYS[:MAX_IPFS_TRIES]]
    if low.startswith("ar://"):
        path = u[5:]
        return [f"https://arweave.net/{path}"]
    return [f"https://{u.lstrip('/')}"]

async def fetch_json_once(session: aiohttp.ClientSession, url: str, timeout_ms: int) -> dict | None:
    try:
        to = aiohttp.ClientTimeout(total=timeout_ms/1000)
        async with session.get(url, timeout=to) as r:
            b = await r.read()
            if not b: return None
            return jloads(b)
    except Exception:
        return None

async def fetch_meta_with_retries(session: aiohttp.ClientSession, uri: str) -> dict | None:
    if uri in URI_META_CACHE:
        return URI_META_CACHE[uri]
    urls = normalize_uri_candidates(uri)
    for delay in RETRY_DELAYS_SEC:
        if delay: await asyncio.sleep(delay)
        tasks = [asyncio.create_task(fetch_json_once(session, u, IPFS_PER_REQ_MS)) for u in urls]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        result = None
        for t in done:
            try:
                j = t.result()
                if isinstance(j, dict):
                    result = j
                    break
            except Exception:
                pass
        for p in pending: p.cancel()
        if isinstance(result, dict):
            URI_META_CACHE[uri] = result
            return result
    return None

# ================= Community helpers =================
def _ensure_scheme(url: str) -> str:
    u = url.strip()
    if not u.lower().startswith(("http://","https://")) and ".com/" in u:
        u = "https://" + u.lstrip("/")
    return u

# ================= WebSocket Client =================
async def send_to_websocket_server(websocket_data: dict):
    """Отправляет данные о токене с username через веб-сокет"""
    try:
        async with websockets.connect(WEBSOCKET_SERVER_URL, timeout=2.0) as ws:
            await ws.send(jdumps(websocket_data))
    except Exception as e:
        print(Fore.RED + f"[WS] Ошибка отправки в веб-сокет: {e}" + Style.RESET_ALL)

def _strings_in_json(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings_in_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings_in_json(v)

def canonicalize_community_url(url_or_id: str) -> tuple[str|None, str|None]:
    s = (url_or_id or "").strip()
    if not s:
        return None, None
    if s.isdigit():
        return f"https://x.com/i/communities/{s}", s
    u = _ensure_scheme(s)
    m = COMMUNITY_ID_RE.search(u)
    if not m:
        return None, None
    cid = m.group(1)
    return f"https://x.com/i/communities/{cid}", cid

def find_community_anywhere_with_src(meta_json: dict) -> tuple[str|None, str|None, str|None]:
    for key in ("twitter", "x", "external_url", "website"):
        v = meta_json.get(key)
        if isinstance(v, str) and v.strip():
            url, cid = canonicalize_community_url(v)
            if cid:
                return url, cid, key
    ex = meta_json.get("extensions")
    if isinstance(ex, dict):
        for key in ("twitter", "x", "external_url", "website"):
            v = ex.get(key)
            if isinstance(v, str) and v.strip():
                url, cid = canonicalize_community_url(v)
                if cid:
                    return url, cid, f"extensions.{key}"
    for s in _strings_in_json(meta_json):
        url, cid = canonicalize_community_url(s)
        if cid:
            return url, cid, "anywhere"
    return None, None, None

def normalize_image_link(meta_json: dict) -> str | None:
    img = (meta_json.get("image") or "").strip()
    if not img: return None
    if img.lower().startswith("ipfs://"):
        path = img[7:]
        if path.startswith("ipfs/"): path = path[5:]
        return IPFS_GATEWAYS[0] + path
    return img

async def _tw_get(session, path, params):
    to = aiohttp.ClientTimeout(total=TW_TIMEOUT_SEC)
    async with session.get(f"{TW_BASE}{path}", headers=TW_HEADERS, params=params, timeout=to) as r:
        r.raise_for_status()
        return await r.json()

def _extract_username_followers(user_obj: dict) -> tuple[str|None, int|None]:
    if not isinstance(user_obj, dict):
        return None, None
    username = user_obj.get("screen_name") or user_obj.get("userName") or user_obj.get("username")
    followers = (
        user_obj.get("followers_count")
        or user_obj.get("followers")
        or ((user_obj.get("public_metrics") or {}).get("followers_count"))
    )
    try:
        followers = int(followers) if followers is not None else None
    except Exception:
        followers = None
    return (username, followers) if username else (None, None)

async def _get_creator_from_info(session: aiohttp.ClientSession, community_id: str):
    j = await _tw_get(session, "/twitter/community/info", {"community_id": community_id})
    ci = (j or {}).get("community_info", {}) or {}
    u, f = _extract_username_followers(ci.get("creator") or {})
    if u:
        return u, f, "creator"
    u, f = _extract_username_followers(ci.get("first_member") or {})
    if u:
        return u, f, "member"
    return None, None, None

async def _get_first_member_via_members(session: aiohttp.ClientSession, community_id: str):
    try:
        j = await _tw_get(session, "/twitter/community/members", {"community_id": community_id, "limit": 1})
    except Exception:
        return None, None, None
    candidates = []
    for key in ("members", "data", "users"):
        arr = j.get(key)
        if isinstance(arr, list):
            candidates.extend(arr)
    if not candidates:
        data = j.get("data")
        if isinstance(data, dict) and isinstance(data.get("users"), list):
            candidates.extend(data["users"])
    if not candidates:
        return None, None, None
    u, f = _extract_username_followers(candidates[0] or {})
    if u:
        return u, f, "member"
    return None, None, None

async def get_creator_or_member(session: aiohttp.ClientSession, community_id: str):
    if community_id in COMMUNITY_INFO_CACHE:
        return COMMUNITY_INFO_CACHE[community_id]
    for attempt in (1, 2):
        try:
            u, f, src = await _get_creator_from_info(session, community_id)
            if not u:
                u, f, src = await _get_first_member_via_members(session, community_id)
            if u:
                COMMUNITY_INFO_CACHE[community_id] = (u, f, src)
                return u, f, src
        except Exception:
            pass
        if attempt == 1:
            await asyncio.sleep(0.5)
    COMMUNITY_INFO_CACHE[community_id] = (None, None, None)
    return None, None, None

# ===================== MAIN LOOP =====================
async def main():
    colorama_init()
    tcp = aiohttp.TCPConnector(limit=60, ttl_dns_cache=300)
    headers = {"User-Agent": f"pump-watcher/{'1.7-fast' if MODE=='fast' else '1.7-strict'}"}

    while True:
        try:
            async with aiohttp.ClientSession(connector=tcp, headers=headers) as http, \
                   websockets.connect(
                       WS_URL,
                       ping_interval=25,
                       ping_timeout=30,
                       close_timeout=5,
                       open_timeout=15,
                       max_size=None,
                   ) as ws:

                await ws.send(jdumps(build_logs_sub()))
                ack = await ws.recv()

                async for raw in ws:
                    msg = jloads(raw)
                    if msg.get("method") != "logsNotification":
                        continue

                    logs, sig, _slot = unpack_logs_notification(msg)
                    if not sig or sig in SEEN_SIGS:
                        continue

                    # быстрая диагностика, если вдруг ничего не ловится
                    global _debug_left
                    if DEBUG_SUB and _debug_left > 0:
                        _debug_left -= 1

                    # ---- фильтры ----
                    if MODE == "strict":
                        if not (looks_like_complete(logs) and not has_program_error(logs)):
                            continue
                        if STRICT_COMPLETE_SUCCESS and not complete_was_successful(logs):
                            continue
                    else:  # fast
                        # минимально строгие условия: есть Create, нет явной ошибки
                        if not (looks_like_create(logs) and not has_program_error(logs)):
                            continue
                        # если явно виден success у pump.fun — отлично; если нет, всё равно печатаем (ради скорости)
                        # но отсекаем явный провал
                        # (ничего не делаем тут — логика уже выше)

                    # Парсим данные из блока Create
                    data = collect_progdata_bytes_after_create(logs)
                    parsed = parse_pump_create(data or b"")
                    if not parsed:
                        continue

                    uri  = (parsed["uri"] or "").strip()
                    mint = (parsed["mint"] or "").strip()
                    sym  = (parsed["symbol"] or "").strip()

                    if not mint or mint in SEEN_MINTS:
                        continue
                    if not sym:
                        continue

                    # помечаем после всех фильтров
                    SEEN_SIGS.add(sig)
                    SEEN_MINTS.add(mint)

                    stage = "LAUNCHED" if looks_like_complete(logs) else "CREATED"

                    # Быстрый вывод готов, ниже — «мягкие» HTTP (не RPC) для доп. инфы
                    links = {}
                    img   = None
                    community_url = community_id = community_src = None

                    if MODE != "fast" or uri:  # в fast тоже можно, но мы уже распечатали основное
                        if uri:
                            meta = await fetch_meta_with_retries(http, uri)
                            if isinstance(meta, dict):
                                for k in ("external_url","website","twitter","x","telegram","discord"):
                                    v = meta.get(k) or (meta.get("extensions", {}) if isinstance(meta.get("extensions"), dict) else {}).get(k)
                                    if isinstance(v, str) and v.strip():
                                        links[k] = v.strip()
                                # картинка / community
                                img = normalize_image_link(meta)
                                # найти community id где угодно
                                for s in (links.get("x"), links.get("twitter"), links.get("external_url"), links.get("website")):
                                    if isinstance(s, str):
                                        m = COMMUNITY_ID_RE.search(s)
                                        if m:
                                            community_id = m.group(1)
                                            community_url = f"https://x.com/i/communities/{community_id}"
                                            community_src = "link"
                                            break

                    websocket_data = {
                        "source": "pumpfun",
                        "mint": mint,
                        "user": parsed['creator'],
                        "name": parsed['name'],
                        "symbol": parsed['symbol'],
                        "uri": uri,
                    }
                    if community_id:
                        try:
                            username, followers, who = await get_creator_or_member(http, community_id)
                            line = f"★ X COMMUNITY: {community_url}"
                            if username:
                                label = "создатель" if who == "creator" else "участник"
                                line += f"  |  {label}: @{username}"
                                if isinstance(followers, int):
                                    line += f"  |  подписчиков: {followers:,}"
                                websocket_data["twitter_name"] = f"@{username}"
                                websocket_data["twitter_followers"] = followers


                                
                        except Exception:
                            pass
                    await send_to_websocket_server(websocket_data)

        except Exception as e:
            print("WS reconnect after error:", e)
            await asyncio.sleep(0.7)

if __name__ == "__main__":
    # import uvloop; uvloop.install()  # опционально
    asyncio.run(main())
