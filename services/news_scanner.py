"""
Verilay — News Scanner Service
Scans Google News RSS, Reddit, NewsData.io, and GNews.io for mentions.
Google News + Reddit are FREE (no API key needed).
"""

import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote


class NewsScanner:
    """
    Scans multiple free news sources for mentions.
    Google News RSS and Reddit need NO API keys.
    """

    @staticmethod
    async def scan_google_news(query: str) -> list[dict]:
        """Scan Google News RSS feed — FREE, no API key needed."""
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

                # Filter: only include if query terms appear in title
                if any(word.lower() in title.lower() for word in query.split()):
                    results.append({
                        "headline": title,
                        "source": source,
                        "url": link,
                        "published_at": pub_date,
                    })
            print(f"[NewsScanner] Google News: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Google News error: {e}")
            return []

    @staticmethod
    async def scan_reddit(query: str) -> list[dict]:
        """Scan Reddit search — FREE, no API key needed."""
        url = f"https://www.reddit.com/search.json?q={quote(query)}&sort=new&limit=10"
        headers = {"User-Agent": "Verilay/1.0"}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            results = []
            for post in data.get("data", {}).get("children", []):
                d = post.get("data", {})
                results.append({
                    "headline": d.get("title", ""),
                    "source": f"Reddit r/{d.get('subreddit', 'unknown')}",
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                    "published_at": datetime.fromtimestamp(
                        d.get("created_utc", 0)
                    ).isoformat() if d.get("created_utc") else "",
                })
            print(f"[NewsScanner] Reddit: {len(results)} results for '{query}'")
            return results
        except Exception as e:
            print(f"[NewsScanner] Reddit error: {e}")
            return []

    @staticmethod
    async def scan_newsdata(query: str, api_key: str) -> list[dict]:
        """Scan NewsData.io API (needs free API key)."""
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
                })
            return results
        except Exception as e:
            print(f"[NewsScanner] NewsData.io error: {e}")
            return []

    @staticmethod
    async def scan_gnews(query: str, api_key: str) -> list[dict]:
        """Scan GNews.io API (needs free API key)."""
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
        Google News + Reddit work without any API keys.
        """
        all_results = []

        # Always scan these (free, no keys needed)
        google_results = await NewsScanner.scan_google_news(query)
        reddit_results = await NewsScanner.scan_reddit(query)
        all_results.extend(google_results)
        all_results.extend(reddit_results)

        # Scan these if API keys are available
        if newsdata_key:
            all_results.extend(await NewsScanner.scan_newsdata(query, newsdata_key))
        if gnews_key:
            all_results.extend(await NewsScanner.scan_gnews(query, gnews_key))

        # Deduplicate by headline
        seen = set()
        unique = []
        for item in all_results:
            key = (item.get("headline") or "").lower().strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(item)

        print(f"[NewsScanner] Total: {len(unique)} unique results for '{query}'")
        return unique


# Singleton
news_scanner = NewsScanner()
