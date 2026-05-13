import feedparser
import httpx
import trafilatura
import logging

logging.basicConfig(level=logging.INFO)

#parse rss feed url and get the feed entries
def parse_rss(url: str) -> list[dict]:
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            logging.warning("Feed error for %s: %s", url, feed.bozo_exception)
            return []
        return feed.entries
    except Exception as e:
        logging.warning("Failed to fetch feed %s: %s", url, e)
        return []

#normalise the feed entries
def normalise_feed_entries(entries: list[dict], source_name: str) -> list[dict]:
    normalised = []
    for entry in entries:
        normalised.append({
            "source_name": source_name,
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "published_parsed": entry.get("published_parsed"),
            "summary": entry.get("summary") or None,
            "content": unwrap_content(entry.get("content", [])),
            "author": entry.get("author") or None,
        })
    return normalised

#unwrap the content list to an html string
def unwrap_content(content_list: list[dict]) -> str:
    if content_list:
        return content_list[0].get("value", None)
    return None

#fetch the html string from the url
def fetch_html_string(url: str) -> str:
    response = httpx.get(url)
    return response.text
    
#get best in feed html string 
def get_embedded_html_string(entries: list[dict]) -> str:
    parts = [entry["content"] for entry in entries if entry.get("content")]
    return "\n".join(parts)

# get plain text from the embedded html string
def get_plain_text_from_embedded_html_string(html_string: str) -> str:
    return trafilatura.extract(html_string)

#check if the plain text is long enough
def is_plain_text_long_enough(plain_text: str) -> bool:
    if plain_text is None:
        return False
    return len(plain_text) > 100