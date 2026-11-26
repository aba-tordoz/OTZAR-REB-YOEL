import os
import sys
import re
import json
import ssl
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
import html as html_lib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = r"C:\Users\avremi-c\.gemini\antigravity\scratch\reb_yoel_archive"
CACHE_DIR = os.path.join(BASE_DIR, "raw_cache")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

ctx = ssl.create_default_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def quote_url(u):
    parts = urllib.parse.urlsplit(u)
    path = urllib.parse.quote(parts.path, safe="/:@&=+$,%")
    query = urllib.parse.quote(parts.query, safe="=&?/:@+$,%")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))

def fetch(url, extra_headers=None, timeout=25, retries=2):
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    qurl = quote_url(url)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(qurl, headers=h)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt == retries:
                raise e
            time.sleep(0.5 * (attempt + 1))

# ==============================================================================
# 1. HEICHALAPP (json.heichalapp.com/authors/8) -> ~3,400+ Shiurim & Niggunim
# ==============================================================================
def harvest_heichalapp():
    cache_file = os.path.join(CACHE_DIR, "heichalapp.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[HeichalApp] Loaded {len(data)} cached tracks")
            return data

    print("[HeichalApp] Fetching author 8 tree...")
    author8 = json.loads(fetch("https://json.heichalapp.com/authors/8"))
    root_cats = author8.get("categoriesByLanguage", {}).get("yi", [])

    visited_cats = set()
    tracks_by_id = {}  # id -> track dict with paths list
    cat_queue = [(c["id"], [c["title"]]) for c in root_cats]

    def process_cat(cid, path_titles):
        cat_data = json.loads(fetch(f"https://json.heichalapp.com/categories/{cid}"))
        subs = cat_data.get("subCategories", [])
        total_pages = cat_data.get("totalPages", 0) or 0
        page_tracks = []
        if total_pages > 0:
            for p in range(1, total_pages + 1):
                try:
                    pdata = json.loads(fetch(f"https://json.heichalapp.com/categories/{cid}/pages/{p}"))
                    items = pdata if isinstance(pdata, list) else pdata.get("items", pdata.get("soundtracks", []))
                    page_tracks.extend(items)
                except Exception as e:
                    print(f"  [HeichalApp] Page err {cid} p{p}: {e}")
        return cid, path_titles, subs, page_tracks

    with ThreadPoolExecutor(max_workers=14) as ex:
        while cat_queue:
            batch = []
            while cat_queue:
                cid, pt = cat_queue.pop(0)
                if cid in visited_cats:
                    continue
                visited_cats.add(cid)
                batch.append(ex.submit(process_cat, cid, pt))
            if not batch:
                break
            for fut in as_completed(batch):
                try:
                    cid, path_titles, subs, page_tracks = fut.result()
                    for sc in subs:
                        sc_id = sc["id"]
                        if sc_id not in visited_cats:
                            cat_queue.append((sc_id, path_titles + [sc["title"]]))
                    for it in page_tracks:
                        tid = it.get("id")
                        if not tid:
                            continue
                        if tid not in tracks_by_id:
                            tracks_by_id[tid] = {
                                "id": tid,
                                "title": it.get("title", "").strip(),
                                "subtitle": it.get("subtitle") or "",
                                "filePath": it.get("filePath", ""),
                                "fileName": it.get("fileName", ""),
                                "duration": it.get("duration") or 0,
                                "hasBookVersion": bool(it.get("hasBookVersion")),
                                "paths": []
                            }
                        tracks_by_id[tid]["paths"].append(path_titles)
                except Exception as e:
                    print(f"  [HeichalApp] Cat err: {e}")

    result = list(tracks_by_id.values())
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"[HeichalApp] Harvested {len(result)} unique tracks across {len(visited_cats)} categories!")
    return result

