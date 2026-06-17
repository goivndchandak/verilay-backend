"""
Verilay — News Scanner Service
Scans Google News RSS, Reddit, Hacker News, NewsData.io, and GNews.io for mentions.

Engagement enrichment:
  • Reddit returns REAL upvotes + comments per post.
  • Hacker News (Algolia) returns REAL points + comments per story.
  • Google News RSS / NewsData / GNews do not expose engagement → reach left 0.

Each result is a dict:
  {
    "headline": str,
    "source":   str,
    "url":      str,
    "published_at": str,
    "platform": "reddit" | "hackernews" | "google" | "newsdata" | "gnews",
    "reach":    int,          # engagement-derived (real where available, else 0)
    "share_count": int,       # comments where available
    "engagement": dict,       # platform-specific real metrics
  }
"""

import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote


class NewsScanner:
    """Scans multiple sources; Google News, Reddit and Hacker News need no API keys."""

    @staticmethod
    async def scan_google_news(query: str) -> list[dict]:
        """Google News RSS — FREE. No engagement metrics available from RSS."""
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
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
        """Reddit search — FREE. Returns REAL upvotes + comments per post."""
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
                    # Reach = upvotes + weighted comments (a comment ≈ deeper engagement).
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
        """Hacker News via Algolia — FREE. Returns REAL points + comments."""
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
        """NewsData.io API (needs free API key). No engagement metrics."""
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
            return results
        except Exception as e:
            print(f"[NewsScanner] NewsData.io error: {e}")
            return []

    @staticmethod
    async def scan_gnews(query: str, api_key: str) -> list[dict]:
        """GNews.io API (needs free API key). No engagement metrics."""
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
        Scan ALL sources and return combined, deduplicated results.
        Google News + Reddit + Hacker News work without any API keys.
        Each source is independent — one failing never breaks the others.
        """
        all_results = []

        # Free, no keys needed
        all_results.extend(await NewsScanner.scan_google_news(query))
        all_results.extend(await NewsScanner.scan_reddit(query))
        all_results.extend(await NewsScanner.scan_hackernews(query))

        # Keyed sources (optional)
        if newsdata_key:
            all_results.extend(await NewsScanner.scan_newsdata(query, newsdata_key))
        if gnews_key:
            all_results.extend(await NewsScanner.scan_gnews(query, gnews_key))

        # Deduplicate by headline (keep the one with the highest reach)
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
