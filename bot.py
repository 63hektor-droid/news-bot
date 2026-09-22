# -*- coding: utf-8 -*-
"""
Iran-news Telegram bot  (runs on GitHub Actions, every 5 minutes)

Every run:
  1. reads RSS feeds of 20 foreign news agencies (data.SOURCES)
  2. scores every headline with the keyword / official / organization lists
  3. keeps only Iran-relevant items, ranks them (credible agencies first),
     removes duplicates of the same story
  4. translates the top items to Persian (free translator + fixed glossary)
  5. posts them to the Telegram channel: text, or photo, or video with
     Persian burned-in subtitles (Whisper + free translator)

Offline self test:  python bot.py selftest
Dry run (no posting): DRY_RUN=1 python bot.py
"""
import calendar
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import data

START = time.time()


def env(name, default):
    v = os.environ.get(name, "")
    return v.strip() if v.strip() else str(default)


BOT_TOKEN = env("BOT_TOKEN", "")
CHANNEL_ID = env("CHANNEL_ID", "")
MAX_POSTS = int(env("MAX_POSTS_PER_RUN", 3))      # 3 posts per 5 min ~ 864/day max
POST_GAP = int(env("POST_GAP_SEC", 90))           # spacing so posts arrive ~ every 1.5-2 min
MIN_SCORE = int(env("MIN_SCORE", 4))
MAX_AGE_H = float(env("MAX_AGE_HOURS", 8))       # kept for reference; day-filter below is authoritative
TEHRAN = ZoneInfo("Asia/Tehran")
TIME_BUDGET = int(env("TIME_BUDGET_SEC", 280))
ENABLE_VIDEO = env("ENABLE_VIDEO", "1") == "1"
MAX_VIDEOS = int(env("MAX_VIDEOS_PER_RUN", 1))
MAX_VIDEO_SEC = int(env("MAX_VIDEO_SECONDS", 180))
MAX_VIDEO_MB = int(env("MAX_VIDEO_MB", 45))
WHISPER_MODEL = env("WHISPER_MODEL", "base")
DRY_RUN = env("DRY_RUN", "0") == "1"
STATE_PATH = "state/posted.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

TIER_BONUS = {"A": 3, "B": 2, "C": 0}
TIER_FA = {"A": "درجه ۱", "B": "درجه ۲", "C": "درجه ۳"}
CAT_TAGS = {
    "nuclear": "#هسته‌ای", "military": "#نظامی", "sanctions": "#تحریم",
    "oil": "#نفت_و_انرژی", "economy": "#اقتصاد", "region": "#منطقه",
    "diplomacy": "#دیپلماسی", "politics": "#سیاست", "rights": "#حقوق_بشر",
    "tech": "#فناوری", "trade": "#تجارت",
}
RLM = "\u200f"


def log(*a):
    print(*a, flush=True)


def left():
    return TIME_BUDGET - (time.time() - START)


def esc(s):
    return html.escape(s or "", quote=False)


def esca(s):
    return html.escape(s or "", quote=True)


# =====================================================================
#  Lists -> matchers
# =====================================================================
TERMS = []          # (term, weight, category, compiled regex)
GLOSS = []          # (compiled regex, persian)


def _rx(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])")


def build_terms():
    best = {}

    def add(t, w, cat):
        t = t.strip().lower()
        if not t:
            return
        if len(t) <= 4 and w > 1 and cat != "iran":   # short abbreviations are ambiguous
            w = 1
        if t not in best or w > best[t][0]:
            best[t] = (w, cat)

    w, cat = 2, "iran"
    for line in data.KEYWORDS.splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and not line.startswith("##")):
            continue
        if line.startswith("##"):
            p = line[2:].split()
            cat, w = p[0], int(p[1])
            continue
        for t in line.split(","):
            add(t, w, cat)
    for t in data.OFFICIALS.replace("\n", ",").split(","):
        t = t.strip()
        if t.startswith("~"):
            add(t[1:], 1, "politics")
        else:
            add(t, 3, "politics")
    for t in data.ORGANIZATIONS.replace("\n", ",").split(","):
        add(t, 3, "org")
    TERMS[:] = [(t, wc[0], wc[1], _rx(t)) for t, wc in best.items()]

    items = []
    for line in data.GLOSSARY.strip().splitlines():
        if "=>" not in line:
            continue
        en, fa = [x.strip() for x in line.split("=>", 1)]
        items.append((en, fa))
    items.sort(key=lambda x: -len(x[0]))
    GLOSS[:] = [(re.compile(r"(?<![A-Za-z0-9])" + re.escape(en) + r"(?![A-Za-z0-9])", re.I), fa)
                for en, fa in items]


def load_sources():
    out = []
    for line in data.SOURCES.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rank, tier, name, fa, urls = [p.strip() for p in line.split("|")]
        out.append(dict(rank=int(rank), tier=tier, name=name, fa=fa, urls=urls.split()))
    return out