# ==============================================================================
# 2. PODCAST RSS FEEDS (4 official Anchor/Spotify feeds)
# ==============================================================================
def harvest_podcasts():
    cache_file = os.path.join(CACHE_DIR, "podcasts.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[Podcasts] Loaded {len(data)} cached episodes")
            return data

    feeds = [
        ("podcast_chazara", "חזרות על התוועדויות הרבי (Chazara - R' Yoel Kahn)", "yi", "https://anchor.fm/s/da801cec/podcast/rss"),
        ("podcast_tanya", "שיעורי תניא בעברית | הרב יואל כהן", "he", "https://anchor.fm/s/d53b97d4/podcast/rss"),
        ("podcast_study", "Study Chassidus with Rabbi Yoel Kahn", "en_yi", "https://anchor.fm/s/45ba83a4/podcast/rss"),
        ("podcast_fabrenguen", "התוועדויות ר' יואל כהן - עברית", "he", "https://anchor.fm/s/67553a2c/podcast/rss"),
    ]
    all_eps = []
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

    def parse_dur(d_str):
        if not d_str:
            return 0
        d_str = d_str.strip()
        if d_str.isdigit():
            return int(d_str)
        parts = [int(p) for p in d_str.split(":") if p.isdigit()]
        if len(parts) == 3:
            return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2:
            return parts[0]*60 + parts[1]
        return 0

    for src_key, feed_name, lang, url in feeds:
        try:
            xml_txt = fetch(url)
            root = ET.fromstring(xml_txt)
            items = root.findall("./channel/item")
            print(f"[Podcasts] {feed_name}: {len(items)} episodes")
            for idx, it in enumerate(items):
                title = (it.findtext("title") or "").strip()
                desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "").strip()
                desc = html_lib.unescape(re.sub(r"\s+", " ", desc))
                pub = it.findtext("pubDate") or ""
                link = it.findtext("link") or ""
                enc = it.find("enclosure")
                mp3 = enc.attrib.get("url", "") if enc is not None else ""
                dur = parse_dur(it.findtext("itunes:duration", namespaces=ns))
                all_eps.append({
                    "source": src_key,
                    "feedName": feed_name,
                    "lang": lang,
                    "title": title,
                    "desc": desc[:400],
                    "pubDate": pub,
                    "link": link,
                    "mp3": mp3,
                    "duration": dur,
                    "idx": idx,
                })
        except Exception as e:
            print(f"[Podcasts] ERR {src_key}: {e}")

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(all_eps, f, ensure_ascii=False)
    return all_eps

# ==============================================================================
# 3. VIDEO.CHASIDUT.NET (hachozer, pages 1..31 -> ~360+ videos + direct MP4)
# ==============================================================================
def harvest_video_chasidut():
    cache_file = os.path.join(CACHE_DIR, "video_chasidut.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[VideoChasidut] Loaded {len(data)} cached videos")
            return data

    print("[VideoChasidut] Crawling listing pages...")
    vid_entries = {}  # vid_id -> {id, url, title, thumb}
    for p in range(1, 35):
        u = "http://video.chasidut.net/videos/load/hachozer" if p == 1 else f"http://video.chasidut.net/videos/load/hachozer/{p}"
        try:
            html = fetch(u)
            matches = re.findall(r'href=["\']((?:http://video\.chasidut\.net/)?videos/(\d+)/([^"\']+))["\']', html)
            if not matches:
                break
            new_count = 0
            for raw_href, vid_id, slug in matches:
                if vid_id not in vid_entries:
                    full_url = raw_href if raw_href.startswith("http") else "http://video.chasidut.net/" + raw_href.lstrip("/")
                    vid_entries[vid_id] = {
                        "id": vid_id,
                        "url": full_url,
                        "slug": urllib.parse.unquote(slug),
                    }
                    new_count += 1
            if new_count == 0 and p > 1:
                break
        except Exception as e:
            print(f"  [VideoChasidut] page {p} err: {e}")
            break

    print(f"[VideoChasidut] Found {len(vid_entries)} unique video pages. Fetching details & MP4 URLs...")

    def fetch_vid_detail(entry):
        vurl = entry["url"]
        vd = fetch(vurl)
        # Title
        t_m = re.search(r'<title[^>]*>(.*?)</title>', vd, re.S | re.I)
        title = html_lib.unescape(re.sub(r"\s+", " ", t_m.group(1)).strip()) if t_m else entry["slug"]
        # Description meta
        d_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']', vd, re.I)
        desc = html_lib.unescape(d_m.group(1).strip()) if d_m else ""
        # Tags
        tag_m = re.search(r'&Tag=([^"&]+)', vd)
        tags = html_lib.unescape(tag_m.group(1).strip()) if tag_m else ""
        # Duration
        dur_m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', vd)
        # Thumb
        th_m = re.search(r'uploads/thumbs/([^"\'\s<>]+\.jpg)', vd)
        thumb = f"http://video.chasidut.net/uploads/thumbs/{th_m.group(1)}" if th_m else ""
        # Direct mp4 via make_player.php with Referer
        mp4 = ""
        ifr_m = re.search(r'<iframe[^>]+src=["\'](http://video\.chasidut\.net/make_player\.php\?[^"\']+)["\']', vd)
        if ifr_m:
            try:
                mp_html = fetch(ifr_m.group(1), extra_headers={"Referer": quote_url(vurl)})
                src_m = re.search(r"src=['\"](http://video\.chasidut\.net/uploads/[^'\"]+)['\"]", mp_html)
                if src_m:
                    mp4 = src_m.group(1)
            except Exception:
                pass
        entry.update({
            "title": title,
            "desc": desc,
            "tags": tags,
            "thumb": thumb,
            "mp4": mp4,
        })
        return entry

    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(fetch_vid_detail, e) for e in vid_entries.values()]
        for fut in as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as e:
                print("  [VideoChasidut] detail err:", e)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"[VideoChasidut] Harvested {len(results)} videos ({sum(1 for r in results if r.get('mp4'))} with direct MP4)!")
    return results

