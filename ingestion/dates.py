import dateparser

#get the dates mentioned in the text and the
def get_dates_mentioned(text: str) -> list[str]:
    dates = dateparser.parse_dates(text)
    return [date.strftime('%Y-%m-%d') for date in dates]

#get the date from the text (eg 7 march 2024 or 7th march 2024 or 7th of march 2024)
def get_date_from_text(text: str) -> str:
    date = dateparser.parse(text)
    return date.strftime('%Y-%m-%d') if date else None

#infer the date from the text eg(3 months ago from 7 march 2024 = 7 december 2023)
def infer_date_from_text(text: str) -> str:
    #get the date article was published
    published_date = get_date_from_text(text)
    #get the date mentioned in the text
    date_mentioned = get_date_from_text(text)
    
    