# =====================================================================
#  Relevance scoring
# =====================================================================
def analyze(title, summary):
    tl, sl = title.lower(), (summary or "").lower()
    pts, strong, medium = 0, 0, 0
    cats = Counter()
    for t, w, cat, rx in TERMS:
        in_t = t in tl and rx.search(tl) is not None
        in_s = (not in_t) and t in sl and rx.search(sl) is not None
        if not (in_t or in_s):
            continue
        p = w * (2 if in_t else 1)
        pts += p
        if w >= 3:
            strong += 1
        elif w == 2:
            medium += 1
        if cat not in ("iran", "org"):
            cats[cat] += p
    pts = min(pts, 30)
    ok = (strong >= 1 or (medium >= 2 and pts >= 6)) and pts >= MIN_SCORE
    tags = [CAT_TAGS[c] for c, _ in cats.most_common(3) if c in CAT_TAGS][:2]
    return dict(pts=pts, strong=strong, medium=medium, ok=ok, tags=["#ایران"] + tags)


STOP = set("the and for with from that this after over amid says said will would have has had "
           "into about more than their they them what when where which while new report reports "
           "news live update updates".split())


def toks(title):
    return {w[:6] for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 3 and w not in STOP}


# query/fragment params that don't change what article a link points to, but
# vary between fetches of the same story (analytics, sharing, session ids) -
# left un-stripped, they defeated exact-URL duplicate detection and were a
# real source of the same story getting posted more than once.
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "utm_id", "utm_name", "utm_social", "utm_social-type",
    "ref", "ref_src", "ref_url", "fbclid", "gclid", "msclkid",
    "cmpid", "cmp", "intcid", "ito", "ns_campaign", "ns_mchannel",
    "ns_source", "ns_linkname", "ns_fee", "src", "sref", "traffic_source",
    "CMP", "at_medium", "at_campaign", "xtor", "spref", "__twitter_impression",
}


def normalize_link(url):
    try:
        parts = urlsplit(url.strip())
        q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k not in TRACKING_PARAMS and not k.lower().startswith("utm_")]
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(q), ""))
    except Exception:                                              # noqa
        return url.strip()


def similar(a, b):
    if not a or not b:
        return False
    inter = len(a & b)
    if inter >= 6:                       # lots of shared tokens -> same story, phrasing aside
        return True
    ratio = inter / max(1, min(len(a), len(b)))
    return inter >= 3 and ratio >= 0.5


# =====================================================================
#  Fetching feeds
# =====================================================================
def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(The post .{0,200} appeared first on .{0,80}\.?)$", "", s).strip()
    return s


def entry_media(e):
    img, vid = None, None
    for m in (e.get("media_content") or []):
        u = m.get("url") or ""
        t = (m.get("type") or m.get("medium") or "").lower()
        if not u:
            continue
        if "video" in t or re.search(r"\.(mp4|m4v|mov)(\?|$)", u, re.I):
            vid = vid or u
        elif "image" in t or re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I):
            img = img or u
    for m in (e.get("media_thumbnail") or []):
        img = img or m.get("url")
    for l in (e.get("links") or []):
        if l.get("rel") == "enclosure":
            t = (l.get("type") or "").lower()
            if t.startswith("video"):
                vid = vid or l.get("href")
            elif t.startswith("image"):
                img = img or l.get("href")
    if not img:
        m = re.search(r'<img[^>]+src="([^"]+)"', e.get("summary") or "")
        if m:
            img = m.group(1)
    return img, vid


def fetch_feed(src, url):
    import requests
    import feedparser
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,application/atom+xml,"
                                   "application/xml;q=0.9,*/*;q=0.8"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError("HTTP %d" % r.status_code)
    fp = feedparser.parse(r.content)
    if not fp.entries:
        raise RuntimeError("no entries")
    gnews = "news.google.com" in url
    out = []
    for e in fp.entries[:60]:
        title = clean_text(e.get("title", ""))
        link = normalize_link((e.get("link") or "").strip())
        if not title or not link:
            continue
        if gnews:
            title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title)
            summ = ""
        else:
            summ = clean_text(e.get("summary") or e.get("description") or "")
            if summ.lower() == title.lower():
                summ = ""
        t = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                t = datetime.fromtimestamp(calendar.timegm(e[k]), tz=timezone.utc)
                break
        if t is None:
            # no real publish/update time from the feed - defaulting to
            # "now" here used to make the same-day (Tehran) filter a no-op
            # for these entries, letting undated items through regardless
            # of their actual age. Skip instead: "definitely today" can't
            # be confirmed without a real timestamp.
            continue
        img, vid = entry_media(e)
        page_video = bool(re.search(r"/videos?/|/video-|/watch", link)) and not gnews
        out.append(dict(title=title, summary=summ[:900], link=link, time=t, src=src["name"],
                        src_fa=src["fa"], tier=src["tier"], rank=src["rank"],
                        img=img, video=vid, page_video=page_video))
    return out


def fetch_all(sources):
    jobs = [(s, u) for s in sources for u in s["urls"]]
    items, health = [], []

    def work(job):
        s, u = job
        try:
            got = fetch_feed(s, u)
            return s["name"], u, len(got), None, got
        except Exception as ex:                                  # noqa
            return s["name"], u, 0, str(ex)[:60], []

    with ThreadPoolExecutor(max_workers=8) as ex:
        for name, u, n, err, got in ex.map(work, jobs):
            health.append((name, n, err))
            items.extend(got)
    return items, health