# ==============================================================================
# 4. MERKAZ ANASH (merkazanash.com/videos -> Chassidus Perspective MP4+MP3+PDF)
# ==============================================================================
def harvest_merkaz_anash():
    cache_file = os.path.join(CACHE_DIR, "merkaz_anash.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[MerkazAnash] Loaded {len(data)} cached items")
            return data

    print("[MerkazAnash] Crawling Chassidus Perspective pages...")
    cp_links = []
    seen = set()
    for p in range(0, 12):
        u = "https://merkazanash.com/videos" if p == 0 else f"https://merkazanash.com/videos?page={p}"
        try:
            html = fetch(u)
            found = re.findall(r'href=["\'](/cp/[^"\']+)["\']', html)
            if not found:
                break
            added = 0
            for path in found:
                if path not in seen:
                    seen.add(path)
                    cp_links.append("https://merkazanash.com" + path)
                    added += 1
            if added == 0:
                break
        except Exception as e:
            print(f"  [MerkazAnash] page {p} err: {e}")
            break

    def fetch_cp(url):
        h = fetch(url)
        t_m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
        if not t_m:
            t_m = re.search(r'<title[^>]*>(.*?)</title>', h, re.S)
        title = html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t_m.group(1))).strip()) if t_m else url.split("/")[-1]
        title = title.replace("| Merkaz Anash", "").strip()
        mp4s = re.findall(r'https?://merkazanash\.com/sites/default/files/[^"\'\s<>]+\.mp4', h, re.I)
        mp3s = re.findall(r'https?://merkazanash\.com/sites/default/files/[^"\'\s<>]+\.mp3', h, re.I)
        pdfs = re.findall(r'https?://merkazanash\.com/sites/default/files/[^"\'\s<>]+\.pdf', h, re.I)
        # Parsha/date subtitle often in h2 or node body
        parsha_m = re.search(r'([A-Za-z\'\s-]+57\d{2})', h)
        return {
            "url": url,
            "slug": url.split("/")[-1],
            "title": title,
            "mp4": mp4s[0] if mp4s else "",
            "mp3": mp3s[0] if mp3s else "",
            "pdf": pdfs[0] if pdfs else "",
            "hint": parsha_m.group(1).strip() if parsha_m else "",
        }

    items = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fut in as_completed([ex.submit(fetch_cp, u) for u in cp_links]):
            try:
                items.append(fut.result())
            except Exception as e:
                print("  [MerkazAnash] item err:", e)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    print(f"[MerkazAnash] Harvested {len(items)} items!")
    return items

