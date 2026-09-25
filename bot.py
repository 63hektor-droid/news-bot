# -*- coding: utf-8 -*-
"""
Iran-news Telegram bot  (runs on GitHub Actions, every ~2 minutes)

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
import threading
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
WEAK_SCORE = int(env("WEAK_SCORE", 12))     # many weak regional terms together also count
MAX_AGE_H = float(env("MAX_AGE_HOURS", 8))       # kept for reference; day-filter below is authoritative
TEHRAN = ZoneInfo("Asia/Tehran")
TIME_BUDGET = int(env("TIME_BUDGET_SEC", 540))      # video (download+whisper+burn) needs far more than 280s
VIDEO_SCAN = int(env("VIDEO_SCAN_TOP", 8))         # how many top-ranked items get checked for a video
ENABLE_VIDEO = env("ENABLE_VIDEO", "1") == "1"
MAX_VIDEOS = int(env("MAX_VIDEOS_PER_RUN", 1))
MAX_VIDEO_SEC = int(env("MAX_VIDEO_SECONDS", 180))
MAX_VIDEO_MB = int(env("MAX_VIDEO_MB", 45))
WHISPER_MODEL = env("WHISPER_MODEL", "base")
DRY_RUN = env("DRY_RUN", "0") == "1"
HISTORY_H = float(env("HISTORY_HOURS", 48))     # a story only counts as "already posted" for this long
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


_ENT = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]{1,8});")


def _unesc(s):
    """Decode HTML entities, even doubly-encoded ones (&amp;quot; -> &quot; -> ").
    Only real 'name;' entities are touched, so URLs like ?a=1&region=2 stay intact."""
    s = s or ""
    for _ in range(3):
        n = _ENT.sub(lambda m: html.unescape(m.group(0)), s)
        if n == s:
            break
        s = n
    return s


def esc(s):
    # decode first so an entity that slipped through a translator is never
    # escaped a second time (that is what printed a literal "&quot;")
    return html.escape(_unesc(s), quote=False)


def esca(s):
    return html.escape(s or "", quote=True)


# =====================================================================
#  Lists -> matchers
# =====================================================================
TERMS = []          # (term, weight, category, compiled regex)
GLOSS = []          # (compiled regex, persian)


def _rx(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])")


WEAKEN = set("""
supreme leader, islamic republic, arak, shiraz, abu musa, chamran, safir, simorgh, phosphorus,
handala, flame malware, khayyam, kowsar, hodhod, nazer, zafar satellite, hengam,
capital market, pension fund, retirement fund, civil servants pension, agricultural bank,
tourism bank, day bank, dey bank, middle east bank, sarmayeh bank, shahr bank, sina bank,
maskan bank, bank maskan, ansar bank, refah bank, social security organization,
securities and exchange organization, mizan, javan, etemad, shargh, kayhan, sazandegi,
general inspectorate, prosecutor general, cyber police, iran press, ham-mihan, hammihan,
esmaili, hejazi, farzin, sanaei, rabiei, hojatoleslam, hojjatoleslam, motahari, hemmati,
mokhber, iravani, abutalebi, akhoundi
""".replace("\n", " ").split(","))
WEAKEN = {t.strip() for t in WEAKEN if t.strip()}


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
    # Generic words that data.py lists as if they were uniquely Iranian (a "pension
    # fund" or the "Agricultural Bank of China" is not Iran news; North Korea also has a
    # "supreme leader"; shiraz is a wine). Downgraded to weak (weight 1) here so that
    # data.py needs no edit: they now only count together with a real Iran term.
    for t in WEAKEN:
        if t in best:
            best[t] = (1, best[t][1])
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


# Feed fixes applied on top of data.SOURCES (so data.py needs no edit):
#   FEED_REPLACE swaps a dead URL list, FEED_EXTRA adds fallback feeds.
GN = "https://news.google.com/rss/search?q=site:%s+%s+when:1d&hl=en-US&gl=US&ceid=US:en"
FEED_REPLACE = {
    "Arab News": [GN % ("arabnews.com", "Iran"), GN % ("arabnews.com", "(Gulf+OR+Hormuz+OR+nuclear)")],
    "The National": ["https://www.thenationalnews.com/arc/outboundfeeds/rss/?outputType=xml",
                     GN % ("thenationalnews.com", "Iran")],
}
FEED_REPLACE["Newsweek"] = [GN % ("newsweek.com", "Iran"),
                            GN % ("newsweek.com", "(Israel+OR+Hormuz+OR+nuclear+OR+Gulf)")]
FEED_EXTRA = {
    "Newsweek": [GN % ("newsweek.com", "Iran")],
}


GNQ = "https://news.google.com/rss/search?q=%s+when:1d&hl=en-US&gl=US&ceid=US:en"
IRAN_TOPICS = "(Iran+OR+Hormuz+OR+nuclear+OR+sanctions+OR+IRGC+OR+Tehran)"
# Extra agencies added on top of data.py (so data.py needs no edit).
# (rank, tier, name, persian name, feed urls). Broken feeds are simply skipped and logged.
EXTRA_SOURCES = [
    (31, "A", "AFP", "خبرگزاری فرانسه (AFP)",
     [GNQ % "AFP+Iran", GNQ % "AFP+(Israel+OR+Hormuz+OR+nuclear+OR+Gulf+OR+sanctions)"]),
    (32, "A", "IAEA", "آژانس بین‌المللی انرژی اتمی (منبع رسمی)",
     ["https://www.iaea.org/feeds/topnews", GN % ("iaea.org", "(Iran+OR+safeguards+OR+enrichment)")]),
    # OFAC retired its own RSS feed in Jan 2025, and it publishes Iran-specific
    # sanctions news rarely (not daily), so a 1-day Google News window
    # (like every other source uses) returns nothing most runs. A 7-day
    # window catches those low-frequency releases; already-posted items are
    # still filtered out by the normal de-dup/state logic, so this is safe.
    (33, "A", "US Treasury (OFAC)", "خزانه‌داری آمریکا (منبع رسمی)",
     ["https://news.google.com/rss/search?q=site:home.treasury.gov+(Iran+OR+sanctions)+when:7d&hl=en-US&gl=US&ceid=US:en",
      "https://news.google.com/rss/search?q=site:ofac.treasury.gov+Iran+when:7d&hl=en-US&gl=US&ceid=US:en"]),
    (34, "B", "Axios", "اکسیوس",
     ["https://api.axios.com/feed/", GN % ("axios.com", IRAN_TOPICS)]),
    (35, "B", "Fox News", "فاکس‌نیوز",
     ["https://moxie.foxnews.com/google-publisher/world.xml", GN % ("foxnews.com", IRAN_TOPICS)]),
    (36, "B", "UN News", "اخبار سازمان ملل",
     ["https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml",
      "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml"]),
    (37, "C", "Al Arabiya English", "العربیه (انگلیسی)",
     [GN % ("english.alarabiya.net", "Iran"), GN % ("english.alarabiya.net", "(Gulf+OR+Hormuz+OR+nuclear+OR+Houthi)")]),
    (38, "C", "Iran International", "ایران اینترنشنال (انگلیسی)",
     [GN % ("iranintl.com", "Iran"), GN % ("iranintl.com", "(IRGC+OR+protest+OR+execution+OR+regime)")]),
]


def load_sources():
    out = []
    for line in data.SOURCES.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rank, tier, name, fa, urls = [p.strip() for p in line.split("|")]
        urls = FEED_REPLACE.get(name) or urls.split()
        urls = urls + [u for u in FEED_EXTRA.get(name, []) if u not in urls]
        out.append(dict(rank=int(rank), tier=tier, name=name, fa=fa, urls=urls))
    have = {o["name"] for o in out}
    for rank, tier, name, fa, urls in EXTRA_SOURCES:
        if name not in have:
            out.append(dict(rank=rank, tier=tier, name=name, fa=fa, urls=list(urls)))
    return out


# =====================================================================
#  Relevance scoring
# =====================================================================
MENA_RX = re.compile(r"\b(lebanon|lebanese|beirut|gaza|israel\w*|syria\w*|iraq\w*|yemen\w*|houthi\w*|"
                     r"hezbollah|hamas|gulf|saudi|qatar\w*|oman|kuwait\w*|bahrain\w*|uae|emirat\w*|"
                     r"middle east|red sea|hormuz|persian)\b")


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
    weak_ok = pts >= WEAK_SCORE and MENA_RX.search(tl + " " + sl) is not None
    ok = ((strong >= 1 or (medium >= 2 and pts >= 6) or weak_ok)
          and pts >= MIN_SCORE)
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
    s = _unesc(s or "")
    s = re.sub(r"</?[A-Za-z][^>]*>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(The post .{0,200} appeared first on .{0,80}\.?)$", "", s).strip()
    # some feeds (WordPress-based excerpts: DW, Euronews, Al-Monitor, etc.) append a
    # "Continue reading" / "Read more" link after the truncated summary; once HTML
    # tags are stripped above, its link text is left dangling as plain text, and the
    # translator turns it into a Persian "ادامه مطلب" that promises content that
    # was never actually included - strip it (and any trailing "[…]" ellipsis marker)
    s = re.sub(
        r"\s*[\[\(]?\s*(?:continue reading|read more|read the full (?:article|story)|"
        r"full story|click here|see more|the post continues|more\s*[»→>]{0,2})"
        r"\s*[\]\)]?\s*[\.…]{0,3}$",
        "", s, flags=re.I,
    ).strip()
    s = re.sub(r"\s*[\[\(]\s*…\s*[\]\)]\s*$|\s*…\s*$", "", s).strip()
    return s


_ABBR = re.compile(
    r"\b(?:U\.S|U\.K|U\.N|E\.U|Mr|Mrs|Ms|Dr|Prof|St|Gen|Sen|Rep|Lt|Col|Sgt|Gov|Pres|Jr|Sr|vs|etc|Inc|Ltd|Co|Corp|Mt|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec|a\.m|p\.m)\.")


def split_sentences(text):
    """Sentence splitter that does not break on U.S. / Mr. / initials."""
    t = _ABBR.sub(lambda m: m.group(0)[:-1] + "\u0001", text or "")
    t = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", "\\1\u0001", t)
    t = re.sub(r'([.!?]+["\u201d\u2019)\]]*)\s+(?=["\u201c\u2018(\[]?[A-Z0-9])', "\\1\u0002", t)
    out = [p.replace("\u0001", ".").strip() for p in t.split("\u0002")]
    return [p for p in out if p]


def trim_complete(s, maxlen=900):
    """Keep WHOLE sentences only. RSS excerpts are often cut mid-sentence
    ("... said that the"); translating such a fragment gives Persian with no
    verb (the verb comes last in Persian), so the unfinished tail is dropped."""
    out = ""
    for x in split_sentences(s):
        cand = (out + " " + x).strip()
        if len(cand) > maxlen:
            break
        out = cand
    if out and not re.search(r'[.!?]["\u201d\u2019)\]]*$', out):
        parts = split_sentences(out)
        out = " ".join(parts[:-1]) if len(parts) > 1 else ""
    return out


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


# Generic text that Google News (and bot-wall / consent / error pages) put in the
# description of a page instead of a real article summary. If one of these slips
# through, the same sentence gets posted under many different news items.
_BOILERPLATE = (
    "comprehensive, up-to-date news coverage",
    "comprehensive up-to-date news coverage",
    "up-to-date news coverage",
    "aggregated from sources all over the world",
    "aggregated from sources around the world",
    "aggregated from sources",
    "from sources all over the world",
    "google news",
    "enable javascript",
    "enable cookies",
    "just a moment...",
    "just a moment",
    "access denied",
    "are you a robot",
    "verify you are human",
    "checking your browser",
    "attention required",
    "subscribe to continue",
    "before you continue",
)


def _is_boilerplate(s):
    s = re.sub(r"[\u2010-\u2015\u00a0]", " ", (s or "").lower())
    s = re.sub(r"\s+", " ", s)
    if any(b in s for b in _BOILERPLATE):
        return True
    return "aggregated" in s and "sources" in s


def _is_google_host(url):
    host = urlsplit(url or "").netloc.lower()
    return (host == "google.com" or host.endswith(".google.com")
            or ".google." in host or host.endswith("googleusercontent.com"))


def _gn_decode(url):
    """Resolve modern Google News article tokens (no HTTP redirect any more)
    to the real publisher URL. Returns "" on failure."""
    import base64, json, requests
    from urllib.parse import quote
    m = re.search(r"/articles/([^/?#]+)", url)
    if not m:
        return ""
    art_id = m.group(1)
    # old-style ids embed the URL directly in the base64 payload
    try:
        raw = base64.urlsafe_b64decode(art_id + "=" * (-len(art_id) % 4)).decode("latin1")
        mm = re.search(r"https?://[^\x00-\x20\"<>]+", raw)
        if mm and "news.google.com" not in mm.group(0):
            return mm.group(0)
    except Exception:                                              # noqa
        pass
    try:
        page = requests.get("https://news.google.com/rss/articles/" + art_id,
                            headers={"User-Agent": UA}, timeout=10).text
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if not (sg and ts):
            return ""
        inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,'
                 'null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]'
                 % (art_id, ts.group(1), sg.group(1)))
        body = "f.req=" + quote(json.dumps([[["Fbv4je", inner]]]))
        r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                          headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                   "User-Agent": UA},
                          data=body, timeout=12)
        parsed = json.loads(r.text.split("\n\n")[1])[:-2]
        out = json.loads(parsed[0][2])[1]
        if out.startswith("http") and "news.google.com" not in out:
            return out
    except Exception as ex:                                        # noqa
        log("gnews decode failed: %s" % str(ex)[:80])
    return ""


def resolve_gnews_link(url):
    """Google News RSS article links are opaque, per-fetch redirect tokens - the
    exact same story can get a different link every time the feed is polled,
    which defeats the URL-based duplicate check in state['urls'] and was
    letting Reuters/AP/France24/Times of Israel items (all routed through
    Google News) get posted again verbatim. Follow the redirect once to the
    real publisher URL, which is stable across fetches - and a better link
    for readers than a news.google.com redirect page."""
    import requests
    try:
        r = requests.head(url, headers={"User-Agent": UA}, timeout=8, allow_redirects=True)
        if r.url and not _is_google_host(r.url):
            return r.url
    except Exception:                                              # noqa
        pass
    try:
        with requests.get(url, headers={"User-Agent": UA}, timeout=10,
                           allow_redirects=True, stream=True) as r:
            if r.url and not _is_google_host(r.url):
                return r.url
    except Exception:                                              # noqa
        pass
    real = _gn_decode(url)
    return real or url


def fetch_feed(src, url):
    import requests
    import feedparser
    header_sets = [
        {"User-Agent": UA, "Accept": "application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8"},
        {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9"},
        {"User-Agent": "Feedly/1.0 (+http://www.feedly.com/fetcher.html; like FeedFetcher-Google)", "Accept": "*/*"},
    ]
    r = None
    for hdr in header_sets:
        r = requests.get(url, headers=hdr, timeout=20)
        if r.status_code not in (403, 406):
            break
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
            if len(title.split()) < 4:          # topic/person hub pages, not real headlines
                continue
        else:
            summ = clean_text(e.get("summary") or e.get("description") or "")
            if summ.lower() == title.lower():
                summ = ""
            if _is_boilerplate(summ):
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
        page_video = (bool(re.search(r"/videos?/|/video-|/watch", link)) and not gnews
                      and not any(h in link for h in ("bloomberg.com", "wsj.com", "ft.com", "nytimes.com",
                                                      "washingtonpost.com", "economist.com")))
        out.append(dict(title=title, summary=trim_complete(summ, 900), link=link, time=t, src=src["name"],
                        src_fa=src["fa"], tier=src["tier"], rank=src["rank"],
                        img=img, video=vid, page_video=page_video))
    return out


def fetch_page_summary(link, title=""):
    """Google-News feeds (Reuters, AP, France 24, Times of Israel, Haaretz) carry a
    headline only, so those posts had no body text. Read the article page and take
    its description (og:description / meta description, else the first real
    paragraphs). Returns whole sentences only, or "" if the site blocks us or the
    page is not the real article (Google page, consent wall, generic boilerplate)."""
    import requests
    from bs4 import BeautifulSoup
    if not link or _is_google_host(link):        # never scrape a Google page as if it were the article
        return ""
    try:
        r = requests.get(link, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
                         timeout=12)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            return ""
        if _is_google_host(r.url or ""):           # redirected to Google's page, not the article
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        cands = []
        for attrs in ({"property": "og:description"}, {"name": "description"},
                      {"name": "twitter:description"}):
            m = soup.find("meta", attrs=attrs)
            if m and m.get("content"):
                cands.append(clean_text(m["content"]))
        paras = [clean_text(x.get_text(" ")) for x in soup.find_all("p")]
        paras = [x for x in paras if not _is_boilerplate(x)]
        body = " ".join(x for x in paras if len(x) > 60)[:1200]
        cands.append(body)
        tl = title.lower().strip()
        best = ""
        for c in cands:
            c = trim_complete(c, 900)
            if _is_boilerplate(c):
                continue
            if len(c) > len(best) and c.lower().strip(" .") != tl and len(c) >= 40:
                best = c
        if best and len(best) < 220:                   # a one-line meta tag: add the lead paragraphs
            lead = " ".join(x for x in paras if len(x) > 60)[:700]
            lead = lead.replace(best[:60], "") if best[:60] in lead else lead
            extra = trim_complete(lead, 450) if len(lead) > 80 else ""
            if extra and extra.lower()[:50] not in best.lower():
                best = trim_complete(best.rstrip() + " " + extra, 650)
        if _is_boilerplate(best):
            return ""
        return best
    except Exception as ex:                                        # noqa
        log("page summary failed (%s): %s" % (link[:60], str(ex)[:80]))
        return ""


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
def common_words(old, min_frac=0.12):
    """Words that show up in a large fraction of *recently posted* titles
    are generic to this feed's beat, not evidence of "same story" - this
    bot only covers Iran/Israel/Gaza-region news, so words like "israel",
    "gaza", "strike", "says" recur in nearly every headline. Matching on
    them was treating unrelated stories that merely share the topic as
    duplicates of each other and of weeks of accumulated history - which
    is how a whole day's worth of genuinely new stories (30 relevant
    items) ended up with 0 surviving de-dup in one run. Strip these out
    before the similarity check; only words specific enough to actually
    identify one story (names, places, unusual nouns) should count."""
    if not old:
        return set()
    freq = Counter()
    for t in old:
        freq.update(t)
    thresh = max(3, int(len(old) * min_frac))
    return {w for w, n in freq.items() if n >= thresh}


def select(items, state):
    seen = set(state["urls"])
    old = recent_titles(state)
    common = common_words([set(t) for t in state["titles"]])
    old = [o - common for o in old]
    now = datetime.now(timezone.utc)
    today_ir = now.astimezone(TEHRAN).date()
    pool = []
    n_seen = n_future = n_notoday = 0
    near_misses = []   # (pts, strong, medium, title) for items that scored but didn't pass
    for it in items:
        age = (now - it["time"]).total_seconds() / 3600.0
        if age < -1:                                   # clock-skew / future timestamp
            n_future += 1
            continue
        if it["time"].astimezone(TEHRAN).date() != today_ir:   # only today's news (Iran time)
            n_notoday += 1
            continue
        a = analyze(it["title"], it["summary"])
        if not a["ok"]:
            if a["pts"] > 0:
                near_misses.append((a["pts"], a["strong"], a["medium"], it["title"]))
            continue
        if not it["summary"] and len(it["title"].split()) < 4:
            continue                       # a bare name/label like "Masoud Pezeshkian" is not a news item
        # only resolve the (few) items that actually made it past scoring - resolving
        # every raw item would mean hundreds of extra requests every run
        if "news.google.com" in it["link"]:
            it["link"] = normalize_link(resolve_gnews_link(it["link"]))
        if it["link"] in seen:
            n_seen += 1
            continue
        fresh = 2 if age < 1 else (1 if age < 3 else 0)
        it.update(a)
        it["age"] = age
        it["total"] = a["pts"] + 2 * TIER_BONUS[it["tier"]] + fresh
        pool.append(it)
    log("select: seen=%d future_ts=%d not_today=%d scored_candidates=%d near_misses=%d"
        % (n_seen, n_future, n_notoday, len(items) - n_future - n_notoday, len(near_misses)))
    near_misses.sort(key=lambda x: -x[0])
    for pts, strong, medium, title in near_misses[:15]:
        log("  near-miss pts=%2d strong=%d med=%d  %s" % (pts, strong, medium, title[:90]))
    pool.sort(key=lambda x: (-x["total"], x["rank"]))
    chosen = []
    n_hist = n_dup = 0
    for it in pool:
        tk = toks(it["title"]) - common
        it["tk"] = tk
        hit = next((o for o in old if similar(tk, o)), None)
        if hit is not None:
            n_hist += 1
            if n_hist <= 5:
                log("  suppressed (shares %s with a recent post): %s"
                    % (sorted(tk & hit)[:6], it["title"][:80]))
            continue
        dup = next((c for c in chosen if similar(tk, c["tk"])), None)
        if dup:
            n_dup += 1
            if it["src_fa"] != dup["src_fa"] and it["src_fa"] not in dup["also"]:
                dup["also"].append(it["src_fa"])
            dup["dups"].append(it["link"])
            continue
        it["also"], it["dups"] = [], []
        chosen.append(it)
    log("de-dup: pool=%d | similar to already-posted=%d | duplicate of another candidate=%d | kept=%d"
        % (len(pool), n_hist, n_dup, len(chosen)))
    return pool, chosen


# =====================================================================
#  Translation (free translator + glossary that protects names)
# =====================================================================
_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


TRANSLATE_EMAIL = env("TRANSLATE_EMAIL", "63hektor@gmail.com")   # raises MyMemory daily quota 5000 -> 50000 chars


# public mirrors are dead / need an API key; set LIBRE_URL (+ keep empty otherwise)
LIBRE_MIRRORS = tuple(u for u in env("LIBRE_URL", "").split() if u)


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


def _looks_translated(out):
    """A cheap accuracy check: catches the case where a backend returns
    ok=True with the source text basically unchanged (rate-limited/broken
    endpoints do this silently rather than raising) - that used to slip
    through as a "successful" translation that was actually still
    English. Short strings (a name, an acronym) can legitimately stay
    mostly Latin, so only flag longer output that's still majority Latin."""
    if not out or not out.strip():
        return False
    if len(out) < 15:
        return True
    fa = len(re.findall(r"[آ-ی]", out))
    lat = len(re.findall(r"[A-Za-z]", out))
    return fa >= lat