# =====================================================================
#  Selection
# =====================================================================
def select(items, state):
    seen = set(state["urls"])
    old = [set(t) for t in state["titles"]]
    now = datetime.now(timezone.utc)
    today_ir = now.astimezone(TEHRAN).date()
    pool = []
    for it in items:
        if it["link"] in seen:
            continue
        age = (now - it["time"]).total_seconds() / 3600.0
        if age < -1:                                   # clock-skew / future timestamp
            continue
        if it["time"].astimezone(TEHRAN).date() != today_ir:   # only today's news (Iran time)
            continue
        a = analyze(it["title"], it["summary"])
        if not a["ok"]:
            continue
        fresh = 2 if age < 1 else (1 if age < 3 else 0)
        it.update(a)
        it["age"] = age
        it["total"] = a["pts"] + 2 * TIER_BONUS[it["tier"]] + fresh
        pool.append(it)
    pool.sort(key=lambda x: (-x["total"], x["rank"]))
    chosen = []
    for it in pool:
        tk = toks(it["title"])
        it["tk"] = tk
        if any(similar(tk, o) for o in old):
            continue
        dup = next((c for c in chosen if similar(tk, c["tk"])), None)
        if dup:
            if it["src_fa"] != dup["src_fa"] and it["src_fa"] not in dup["also"]:
                dup["also"].append(it["src_fa"])
            dup["dups"].append(it["link"])
            continue
        it["also"], it["dups"] = [], []
        chosen.append(it)
    return pool, chosen


# =====================================================================
#  Translation (free translator + glossary that protects names)
# =====================================================================
_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


TRANSLATE_EMAIL = env("TRANSLATE_EMAIL", "63hektor@gmail.com")   # raises MyMemory daily quota 5000 -> 50000 chars


LIBRE_MIRRORS = (
    "https://libretranslate.de/translate",
    "https://translate.terraprint.co/translate",
    "https://libretranslate.com/translate",
)


def _libre(text):
    import random
    import requests
    last = None
    for base in LIBRE_MIRRORS:
        try:
            r = requests.post(
                base,
                data={"q": text, "source": "en", "target": "fa", "format": "text"},
                timeout=20,
            )
            j = r.json()
            out = j.get("translatedText")
            if out:
                return out
            last = RuntimeError(str(j)[:150])
        except Exception as ex:                                  # noqa
            last = ex
            log("LibreTranslate (%s) failed: %s" % (base, str(ex)[:150]))
        time.sleep(1 + random.uniform(0, 1))
    raise last


_ARGOS_READY = False


def _argos_init():
    """Download + install the en->fa Argos model once (cached for the rest
    of this process). Runs entirely offline once installed - no per-request
    network call, so it can never be rate-limited."""
    global _ARGOS_READY
    if _ARGOS_READY:
        return
    import argostranslate.package
    import argostranslate.translate
    have = {l.code for l in argostranslate.translate.get_installed_languages()}
    if not ({"en", "fa"} <= have):
        argostranslate.package.update_package_index()
        pkgs = argostranslate.package.get_available_packages()
        pkg = next(p for p in pkgs if p.from_code == "en" and p.to_code == "fa")
        argostranslate.package.install_from_path(pkg.download())
    _ARGOS_READY = True


def _argos(text):
    import argostranslate.translate
    _argos_init()
    out = argostranslate.translate.translate(text, "en", "fa")
    if not out or not out.strip():
        raise RuntimeError("argos returned empty output")
    return out


