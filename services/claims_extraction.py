from __future__ import annotations

import json
import re
from datetime import datetime
from uuid import UUID
import httpx
import spacy
import logging

from db.claims import insert_claim, insert_entities
from db.connection import get_conn

logger = logging.getLogger(__name__)

#constants
MAX_OLLAMA_CALLS = 20        # max LLM calls per article
MAX_SPAN_CHARS = 300         # only send short sentences to Ollama
BODY_CHAR_LIMIT = 50_000     # cap to avoid spaCy OOM on very long docs

#spaCy model — module-level singleton

_nlp: spacy.Language | None = None


def _get_nlp() -> spacy.Language:
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# Named Entity Recognition
def extract_entities(doc: spacy.tokens.Doc, article_id: UUID) -> list[dict]:
    """Deduplicated named entities with character offsets."""
    seen: set[tuple[str, str]] = set()
    entities: list[dict] = []
    for ent in doc.ents:
        key = (ent.text.lower(), ent.label_)
        if key in seen:
            continue
        seen.add(key)
        entities.append({
            "article_id": article_id,
            "text": ent.text,
            "label": ent.label_,
            "offset_start": ent.start_char,
            "offset_end": ent.end_char,
        })
    return entities


# Numeric claim regex
# Regex to extract numeric claims from a sentence
_NUMERIC_RE = re.compile(
    r"(\d{1,3}(?:[,\d]{3})*(?:\.\d+)?)\s*"
    r"(%|percent|percentage points?|"
    r"million|billion|trillion|thousand|"
    r"pp|bps|basis points?)?",
    re.IGNORECASE,
)

# High value units
_HIGH_VALUE_UNITS = {"%", "percent", "pp", "bps", "basis points", "basis point",
                     "percentage points", "percentage point"}

def extract_numeric_claims(
    sent_text: str,
    article_id: UUID,
    time_phrases: list[str],
    subject_text: str | None = None,
) -> list[dict]:
    """
    Detect numeric claims (%, large magnitudes) in a sentence.
    The full sentence is stored as `object` for provenance.
    """
    claims: list[dict] = []
    for m in _NUMERIC_RE.finditer(sent_text):
        raw_val = m.group(1)
        unit = (m.group(2) or "").strip()
        try:
            norm = float(raw_val.replace(",", ""))
        except ValueError:
            continue
        is_notable = unit.lower() in {
            "%", "percent", "percentage points", "percentage point",
            "pp", "bps", "basis points", "basis point",
        } or norm >= 1_000
        if not is_notable:
            continue
        claims.append({
            "article_id": article_id,
            "predicate": "states",
            "object": sent_text.strip(),
            "subject_text": subject_text,
            "is_numeric": True,
            "raw_value": f"{raw_val} {unit}".strip(),
            "normalized_value": norm,
            "unit": unit or None,
            "time_phrase": time_phrases,
            "extraction_method": "regex_numeric",
            "confidence": 0.85 if unit.lower() in _HIGH_VALUE_UNITS else 0.65,
        })
    return claims


# spaCy dependency-parse triplets (subject, predicate, object)
def _dep_triplets(sent: spacy.tokens.Span) -> list[tuple[str, str, str]]:
    """
    Extract (subject_span, verb_lemma, object_span) from a sentence.
    Uses multi-token spans (not just head tokens) for readable output.
    Returns empty list when no clean SVO is found.
    """
    triplets: list[tuple[str, str, str]] = []
    for token in sent:
        if token.pos_ not in ("VERB", "AUX") or token.dep_ not in ("ROOT", "relcl", "advcl"):
            continue
        subj = next(
            (c for c in token.children if c.dep_ in ("nsubj", "nsubjpass")),
            None,
        )
        obj = next(
            (c for c in token.children
             if c.dep_ in ("dobj", "attr", "pobj", "oprd", "ccomp", "xcomp")),
            None,
        )
        if subj is None or obj is None:
            continue
        # Use subtree spans for richer text (e.g. "the central bank" not just "bank")
        subj_text = " ".join(t.text for t in subj.subtree
                             if not t.is_punct).strip()[:120]
        _EXCLUDE_DEPS = {"advcl", "relcl", "ccomp", "xcomp"}
        obj_text = " ".join(
            t.text for t in obj.subtree
            if not t.is_punct and t.dep_ not in _EXCLUDE_DEPS
        ).strip()[:200]
        triplets.append((subj_text, token.lemma_, obj_text))
    return triplets


# Ollama fallback for claims extraction
_OLLAMA_PROMPT = (
    "Extract ONE factual claim from this news sentence.\n"
    "Return ONLY valid JSON in this exact shape:\n"
    '{"subject": "...", "predicate": "...", "object": "..."}\n'
    "If no factual claim is present, return null.\n\n"
    "Sentence: {sentence}"
)