_GOOGLE_DEAD_UNTIL = 0.0      # circuit breaker: Google rate-limit (429) -> skip it for a while


_TR_CACHE = {}


def _gt(text):
    """Memoised wrapper: the same chunk is often translated twice (glossary
    retry, same sentence in title and summary) - never spend a rate-limited
    request on it again within one run."""
    hit = _TR_CACHE.get(text)
    if hit is not None:
        return hit
    out = _gt_uncached(text)
    _TR_CACHE[text] = out
    return out


def _gt_uncached(text):
    global _GOOGLE_DEAD_UNTIL
    from deep_translator import MyMemoryTranslator, GoogleTranslator
    import random
    last = None
    # 0) Google - most fluent free option. After ONE 429 it is switched off for
    #    10 minutes so the run never wastes minutes on doomed retries.
    if time.time() >= _GOOGLE_DEAD_UNTIL:
        try:
            time.sleep(0.3 + random.uniform(0, 0.4))
            out = GoogleTranslator(source="auto", target="fa").translate(text)
            if _looks_translated(out):
                return out
            last = RuntimeError("Google returned non-Persian/unchanged text")
            log("Google output failed the Persian-content check, trying next engine")
        except Exception as ex:                                  # noqa
            last = ex
            msg = str(ex).lower()
            if "429" in msg or "too many requests" in msg:
                _GOOGLE_DEAD_UNTIL = time.time() + 600
                log("Google rate-limited -> disabled for 10 min, using MyMemory/Argos")
            else:
                log("Google failed: %s" % str(ex)[:150])
    # 1) LibreTranslate - only if mirrors are configured (public ones are dead/keyed)
    if LIBRE_MIRRORS:
        try:
            out = _libre(text)
            if _looks_translated(out):
                return out
            last = RuntimeError("LibreTranslate returned non-Persian/unchanged text")
        except Exception as ex:                                  # noqa
            last = ex
            log("LibreTranslate failed: %s" % str(ex)[:200])
    # 2) MyMemory - single quick try; refuses inputs over 500 chars.
    if len(text) <= 480:
        try:
            kwargs = dict(source="en-GB", target="fa-IR")
            if TRANSLATE_EMAIL:
                kwargs["email"] = TRANSLATE_EMAIL
            out = MyMemoryTranslator(**kwargs).translate(text)
            if _looks_translated(out):
                return out
            last = RuntimeError("MyMemory returned non-Persian/unchanged text")
        except Exception as ex:                                  # noqa
            last = ex
            log("MyMemory failed: %s" % str(ex)[:150])
    # 3) Argos Translate - offline, never rate-limited: last resort that always works.
    try:
        return _argos(text)
    except Exception as ex:                                      # noqa
        last = ex
    raise last


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fix_fa(s):
    s = _unesc(s)                      # &quot; / &#39; some translators return -> real characters
    s = s.replace("ي", "ی").replace("ك", "ک")
    # Persian punctuation marks instead of the Latin ones free translators
    # often leave behind (real "رعایت نگارش فارسی" issue, not cosmetic)
    s = re.sub(r"(?<=[آ-ی۰-۹])\s*\?", "؟", s)
    s = re.sub(r"(?<=[آ-ی۰-۹])\s*;", "؛", s)
    # a "," only turns into "،" when it's between/after Persian text, not
    # inside a number like 12,000 or a still-Latin abbreviation
    s = re.sub(r"(?<=[آ-ی])\s*,\s*", "، ", s)
    s = re.sub(r"\s+([،؛:!؟.])", r"\1", s)
    # straight double quotes -> paired Persian guillemets, alternating
    # open/close so a translated quote reads as Persian typography instead
    # of the Latin " the translators leave behind
    _q = {"n": 0}

    def _quote(_m):
        _q["n"] += 1
        return "«" if _q["n"] % 2 else "»"
    s = re.sub(r'"', _quote, s)
    # Persian digits, but never inside a URL/link (leave those untouched)
    parts = re.split(r"(https?://\S+)", s)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\d+", lambda m: m.group(0).translate(_FA_DIGITS), parts[i])
    s = "".join(parts)
    # percent sign glued to its number with no space, Persian-style, and
    # written as ٪ rather than the Latin %
    s = re.sub(r"(?<=[۰-۹])\s*%", "٪", s)
    # one space after sentence/clause punctuation when text runs on without one
    s = re.sub(r"([،؛:؟!])(?=[آ-یA-Za-z0-9])", r"\1 ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    # proper Persian half-space (ZWNJ) in common compounds, instead of the
    # full space free translators usually leave (bad Persian typography)
    s = re.sub(r"\b(می|نمی)\s+(?=[آ-ی])", "\\1\u200c", s)
    s = re.sub(r"(?<=[آ-ی])\s+(ها|های)\b", "\u200c\\1", s)
    s = re.sub(r"(?<=[آ-ی])\s+(تر|ترین)\b", "\u200c\\1", s)
    s = re.sub(r"\bبی\s+(?=[آ-ی]{2,})", "بی\u200c", s)
    return s.strip()


def _chunks(text, maxlen=280):
    """Group whole sentences into pieces of at most ~maxlen chars. Translating
    sentence-sized pieces (instead of one long blob) stops the free engines
    from dropping clauses - and with them the verb."""
    out, cur = [], ""
    for s in split_sentences(text):
        if cur and len(cur) + 1 + len(s) > maxlen:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out or [text]


def _too_short(src, out):
    n = len(re.findall(r"[A-Za-z0-9']+", src))
    m = len(out.split())
    return n >= 8 and m < 0.4 * n


def _translate_chunk(text, translator=None):
    translator = translator or _gt
    mapping, protected = {}, text
    for rx, fa in GLOSS:
        def sub(m, fa=fa):
            k = len(mapping)
            tok = "ZQ%dQZ" % k
            mapping[k] = fa
            return tok
        protected = rx.sub(sub, protected)
    res = None
    if mapping:
        out = translator(protected)
        found = set()

        def back(m):
            k = int(m.group(1).translate(_DIG))
            found.add(k)
            return mapping.get(k, "")
        res = re.sub(r"Z\s?Q\s?([0-9\u06f0-\u06f9]+)\s?Q\s?Z", back, out, flags=re.I)
        if len(found) != len(mapping):
            log("glossary tokens lost, retrying without glossary")
            res = None
    if res is None:
        res = translator(text)
    elif _too_short(text, res):
        # the placeholders can make an engine give up on the rest of the
        # sentence; if the result is suspiciously short, compare with a
        # plain translation and keep the fuller one
        log("translation looks truncated, retrying without glossary")
        alt = translator(text)
        if len(alt.split()) > len(res.split()):
            res = alt
    return res


def translate(text, translator=None):
    """English (any language) -> fluent-as-possible Persian, with glossary."""
    text = clean_text(text)
    if not text:
        return ""
    outs = [_translate_chunk(ch, translator) for ch in _chunks(text)]
    return fix_fa(" ".join(o.strip() for o in outs if o and o.strip()))


# Persian renderings of the Google News boilerplate ("پوشش جامع و به‌روز اخبار ... گوگل نیوز").
# Last safety net in case the English check missed it: such a summary is dropped.
_FA_BOILERPLATE = ("گوگل نیوز", "گوگل‌نیوز", "گوگل نیوز", "پوشش جامع و به‌روز", "پوشش جامع و بهروز",
                   "پوشش خبری جامع و به‌روز", "پوشش خبری جامع و بهروز")


def _fa_is_boilerplate(s):
    s = (s or "").replace("\u200c", "‌")
    flat = s.replace("\u200c", "")
    return any(b.replace("\u200c", "") in flat for b in _FA_BOILERPLATE)


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


_CH_TAG = None


def channel_tag():
    """@username of the channel this bot posts to (auto-detected from CHANNEL_ID via getChat),
    so every post carries the channel handle - helps growth when posts get forwarded.
    Disable with ADD_CHANNEL_TAG=0."""
    global _CH_TAG
    if _CH_TAG is not None:
        return _CH_TAG
    tag = ""
    if env("ADD_CHANNEL_TAG", "1") == "1" and CHANNEL_ID and not DRY_RUN:
        if CHANNEL_ID.startswith("@"):
            tag = CHANNEL_ID
        else:
            j = tg("getChat", dict(chat_id=CHANNEL_ID), retries=1)
            u = ((j or {}).get("result") or {}).get("username")
            if u:
                tag = "@" + u
    _CH_TAG = tag
    return tag


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
        ch = channel_tag()
        if ch:
            lines.append(RLM + "📢 " + esc(ch))
        return "\n".join(lines)

    s, t = (sum_fa or "").strip(), title_fa
    if s and s[-1] not in ".!؟?…»\")":
        s += "."
    guard = 0
    while visible_len(assemble(t, s)) > limit and guard < 40:
        guard += 1
        if s:
            # drop whole sentences from the end - never cut in the middle of
            # one (a Persian sentence cut mid-way loses its verb)
            parts = re.split(r"(?<=[.!؟?])\s+", s)
            s = " ".join(parts[:-1]) if len(parts) > 1 else ""
        else:
            t = t[:int(len(t) * 0.85)].rstrip() + "…"
    return assemble(t, s)


def og_image(url):
    if _is_google_host(url):
        return None
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": UA}, timeout=8)
        if r.status_code != 200 or _is_google_host(r.url or ""):
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


_IMG_NOISE = {"w", "h", "width", "height", "quality", "q", "fit", "crop", "auto", "format", "fm", "fmt",
              "dpr", "resize", "size", "ts", "v", "t", "cb", "strip", "ssl", "compress"}
FPCACHE = {}


def norm_img(url):
    """Netloc + path + the query parameters that actually identify the picture
    (size/quality/cache-buster parameters are ignored)."""
    try:
        p = urlsplit(url)
        q = sorted((k, v) for k, v in parse_qsl(p.query) if k.lower() not in _IMG_NOISE)
        return (p.netloc.lower() + p.path + ("?" + urlencode(q) if q else "")).rstrip("/")
    except Exception:                                              # noqa
        return url


def img_fp(url):
    """Content fingerprint of a picture: (sha1 of the bytes, 64-bit dHash).
    The same photo served under different URLs/sizes gets the same/similar
    fingerprint, which the URL comparison alone could never catch."""
    try:
        import requests
        import hashlib
        import io
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12, stream=True)
        try:
            if r.status_code != 200:
                return None
            b = r.raw.read(4000000, decode_content=True)
        finally:
            r.close()
        if not b:
            return None
        sha = hashlib.sha1(b).hexdigest()
        dh = None
        try:
            from PIL import Image, ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            px = list(Image.open(io.BytesIO(b)).convert("L").resize((9, 8)).getdata())
            dh = 0
            for row in range(8):
                for col in range(8):
                    dh = (dh << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
        except Exception:                                          # noqa
            dh = None
        return sha, dh
    except Exception:                                              # noqa
        return None


def img_is_dup(fp, state):
    sha, dh = fp
    for old in state.get("img_fp", []):
        try:
            osha, odh = old
        except Exception:                                          # noqa
            continue
        if osha == sha:
            return True
        if dh is not None and odh is not None and bin(dh ^ odh).count("1") <= 3:
            return True
    return False


# ---- video validation --------------------------------------------------
# Mirrors the image validation above: a video attached to a post must really
# belong to THAT story. Two failure modes were seen: (1) a site-wide "hero"/
# "trending" video widget that's embedded on many unrelated article pages and
# gets picked up as if it were the article's own video, and (2) yt-dlp's
# generic-page fallback grabbing an unrelated player (an ad, a "related
# videos" reel) from a page that has more than one video embedded. Neither
# is caught by URL inspection alone, so - exactly like images - every video
# actually downloaded is content-fingerprinted and checked against every
# video already posted for a *different* story; a repeat is rejected and the
# next candidate is tried instead.
GENERIC_VIDEO_PAT = re.compile(
    r"(sponsor|advert|promo|trailer|stinger|bumper|ident|loop|placeholder|"
    r"generic|default[-_]?video|site[-_]?video|masthead|hero[-_]?video)",
    re.I,
)


def vid_looks_generic(url):
    return bool(url) and bool(GENERIC_VIDEO_PAT.search(url))


def vid_fp(path):
    """Content fingerprint of a video file: sha1 of a chunk of the encoded
    bytes plus a coarse perceptual hash of the first decoded frame. Cheap
    (no full decode) but enough to catch the same physical clip being
    reused - whether served from the same URL again or re-encoded by a
    different article page."""
    try:
        import hashlib
        with open(path, "rb") as f:
            head = f.read(2_000_000)
        if not head:
            return None
        sha = hashlib.sha1(head).hexdigest()
        dh = None
        try:
            frame = os.path.join(os.path.dirname(path), "_fp_frame.jpg")
            r = subprocess.run(
                ["ffmpeg", "-y", "-ss", "0.5", "-i", path, "-frames:v", "1", "-vf", "scale=9:8", frame],
                capture_output=True, timeout=20,
            )
            if r.returncode == 0 and os.path.exists(frame):
                from PIL import Image
                px = list(Image.open(frame).convert("L").getdata())
                if len(px) >= 72:
                    dh = 0
                    for row in range(8):
                        for col in range(8):
                            dh = (dh << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
        except Exception:                                          # noqa
            dh = None
        return sha, dh
    except Exception:                                              # noqa
        return None


def vid_is_dup(fp, state):
    sha, dh = fp
    for old in state.get("vid_fp", []):
        try:
            osha, odh = old
        except Exception:                                          # noqa
            continue
        if osha == sha:
            return True
        if dh is not None and odh is not None and bin(dh ^ odh).count("1") <= 3:
            return True
    return False


def image_candidates(item, state):
    """Yield validated image URLs for this specific item, best first: the
    RSS-supplied image, then the og:image of the item's own article page.
    A candidate is skipped when (a) its URL was used before, (b) it is
    unreachable/too small/a logo, or (c) its CONTENT matches a picture already
    posted for another story (same photo under a different URL)."""
    seen = {norm_img(u) for u in state.get("images", [])}

    def usable(u):
        if not u or norm_img(u) in seen or not img_ok(u):
            return False
        fp = img_fp(u)
        if fp is not None:
            if img_is_dup(fp, state):
                log("skipping image, same picture already used for another story:", u[:90])
                return False
            FPCACHE[u] = fp
        return True

    rss_img = item.get("img")
    if usable(rss_img):
        yield rss_img
    if not _is_google_host(item["link"]):
        scraped = og_image(item["link"])
        if scraped and scraped != rss_img and usable(scraped):
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


def ensure_python_deps():
    """Install yt-dlp / faster-whisper on the fly when the workflow does not
    provide them, so replacing bot.py alone is enough."""
    if not ENABLE_VIDEO:
        return
    for mod, pkg in (("yt_dlp", "yt-dlp"), ("faster_whisper", "faster-whisper")):
        try:
            __import__(mod)
            continue
        except Exception:                                        # noqa
            pass
        log("installing missing python package:", pkg)
        for extra in ([], ["--break-system-packages"]):
            try:
                r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg] + extra,
                                   capture_output=True, text=True, timeout=240)
                if r.returncode == 0:
                    import importlib
                    importlib.invalidate_caches()
                    break
                log("pip install %s failed: %s" % (pkg, r.stderr[-200:]))
            except Exception as ex:                              # noqa
                log("pip install %s error: %s" % (pkg, str(ex)[:150]))
                break