def _gt(text):
    from deep_translator import MyMemoryTranslator, GoogleTranslator
    import random
    last = None
    # 0) Google - free, no key; by far the most fluent Persian output of the
    #    free options, so it's the default choice whenever it's reachable.
    for i in range(2):
        try:
            time.sleep(1.5 + random.uniform(0, 1.5))
            return GoogleTranslator(source="auto", target="fa").translate(text)
        except Exception as ex:                                  # noqa
            last = ex
            log("Google failed (try %d/2): %s" % (i + 1, str(ex)[:150]))
            # 429s from the free endpoint need a longer, exponential backoff,
            # especially on shared CI IPs (GitHub Actions runners) that get
            # rate-limited fast; short sleeps just burn through retries.
            is_429 = "429" in str(ex) or "too many requests" in str(ex).lower()
            base = 15 if is_429 else 5
            time.sleep(base * (2 ** i) + random.uniform(0, 3))
    # 1) MyMemory - second online option, has a raised daily quota via TRANSLATE_EMAIL.
    #    deep_translator's MyMemoryTranslator needs locale-style codes
    #    (e.g. "en-GB", "fa-IR"), not bare "en"/"fa" - that's what was
    #    causing "No support for the provided language" on every attempt.
    for i in range(3):
        try:
            time.sleep(2.5 + random.uniform(0, 1.5))
            kwargs = dict(source="en-GB", target="fa-IR")
            if TRANSLATE_EMAIL:
                kwargs["email"] = TRANSLATE_EMAIL
            return MyMemoryTranslator(**kwargs).translate(text)
        except Exception as ex:                                  # noqa
            last = ex
            log("MyMemory failed (try %d/3): %s" % (i + 1, str(ex)[:150]))
            time.sleep(3 + 3 * i + random.uniform(0, 2))
    # 2) LibreTranslate - different infra than Google/MyMemory, still a
    #    real neural MT engine so noticeably more fluent than the offline
    #    fallback below; tried before Argos for that reason.
    try:
        return _libre(text)
    except Exception as ex:                                      # noqa
        last = ex
        log("LibreTranslate failed too: %s" % str(ex)[:200])
    # 3) Argos Translate - offline, free, no key, no rate limit. Lowest
    #    fluency of the four, so it's the true last resort, used only when
    #    every online option above is unreachable.
    try:
        return _argos(text)
    except Exception as ex:                                      # noqa
        last = ex
    raise last


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fix_fa(s):
    s = s.replace("ي", "ی").replace("ك", "ک")
    # Persian punctuation marks instead of the Latin ones free translators
    # often leave behind (real "رعایت نگارش فارسی" issue, not cosmetic)
    s = re.sub(r"(?<=[آ-ی۰-۹])\s*\?", "؟", s)
    s = re.sub(r"(?<=[آ-ی۰-۹])\s*;", "؛", s)
    # a "," only turns into "،" when it's between/after Persian text, not
    # inside a number like 12,000 or a still-Latin abbreviation
    s = re.sub(r"(?<=[آ-ی])\s*,\s*", "، ", s)
    s = re.sub(r"\s+([،؛:!؟.])", r"\1", s)
    # Persian digits, but never inside a URL/link (leave those untouched)
    parts = re.split(r"(https?://\S+)", s)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\d+", lambda m: m.group(0).translate(_FA_DIGITS), parts[i])
    s = "".join(parts)
    # one space after sentence/clause punctuation when text runs on without one
    s = re.sub(r"([،؛:؟!])(?=[آ-یA-Za-z0-9])", r"\1 ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    # proper Persian half-space (ZWNJ) in common compounds, instead of the
    # full space free translators usually leave (bad Persian typography)
    s = re.sub(r"\b(می|نمی)\s+(?=[آ-ی])", "\\1\u200c", s)
    s = re.sub(r"(?<=[آ-ی])\s+(ها|های)\b", "\u200c\\1", s)
    s = re.sub(r"(?<=[آ-ی])\s+(تر|ترین)\b", "\u200c\\1", s)
    return s.strip()


def translate(text, translator=None):
    """English (any language) -> fluent-as-possible Persian, with glossary."""
    translator = translator or _gt
    text = clean_text(text)
    if not text:
        return ""
    mapping, protected = {}, text
    for rx, fa in GLOSS:
        def sub(m, fa=fa):
            k = len(mapping)
            tok = "ZQ%dQZ" % k
            mapping[k] = fa
            return tok
        protected = rx.sub(sub, protected)
    if mapping:
        out = translator(protected)
        found = set()

        def back(m):
            k = int(m.group(1).translate(_DIG))
            found.add(k)
            return mapping.get(k, "")
        res = re.sub(r"Z\s?Q\s?([0-9۰-۹]+)\s?Q\s?Z", back, out, flags=re.I)
        if len(found) == len(mapping):
            return fix_fa(res)
        log("glossary tokens lost, retrying without glossary")
    return fix_fa(translator(text))


# =====================================================================
#  Telegram
# =====================================================================
def tg(method, payload=None, files=None, retries=3):
    import requests
    url = "https://api.telegram.org/bot%s/%s" % (BOT_TOKEN, method)
    for i in range(retries):
        try:
            r = requests.post(url, data=payload, files=files, timeout=180)
            try:
                j = r.json()
            except Exception:                                    # noqa
                j = {"ok": False, "description": r.text[:200]}
            if j.get("ok"):
                return j
            if r.status_code == 429:
                time.sleep(int(j.get("parameters", {}).get("retry_after", 5)) + 1)
                continue
            log("telegram error:", method, str(j)[:300])
            return None
        except Exception as ex:                                  # noqa
            log("telegram exception:", method, str(ex)[:200])
            time.sleep(3 + 3 * i)
    return None


def visible_len(t):
    return len(html.unescape(re.sub(r"<[^>]+>", "", t)))


def build_post(item, title_fa, sum_fa, limit):
    src = "%s (%s)" % (item["src_fa"], TIER_FA[item["tier"]])
    also = "، ".join(item.get("also", [])[:3])
    tags = " ".join(item["tags"])

    def assemble(title, summ):
        lines = [RLM + "🔺 <b>" + esc(title) + "</b>"]
        if summ:
            lines += [RLM, RLM + esc(summ)]
        lines += [RLM, RLM + "📰 منبع: " + esc(src)]
        if also:
            lines.append(RLM + "🔁 همچنین در: " + esc(also))
        lines.append(RLM + '🔗 <a href="' + esca(item["link"]) + '">مطالعه‌ی خبر اصلی</a>')
        lines.append(RLM + tags)
        return "\n".join(lines)

    s, t = sum_fa, title_fa
    guard = 0
    while visible_len(assemble(t, s)) > limit and guard < 40:
        guard += 1
        if s:
            cut = int(len(s) * 0.8)
            cut_at = max(s.rfind(" ", 0, cut), s.rfind(".", 0, cut), 0)
            s = (s[:cut_at].rstrip(" ،.") + "…") if cut_at > 40 else ""
        else:
            t = t[:int(len(t) * 0.85)].rstrip() + "…"
    return assemble(t, s)


def og_image(url):
    if "news.google.com" in url:
        return None
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": UA}, timeout=8)
        if r.status_code != 200:
            return None
        for pat in (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'):
            m = re.search(pat, r.text[:200000], re.I)
            if m:
                return html.unescape(m.group(1))
    except Exception:                                            # noqa
        pass
    return None


# ---- image validation ------------------------------------------------
# Goal: never attach a picture that isn't really the specific photo for
# that specific story - no generic site logos/icons, no tiny placeholder
# pixels, no broken links. Every candidate image (whether it came from the
# RSS entry or was scraped from the article page) is checked here before
# it's allowed to be posted; a candidate that fails is simply skipped and
# the next one is tried, so a bad match never silently goes out.
GENERIC_IMG_PAT = re.compile(
    r"(logo|sprite|placeholder|default[-_]?image|avatar|favicon|"
    r"blank\.gif|spacer|1x1|pixel\.gif|icon[-_]|masthead|site-image)",
    re.I,
)


def img_looks_generic(url):
    return bool(url) and bool(GENERIC_IMG_PAT.search(url))


def img_ok(url):
    """True only if `url` is reachable, is really an image, and is large
    enough to be an actual news photo rather than an icon/logo."""
    if not url or img_looks_generic(url):
        return False
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": UA}, timeout=8, stream=True)
        try:
            if r.status_code != 200:
                return False
            ctype = (r.headers.get("Content-Type") or "").lower()
            if not ctype.startswith("image/") or "svg" in ctype:
                return False
            clen = int(r.headers.get("Content-Length") or 0)
            if clen and clen < 8000:          # icons/logos are typically tiny
                return False
            chunk = r.raw.read(262144, decode_content=True)
            if len(chunk) < 8000 and not clen:
                return False
            try:
                from PIL import Image
                import io
                w, h = Image.open(io.BytesIO(chunk)).size
                if w < 300 or h < 200:        # too small to be a real article photo
                    return False
            except Exception:                                    # noqa
                pass                          # Pillow unavailable/undecodable header - fall back to size checks above
            return True
        finally:
            r.close()
    except Exception:
        return False


def image_candidates(item):
    """Yield validated image URLs for this specific item, best first: the
    RSS-supplied image (fast, already item-specific) then, if that fails
    validation, the og:image scraped straight from this item's own article
    page (skipped for Google News redirect links, which aren't real
    article pages)."""
    rss_img = item.get("img")
    if rss_img and img_ok(rss_img):
        yield rss_img
    if "news.google.com" not in item["link"]:
        scraped = og_image(item["link"])
        if scraped and scraped != rss_img and img_ok(scraped):
            yield scraped


def send_text(text):
    return tg("sendMessage", dict(chat_id=CHANNEL_ID, text=text, parse_mode="HTML",
                                  disable_web_page_preview="true"))


def send_photo(img_url, caption):
    j = tg("sendPhoto", dict(chat_id=CHANNEL_ID, photo=img_url, caption=caption, parse_mode="HTML"), retries=1)
    if j:
        return j
    try:
        import requests
        r = requests.get(img_url, headers={"User-Agent": UA}, timeout=20)
        if r.status_code == 200 and 1000 < len(r.content) < 9_000_000:
            return tg("sendPhoto", dict(chat_id=CHANNEL_ID, caption=caption, parse_mode="HTML"),
                      files={"photo": ("p.jpg", r.content)}, retries=2)
    except Exception as ex:                                      # noqa
        log("photo download failed:", str(ex)[:100])
    return None


def send_video(path, caption, w, h, dur):
    with open(path, "rb") as f:
        return tg("sendVideo", dict(chat_id=CHANNEL_ID, caption=caption, parse_mode="HTML",
                                    supports_streaming="true", width=w, height=h, duration=int(dur)),
                  files={"video": ("v.mp4", f)}, retries=2)


# =====================================================================
#  Video: download -> Whisper -> Persian subtitles -> burn with ffmpeg
# =====================================================================
def run(cmd, timeout):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ensure_tools():
    """Returns the Persian font family to burn subtitles with, or None if
    ffmpeg or a real Persian font couldn't be made available. Falling back
    to a non-Persian font (e.g. DejaVu Sans) would burn broken/undisplayable
    text into the video, which is worse than no subtitles - so the caller
    must skip burning entirely when this returns None."""
    if not shutil.which("ffmpeg"):
        log("installing ffmpeg ...")
        run(["bash", "-c", "sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg"], 240)
    if not shutil.which("ffmpeg"):
        log("ERROR: ffmpeg still not available after install attempt - cannot burn subtitles")
        return None
    fams = run(["bash", "-c", "fc-list :lang=fa family || true"], 30).stdout
    if "Vazir" not in fams and "Naskh" not in fams:
        log("installing Persian fonts ...")
        run(["bash", "-c", "sudo apt-get install -y -qq fonts-vazirmatn fonts-noto-core "
             "|| sudo apt-get install -y -qq fonts-noto-core"], 240)
        fams = run(["bash", "-c", "fc-list :lang=fa family || true"], 30).stdout
    if "Vazir" in fams:
        return "Vazirmatn"
    if "Naskh" in fams:
        return "Noto Naskh Arabic"
    log("ERROR: no Persian font available after install attempt - cannot burn readable Persian subtitles")
    return None


def download(url, path):
    import requests
    limit = MAX_VIDEO_MB * 1024 * 1024
    for i in range(3):
        try:
            with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=30) as r:
                if r.status_code != 200:
                    raise RuntimeError("HTTP %d" % r.status_code)
                size = 0
                with open(path, "wb") as f:
                    for ch in r.iter_content(1 << 16):
                        size += len(ch)
                        if size > limit:
                            raise RuntimeError("file too big")
                        f.write(ch)
            return True
        except Exception as ex:                                  # noqa
            log("download retry %d: %s" % (i + 1, str(ex)[:80]))
            time.sleep(2 + 2 * i)
    return False


def ytdlp_download(url, tmp):
    try:
        import yt_dlp
    except Exception:                                            # noqa
        return None
    out = os.path.join(tmp, "yt.%(ext)s")
    opts = {"outtmpl": out, "quiet": True, "no_warnings": True, "noplaylist": True,
            "socket_timeout": 20, "retries": 3, "max_filesize": MAX_VIDEO_MB * 1024 * 1024,
            "format": "best[ext=mp4][height<=720]/best[height<=720]/best",
            "match_filter": yt_dlp.utils.match_filter_func("duration <= %d" % MAX_VIDEO_SEC)}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
    except Exception as ex:                                      # noqa
        log("yt-dlp failed:", str(ex)[:120])
        return None
    for f in os.listdir(tmp):
        if f.startswith("yt."):
            return os.path.join(tmp, f)
    return None


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path], 40)
    j = json.loads(r.stdout or "{}")
    w = h = 0
    has_audio = False
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and not w:
            w, h = int(s.get("width", 0)), int(s.get("height", 0))
        if s.get("codec_type") == "audio":
            has_audio = True
    dur = float(j.get("format", {}).get("duration", 0) or 0)
    return w, h, dur, has_audio