# ==============================================================================
# 5. HEICHAL MENACHEM MONSEY (Full farbrengens + 51+ short vorts)
# ==============================================================================
def harvest_monsey():
    cache_file = os.path.join(CACHE_DIR, "monsey.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[Monsey] Loaded {len(data)} cached items")
            return data

    print("[Monsey] Crawling Heichal Menachem Monsey...")
    post_urls = []
    seen = set()
    for p in [1, 2, 3]:
        u = "https://heichalmenachemmonsey.org/cat/rabbunim/yoel-kahn/" if p == 1 else f"https://heichalmenachemmonsey.org/cat/rabbunim/yoel-kahn/page/{p}/"
        try:
            h = fetch(u)
            for art in re.findall(r'<article[^>]*>.*?</article>', h, re.S):
                lnk_m = re.search(r'href=["\'](https://heichalmenachemmonsey\.org/[^"\']+)["\']', art)
                if lnk_m and lnk_m.group(1) not in seen:
                    seen.add(lnk_m.group(1))
                    post_urls.append(lnk_m.group(1))
        except Exception:
            break

    items = []
    for u in post_urls:
        try:
            h = fetch(u)
            t_m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
            title = html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t_m.group(1))).strip()) if t_m else u
            if "short_vort_reb_yoel" in u:
                # Split by each short vort mp4/mp3 block cleanly
                blocks = re.split(r'(?=<p[^>]*direction:\s*rtl[^>]*>)', h)
                seen_vorts = set()
                for blk in blocks:
                    mp3_m = re.search(r'(https?://(?:www\.)?merkazanash\.com/sites/default/files/[^"\'\s<>]+\.mp3)', blk, re.I)
                    if not mp3_m:
                        continue
                    mp3 = mp3_m.group(1)
                    if mp3 in seen_vorts:
                        continue
                    seen_vorts.add(mp3)
                    mp4_m = re.search(r'(https?://(?:www\.)?merkazanash\.com/sites/default/files/[^"\'\s<>]+\.mp4)', blk, re.I)
                    pdf_m = re.search(r'(https?://(?:www\.)?merkazanash\.com/sites/default/files/[^"\'\s<>]+\.pdf)', blk, re.I)
                    strong_m = re.search(r'<strong[^>]*>(.*?)</strong>', blk, re.S)
                    parsha_t = html_lib.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', strong_m.group(1))).strip()) if strong_m else ""
                    src_m = re.search(r'מקור:\s*([^\n<]+)', blk)
                    mekor = html_lib.unescape(src_m.group(1).strip()) if src_m else ""
                    fname = mp3.split("/")[-1].replace(".mp3", "")
                    yr_m = re.search(r'(\d{2})$', fname)
                    yr_tag = f"תשע\"{['', 'א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט'][int(yr_m.group(1)[1])]}" if yr_m and yr_m.group(1).startswith("7") else ""
                    if yr_m and yr_m.group(1) == "80":
                        yr_tag = "תש\"פ"
                    full_title = f"רעיון קצר — {parsha_t or fname}" + (f" ({yr_tag})" if yr_tag else "")
                    items.append({
                        "url": u,
                        "title": full_title,
                        "mekor": mekor,
                        "mp3": mp3,
                        "mp4": mp4_m.group(1) if mp4_m else "",
                        "pdf": pdf_m.group(1) if pdf_m else "",
                        "youtube": "",
                        "slug": fname,
                        "isShortVort": True,
                    })
            else:
                mp3s = list(dict.fromkeys(re.findall(r'https?://[^"\'\s<>]+\.mp3', h, re.I)))
                yts = list(dict.fromkeys(re.findall(r'(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})', h)))
                if mp3s:
                    for idx, mp3 in enumerate(mp3s):
                        part_t = title if len(mp3s) == 1 else f"{title} (חלק {idx+1})"
                        items.append({
                            "url": u,
                            "title": part_t,
                            "mp3": mp3,
                            "youtube": yts[idx] if idx < len(yts) else (yts[0] if yts else ""),
                            "slug": u.rstrip("/").split("/")[-1],
                            "isShortVort": False,
                        })
                elif yts:
                    for idx, yt in enumerate(yts):
                        part_t = title if len(yts) == 1 else f"{title} (חלק {idx+1})"
                        items.append({
                            "url": u,
                            "title": part_t,
                            "mp3": "",
                            "youtube": yt,
                            "slug": u.rstrip("/").split("/")[-1],
                            "isShortVort": False,
                        })
                else:
                    items.append({
                        "url": u,
                        "title": title,
                        "mp3": "",
                        "youtube": "",
                        "slug": u.rstrip("/").split("/")[-1],
                        "isShortVort": False,
                    })
        except Exception as e:
            print("  [Monsey] err:", u, e)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    print(f"[Monsey] Harvested {len(items)} items!")
    return items

