import hashlib

#normalise the url
def normalise_url(url: str) -> str:
    return url.lower().strip()

#check sha unicode for exact duplicate bodies
def content_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

#store tuple to compare 
def dedup_key(normalized_url: str, content_fingerprint: str) -> tuple[str, str]:
    return (normalized_url, content_fingerprint)

# seen set , passed in from the pipeline, shared across all articles in the run
def is_duplicate(url: str, text: str, seen: set) -> bool:
    key = dedup_key(normalise_url(url), content_fingerprint(text))
    if key in seen:
        return True
    seen.add(key)
    return False