def video_preflight():
    """One log line that tells at a glance why videos are (not) working."""
    ensure_python_deps()

    def has(mod):
        try:
            __import__(mod)
            return True
        except Exception:                                        # noqa
            return False
    log("video: enabled=%s | ffmpeg=%s | ffprobe=%s | yt_dlp=%s | faster_whisper=%s | budget=%ds"
        % (ENABLE_VIDEO, bool(shutil.which("ffmpeg")), bool(shutil.which("ffprobe")),
           has("yt_dlp"), has("faster_whisper"), TIME_BUDGET))
    if ENABLE_VIDEO and not DRY_RUN and not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        log("ffmpeg missing -> installing in the background while feeds are fetched")
        threading.Thread(target=ensure_tools, daemon=True).start()
    if ENABLE_VIDEO and not has("yt_dlp"):
        log("WARNING: yt-dlp is not installed -> article-page videos can never be fetched "
            "(add 'yt-dlp' to the pip install step)")
    if ENABLE_VIDEO and not has("faster_whisper"):
        log("WARNING: faster-whisper is not installed -> videos go out without Persian subtitles")


_TOOLS_LOCK = threading.Lock()
_TOOLS_DONE = False
_TOOLS_FONT = None


def ensure_tools():
    """Memoised + locked wrapper. video_preflight() starts this in a background
    thread at the beginning of the run (ffmpeg/fonts install takes ~30-60 s), so
    it overlaps with feed fetching instead of eating the video time budget."""
    global _TOOLS_DONE, _TOOLS_FONT
    with _TOOLS_LOCK:
        if not _TOOLS_DONE:
            try:
                _TOOLS_FONT = _ensure_tools()
            finally:
                _TOOLS_DONE = True
        return _TOOLS_FONT