def ass_time(t):
    return "%d:%02d:%05.2f" % (int(t // 3600), int(t % 3600 // 60), t % 60)


def wrap_fa(text, width=34):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > width and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    if cur:
        lines.append(cur)
    return "\\N".join(lines)


def build_ass(segs, w, h, font, path):
    fs = max(20, int(h / 20))
    mv = max(20, int(h * 0.07))
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,%s,%d,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,3,1,2,"
        "30,30,%d,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    ) % (w, h, font, fs, mv)
    lines = []
    for start, end, text in segs:
        clean = text.replace("{", "(").replace("}", ")").replace("\n", " ")
        lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" % (ass_time(start), ass_time(end), wrap_fa(clean)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")


def detect_page_video(link):
    """RSS entries rarely carry a video enclosure, and most video-led
    articles (Guardian, DW, ...) don't have '/video/' or '/watch' in their
    URL either - they just embed a YouTube/Vimeo/Brightcove/JW player in
    the page with JS. That combination meant page_video was almost never
    True, so the video pipeline was never even attempted for these. Fetch
    the article page itself and look for real embed signals; yt-dlp's
    generic extractor can pull the video out of the link once we know one
    is actually there. Only called for the few items about to be posted,
    not for every RSS entry, so the extra request is cheap."""
    try:
        import requests
        r = requests.get(link, headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200:
            return False
        body = r.text[:400000].lower()
    except Exception as ex:                                      # noqa
        log("page fetch for video-detect failed:", str(ex)[:100])
        return False
    signals = (
        "og:video", '"videoobject"', "youtube.com/embed", "youtube-nocookie.com/embed",
        "player.vimeo.com", "brightcove", "jwplayer", "<video",
    )
    return any(s in body for s in signals)


def make_video(item, tmp):
    """Returns (path, w, h, dur, subtitled) or None."""
    src = os.path.join(tmp, "in.mp4")
    if item.get("video"):
        if not download(item["video"], src):
            return None
    elif item.get("page_video"):
        p = ytdlp_download(item["link"], tmp)
        if not p:
            return None
        src = p
    else:
        return None
    w, h, dur, has_audio = probe(src)
    if not w or not h or dur <= 0 or dur > MAX_VIDEO_SEC + 5:
        log("video rejected (size/duration):", w, h, dur)
        return None
    font = ensure_tools()
    if not font:
        log("skipping subtitles for this video: no usable ffmpeg/Persian font")
        return src, w, h, dur, False
    segs = []
    if has_audio and left() > 120:
        wav = os.path.join(tmp, "a.wav")
        run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], 90)
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            it, info = model.transcribe(wav, vad_filter=True, beam_size=1)
            log("whisper language:", info.language)
            if info.language != "fa":
                raw = []
                for s in it:
                    tx = s.text.strip()
                    if len(tx) < 2:
                        continue
                    raw.append((s.start, s.end, tx))
                # merge short/fragmented segments into fuller phrases before
                # translating each one - translating single disjointed
                # fragments in isolation (e.g. "and then", "the president")
                # produced choppy, incoherent subtitles; giving the
                # translator a fuller phrase for context makes each line
                # noticeably more fluent. Only merges across small gaps, so
                # it doesn't glue together unrelated sentences after a pause.
                groups = []
                for start, end, tx in raw:
                    if (groups and len(groups[-1][2]) < 40
                            and start - groups[-1][1] < 1.2):
                        gs, ge, gt = groups[-1]
                        groups[-1] = (gs, end, (gt + " " + tx).strip())
                    else:
                        groups.append((start, end, tx))
                for gs, ge, gt in groups:
                    if left() < 60:
                        break
                    fa = translate(gt)
                    if fa:
                        segs.append((gs, max(ge, gs + 1.0), fa))
        except Exception as ex:                                  # noqa
            log("whisper failed:", str(ex)[:200])
            segs = []
    if not segs:
        return src, w, h, dur, False
    ass = os.path.join(tmp, "sub.ass")
    build_ass(segs, w, h, font, ass)
    outp = os.path.join(tmp, "out.mp4")
    for crf in ("26", "32"):
        if _burn(tmp, src, crf) and os.path.exists(outp) and os.path.getsize(outp) < 49 * 1024 * 1024:
            return outp, w, h, dur, True
    log("burn-in failed, sending original video")
    return src, w, h, dur, False


