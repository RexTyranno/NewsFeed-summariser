import dateparser
import re

#get the dates mentioned in the text and the
def get_dates_mentioned(text: str) -> list[str]:
    # Extract potential date strings from text
    pattern = r'\b\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b'
    candidates = re.findall(pattern, text)
    results = []
    for candidate in candidates:
        date = dateparser.parse(candidate)
        if date:
            results.append(date.strftime('%Y-%m-%d'))
    return results

#get the date from the text (eg 7 march 2024 or 7th march 2024 or 7th of march 2024)
def get_date_from_text(text: str) -> str:
    date = dateparser.parse(text)
    return date.strftime('%Y-%m-%d') if date else None

#infer the date from the text eg(3 months ago from 7 march 2024 = 7 december 2023)
def infer_date_from_text(text: str, published_date: str) -> str:
    base_date = dateparser.parse(published_date)
    inferred = dateparser.parse(text, settings={'RELATIVE_BASE': base_date})
    return inferred.strftime('%Y-%m-%d') if inferred else None
    
    