def _ensure_tools():
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
                ct = (r.headers.get("Content-Type") or "").lower()
                if ct.startswith("text/") or "html" in ct or "json" in ct:
                    log("not a video file (Content-Type %s): %s" % (ct, url[:90]))
                    return False
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
        log("ERROR: yt-dlp is NOT installed - videos embedded in article pages can never be fetched. "
            "Add 'yt-dlp' to the pip install step of the workflow.")
        return None
    sub = tempfile.mkdtemp(dir=tmp)
    opts = {"outtmpl": os.path.join(sub, "yt.%(ext)s"), "quiet": True, "no_warnings": True, "noplaylist": True,
            "socket_timeout": 20, "retries": 3, "max_filesize": MAX_VIDEO_MB * 1024 * 1024,
            "format": "b[ext=mp4][height<=720]/bv*[height<=720]+ba/b[height<=720]/b",
            "merge_output_format": "mp4",
            "http_headers": {"User-Agent": UA},
            # "<=?" = also accept when the site does not report a duration
            "match_filter": yt_dlp.utils.match_filter_func("duration <=? %d & !is_live" % MAX_VIDEO_SEC)}
    cookies = env("YT_COOKIES", "")            # optional secret: Netscape-format cookies.txt content
    if cookies:
        cpath = os.path.join(tmp, "cookies.txt")
        with open(cpath, "w", encoding="utf-8") as f:
            f.write(cookies)
        opts["cookiefile"] = cpath
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
    except Exception as ex:                                      # noqa
        log("yt-dlp failed for %s: %s" % (url[:80], str(ex)[:300]))
        return None
    files = [os.path.join(sub, f) for f in os.listdir(sub)
             if not f.endswith((".part", ".ytdl", ".json", ".txt"))]
    if not files:
        log("yt-dlp finished but produced no file for", url[:80])
        return None
    return max(files, key=os.path.getsize)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path], 40)
    try:
        j = json.loads(r.stdout or "{}")
    except Exception:                                            # noqa
        j = {}
    w = h = 0
    has_audio = False
    vcodec = ""
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and not w:
            w, h = int(s.get("width", 0) or 0), int(s.get("height", 0) or 0)
            vcodec = s.get("codec_name", "")
        if s.get("codec_type") == "audio":
            has_audio = True
    dur = float(j.get("format", {}).get("duration", 0) or 0)
    return w, h, dur, has_audio, vcodec


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


