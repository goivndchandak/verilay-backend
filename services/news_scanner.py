"""
Verilay — News Scanner Service
Scans many sources for mentions and enriches each with engagement where available.

Why several sources: Google News RSS and Reddit block datacenter/cloud IPs
(503/403 from Render), so we lean on server-friendly sources too:
  • GDELT      — free, no key, near-real-time GLOBAL news index (best coverage)
  • Bing News  — RSS, server-tolerant with a browser User-Agent
  • Hacker News (Algolia) — real points + comments
  • Reddit     — real upvotes + comments (often blocked on cloud IPs)
  • Google News RSS — often 503 on cloud IPs; kept as a bonus
  • NewsData.io / GNews.io — optional, need free API keys

All sources run concurrently; one failing never breaks the others.

Each result dict:
  { headline, source, url, published_at, platform, reach, share_count, engagement }
"""

import asyncio
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote

# A realistic desktop browser UA helps with Google/Bing bot filtering.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class NewsScanner:
    """Multi-source scanner. GDELT, Bing, Google News and Hacker News need no keys."""

    # ── GDELT: free, no key, global, near-real-time (primary coverage) ──
    @staticmethod
    async def scan_gdelt(query: str) -> list[dict]:
        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": f'"{query}"',
            "mode": "ArtList",
            "maxrecords": "30",
            "format": "json",
            "sort": "DateDesc",
        }
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
                    "headline": title,
                    "source": a.get("domain", "News"),
                    "url": a.get("url", ""),
                    "published_at": a.get("seendate", ""),
                    "platform": "gdelt",
                    "image": a.get("socialimage", ""),
                    "reach": 0,
                    "share_count": 0,
                    "engagement": {},
                })
            print(f"[NewsScanner] GDELT: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] GDELT error: {e}")
            return []

    # ── Bing News RSS: server-tolerant with a browser UA ──
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
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                if not title:
                    continue
                results.append({
                    "headline": title,
                    "source": "Bing News",
                    "url": link,
                    "published_at": pub_date,
                    "platform": "bing",
                    "reach": 0,
                    "share_count": 0,
                    "engagement": {},
                })
            print(f"[NewsScanner] Bing News: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Bing News error: {e}")
            return []

    @staticmethod
    async def scan_google_news(query: str) -> list[dict]:
        """Google News RSS — often 503 on cloud IPs; UA gives it a better chance."""
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": BROWSER_UA}) as client:
                response = await client.get(url)
                response.raise_for_status()

            root = ET.fromstring(response.text)
            results = []
            for item in root.findall(".//item")[:15]:
                title = item.findtext("title", "")
                source = item.findtext("source", "Google News")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                if any(word.lower() in title.lower() for word in query.split()):
                    results.append({
                        "headline": title,
                        "source": source or "Google News",
                        "url": link,
                        "published_at": pub_date,
                        "platform": "google",
                        "reach": 0,
                        "share_count": 0,
                        "engagement": {},
                    })
            print(f"[NewsScanner] Google News: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Google News error: {e}")
            return []

    @staticmethod
    async def scan_reddit(query: str) -> list[dict]:
        """Reddit — REAL upvotes + comments. Often 403 on cloud IPs (needs OAuth to fix)."""
        url = f"https://www.reddit.com/search.json?q={quote(query)}&sort=new&limit=12"
        headers = {"User-Agent": "Verilay/1.0 (reputation monitor)"}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(url, headers=headers)
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
                    "published_at": datetime.fromtimestamp(
                        d.get("created_utc", 0)
                    ).isoformat() if d.get("created_utc") else "",
                    "platform": "reddit",
                    "reach": upvotes + comments * 2,
                    "share_count": comments,
                    "engagement": {"upvotes": upvotes, "comments": comments},
                })
            print(f"[NewsScanner] Reddit: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Reddit error: {e}")
            return []

    @staticmethod
    async def scan_hackernews(query: str) -> list[dict]:
        """Hacker News via Algolia — REAL points + comments."""
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
                object_id = hit.get("objectID", "")
                results.append({
                    "headline": title,
                    "source": "Hacker News",
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                    "published_at": hit.get("created_at", ""),
                    "platform": "hackernews",
                    "reach": points + comments * 2,
                    "share_count": comments,
                    "engagement": {"points": points, "comments": comments},
                })
            print(f"[NewsScanner] Hacker News: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Hacker News error: {e}")
            return []

    @staticmethod
    async def scan_newsdata(query: str, api_key: str) -> list[dict]:
        if not api_key:
            return []
        url = "https://newsdata.io/api/1/news"
        params = {"apikey": api_key, "q": query, "language": "en"}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for article in data.get("results", []):
                results.append({
                    "headline": article.get("title", ""),
                    "source": article.get("source_id", "Unknown"),
                    "url": article.get("link", ""),
                    "published_at": article.get("pubDate", ""),
                    "platform": "newsdata",
                    "reach": 0,
                    "share_count": 0,
                    "engagement": {},
                })
            print(f"[NewsScanner] NewsData.io: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] NewsData.io error: {e}")
            return []

    @staticmethod
    async def scan_gnews(query: str, api_key: str) -> list[dict]:
        if not api_key:
            return []
        url = "https://gnews.io/api/v4/search"
        params = {"token": api_key, "q": query, "lang": "en", "max": 10}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for article in data.get("articles", []):
                results.append({
                    "headline": article.get("title", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "url": article.get("url", ""),
                    "published_at": article.get("publishedAt", ""),
                    "platform": "gnews",
                    "reach": 0,
                    "share_count": 0,
                    "engagement": {},
                })
            print(f"[NewsScanner] GNews.io: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] GNews.io error: {e}")
            return []

    @staticmethod
    async def scan_all(
        query: str,
        newsdata_key: str = "",
        gnews_key: str = "",
    ) -> list[dict]:
        """
        Scan ALL sources CONCURRENTLY and return combined, deduplicated results.
        GDELT + Bing + Google News + Hacker News + Reddit need no keys.
        """
        tasks = [
            NewsScanner.scan_gdelt(query),
            NewsScanner.scan_bing_news(query),
            NewsScanner.scan_google_news(query),
            NewsScanner.scan_hackernews(query),
            NewsScanner.scan_reddit(query),
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

        # Deduplicate by headline (keep the one with the highest reach).
        best: dict[str, dict] = {}
        for item in all_results:
            key = (item.get("headline") or "").lower().strip()
            if not key:
                continue
            if key not in best or item.get("reach", 0) > best[key].get("reach", 0):
                best[key] = item

        unique = list(best.values())
        print(f"[NewsScanner] Total: {len(unique)} unique results for '{query}'")
        return unique


# Singleton
news_scanner = NewsScanner()
