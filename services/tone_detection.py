from __future__ import annotations

import re
from typing import Any

from LLM_service.client import llm_client

EXTRACTION_METHOD = "llm+lexicon"

_HEDGING_RE = re.compile(
    r"\b("
    r"alleged(?:ly)?|reportedly|purportedly|supposedly|"
    r"may|might|could|possibly|perhaps|"
    r"appears? to|seems? to|suggest(?:s|ed|ing)?|"
    r"claim(?:s|ed|ing)?|accused of|rumou?r(?:ed)?"
    r")\b",
    re.IGNORECASE,
)
_CERTAINTY_RE = re.compile(
    r"\b("
    r"definitely|certainly|undoubtedly|confirmed|proven|"
    r"without doubt|always|never|must|will certainly|"
    r"no question|clearly established"
    r")\b",
    re.IGNORECASE,
)
_ATTRIBUTION_RE = re.compile(
    r"\b("
    r"according to|as reported by|sources? say|sources? told|"
    r"told reporters|said|stated|wrote|announced|"
    r"in a statement|officials? said"
    r")\b",
    re.IGNORECASE,
)

_VALID_TONES = frozenset({"positive", "negative", "neutral"})


def extract_framing_cues(text: str) -> dict[str, Any]:
    """Rule layer: hedging / certainty / attribution signals for JSONB storage."""
    hedging_hits = _HEDGING_RE.findall(text)
    certainty_hits = _CERTAINTY_RE.findall(text)
    attribution_hits = _ATTRIBUTION_RE.findall(text)
    return {
        "hedging": len(hedging_hits) > 0,
        "certainty": len(certainty_hits) > 0,
        "attribution": len(attribution_hits) > 0,
        "hedging_count": len(hedging_hits),
        "certainty_count": len(certainty_hits),
        "attribution_count": len(attribution_hits),
    }


def _clamp_tone_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(-1.0, min(1.0, score))


def _normalise_overall_tone(raw: Any) -> str:
    tone = str(raw or "neutral").strip().lower()
    if tone in _VALID_TONES:
        return tone
    if tone in {"pos", "optimistic", "favorable", "favourable"}:
        return "positive"
    if tone in {"neg", "pessimistic", "critical", "unfavorable", "unfavourable"}:
        return "negative"
    return "neutral"


def _tone_prompt(text: str) -> str:
    sample = text.strip()[:8000]
    return (
        "Classify the overall editorial tone of this news text.\n"
        "Return ONLY JSON:\n"
        '{"overall_tone":"positive|negative|neutral","tone_score":-1.0}\n'
        "tone_score: -1 (most negative) to +1 (most positive).\n\n"
        f"Text:\n{sample}"
    )


def _stance_prompt(text: str, query_topic: str) -> str:
    sample = text.strip()[:8000]
    return (
        f"How does this text position itself toward the topic: {query_topic!r}?\n"
        "Return ONLY JSON:\n"
        '{"stance":"supportive|neutral|critical|mixed","confidence":0.0,"reason":"..."}\n\n'
        f"Text:\n{sample}"
    )


async def _detect_stance(
    text: str,
    query_topic: str,
    *,
    model: str | None,
) -> dict[str, Any] | None:
    data = await llm_client.generate_json(
        _stance_prompt(text, query_topic),
        required_keys={"stance", "confidence", "reason"},
        model=model,
    )
    if data is None:
        return None
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    return {
        "topic": query_topic,
        "stance": str(data.get("stance", "neutral")).strip().lower(),
        "confidence": confidence,
        "reason": str(data.get("reason", "")).strip(),
    }


async def detect_tone(
    text: str,
    *,
    model: str | None = None,
    query_topic: str | None = None,
) -> dict[str, Any] | None:
    """
    Returns a row-shaped dict for db.tone.upsert_tone_framing (plus optional stance).

    Keys: overall_tone, tone_score, framing_cues, extraction_method
    Optional: stance_toward_topic (query-time only, not persisted in tone_framing table)
    """
    if not text or not text.strip():
        return None

    framing_cues = extract_framing_cues(text)

    data = await llm_client.generate_json(
        _tone_prompt(text),
        required_keys={"overall_tone", "tone_score"},
        model=model,
    )
    if data is None:
        return None

    result: dict[str, Any] = {
        "overall_tone": _normalise_overall_tone(data.get("overall_tone")),
        "tone_score": _clamp_tone_score(data.get("tone_score")),
        "framing_cues": framing_cues,
        "extraction_method": EXTRACTION_METHOD,
    }

    if query_topic and query_topic.strip():
        stance = await _detect_stance(text, query_topic.strip(), model=model)
        if stance is not None:
            result["stance_toward_topic"] = stance

    return result