# ==============================================================================
# 6. PROJECT MELUKAT (projectmelukat.org/sitemap.xml -> 47 Maamarim & PDFs)
# ==============================================================================
def harvest_melukat():
    cache_file = os.path.join(CACHE_DIR, "melukat.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[Melukat] Loaded {len(data)} cached items")
            return data

    print("[Melukat] Crawling sitemap...")
    sm = fetch("https://projectmelukat.org/sitemap.xml")
    yoel_urls = re.findall(r'<loc>([^<]*(?:yoel|kahn)[^<]*)</loc>', sm, re.I)

    def fetch_pm(u):
        h = fetch(u)
        t_m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
        h1 = html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t_m.group(1))).strip()) if t_m else ""
        # Also get h2/h3 for Maamar name
        h2_m = re.search(r'<h2[^>]*>(.*?)</h2>', h, re.S)
        h2 = html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h2_m.group(1))).strip()) if h2_m else ""
        # Drive iframes
        drives = re.findall(r'https?://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/', h)
        is_pdf = "/pdfs/" in u
        # parse maamar slug e.g. podoh-bsholom-5726
        slug = u.replace("https://projectmelukat.org/", "").split("/")[0]
        return {
            "url": u,
            "slug": slug,
            "h1": h1,
            "h2": h2,
            "isPdf": is_pdf,
            "driveId": drives[0] if drives else "",
        }

    items = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fut in as_completed([ex.submit(fetch_pm, u) for u in yoel_urls]):
            try:
                items.append(fut.result())
            except Exception as e:
                print("  [Melukat] err:", e)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    print(f"[Melukat] Harvested {len(items)} items!")
    return items

