import httpx
import trafilatura
import logging

logging.basicConfig(level=logging.INFO)

#run the content ladder
def resolve_full_text(article: dict) -> str:
    #embedded HTML from feed content field
    if article.get("content"):
        text = trafilatura.extract(article["content"])
        if text:
            return text
    #short summary blurb from feed
    summary = article.get("summary")
    if summary and summary.strip():
        text = trafilatura.extract(summary)
        if text:
            return text

    #fetch the article URL and extract
    url = article.get("url")
    if url:
        try:
            response = httpx.get(url, timeout=10, follow_redirects=True)
            response.raise_for_status()
            text = trafilatura.extract(response.text)
            if text:
                return text
        except Exception as e:
            logging.warning("URL fetch failed for %s: %s", url, e)
    return None

#chexk if text passed quality gate
def quality_gate(text: str | None) -> bool:
    if not text or not text.strip():
        return False
    return len(text) > 100