def find_video_urls(link):
    """Look inside the article page for real video sources. RSS entries almost
    never carry a video enclosure and most video-led articles have no
    '/video/' in the URL; they embed a player. Returns candidate URLs (best
    first) for download()/yt-dlp; [] when the page has no video."""
    try:
        import requests
        r = requests.get(link, headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200:
            return []
        body = r.text[:600000]
    except Exception as ex:                                      # noqa
        log("page fetch for video-detect failed:", str(ex)[:100])
        return []
    found = []

    def add(u):
        u = html.unescape((u or "").strip())
        if u.startswith("//"):
            u = "https:" + u
        if u.startswith("http") and u not in found:
            found.append(u)
    for pat in (r'<meta[^>]+(?:property|name)=["\']og:video(?::secure_url|:url)?["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:video(?::secure_url|:url)?["\']',
                r'<meta[^>]+name=["\']twitter:player:stream["\'][^>]+content=["\']([^"\']+)'):
        for m in re.finditer(pat, body, re.I):
            add(m.group(1))
    for m in re.finditer(r'<(?:video|source)[^>]+src=["\']([^"\']+\.(?:mp4|m4v|mov|webm|m3u8)[^"\']*)', body, re.I):
        add(m.group(1))
    for m in re.finditer(r'youtube(?:-nocookie)?\.com/embed/([\w-]{11})', body, re.I):
        add("https://www.youtube.com/watch?v=" + m.group(1))
    for m in re.finditer(r'player\.vimeo\.com/video/(\d+)', body, re.I):
        add("https://vimeo.com/" + m.group(1))
    low = body.lower()
    if any(sg in low for sg in ("brightcove", "jwplayer", "<video", '"videoobject"')):
        add(link)                    # let yt-dlp's generic extractor try the page itself
    return found[:4]


VIDEO_BLOCKED = ("bloomberg.com", "wsj.com", "ft.com", "nytimes.com", "washingtonpost.com",
                 "economist.com", "news.google.com")


def video_blocked(link):
    return any(h in (link or "") for h in VIDEO_BLOCKED)


def _scan_video(item):
    if video_blocked(item.get("link")):
        return
    urls = find_video_urls(item["link"])
    if urls:
        item["vurls"] = urls
        item["page_video"] = True


def fetch_video_source(item, tmp, state):
    """Try each candidate until one is a real, playable, short-enough video
    that isn't a duplicate of a video already posted for a DIFFERENT story
    (a site-wide promo/hero video reused across many article pages, or the
    same clip yt-dlp's generic extractor grabbed for an earlier item).
    Returns (path, (w, h, dur, has_audio, vcodec), fp) or None."""
    cands = []
    for u in [item.get("video")] + list(item.get("vurls") or []):
        if u and u not in cands and not vid_looks_generic(u):
            cands.append(u)
    if item.get("page_video") and item["link"] not in cands:
        cands.append(item["link"])
    for n, u in enumerate(cands[:4]):
        p = None
        m = re.search(r"\.(mp4|m4v|mov|webm)(?:\?|$)", u, re.I)
        if m or u == item.get("video"):
            ext = m.group(1).lower() if m else "mp4"
            p = os.path.join(tmp, "dl%d.%s" % (n, ext))
            if not download(u, p):
                p = None
        if not p and not m:
            p = ytdlp_download(u, tmp)
        if not p:
            continue
        info = probe(p)
        w, h, dur = info[0], info[1], info[2]
        if not w or not h or dur <= 0:
            log("candidate is not a playable video:", u[:90])
            continue
        if dur > MAX_VIDEO_SEC + 5:
            log("video too long (%ds > %ds): %s" % (dur, MAX_VIDEO_SEC, u[:90]))
            continue
        fp = vid_fp(p)
        if fp is not None and vid_is_dup(fp, state):
            log("skipping video, same clip already used for another story:", u[:90])
            continue
        return p, info, fp
    return None


def _ensure_mp4(tmp, src, vcodec):
    """Telegram plays mp4/h264/aac (<50MB) reliably. Re-encode anything else
    (webm, hevc, av1, ...) or anything too large. None if that is impossible."""
    limit = 49 * 1024 * 1024
    if src.lower().endswith(".mp4") and vcodec == "h264" and os.path.getsize(src) < limit:
        return src
    outp = os.path.join(tmp, "norm.mp4")
    for crf in ("28", "33"):
        r = subprocess.run(["ffmpeg", "-y", "-i", src, "-c:v", "libx264", "-preset", "veryfast", "-crf", crf,
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", outp],
                           capture_output=True, text=True, timeout=max(60, int(left() - 20)))
        if r.returncode == 0 and os.path.exists(outp) and os.path.getsize(outp) < limit:
            return outp
        log("re-encode failed or too big (crf %s): %s" % (crf, r.stderr[-200:]))
    return None


def make_video(item, tmp, state):
    """Returns (path, w, h, dur, subtitled, fp) or None. `fp` is the content
    fingerprint of the source clip - the caller records it in state on a
    successful post so the same clip can't be reused for a later story."""
    # ffmpeg/ffprobe must exist BEFORE anything is probed or merged
    font = ensure_tools()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        log("no ffmpeg/ffprobe available even after install attempt - cannot post this video")
        return None
    got = fetch_video_source(item, tmp, state)
    if not got:
        log("no playable (non-duplicate) video could be fetched for:", item["link"][:90])
        return None
    src, (w, h, dur, has_audio, vcodec), fp = got
    log("video fetched: %dx%d %.0fs codec=%s audio=%s" % (w, h, dur, vcodec, has_audio))

    def plain():
        base = _ensure_mp4(tmp, src, vcodec)
        return (base, w, h, dur, False, fp) if base else None
    if not font:
        log("skipping subtitles for this video: no Persian font available")
        return plain()
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
                # merge short fragments into fuller phrases before translating
                # (isolated fragments translate into choppy, verbless subtitles)
                groups = []
                for start, end, tx in raw:
                    if (groups and len(groups[-1][2]) < 60
                            and start - groups[-1][1] < 1.2):
                        gs, ge, gt = groups[-1]
                        groups[-1] = (gs, end, (gt + " " + tx).strip())
                    else:
                        groups.append((start, end, tx))
                # Translate EVERY phrase. The online engines (Google -> Libre ->
                # MyMemory) can take 30-60s per phrase when rate-limited, and the
                # old "if left() < 60: break" then silently dropped everything
                # after the first few phrases (subtitles only for the first ~20s).
                # Now: a translation deadline, and once we are slow or short on
                # time the rest is translated with the offline Argos model.
                tr_deadline = time.time() + max(60, left() - 170)
                offline = False
                for gs, ge, gt in groups:
                    t0 = time.time()
                    try:
                        if offline or time.time() > tr_deadline:
                            fa = translate(gt, _argos)
                        else:
                            fa = translate(gt)
                    except Exception as ex:                      # noqa
                        log("segment translation failed, trying offline:", str(ex)[:120])
                        try:
                            fa = translate(gt, _argos)
                        except Exception:                        # noqa
                            fa = ""
                    if time.time() - t0 > 20:
                        offline = True       # online engines are throttled: stop wasting time on them
                    if fa:
                        segs.append((gs, max(ge, gs + 1.0), fa))
                log("subtitle segments: %d of %d phrases (offline fallback=%s)" % (len(segs), len(groups), offline))
        except Exception as ex:                                  # noqa
            log("whisper failed:", str(ex)[:200])
            segs = []
    if not segs:
        return plain()
    ass = os.path.join(tmp, "sub.ass")
    build_ass(segs, w, h, font, ass)
    outp = os.path.join(tmp, "out.mp4")
    for crf in ("26", "32"):
        if _burn(tmp, src, crf) and os.path.exists(outp) and os.path.getsize(outp) < 49 * 1024 * 1024:
            return outp, w, h, dur, True, fp
    log("burn-in failed, sending original video")
    return plain()


def _burn(tmp, src, crf):
    name = os.path.relpath(src, tmp)
    try:
        r = subprocess.run(["ffmpeg", "-y", "-i", name, "-vf", "ass=sub.ass", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", crf, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
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
        s.setdefault("images", [])
        s.setdefault("img_fp", [])
        s.setdefault("vid_fp", [])
        s.setdefault("title_seen", {})
        for t in s["titles"]:                     # legacy entries get stamped "now" and expire normally
            s["title_seen"].setdefault(" ".join(t), time.time())
        return s
    except Exception:                                            # noqa
        return {"urls": [], "titles": [], "images": [], "img_fp": [], "vid_fp": [], "title_seen": {}}


def recent_titles(state):
    """Token sets of stories posted within HISTORY_H hours. Without this limit the
    500-title history suppressed every new story on a recurring topic (Hormuz, talks...)
    for days - 21 of 21 relevant items were being dropped as 'already posted'."""
    now = time.time()
    seen = state.get("title_seen", {})
    return [set(t) for t in state["titles"]
            if now - seen.get(" ".join(t), now) < HISTORY_H * 3600]


def save_state(s):
    s["urls"] = s["urls"][-4000:]
    s["titles"] = s["titles"][-500:]
    s["images"] = s.get("images", [])[-500:]
    s["img_fp"] = s.get("img_fp", [])[-500:]
    s["vid_fp"] = s.get("vid_fp", [])[-200:]
    keep = {" ".join(t) for t in s["titles"]}
    s["title_seen"] = {k: v for k, v in s.get("title_seen", {}).items() if k in keep}
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)


def git_pull_quiet():
    try:
        subprocess.run(["git", "pull", "--rebase", "-q"], check=False, timeout=30)
    except Exception as ex:                                        # noqa
        log("git pull before posting failed: %s" % str(ex)[:150])


def refresh_seen(state):
    """Re-read state/posted.json from disk (after a git pull) right before
    posting, and merge it into the in-memory state. Two runs can overlap
    (the schedule fires every few minutes but a run with a video can take
    most of TIME_BUDGET_SEC), and the in-memory state loaded at the start
    of *this* run goes stale the moment another run pushes in the
    meantime - that overlap, not a hole in the similarity/URL de-dup
    logic itself, is what was letting the same story slip through twice."""
    git_pull_quiet()
    fresh = load_state()
    for u in fresh.get("urls", []):
        if u not in state["urls"]:
            state["urls"].append(u)
    for t in fresh.get("titles", []):
        if t not in state["titles"]:
            state["titles"].append(t)
    for k, v in fresh.get("title_seen", {}).items():
        state.setdefault("title_seen", {}).setdefault(k, v)
    for im in fresh.get("images", []):
        if im not in state.get("images", []):
            state.setdefault("images", []).append(im)
    for fp in fresh.get("img_fp", []):
        if fp not in state.setdefault("img_fp", []):
            state["img_fp"].append(fp)
    for fp in fresh.get("vid_fp", []):
        if fp not in state.setdefault("vid_fp", []):
            state["vid_fp"].append(fp)


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
def post_item(item, allow_video, state):
    # Read the article page for a summary only when the link is a REAL publisher
    # URL. If the Google News link could not be resolved, scraping it returns
    # Google's own generic page ("Comprehensive, up-to-date news coverage ...")
    # and that sentence was being posted as the news summary.
    if not item["summary"] and left() > 60 and not _is_google_host(item["link"]):
        item["summary"] = fetch_page_summary(item["link"], item["title"])
        log("page summary: %s" % ("%d chars" % len(item["summary"]) if item["summary"] else "none (site blocked/empty)"))
    if _is_boilerplate(item["summary"]):
        log("dropping boilerplate summary: %s" % item["summary"][:80])
        item["summary"] = ""
    title_fa = translate(item["title"])
    sum_fa = translate(item["summary"]) if item["summary"] else ""
    if sum_fa and _fa_is_boilerplate(sum_fa):
        log("dropping boilerplate Persian summary: %s" % sum_fa[:80])
        sum_fa = ""
    if not title_fa:
        raise RuntimeError("empty translation")

    if DRY_RUN:
        log("---- DRY RUN ----\n" + build_post(item, title_fa, sum_fa, 1000))
        return True

    if allow_video and ENABLE_VIDEO and not (item.get("video") or item.get("page_video")) \
            and not video_blocked(item["link"]):
        urls = find_video_urls(item["link"])
        if urls:
            item["vurls"], item["page_video"] = urls, True
            log("video detected on article page (not in RSS/URL):", item["link"][:90])

    if allow_video and ENABLE_VIDEO and (item.get("video") or item.get("page_video")):
        tmp = tempfile.mkdtemp(prefix="vid")
        try:
            res = make_video(item, tmp, state)
            if res:
                path, w, h, dur, sub, vfp = res
                cap = build_post(item, title_fa, sum_fa, 1000)
                if sub:
                    cap = cap.replace(RLM + "🔗", RLM + "🎬 زیرنویس فارسی خودکار\n" + RLM + "🔗", 1)
                if send_video(path, cap, w, h, dur):
                    if vfp is not None:
                        state.setdefault("vid_fp", []).append(list(vfp))
                    return "video"
                log("sending the video to Telegram failed, falling back to photo/text")
            else:
                log("video pipeline produced nothing, falling back to photo/text")
        except Exception as ex:                                  # noqa
            log("video pipeline failed:", str(ex)[:200])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    for img in image_candidates(item, state):
        if send_photo(img, build_post(item, title_fa, sum_fa, 1000)):
            state.setdefault("images", []).append(norm_img(img))
            if FPCACHE.get(img):
                state.setdefault("img_fp", []).append(list(FPCACHE[img]))
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
    video_preflight()

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
    if ENABLE_VIDEO and MAX_VIDEOS > 0 and chosen:
        scan = [c for c in chosen[:VIDEO_SCAN] if not c.get("video") and not c.get("page_video")
                and not video_blocked(c["link"])]
        if scan:
            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(_scan_video, scan))
        vids = [c for c in chosen[:VIDEO_SCAN] if c.get("video") or c.get("page_video")]
        log("video candidates among the top %d items: %d" % (min(VIDEO_SCAN, len(chosen)), len(vids)))
        # if none of today's posts has a video but a slightly lower-ranked item
        # does, let it take the last slot so videos actually reach the channel
        if vids and not any(v is t for v in vids for t in todo):
            if len(todo) >= MAX_POSTS:
                todo[-1] = vids[0]
            else:
                todo.append(vids[0])
    todo.sort(key=lambda x: 0 if (x.get("video") or x.get("page_video")) else 1)
    if not DRY_RUN:
        refresh_seen(state)          # catch anything a concurrent/overlapping run already posted
    posted, videos = 0, 0
    for i, it in enumerate(todo):
        if left() < 25:
            log("time budget reached")
            break
        if not DRY_RUN and i > 0:
            refresh_seen(state)      # re-check right before each post, not just once at the top
        if it["link"] in state["urls"] or any(similar(it["tk"], o) for o in recent_titles(state)):
            log("skipping, already posted (concurrent run caught it first): %s" % it["title"][:80])
            continue
        try:
            allow_video = ENABLE_VIDEO and videos < MAX_VIDEOS and left() > 150
            if (it.get("video") or it.get("page_video")) and not allow_video:
                log("video item won't get subtitles this run (enabled=%s, videos_used=%d, time_left=%ds)"
                    % (ENABLE_VIDEO, videos, left()))
            res = post_item(it, allow_video, state)
        except Exception:                                        # noqa
            log("post failed:\n" + traceback.format_exc()[-600:])
            res = False
        if res:
            posted += 1
            videos += 1 if res == "video" else 0
            state["urls"] += [it["link"]] + it["dups"]
            state["titles"].append(sorted(it["tk"]))
            state.setdefault("title_seen", {})[" ".join(sorted(it["tk"]))] = time.time()
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
    assert len(srcs) == 30 + len(EXTRA_SOURCES), len(srcs)
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
    # Google News boilerplate must never be accepted as a summary
    for junk in ("Comprehensive, up-to-date news coverage, aggregated from sources all over the world by Google News.",
                 "Comprehensive up-to-date news coverage \u2013 aggregated from sources around the world by Google News",
                 "Google News",
                 "Just a moment...",
                 "Enable JavaScript and cookies to continue"):
        assert _is_boilerplate(junk), junk
    assert not _is_boilerplate("Iran says it is ready to resume talks with Washington if sanctions are lifted.")
    assert _is_google_host("https://news.google.com/rss/articles/abc")
    assert _is_google_host("https://consent.google.com/ml?continue=x")
    assert not _is_google_host("https://www.reuters.com/world/iran/story")
    assert _fa_is_boilerplate("پوشش جامع و به‌روز اخبار، جمع‌آوری‌شده از منابع مختلف توسط گوگل نیوز.")
    assert not _fa_is_boilerplate("ایران آمادگی خود را برای از سرگیری مذاکرات اعلام کرد.")
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
    # entities must never reach the channel, even doubly encoded
    assert "&" not in fix_fa("&quot;test&quot; and &amp;quot;x&amp;quot; &#39;y&#39;")
    assert esc("&amp;quot;a&amp;quot;") == '"a"'
    assert esc("a & b < c") == "a &amp; b &lt; c"
    # summaries are cut on sentence boundaries only
    assert trim_complete("Trump spoke at the U.S. Mission. He then said that the", 900) == "Trump spoke at the U.S. Mission."
    assert trim_complete("He said that the", 900) == ""
    assert build_post(it, "عنوان", "جمله اول است. جمله دوم " + "بلند " * 300 + ".", 400).count("بلند") == 0
    # same photo under a different URL is caught by content
    st = {"img_fp": [["abc", 0b1011]]}
    assert img_is_dup(("abc", None), st) and img_is_dup(("zzz", 0b1010), st) and not img_is_dup(("zzz", (1 << 60) | 5), st)
    # same check, for videos (a shared/reused clip must be caught the same way images are)
    stv = {"vid_fp": [["vabc", 0b1011]]}
    assert vid_is_dup(("vabc", None), stv) and vid_is_dup(("vzzz", 0b1010), stv) and not vid_is_dup(("vzzz", (1 << 60) | 5), stv)
    assert vid_looks_generic("https://cdn.example.com/hero-video.mp4") and not vid_looks_generic("https://cdn.example.com/najaf-flights.mp4")
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