def _burn(tmp, src, crf):
    name = os.path.basename(src)
    try:
        r = subprocess.run(["ffmpeg", "-y", "-i", name, "-vf", "ass=sub.ass", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", crf, "-c:a", "aac", "-b:a", "96k",
                            "-movflags", "+faststart", "out.mp4"],
                           cwd=tmp, capture_output=True, text=True, timeout=max(60, int(left() - 20)))
        if r.returncode != 0:
            log("ffmpeg error:", r.stderr[-300:])
        return r.returncode == 0
    except Exception as ex:                                      # noqa
        log("ffmpeg exception:", str(ex)[:150])
        return False


# =====================================================================
#  State
# =====================================================================
def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            s = json.load(f)
        s.setdefault("urls", [])
        s.setdefault("titles", [])
        return s
    except Exception:                                            # noqa
        return {"urls": [], "titles": []}


def save_state(s):
    s["urls"] = s["urls"][-4000:]
    s["titles"] = s["titles"][-500:]
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)


def git_push_state(state):
    """Commit + push state/posted.json right now, not just at the end of the
    workflow. If the job dies mid-run (15-min timeout, crash, cancelled
    runner) after some posts already went to Telegram, this is what keeps
    those posts recorded - otherwise the next run re-selects and re-posts
    them, which is what was causing the duplicates."""
    save_state(state)
    try:
        subprocess.run(["git", "config", "user.name", "news-bot"], check=False)
        subprocess.run(["git", "config", "user.email", "news-bot@users.noreply.github.com"], check=False)
        subprocess.run(["git", "add", "state"], check=False)
        if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
            return  # nothing changed, nothing to push
        subprocess.run(["git", "commit", "-m", "state [skip ci]"], check=False)
        for i in range(5):
            pulled = subprocess.run(["git", "pull", "--rebase", "-q"]).returncode == 0
            pushed = subprocess.run(["git", "push", "-q"]).returncode == 0
            if pulled and pushed:
                return
            log("state push attempt %d failed, retrying..." % (i + 1))
            time.sleep((i + 1) * 5)
        log("WARNING: failed to push state after retries - post already sent to Telegram, "
            "risk of duplicate on next run")
    except Exception as ex:                                        # noqa
        log("git push error: %s" % str(ex)[:200])