# ==============================================================================
# 7. YOUTUBE & SINUN770 (Reb Yoel Kahn Mamarim Yiddish + 5751-5754 Speeches)
# ==============================================================================
def harvest_youtube_sinun():
    cache_file = os.path.join(CACHE_DIR, "youtube.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[YouTube] Loaded {len(data)} cached videos")
            return data

    print("[YouTube] Crawling Sinun770 Reb Yoel channel & YouTube playlists...")
    yt_map = {}  # videoId -> item

    # A. YouTube Playlist Feeds
    playlists = [
        ("PLSPKgUP5UiIq2n_aXB0NG5TXEPXsUvmMS", "נאומי ר' יואל כהן תנש\"א - תשנ\"ד", "yi"),
        ("PLnDn_AIZad-sSIf-a_yhCRNtRSeha20ba", "התוועדויות ושיעורים — הרב יואל כהן", "he"),
    ]
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    for pl_id, pl_name, lang in playlists:
        try:
            xml_txt = fetch(f"https://www.youtube.com/feeds/videos.xml?playlist_id={pl_id}")
            root = ET.fromstring(xml_txt)
            for e in root.findall("a:entry", namespaces=ns):
                vid = e.findtext("yt:videoId", namespaces=ns)
                title = e.findtext("a:title", namespaces=ns) or ""
                if vid and vid not in yt_map:
                    yt_map[vid] = {
                        "videoId": vid,
                        "title": title.strip(),
                        "series": pl_name,
                        "lang": lang,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                    }
        except Exception as e:
            print(f"  [YT] playlist {pl_id} err: {e}")

    # B. Sinun770 channel pages (UCHNCfybOXvA1N3P1B1Eyg-A - Reb Yoel Kahn Mamarim Yiddish)
    post_links = []
    for p in [1, 2, 3]:
        u = "https://sinun770.org/author/UCHNCfybOXvA1N3P1B1Eyg-A/" if p == 1 else f"https://sinun770.org/author/UCHNCfybOXvA1N3P1B1Eyg-A/page/{p}/"
        try:
            sn = fetch(u)
            for art in re.findall(r'<article[^>]*>.*?</article>', sn, re.S):
                t_m = re.search(r'<h[1-4][^>]*>(.*?)</h[1-4]>', art, re.S)
                lnk_m = re.search(r'href=["\'](https://sinun770\.org/[^"\']+)["\']', art)
                if lnk_m:
                    title = html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t_m.group(1))).strip()) if t_m else ""
                    post_links.append((lnk_m.group(1), title))
        except Exception:
            break

    def fetch_sinun_post(lnk, title):
        sp = fetch(lnk)
        yt_m = re.search(r'(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})', sp)
        if yt_m:
            return yt_m.group(1), title, lnk
        return None

    with ThreadPoolExecutor(max_workers=12) as ex:
        for fut in as_completed([ex.submit(fetch_sinun_post, l, t) for l, t in post_links]):
            try:
                res = fut.result()
                if res:
                    vid, title, lnk = res
                    if vid not in yt_map:
                        yt_map[vid] = {
                            "videoId": vid,
                            "title": title,
                            "series": "מאמרי חסידות ביוטיוב (אידיש)",
                            "lang": "yi",
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "sinunUrl": lnk,
                        }
            except Exception:
                pass

    # C. Also explicitly verified individual YouTube videos of Reb Yoel found earlier
    extra_yt = [
        ("9qgrwKlOZCA", "ר' יואל כהן — מאמר לי\"א ניסן / שיעור חסידות", "yi"),
        ("CaqQSEOOH8s", "ר' יואל כהן — שיעור תניא / חסידות", "he"),
        ("3OjDyBuJ75w", "הרב יואל כהן — שיעור והתוועדות", "he"),
        ("leR3Ac2CARQ", "הרב יואל כהן — שיעור ביוטיוב", "he"),
        ("q3Px0Kds9yA", "מאמר ל\"י שבט באתי לגני תשי\"ג — הרב יואל כהן", "yi"),
    ]
    # Fetch real <title> for those 5 videos from YouTube oEmbed!
    for vid, fallback_t, lang in extra_yt:
        if vid not in yt_map:
            real_t = fallback_t
            try:
                oe = json.loads(fetch(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"))
                real_t = oe.get("title") or fallback_t
            except Exception:
                pass
            yt_map[vid] = {
                "videoId": vid,
                "title": real_t,
                "series": "שיעורים והתוועדויות ביוטיוב",
                "lang": lang,
                "url": f"https://www.youtube.com/watch?v={vid}",
            }

    results = list(yt_map.values())
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"[YouTube] Harvested {len(results)} YouTube videos!")
    return results

# ==============================================================================
# 8. OTZER HACHASSIDUS (Initial public browseFilter items from Reb Yoel page)
# ==============================================================================
def harvest_otzer():
    cache_file = os.path.join(CACHE_DIR, "otzer.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[Otzer] Loaded {len(data)} cached items")
            return data

    print("[Otzer] Fetching public Reb Yoel Kahn page...")
    html = fetch("https://otzerhachassidus.com/%D7%9E%D7%92%D7%99%D7%93%D7%A9%D7%99%D7%A2%D7%95%D7%A8/%D7%94%D7%A8%D7%91-%D7%99%D7%95%D7%90%D7%9C-%D7%9B%D7%94%D7%9F/")
    m = re.search(r'var\s+browseFilter\s*=\s*(\{.*?\});\s*</script>', html, re.S)
    if not m:
        m = re.search(r'var\s+browseFilter\s*=\s*(\{.*?\});', html, re.S)
    items = []
    if m:
        bf = json.loads(m.group(1))
        data_dict = bf.get("data", {})
        for pid, obj in data_dict.items():
            src = obj.get("src", "")
            if src.startswith("//"):
                src = "https:" + src
            items.append({
                "id": pid,
                "title": html_lib.unescape(obj.get("display_title", "").strip()),
                "src": src,
                "length": obj.get("length", ""),
                "attachment": obj.get("attachment", ""),
                "oz_lang": obj.get("oz_lang", {}),
                "oz_topic": obj.get("oz_topic", {}),
                "oz_subject": obj.get("oz_subject", {}),
                "oz_litwork": obj.get("oz_litwork", {}),
                "courtesy": (obj.get("courtesy") or {}).get("courtesy", ""),
            })
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    print(f"[Otzer] Harvested {len(items)} public items (out of 665 on Otzer HaChassidus)!")
    return items

# ==============================================================================
# 9. USER GOOGLE DRIVE FOLDER ("Reb Yoel Shiurim" - metadata only, ZERO media downloads!)
# ==============================================================================
def harvest_user_gdrive():
    cache_file = os.path.join(CACHE_DIR, "user_gdrive.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[UserGDrive] Loaded {len(data)} cached files")
            return data

    print("[UserGDrive] Crawling folder metadata only (zero file downloads)...")
    root_id = "0B7BtXyKG9O_rQmdKOUd2U0owYk0"
    root_rk = "0-EZQ3wdHgQEgeD14j3cKLUQ"

    def parse_embedded(fid, rkey=""):
        u = f"https://drive.google.com/embeddedfolderview?id={fid}" + (f"&resourcekey={rkey}" if rkey else "") + "#list"
        body = fetch(u, timeout=25)
        entries = []
        parts = body.split('<div class="flip-entry" id="entry-')[1:]
        for p in parts:
            eid = p.split('"', 1)[0]
            href_m = re.search(r'href="([^"]+)"', p)
            href = html_lib.unescape(href_m.group(1)) if href_m else ""
            t_m = re.search(r'<div class="flip-entry-title"[^>]*>(.*?)</div>', p, re.S)
            title = html_lib.unescape(re.sub(r'<[^>]+>', '', t_m.group(1)).strip()) if t_m else ""
            is_folder = 'aria-label="Folder"' in p or '/drive/folders/' in href
            rk_m = re.search(r'resourcekey=([a-zA-Z0-9_-]+)', href)
            entries.append({
                "id": eid,
                "title": title,
                "is_folder": is_folder,
                "href": href,
                "rkey": rk_m.group(1) if rk_m else "",
            })
        return entries

    visited_folders = set()
    files = []
    queue = [(root_id, root_rk, [])]

    with ThreadPoolExecutor(max_workers=10) as ex:
        while queue:
            batch = []
            while queue:
                fid, rk, path = queue.pop(0)
                if fid in visited_folders:
                    continue
                visited_folders.add(fid)
                batch.append((fid, path, ex.submit(parse_embedded, fid, rk)))
            if not batch:
                break
            for fid, path, fut in batch:
                try:
                    entries = fut.result()
                    for e in entries:
                        if e["is_folder"]:
                            if e["id"] not in visited_folders:
                                queue.append((e["id"], e["rkey"], path + [e["title"]]))
                        else:
                            files.append({
                                "id": e["id"],
                                "title": e["title"],
                                "path": path,
                                "href": e["href"],
                                "rkey": e["rkey"],
                            })
                except Exception as err:
                    print(f"  [UserGDrive] Folder err {fid} ({'/'.join(path)}): {err}")

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(files, f, ensure_ascii=False)
    print(f"[UserGDrive] Harvested metadata for {len(files)} files across {len(visited_folders)} folders!")
    return files

if __name__ == "__main__":
    t0 = time.time()
    harvest_heichalapp()
    harvest_podcasts()
    harvest_video_chasidut()
    harvest_merkaz_anash()
    harvest_monsey()
    harvest_melukat()
    harvest_youtube_sinun()
    harvest_otzer()
    harvest_user_gdrive()
    print(f"\nALL DONE in {time.time()-t0:.1f}s!")
