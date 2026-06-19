"""
Verilay — News Scanner Service
Scans many sources for mentions and enriches each with engagement + preview image.

Sources (all concurrent; one failing never breaks the others):
  • GDELT         — free, no key, global near-real-time news (+ social preview image)
  • Bing News     — RSS, server-tolerant with a browser UA
  • Google News   — RSS, often 503 on cloud IPs (bonus)
  • Hacker News   — Algolia, real points + comments
  • Bluesky       — free public search, real likes/reposts/replies
  • Reddit        — OAuth (server-safe) when creds set, else public endpoint (often 403)
  • NewsData / GNews — optional, need free API keys

After collecting, articles WITHOUT an image get an og:image fetched from the page,
so previews show up across Radar / Feed / Truth Log / shared cards.

Each result dict:
  { headline, source, url, published_at, platform, image, reach, share_count, engagement }
"""

import re
import asyncio
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote

from config import get_settings

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_OG_RE_A = re.compile(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)
_OG_RE_B = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']', re.I)


class NewsScanner:
    """Multi-source scanner. GDELT, Bing, Google, Hacker News and Bluesky need no keys."""

    # ── GDELT ──
    @staticmethod
    async def scan_gdelt(query: str) -> list[dict]:
        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {"query": f'"{query}"', "mode": "ArtList", "maxrecords": "30",
                  "format": "json", "sort": "DateDesc"}
        try:
            async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": BROWSER_UA}) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            results = []
            for a in data.get("articles", []):
                title = a.get("title") or ""
                if not title:
                    continue
                results.append({
                    "headline": title, "source": a.get("domain", "News"),
                    "url": a.get("url", ""), "published_at": a.get("seendate", ""),
                    "platform": "gdelt", "image": a.get("socialimage", ""),
                    "reach": 0, "share_count": 0, "engagement": {},
                })
            print(f"[NewsScanner] GDELT: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] GDELT error: {e}")
            return []

    # ── Bing News RSS ──
    @staticmethod
    async def scan_bing_news(query: str) -> list[dict]:
        url = f"https://www.bing.com/news/search?q={quote(query)}&format=rss"
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": BROWSER_UA}) as client:
                response = await client.get(url)
                response.raise_for_status()
            root = ET.fromstring(response.text)
            results = []
            for item in root.findall(".//item")[:15]:
                title = item.findtext("title", "")
                if not title:
                    continue
                results.append({
                    "headline": title, "source": "Bing News",
                    "url": item.findtext("link", ""), "published_at": item.findtext("pubDate", ""),
                    "platform": "bing", "image": "", "reach": 0, "share_count": 0, "engagement": {},
                })
            print(f"[NewsScanner] Bing News: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Bing News error: {e}")
            return []

    # ── Google News RSS ──
    @staticmethod
    async def scan_google_news(query: str) -> list[dict]:
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": BROWSER_UA}) as client:
                response = await client.get(url)
                response.raise_for_status()
            root = ET.fromstring(response.text)
            results = []
            for item in root.findall(".//item")[:15]:
                title = item.findtext("title", "")
                if any(word.lower() in title.lower() for word in query.split()):
                    results.append({
                        "headline": title, "source": item.findtext("source", "Google News") or "Google News",
                        "url": item.findtext("link", ""), "published_at": item.findtext("pubDate", ""),
                        "platform": "google", "image": "", "reach": 0, "share_count": 0, "engagement": {},
                    })
            print(f"[NewsScanner] Google News: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Google News error: {e}")
            return []

    # ── Hacker News (Algolia) ──
    @staticmethod
    async def scan_hackernews(query: str) -> list[dict]:
        url = f"https://hn.algolia.com/api/v1/search?query={quote(query)}&tags=story&hitsPerPage=10"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            results = []
            for hit in data.get("hits", []):
                title = hit.get("title") or hit.get("story_title") or ""
                if not title:
                    continue
                points = int(hit.get("points", 0) or 0)
                comments = int(hit.get("num_comments", 0) or 0)
                oid = hit.get("objectID", "")
                results.append({
                    "headline": title, "source": "Hacker News",
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                    "published_at": hit.get("created_at", ""), "platform": "hackernews",
                    "image": "", "reach": points + comments * 2, "share_count": comments,
                    "engagement": {"points": points, "comments": comments},
                })
            print(f"[NewsScanner] Hacker News: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Hacker News error: {e}")
            return []

    # ── Bluesky (free public search; real likes/reposts/replies) ──
    @staticmethod
    async def scan_bluesky(query: str) -> list[dict]:
        url = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": BROWSER_UA}) as client:
                response = await client.get(url, params={"q": query, "limit": 25})
                response.raise_for_status()
                data = response.json()
            results = []
            for post in data.get("posts", []):
                rec = post.get("record", {})
                text = (rec.get("text") or "").strip()
                if not text:
                    continue
                author = post.get("author", {})
                handle = author.get("handle", "")
                uri = post.get("uri", "")
                rkey = uri.split("/")[-1] if uri else ""
                likes = int(post.get("likeCount", 0) or 0)
                reposts = int(post.get("repostCount", 0) or 0)
                replies = int(post.get("replyCount", 0) or 0)
                results.append({
                    "headline": text[:280],
                    "source": f"Bluesky @{handle}" if handle else "Bluesky",
                    "url": f"https://bsky.app/profile/{handle}/post/{rkey}" if handle and rkey else "",
                    "published_at": rec.get("createdAt", ""), "platform": "bluesky", "image": "",
                    "reach": likes + reposts * 2 + replies, "share_count": reposts,
                    "engagement": {"likes": likes, "reposts": reposts, "replies": replies},
                })
            print(f"[NewsScanner] Bluesky: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Bluesky error: {e}")
            return []

    # ── Reddit (OAuth when creds present — works from servers) ──
    @staticmethod
    async def scan_reddit(query: str, client_id: str = "", client_secret: str = "",
                          user_agent: str = "Verilay/1.0") -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                if client_id and client_secret:
                    tok = await client.post(
                        "https://www.reddit.com/api/v1/access_token",
                        data={"grant_type": "client_credentials"},
                        auth=httpx.BasicAuth(client_id, client_secret),
                        headers={"User-Agent": user_agent},
                    )
                    tok.raise_for_status()
                    token = tok.json().get("access_token", "")
                    response = await client.get(
                        "https://oauth.reddit.com/search",
                        params={"q": query, "sort": "new", "limit": 12},
                        headers={"Authorization": f"bearer {token}", "User-Agent": user_agent},
                    )
                else:
                    response = await client.get(
                        f"https://www.reddit.com/search.json?q={quote(query)}&sort=new&limit=12",
                        headers={"User-Agent": user_agent},
                    )
                response.raise_for_status()
                data = response.json()
            results = []
            for post in data.get("data", {}).get("children", []):
                d = post.get("data", {})
                upvotes = int(d.get("ups", d.get("score", 0)) or 0)
                comments = int(d.get("num_comments", 0) or 0)
                results.append({
                    "headline": d.get("title", ""),
                    "source": f"Reddit r/{d.get('subreddit', 'unknown')}",
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                    "published_at": datetime.fromtimestamp(d.get("created_utc", 0)).isoformat() if d.get("created_utc") else "",
                    "platform": "reddit", "image": "", "reach": upvotes + comments * 2,
                    "share_count": comments, "engagement": {"upvotes": upvotes, "comments": comments},
                })
            mode = "OAuth" if (client_id and client_secret) else "public"
            print(f"[NewsScanner] Reddit ({mode}): {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Reddit error: {e}")
            return []

    # ── Keyed sources ──
    @staticmethod
    async def scan_newsdata(query: str, api_key: str) -> list[dict]:
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get("https://newsdata.io/api/1/news",
                                            params={"apikey": api_key, "q": query, "language": "en"})
                response.raise_for_status()
                data = response.json()
            return [{
                "headline": a.get("title", ""), "source": a.get("source_id", "Unknown"),
                "url": a.get("link", ""), "published_at": a.get("pubDate", ""),
                "platform": "newsdata", "image": a.get("image_url", "") or "",
                "reach": 0, "share_count": 0, "engagement": {},
            } for a in data.get("results", [])]
        except Exception as e:
            print(f"[NewsScanner] NewsData.io error: {e}")
            return []

    @staticmethod
    async def scan_gnews(query: str, api_key: str) -> list[dict]:
        if not api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get("https://gnews.io/api/v4/search",
                                            params={"token": api_key, "q": query, "lang": "en", "max": 10})
                response.raise_for_status()
                data = response.json()
            return [{
                "headline": a.get("title", ""), "source": a.get("source", {}).get("name", "Unknown"),
                "url": a.get("url", ""), "published_at": a.get("publishedAt", ""),
                "platform": "gnews", "image": a.get("image", "") or "",
                "reach": 0, "share_count": 0, "engagement": {},
            } for a in data.get("articles", [])]
        except Exception as e:
            print(f"[NewsScanner] GNews.io error: {e}")
            return []

    # ── og:image enrichment for articles without a picture ──
    @staticmethod
    async def _og_image(client, url: str) -> str:
        if not url:
            return ""
        try:
            r = await client.get(url)
            html = r.text[:200000]
            m = _OG_RE_A.search(html) or _OG_RE_B.search(html)
            return m.group(1).strip() if m else ""
        except Exception:
            return ""

    @staticmethod
    async def enrich_images(results: list[dict], cap: int = 12) -> list[dict]:
        targets = [r for r in results if not r.get("image")][:cap]
        if not targets:
            return results
        try:
            async with httpx.AsyncClient(timeout=5.0, headers={"User-Agent": BROWSER_UA},
                                         follow_redirects=True) as client:
                imgs = await asyncio.gather(
                    *[NewsScanner._og_image(client, r.get("url", "")) for r in targets],
                    return_exceptions=True,
                )
            for r, img in zip(targets, imgs):
                if isinstance(img, str) and img:
                    r["image"] = img
        except Exception as e:
            print(f"[NewsScanner] image enrich error: {e}")
        return results

    @staticmethod
    async def scan_all(query: str, newsdata_key: str = "", gnews_key: str = "") -> list[dict]:
        """Scan ALL sources concurrently, dedupe, then enrich with preview images."""
        s = get_settings()
        tasks = [
            NewsScanner.scan_gdelt(query),
            NewsScanner.scan_bing_news(query),
            NewsScanner.scan_google_news(query),
            NewsScanner.scan_hackernews(query),
            NewsScanner.scan_bluesky(query),
            NewsScanner.scan_reddit(query, s.REDDIT_CLIENT_ID, s.REDDIT_CLIENT_SECRET, s.REDDIT_USER_AGENT),
        ]
        if newsdata_key:
            tasks.append(NewsScanner.scan_newsdata(query, newsdata_key))
        if gnews_key:
            tasks.append(NewsScanner.scan_gnews(query, gnews_key))

        settled = await asyncio.gather(*tasks, return_exceptions=True)
        all_results = []
        for r in settled:
            if isinstance(r, list):
                all_results.extend(r)

        # Dedupe by headline, keep the highest-reach copy.
        best: dict[str, dict] = {}
        for item in all_results:
            key = (item.get("headline") or "").lower().strip()
            if not key:
                continue
            if key not in best or item.get("reach", 0) > best[key].get("reach", 0):
                best[key] = item
        unique = list(best.values())

        unique = await NewsScanner.enrich_images(unique)
        print(f"[NewsScanner] Total: {len(unique)} unique results for '{query}'")
        return unique


news_scanner = NewsScanner()