# =====================================================================
#  Posting one item
# =====================================================================
def post_item(item, allow_video):
    title_fa = translate(item["title"])
    sum_fa = translate(item["summary"]) if item["summary"] else ""
    if not title_fa:
        raise RuntimeError("empty translation")

    if DRY_RUN:
        log("---- DRY RUN ----\n" + build_post(item, title_fa, sum_fa, 1000))
        return True

    if allow_video and ENABLE_VIDEO and not (item.get("video") or item.get("page_video")):
        if detect_page_video(item["link"]):
            item["page_video"] = True
            log("video detected on article page (not in RSS/URL):", item["link"][:90])

    if allow_video and ENABLE_VIDEO and (item.get("video") or item.get("page_video")):
        tmp = tempfile.mkdtemp(prefix="vid")
        try:
            res = make_video(item, tmp)
            if res:
                path, w, h, dur, sub = res
                cap = build_post(item, title_fa, sum_fa, 1000)
                if sub:
                    cap = cap.replace(RLM + "🔗", RLM + "🎬 زیرنویس فارسی خودکار\n" + RLM + "🔗", 1)
                if send_video(path, cap, w, h, dur):
                    return "video"
        except Exception as ex:                                  # noqa
            log("video pipeline failed:", str(ex)[:200])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    for img in image_candidates(item):
        if send_photo(img, build_post(item, title_fa, sum_fa, 1000)):
            return "photo"
    if send_text(build_post(item, title_fa, sum_fa, 3900)):
        return "text"
    return False