async def _ollama_extract(sentence: str, ollama_url: str, model: str) -> dict | None:
    """
    Ask Ollama for a structured (subject, predicate, object) claim.
    Returns None on any failure — callers must be resilient.
    """
    prompt = _OLLAMA_PROMPT.format(sentence=sentence)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
            # Strip markdown code fences Ollama sometimes adds
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)
            if not data or not isinstance(data, dict):
                return None
            required = {"subject", "predicate", "object"}
            if not required.issubset(data.keys()):
                return None
            if not all(str(data[k]).strip() for k in required):
                return None
            return {
                "predicate": str(data["predicate"])[:200],
                "object":    str(data["object"])[:500],
                "subject_text": str(data["subject"])[:200] or None,
                "extraction_method": "ollama_json",
                "confidence": 0.60,
            }
    except Exception:
        return None

def _merge_sentence_claims(claims: list[dict]) -> list[dict]:
    numeric = next((c for c in claims if c.get("is_numeric")), None)
    dep = next((c for c in claims if c.get("extraction_method") == "spacy_dep"), None)
    if numeric and dep:
        numeric["subject_text"] = dep.get("subject_text")
        return [numeric]
    return [numeric or dep] if (numeric or dep) else claims

# Public API for claims extraction
async def extract_claims_for_article(
    article_id: UUID,
    body: str,
    published_at: datetime | None = None,
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "llama3",
    use_ollama_fallback: bool = True,
) -> dict:
    """
    Run the full extraction pipeline for one article.

    Returns {"entities": [...], "claims": [...]} without writing to DB.
    Call `persist_claims()` to commit the result.

    `use_ollama_fallback=False` is useful during batch reprocessing or testing
    when you want deterministic, fast output.
    """
    nlp = _get_nlp()
    doc = nlp(body[:BODY_CHAR_LIMIT])

    entities = extract_entities(doc, article_id)
    entity_texts = {e["text"].lower() for e in entities}

    all_claims: list[dict] = []
    ollama_candidates: list[str] = []

    for sent in doc.sents:
        sent_text = sent.text.strip()
        if len(sent_text) < 25:
            continue
        sentence_claims: list[dict] = []

        time_phrases = [ent.text for ent in sent.ents if ent.label_ == "DATE"]

        # numeric regex (always)
        sentence_claims.extend(
            extract_numeric_claims(sent_text, article_id, time_phrases)
        )
        # dep-parse triplets
        triplets = _dep_triplets(sent)
        if triplets:
            for subj, pred, obj in triplets:
                sentence_claims.append({
                    "article_id": article_id,
                    "subject_text": subj,
                    "predicate": pred,
                    "object": obj,
                    "is_numeric": False,
                    "time_phrase": time_phrases,
                    "extraction_method": "spacy_dep",
                    "confidence": 0.55,
                })
        else:
            # queue for Ollama if sentence mentions a known entity
            sent_lower = sent_text.lower()
            has_entity = any(et in sent_lower for et in entity_texts)
            if (
                has_entity
                and use_ollama_fallback
                and len(sent_text) <= MAX_SPAN_CHARS
            ):
                ollama_candidates.append(sent_text)
        all_claims.extend(_merge_sentence_claims(sentence_claims))

    # Ollama, capped
    if len(ollama_candidates) > MAX_OLLAMA_CALLS:
        logger.warning(
        "article %s: %d Ollama candidates truncated to %d",
        article_id, len(ollama_candidates), MAX_OLLAMA_CALLS,
    )
    for sent_text in ollama_candidates[:MAX_OLLAMA_CALLS]:
        result = await _ollama_extract(sent_text, ollama_url, ollama_model)
        if result:
            all_claims.append({
                "article_id": article_id,
                "predicate": result["predicate"],
                "object": result["object"],
                "subject_text": result.get("subject_text"),
                "is_numeric": False,
                "extraction_method": result["extraction_method"],
                "confidence": result["confidence"],
            })

    return {"entities": entities, "claims": all_claims}


async def persist_claims(article_id: UUID, extraction_result: dict) -> None:
    """
    Write entities and claims from `extract_claims_for_article` to Postgres.
    Must be called after extraction so entity IDs exist for FK linking.
    """
    async with get_conn() as conn:
        if extraction_result["entities"]:
            await insert_entities(conn, extraction_result["entities"])

        entity_rows = await conn.fetch(
            "SELECT id, text FROM entities WHERE article_id = $1", article_id
        )
        entity_id_map: dict[str, UUID] = {
            row["text"].lower(): row["id"] for row in entity_rows
        }

        for claim in extraction_result["claims"]:
            claim = dict(claim)  # avoid mutating the input
            subject_text = claim.pop("subject_text", None)
            claim["subject_entity_id"] = (
                entity_id_map.get(subject_text.lower())
                if subject_text
                else None
            )
            await insert_claim(conn, claim)