# =====================================================================
#  Main
# =====================================================================
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    if not DRY_RUN and (not BOT_TOKEN or not CHANNEL_ID):
        log("ERROR: secrets BOT_TOKEN and CHANNEL_ID are not set")
        sys.exit(1)
    build_terms()
    sources = load_sources()
    log("terms: %d | glossary: %d | sources: %d" % (len(TERMS), len(GLOSS), len(sources)))

    state = load_state()
    items, health = fetch_all(sources)
    bad = [h for h in health if h[2]]
    log("feeds ok: %d / %d" % (len(health) - len(bad), len(health)))
    for name, n, err in health:
        log("  %-24s %s" % (name, ("%d items" % n) if not err else "FAILED: " + err))

    pool, chosen = select(items, state)
    log("items: %d | relevant: %d | after de-dup: %d" % (len(items), len(pool), len(chosen)))
    for c in chosen[:10]:
        log("  [%2d] %s (%s) %s" % (c["total"], c["src"], c["tier"], c["title"][:90]))

    # the (slow) video item goes first so its subtitling pipeline always
    # gets the full time budget, instead of whatever's left after the
    # other posts' translation retries/sleeps have eaten into it
    todo = chosen[:MAX_POSTS]
    todo.sort(key=lambda x: 0 if (x.get("video") or x.get("page_video")) else 1)
    posted, videos = 0, 0
    for i, it in enumerate(todo):
        if left() < 25:
            log("time budget reached")
            break
        try:
            allow_video = ENABLE_VIDEO and videos < MAX_VIDEOS and left() > 200
            if (it.get("video") or it.get("page_video")) and not allow_video:
                log("video item won't get subtitles this run (enabled=%s, videos_used=%d, time_left=%ds)"
                    % (ENABLE_VIDEO, videos, left()))
            res = post_item(it, allow_video)
        except Exception:                                        # noqa
            log("post failed:\n" + traceback.format_exc()[-600:])
            res = False
        if res:
            posted += 1
            videos += 1 if res == "video" else 0
            state["urls"] += [it["link"]] + it["dups"]
            state["titles"].append(sorted(it["tk"]))
            if DRY_RUN:
                save_state(state)
            else:
                git_push_state(state)
            log("posted (%s): %s" % (res, it["title"][:80]))
        if i < len(todo) - 1 and POST_GAP > 0 and left() > POST_GAP + 30 and not DRY_RUN:
            time.sleep(POST_GAP)
    save_state(state)
    log("done. posted %d in %ds" % (posted, time.time() - START))


# =====================================================================
#  Offline self test
# =====================================================================
def selftest():
    build_terms()
    srcs = load_sources()
    assert len(srcs) == 20, len(srcs)
    log("terms loaded:", len(TERMS))
    cases = [
        ("Iran says it will resume uranium enrichment at Fordow", "", True),
        ("Oil rises as Strait of Hormuz tensions grow after tanker seizure", "Brent crude up 2%", True),
        ("Pezeshkian meets Araghchi to discuss talks with E3", "", True),
        ("Apple unveils new iPhone with faster chip", "", False),
        ("Russia sanctions widen after Ukraine peace talks fail", "new tariffs and missiles", False),
        ("Kenya police fire tear gas at protesters in Nairobi", "riot police", False),
        ("IAEA says Zaporizhzhia plant lost power again", "", False),
        ("Houthis fire missiles at ship as Hezbollah warns Israel", "", True),
        ("Trump says maximum pressure on Iran will continue", "", True),
        ("Stock markets rally on earnings", "oil price steady", False),
    ]
    bad = 0
    for title, summ, want in cases:
        a = analyze(title, summ)
        flag = "OK " if a["ok"] == want else "BAD"
        bad += a["ok"] != want
        log("%s pts=%2d strong=%d med=%d %s" % (flag, a["pts"], a["strong"], a["medium"], title[:70]))
    # glossary round trip with a fake translator that keeps the tokens
    fake = lambda s: s.replace("was seized", "توقیف شد")                 # noqa
    out = translate("IRGC seized a tanker in the Strait of Hormuz", fake)
    log("glossary:", out)
    assert "سپاه پاسداران" in out and "تنگه هرمز" in out
    # translator that destroys the tokens -> must fall back
    calls = []

    def evil(s):
        calls.append(s)
        return "خروجی " + re.sub(r"ZQ\d+QZ", "", s)
    out = translate("IRGC seized a tanker", evil)
    assert len(calls) == 2, calls
    # de-dup similarity
    assert similar(toks("Iran resumes uranium enrichment at Fordow site"),
                   toks("Iran to resume enrichment at Fordow nuclear site, officials say"))
    assert not similar(toks("Oil prices rise on Hormuz fears"), toks("Apple unveils new iPhone today"))
    # caption trimming
    it = dict(src_fa="رویترز", tier="A", link="https://x.com/a?b=1&c=2", also=["بی‌بی‌سی"], tags=["#ایران", "#نفت_و_انرژی"])
    cap = build_post(it, "عنوان " * 10, "متن طولانی " * 300, 1000)
    assert visible_len(cap) <= 1000, visible_len(cap)
    # ASS build
    d = tempfile.mkdtemp()
    build_ass([(0.0, 2.5, "این یک زیرنویس آزمایشی است که باید در چند خط شکسته شود")], 1280, 720,
              "Vazirmatn", os.path.join(d, "s.ass"))
    assert "Dialogue" in open(os.path.join(d, "s.ass"), encoding="utf-8").read()
    log("selftest finished, failures: %d" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:                                            # noqa
        log("FATAL:\n" + traceback.format_exc())
        sys.exit(1)
