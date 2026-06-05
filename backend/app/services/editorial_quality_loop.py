from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.all_models import Channel, Post, Topic
from app.services.org import log_activity
from app.services.public_sources import public_source_urls

QUALITY_LOOP_VERSION = "v1"
MAX_LLM_CALLS_PER_POST = 6
MAX_REWRITES_PER_POST = 0  # 0 means unlimited manual rewrites in local/operator mode.
HUMAN_RESOLVABLE_BLOCKING_CODES = {
    "missing_primary_source",
    "high_risk_needs_human",
    "unsupported_claim",
    "invented_number",
    "invented_date",
    "invented_quote",
    "unsupported_motive",
    "causality_not_supported",
    "responsibility_not_supported",
    "experts_without_source",
}

NON_CLAIM_PREFIXES = (
    "зона ручной проверки",
    "ручная проверка",
    "источник:",
    "источники:",
    "редакторский нерв:",
    "смысл для читателя:",
    "опора на источник:",
    "подписаться",
)

SourceTier = Literal["primary_source", "credible_secondary", "low_confidence"]
AtomicFactType = Literal["fact", "interpretation", "opinion", "prediction"]

NON_CLAIM_PREFIXES = NON_CLAIM_PREFIXES + (
    "зона ручной проверки",
    "ручная проверка",
    "источник:",
    "источники:",
    "редакционный нерв:",
    "редакционная оценка:",
    "практический вывод",
    "смысл для читателя:",
    "опора на источник:",
    "будем смотреть",
    "подписаться",
)

BLOCKING_CODES = {
    "missing_primary_source",
    "unsupported_claim",
    "invented_number",
    "invented_date",
    "invented_quote",
    "unsupported_motive",
    "causality_not_supported",
    "responsibility_not_supported",
    "experts_without_source",
    "quality_loop_error",
    "generated_image_as_evidence",
    "high_risk_needs_human",
    "headline_body_mismatch",
}

HIGH_RISK_KEYWORDS = {
    "война",
    "удар",
    "дрон",
    "ракета",
    "всу",
    "россия",
    "украина",
    "чс",
    "пожар",
    "наводнение",
    "землетрясение",
    "здоровье",
    "вирус",
    "болезнь",
    "лекарств",
    "дети",
    "ребен",
    "криминал",
    "убий",
    "суд",
    "иск",
    "штраф",
    "банк",
    "деньги",
    "рубл",
    "доллар",
    "политик",
    "президент",
    "парламент",
    "смерт",
    "погиб",
    "персональн",
    "данные",
}

HARD_NEWS_KEYWORDS = {
    "заявил",
    "сообщил",
    "объявил",
    "произош",
    "погиб",
    "пострад",
    "дата",
    "причин",
    "последств",
    "ответствен",
    "обвин",
    "цифр",
}

NUMBER_RE = re.compile(r"(?<![\w/])\d+(?:[.,]\d+)?(?:\s?(?:тыс|млн|млрд|км|кв\.?\s?км|%|процент|человек|дрон|ракет))?", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?:\d{1,2}[.\/-]\d{1,2}(?:[.\/-]\d{2,4})?|\d{4}|января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\b", re.IGNORECASE)
QUOTE_RE = re.compile(r"[«“\"]([^»”\"]{8,})[»”\"]")
CAUSAL_RE = re.compile(r"\b(из-за|потому что|поэтому|в результате|привело к|стал причиной|спровоцировал)\b", re.IGNORECASE)
RESPONSIBILITY_RE = re.compile(r"\b(виновн|ответственн|нарушил|обвинил|причастн|совершил|атаковал|украл|убил)\b", re.IGNORECASE)
EXPERTS_RE = re.compile(r"\b(эксперты считают|аналитики считают|по мнению экспертов|специалисты считают)\b", re.IGNORECASE)
SUPERLATIVE_RE = re.compile(r"\b(первый|крупнейший|лучший|самый|рекордн)\b", re.IGNORECASE)


HIGH_RISK_KEYWORDS = {
    "война", "war", "удар", "attack", "дрон", "drone", "ракета", "missile",
    "всу", "россия", "russia", "украина", "ukraine", "чс", "пожар", "fire",
    "наводнение", "flood", "землетрясение", "earthquake", "здоровье", "health",
    "вирус", "virus", "болезнь", "disease", "лекарств", "medicine", "дети",
    "children", "ребен", "криминал", "crime", "убий", "murder", "суд", "court",
    "иск", "lawsuit", "штраф", "банк", "bank", "деньги", "finance", "рубл",
    "доллар", "политик", "politic", "президент", "president", "парламент",
    "смерт", "death", "погиб", "персональн", "personal data", "данные",
}

HARD_NEWS_KEYWORDS = {
    "заявил", "said", "сообщил", "reported", "объявил", "announced",
    "произош", "happened", "погиб", "killed", "пострад", "injured",
    "дата", "date", "причин", "cause", "последств", "consequence",
    "ответствен", "responsib", "обвин", "accus", "цифр", "number",
}

NUMBER_RE = re.compile(r"(?<![\w/])\d+(?:[.,]\d+)?(?:\s?(?:тыс|млн|млрд|км|кв\.?\s?км|%|процент|человек|дрон|ракет|thousand|million|billion|km|people|drone|missile))?", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?:\d{1,2}[.\/-]\d{1,2}(?:[.\/-]\d{2,4})?|\d{4}|января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|january|february|march|april|may|june|july|august|september|october|november|december)\b", re.IGNORECASE)
QUOTE_RE = re.compile(r"[«“\"]([^»”\"]{8,})[»”\"]")
CAUSAL_RE = re.compile(r"\b(из-за|потому что|поэтому|в результате|привело к|стал причиной|спровоцировал|because|therefore|as a result|led to|caused|triggered)\b", re.IGNORECASE)
RESPONSIBILITY_RE = re.compile(r"\b(виновн|ответственн|нарушил|обвинил|причастн|совершил|атаковал|украл|убил|responsib|violated|accused|involved|committed|attacked|stole|killed)\b", re.IGNORECASE)
EXPERTS_RE = re.compile(r"\b(эксперты считают|аналитики считают|по мнению экспертов|специалисты считают|experts say|experts think|analysts say|according to experts)\b", re.IGNORECASE)
SUPERLATIVE_RE = re.compile(r"\b(первый|крупнейший|лучший|самый|рекордн|first|largest|biggest|best|worst|record)\b", re.IGNORECASE)


QUOTE_ATTRIBUTION_RE = re.compile(r"\b(сказал|сказала|заявил|заявила|сообщил|сообщила|написал|написала|отметил|отметила|по словам|said|stated|reported|wrote|according to)\b", re.IGNORECASE)


HIGH_RISK_KEYWORDS.update(
    {
        "война", "удар", "дрон", "ракета", "всу", "россия", "украина", "чс", "пожар",
        "наводнение", "землетрясение", "здоровье", "вирус", "болезнь", "лекарств",
        "дети", "ребен", "криминал", "убий", "суд", "иск", "штраф", "банк",
        "деньги", "рубл", "доллар", "политик", "президент", "парламент",
        "смерт", "погиб", "персональн", "данные",
    }
)
HARD_NEWS_KEYWORDS.update(
    {
        "заявил", "заявила", "сообщил", "сообщила", "объявил", "произош",
        "погиб", "пострад", "дата", "причин", "последств", "ответствен",
        "обвин", "цифр",
    }
)


class BlockingIssue(BaseModel):
    code: str
    message: str
    severity: Literal["blocker", "warning"] = "blocker"
    claim: str = ""
    recommended_fix: str = ""


class AtomicFact(BaseModel):
    text: str
    type: AtomicFactType = "fact"
    source_url: str = ""
    source_tier: SourceTier = "credible_secondary"
    confidence: float = 0.7
    retrieved_at: str
    published_at: str | None = None
    notes: str = ""


class EvidencePack(BaseModel):
    version: str = QUALITY_LOOP_VERSION
    facts: list[AtomicFact] = Field(default_factory=list)
    primary_source: str = ""
    credible_secondary_sources: list[str] = Field(default_factory=list)
    low_confidence_sources: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "medium"
    hard_news: bool = False
    high_risk: bool = False
    novelty_score: float = 0
    dedup_decision: dict[str, Any] = Field(default_factory=dict)
    recommended_post_type: str = "NEWS"
    risk_flags: list[str] = Field(default_factory=list)


class MeaningCard(BaseModel):
    version: str = QUALITY_LOOP_VERSION
    what_happened: str
    why_it_matters: str
    who_is_involved: list[str] = Field(default_factory=list)
    when: str = ""
    where: str = ""
    confirmed_facts: list[str] = Field(default_factory=list)
    uncertain_claims: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    primary_source: str = ""
    missing_context: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "medium"
    recommended_angle: str = ""
    do_not_say: list[str] = Field(default_factory=list)


class DraftClaimCheck(BaseModel):
    version: str = QUALITY_LOOP_VERSION
    verified_claims: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_claims: list[dict[str, Any]] = Field(default_factory=list)
    meaning_preserved: bool = True
    style_passed: bool = True
    rewrite_required: bool = False


class ChiefEditorV2(BaseModel):
    version: str = QUALITY_LOOP_VERSION
    decision: Literal["approved", "rewrite_required", "needs_human", "rejected"]
    reasons: list[str] = Field(default_factory=list)
    blocking_issues: list[BlockingIssue] = Field(default_factory=list)
    recommended_fix: str = ""
    confidence: float = 0.7


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    sentences = []
    for part in parts:
        sentence = part.strip()
        if len(sentence) < 25:
            continue
        normalized = _norm(sentence).lstrip("*#- ")
        if normalized.startswith(NON_CLAIM_PREFIXES):
            continue
        if _is_editorial_meta_sentence(sentence):
            continue
        sentences.append(sentence)
    return sentences


def _is_editorial_meta_sentence(text: str) -> bool:
    normalized = _norm(text).lstrip("*#- ")
    prefixes = (
        "редакционная оценка:",
        "редакционный нерв:",
        "практический вывод",
        "смысл для читателя:",
        "зона ручной проверки",
        "будем смотреть",
        "подписаться",
        "источник:",
        "источники:",
    )
    if normalized.startswith(prefixes):
        return True
    editorial_markers = (
        "нельзя выдавать",
        "некорректно писать",
        "безопаснее говорить",
        "не готова подавать",
        "стоит читать правила",
        "остаётся вопросом",
    )
    return any(marker in normalized for marker in editorial_markers)


def _contains_any(text: str, needles: set[str]) -> bool:
    value = _norm(text)
    for item in needles:
        needle = _norm(item)
        if not needle:
            continue
        if re.fullmatch(r"[a-z0-9]{1,4}", needle) or re.fullmatch(r"[а-яё]{1,3}", needle):
            if re.search(rf"(?<![a-zа-яё0-9]){re.escape(needle)}(?![a-zа-яё0-9])", value):
                return True
            continue
        if needle in value:
            return True
    return False


def is_high_risk(topic: Topic | None, post: Post) -> bool:
    text = " ".join(
        [
            post.title or "",
            post.body or "",
            topic.title if topic else "",
            topic.summary if topic else "",
            topic.raw_text if topic else "",
        ]
    )
    return bool((post.risk_score or 0) >= 60 or (topic and (topic.risk_score or 0) >= 40) or _contains_any(text, HIGH_RISK_KEYWORDS))


def is_hard_news(topic: Topic | None, post: Post) -> bool:
    text = " ".join([post.title or "", post.body or "", topic.title if topic else "", topic.summary if topic else ""])
    if post.channel and post.channel.category == "food" and not _contains_any(text, HARD_NEWS_KEYWORDS):
        return False
    return bool(_contains_any(text, HARD_NEWS_KEYWORDS) or NUMBER_RE.search(text) or DATE_RE.search(text))


def source_tier_for_url(url: str, topic: Topic | None = None) -> SourceTier:
    tier = ""
    trust = 0.0
    source_url = ""
    if topic and topic.source:
        tier = (topic.source.source_quality_tier or "").lower()
        trust = float(topic.source.trust_score or topic.source.reliability_score or 0)
        source_url = topic.source.url or ""

    domain = urlparse(url or "").netloc.lower()
    source_domain = urlparse(source_url or "").netloc.lower()
    official_markers = (
        ".gov",
        ".int",
        "who.int",
        "un.org",
        "mchs.gov",
        "kremlin.ru",
        "cbr.ru",
        "court",
        "police",
        "sec.gov",
        "fda.gov",
        "cdc.gov",
        "justice.gov",
    )
    agency_or_media_tiers = {"reputable_media", "expert_blog", "wire", "agency", "news_agency"}
    if tier in {"official", "primary", "primary_source"} or any(marker in domain for marker in official_markers):
        return "primary_source"
    if source_domain and domain == source_domain and tier in agency_or_media_tiers:
        return "credible_secondary"
    if trust >= 0.7 or tier in {*agency_or_media_tiers, "credible_secondary"}:
        return "credible_secondary"
    return "low_confidence"


def _published_at(topic: Topic | None) -> str | None:
    if topic is None:
        return None
    value = topic.source_published_at or topic.source_updated_at or topic.published_at
    return value.isoformat() if value else None


def _topic_source_urls(post: Post, topic: Topic | None) -> list[str]:
    urls = public_source_urls(post.source_urls, limit=10)
    if topic:
        urls.extend(public_source_urls([topic.url or "", topic.canonical_url or ""], limit=3))
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def build_evidence_pack(post: Post, topic: Topic | None = None) -> EvidencePack:
    retrieved_at = now_iso()
    source_urls = _topic_source_urls(post, topic)
    published_at = _published_at(topic)
    primary: list[str] = []
    secondary: list[str] = []
    low: list[str] = []
    for url in source_urls:
        tier = source_tier_for_url(url, topic)
        if tier == "primary_source":
            primary.append(url)
        elif tier == "credible_secondary":
            secondary.append(url)
        else:
            low.append(url)

    raw_facts = []
    if topic:
        raw_facts.extend([topic.title, topic.summary, topic.why_this_matters, topic.suggested_angle])
        raw_facts.extend(_sentences(topic.raw_text)[:8])
    data = post.structured_outputs_json or {}
    research = data.get("research") or {}
    raw_facts.extend([research.get("what_happened", ""), research.get("why_it_matters", "")])
    raw_facts.extend(research.get("key_facts") or [])

    facts: list[AtomicFact] = []
    default_url = primary[0] if primary else (secondary[0] if secondary else (source_urls[0] if source_urls else ""))
    default_tier = source_tier_for_url(default_url, topic) if default_url else "low_confidence"
    seen: set[str] = set()
    for text in raw_facts:
        clean = " ".join(str(text or "").split())
        if len(clean) < 12 or clean.lower() in seen:
            continue
        seen.add(clean.lower())
        fact_type: AtomicFactType = "fact"
        lower = clean.lower()
        if lower.startswith(("на наш взгляд", "редакция считает", "по мнению")):
            fact_type = "opinion"
        elif any(marker in lower for marker in ("может", "вероятно", "ожидается", "рискует")):
            fact_type = "prediction"
        elif any(marker in lower for marker in ("это значит", "показывает", "сигнал")):
            fact_type = "interpretation"
        facts.append(
            AtomicFact(
                text=clean[:700],
                type=fact_type,
                source_url=default_url if fact_type == "fact" else "",
                source_tier=default_tier,
                confidence=0.85 if default_tier != "low_confidence" else 0.45,
                retrieved_at=retrieved_at,
                published_at=published_at,
                notes="Extracted from topic/research/post context.",
            )
        )
        if len(facts) >= 18:
            break

    high = is_high_risk(topic, post)
    hard = is_hard_news(topic, post)
    risk_level: Literal["low", "medium", "high"] = "high" if high else ("medium" if hard else "low")
    missing_context: list[str] = []
    if not source_urls:
        missing_context.append("Нет публичных URL источников.")
    if (high or hard) and not primary:
        missing_context.append("Для high-risk/hard-news нет primary source.")
    pre_draft = data.get("evidence_pack_pre_draft") or (topic.evidence_pack_json if topic else {}) or {}
    dedup_decision = data.get("dedup_decision") or data.get("pre_draft_gate") or (topic.dedup_decision_json if topic else {}) or post.dedup_decision_json or {}
    return EvidencePack(
        facts=facts,
        primary_source=primary[0] if primary else "",
        credible_secondary_sources=secondary,
        low_confidence_sources=low,
        source_urls=source_urls,
        missing_context=missing_context,
        risk_level=risk_level,
        hard_news=hard,
        high_risk=high,
        novelty_score=float(post.novelty_score or (topic.novelty_score if topic else 0) or 0),
        dedup_decision=dedup_decision,
        recommended_post_type=post.post_type or (topic.recommended_post_type if topic else "NEWS") or "NEWS",
        risk_flags=list(pre_draft.get("risk_flags") or []),
    )


def build_meaning_card(post: Post, topic: Topic | None, evidence_pack: EvidencePack) -> MeaningCard:
    data = post.structured_outputs_json or {}
    research = data.get("research") or {}
    confirmed = [fact.text for fact in evidence_pack.facts if fact.type == "fact" and fact.source_url][:8]
    uncertain = [fact.text for fact in evidence_pack.facts if fact.type in {"interpretation", "prediction"}][:6]
    return MeaningCard(
        what_happened=research.get("what_happened") or (topic.summary if topic else "") or post.title,
        why_it_matters=research.get("why_it_matters") or (topic.why_this_matters if topic else "") or post.quality_reason or "Нужно понять последствия события для читателя.",
        who_is_involved=[],
        when=_published_at(topic) or "",
        where="",
        confirmed_facts=confirmed,
        uncertain_claims=uncertain,
        source_urls=evidence_pack.source_urls,
        primary_source=evidence_pack.primary_source,
        missing_context=evidence_pack.missing_context,
        risk_level=evidence_pack.risk_level,
        recommended_angle=(topic.suggested_angle if topic else "") or (data.get("editorial_voice") or {}).get("chief_editor_angle", {}).get("editorial_angle", ""),
        do_not_say=[
            "Не добавлять числа, даты, цитаты, причины, мотивы или ответственность вне evidence_pack.",
            "Не выдавать редакционную оценку за факт.",
            "Не представлять сгенерированную картинку как доказательство события.",
        ],
    )


def _evidence_text(evidence_pack: EvidencePack) -> str:
    return _norm(" ".join([fact.text for fact in evidence_pack.facts] + evidence_pack.source_urls))


def _numbers(text: str) -> set[str]:
    return {item.group(0).replace(" ", "").lower() for item in NUMBER_RE.finditer(text or "")}


def _dates(text: str) -> set[str]:
    return {item.group(0).replace(" ", "").lower() for item in DATE_RE.finditer(text or "")}


def _quoted(text: str) -> set[str]:
    return {_norm(item.group(1)) for item in QUOTE_RE.finditer(text or "")}


def _substantive_quotes(text: str) -> set[str]:
    quotes: set[str] = set()
    for item in QUOTE_RE.finditer(text or ""):
        quote = _norm(item.group(1))
        words = re.findall(r"[Р°-СЏa-z0-9]{3,}", quote)
        if len(words) >= 4:
            quotes.add(quote)
    return quotes


def _claim_supported(claim: str, evidence_pack: EvidencePack) -> bool:
    evidence = _evidence_text(evidence_pack)
    words = [word for word in re.findall(r"[а-яa-z0-9]{4,}", _norm(claim)) if word not in {"котор", "потому", "может", "после", "этого"}]
    if not words:
        return True
    hits = sum(1 for word in words if word in evidence)
    return hits >= max(2, min(5, len(words) // 3))


def _is_soft_editorial_claim(claim: str) -> bool:
    normalized = _norm(claim)
    if NUMBER_RE.search(claim) or DATE_RE.search(claim) or RESPONSIBILITY_RE.search(claim) or EXPERTS_RE.search(claim):
        return False
    soft_markers = (
        "\u0434\u043e\u043b\u0436\u043d\u044b \u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c\u0441\u044f",
        "\u0441\u043d\u043e\u0432\u0430 \u0434\u043e\u043b\u0436\u043d\u044b",
        "\u0433\u043b\u0430\u0432\u043d\u044b\u0439 \u043d\u0435\u0440\u0432",
        "\u0432\u0430\u0436\u043d\u043e \u043f\u043e\u043d\u0438\u043c\u0430\u0442\u044c",
        "\u043d\u0435\u043b\u044c\u0437\u044f \u0441\u0447\u0438\u0442\u0430\u0442\u044c",
        "\u0441\u0442\u043e\u0438\u0442",
        "\u0432\u043d\u0438\u043c\u0430\u043d\u0438\u0435 \u043d\u0443\u0436\u043d\u043e",
        "\u0441\u043d\u0438\u043c\u0430\u0435\u0442",
        "\u043d\u0435 \u0441\u0442\u043e\u0438\u0442",
        "\u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u0432\u0437\u0432\u0435\u0448\u0435\u043d\u043d\u043e\u0433\u043e \u043f\u043e\u0434\u0445\u043e\u0434\u0430",
        "\u043f\u043e\u043a\u0430 \u044d\u0442\u043e",
        "\u043f\u043e \u043f\u0440\u0435\u0434\u0432\u0430\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u043c \u043f\u043b\u0430\u043d\u0430\u043c",
        "\u044d\u0442\u043e \u043f\u043e\u043a\u0430 \u043d\u0435 \u043e\u043a\u043e\u043d\u0447\u0430\u0442\u0435\u043b\u044c\u043d\u043e\u0435 \u0440\u0435\u0448\u0435\u043d\u0438\u0435",
    )
    return any(marker in normalized for marker in soft_markers)


def _issue(code: str, message: str, claim: str = "", fix: str = "") -> BlockingIssue:
    return BlockingIssue(code=code, message=message, claim=claim[:500], recommended_fix=fix)


def claim_check(post: Post, evidence_pack: EvidencePack, meaning_card: MeaningCard) -> DraftClaimCheck:
    verified: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for claim in _sentences(post.body):
        codes: list[str] = []
        evidence = _evidence_text(evidence_pack)
        if NUMBER_RE.search(claim) and (not _numbers(claim).issubset(_numbers(evidence)) or not _claim_supported(claim, evidence_pack)):
            codes.append("invented_number")
        if DATE_RE.search(claim) and (not _dates(claim).issubset(_dates(evidence)) or not _claim_supported(claim, evidence_pack)):
            codes.append("invented_date")
        substantive_quotes = _substantive_quotes(claim)
        if substantive_quotes and QUOTE_ATTRIBUTION_RE.search(claim) and (not substantive_quotes.issubset(_quoted(evidence)) or not _claim_supported(claim, evidence_pack)):
            codes.append("invented_quote")
        if CAUSAL_RE.search(claim) and not _claim_supported(claim, evidence_pack):
            codes.append("causality_not_supported")
        if RESPONSIBILITY_RE.search(claim) and not _claim_supported(claim, evidence_pack):
            codes.append("responsibility_not_supported")
        if EXPERTS_RE.search(claim):
            codes.append("experts_without_source")
        if SUPERLATIVE_RE.search(claim) and not _claim_supported(claim, evidence_pack):
            codes.append("unsupported_claim")
        if not codes and not _claim_supported(claim, evidence_pack):
            if _is_soft_editorial_claim(claim):
                verified.append(
                    {
                        "claim": claim,
                        "source_url": evidence_pack.primary_source or (evidence_pack.credible_secondary_sources[0] if evidence_pack.credible_secondary_sources else ""),
                        "claim_type": "editorial_interpretation",
                    }
                )
                continue
            if not claim.lower().startswith(("на наш взгляд", "редакция считает", "поэтому", "важно")):
                codes.append("unsupported_claim")
        if codes:
            unsupported.append({"claim": claim, "codes": list(dict.fromkeys(codes)), "source_url": ""})
        else:
            verified.append({"claim": claim, "source_url": evidence_pack.primary_source or (evidence_pack.credible_secondary_sources[0] if evidence_pack.credible_secondary_sources else "")})

    body_norm = _norm(post.body)
    meaning_words = [word for word in re.findall(r"[а-яa-z0-9]{5,}", _norm(meaning_card.what_happened))[:10]]
    meaning_preserved = not meaning_words or sum(1 for word in meaning_words if word in body_norm) >= max(1, len(meaning_words) // 3)
    return DraftClaimCheck(
        verified_claims=verified,
        unsupported_claims=unsupported,
        meaning_preserved=meaning_preserved,
        style_passed=True,
        rewrite_required=bool(unsupported) or not meaning_preserved,
    )


def _meaningful_words(text: str) -> set[str]:
    stop_words = {
        "это",
        "как",
        "что",
        "для",
        "или",
        "при",
        "если",
        "после",
        "когда",
        "почему",
        "котор",
        "только",
        "читать",
        "читайте",
        "this",
        "that",
        "with",
        "from",
        "about",
        "after",
        "before",
        "because",
    }
    return {
        word
        for word in re.findall(r"[а-яa-z0-9]{4,}", _norm(text))
        if word not in stop_words
    }


def _headline_body_mismatch(post: Post, evidence_pack: EvidencePack) -> bool:
    title_words = _meaningful_words(post.title)
    if len(title_words) < 2:
        return False
    body_words = _meaningful_words(f"{post.body} {_evidence_text(evidence_pack)}")
    if not body_words:
        return True
    overlap = len(title_words & body_words) / max(1, len(title_words))
    return overlap < 0.34


def _blocking_issues(post: Post, evidence_pack: EvidencePack, claim_result: DraftClaimCheck) -> list[BlockingIssue]:
    issues: list[BlockingIssue] = []
    if re.search(r"\bчитать на\b", _norm(post.title)) or _headline_body_mismatch(post, evidence_pack):
        issues.append(
            _issue(
                "headline_body_mismatch",
                "Заголовок не подтверждается текстом/источником или содержит SEO-хвост.",
                claim=post.title,
                fix="Переписать заголовок по сути конкретного материала.",
            )
        )
    if not evidence_pack.source_urls:
        issues.append(_issue("unsupported_claim", "Нет публичных ссылок на источники.", fix="Добавить source_url или отклонить пост."))
    if (evidence_pack.high_risk or evidence_pack.hard_news) and not evidence_pack.primary_source and not evidence_pack.credible_secondary_sources:
        if len(evidence_pack.credible_secondary_sources) >= 2:
            issues.append(_issue("missing_primary_source", "Нет primary source. Есть 2+ credible secondary, поэтому только needs_human.", fix="Проверить первоисточник или оставить ручную проверку."))
        else:
            issues.append(_issue("missing_primary_source", "High-risk/hard-news требует primary source.", fix="Найти первоисточник или отклонить пост."))
    if evidence_pack.high_risk:
        issues.append(_issue("high_risk_needs_human", "High-risk тема требует ручного решения.", fix="Проверить факты, риск и формулировки вручную."))
    for item in claim_result.unsupported_claims:
        for code in item.get("codes") or ["unsupported_claim"]:
            if code in BLOCKING_CODES:
                issues.append(_issue(code, f"Claim не подтверждён evidence_pack: {code}", claim=item.get("claim", ""), fix="Удалить claim, смягчить формулировку или добавить источник."))
    if post.media_source_type == "generated":
        text = _norm(f"{post.body} {post.max_packaged_text} {post.media_rights_note} {post.visual_safety_notes}")
        if any(marker in text for marker in ["на фото", "снимок показывает", "видно как", "доказательств"]):
            issues.append(_issue("generated_image_as_evidence", "Generated image нельзя подавать как доказательство.", fix="Пометить визуал как иллюстрацию или заменить реальным медиа."))
    return issues


def build_chief_editor_v2(evidence_pack: EvidencePack, claim_result: DraftClaimCheck, issues: list[BlockingIssue]) -> ChiefEditorV2:
    blocker_codes = {issue.code for issue in issues if issue.severity == "blocker"}
    if "quality_loop_error" in blocker_codes:
        decision: Literal["approved", "rewrite_required", "needs_human", "rejected"] = "needs_human"
    elif blocker_codes:
        decision = "needs_human" if blocker_codes <= {"missing_primary_source", "high_risk_needs_human"} else "rewrite_required"
    else:
        decision = "approved"
    if not claim_result.meaning_preserved and decision == "approved":
        decision = "rewrite_required"
    reasons = []
    if evidence_pack.high_risk:
        reasons.append("High-risk taxonomy matched.")
    if evidence_pack.hard_news:
        reasons.append("Hard-news taxonomy matched.")
    if issues:
        reasons.append("Blocking issues require human/rewrite before approval.")
    if not issues:
        reasons.append("Evidence, meaning and claims passed v1 quality loop.")
    fix = issues[0].recommended_fix if issues else "Можно отправлять на ручное одобрение."
    confidence = 0.9 if not issues else 0.55
    return ChiefEditorV2(decision=decision, reasons=reasons, blocking_issues=issues, recommended_fix=fix, confidence=confidence)


def quality_verdict(chief: ChiefEditorV2, evidence_pack: EvidencePack, issues: list[BlockingIssue]) -> str:
    action = str((evidence_pack.dedup_decision or {}).get("action") or "")
    if action in {"duplicate_skip", "attach_to_existing_topic"}:
        return "REJECT_DUPLICATE"
    codes = {issue.code for issue in issues}
    if "missing_primary_source" in codes:
        return "NEEDS_MORE_SOURCES"
    if "unsupported_claim" in codes:
        return "REJECT_UNSUPPORTED_CLAIMS"
    if evidence_pack.low_confidence_sources and not evidence_pack.primary_source and not evidence_pack.credible_secondary_sources:
        return "REJECT_LOW_TRUST"
    if chief.decision == "approved":
        return "PASS"
    if chief.decision == "rewrite_required":
        return "REWRITE_REQUIRED"
    if chief.decision == "needs_human":
        return "NEEDS_REVIEW"
    return "REJECT_LOW_VALUE"


def quality_loop_passed(data: dict[str, Any] | None) -> bool:
    loop = (data or {}).get("quality_loop") or {}
    return loop.get("version") == QUALITY_LOOP_VERSION and bool(loop.get("passed")) and not loop.get("blocking_issues")


def quality_loop_blocking_issues(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    loop = (data or {}).get("quality_loop") or {}
    return list(loop.get("blocking_issues") or [])


def human_resolvable_blocking_issues(data: dict[str, Any] | None) -> bool:
    issues = quality_loop_blocking_issues(data)
    if not issues:
        return False
    codes = {str(item.get("code") or "") for item in issues}
    return bool(codes) and codes <= HUMAN_RESOLVABLE_BLOCKING_CODES


def resolve_human_review_blockers(post: Post, *, approved_by: str = "human") -> None:
    data = post.structured_outputs_json or {}
    loop = dict(data.get("quality_loop") or {})
    if loop.get("version") != QUALITY_LOOP_VERSION:
        raise ValueError("Quality loop v1 is required before human resolution")
    issues = list(loop.get("blocking_issues") or [])
    codes = {str(item.get("code") or "") for item in issues}
    if not codes:
        return
    if not codes <= HUMAN_RESOLVABLE_BLOCKING_CODES:
        raise ValueError("Only human-review blockers can be resolved by editor approval")

    loop["original_blocking_issues"] = list(loop.get("original_blocking_issues") or issues)
    loop["resolved_blocking_issues"] = issues
    loop["blocking_issues"] = []
    loop["passed"] = True
    loop["suggested_status"] = "needs_review"
    loop["reason"] = "Human editor resolved high-risk/manual-source blockers."
    loop["human_resolution"] = {
        "approved_by": approved_by,
        "resolved_at": datetime.now(UTC).isoformat(),
        "resolved_codes": sorted(codes),
        "note": "Редактор вручную проверил источник, риск и формулировки. Неподтверждённых claims в quality loop не осталось.",
    }

    chief = dict(data.get("chief_editor_v2") or {})
    chief["decision"] = "approved"
    chief["blocking_issues"] = []
    chief["reasons"] = list(chief.get("reasons") or []) + ["Human editor resolved manual blockers."]
    chief["recommended_fix"] = "Можно одобрить и публиковать после ручного решения редактора."
    chief["confidence"] = max(float(chief.get("confidence") or 0), 0.72)

    post.structured_outputs_json = {**data, "quality_loop": loop, "chief_editor_v2": chief}
    post.status_reason = "Quality loop human-reviewed and resolved."


def validate_post_quality_for_approval(post: Post) -> None:
    data = post.structured_outputs_json or {}
    loop = data.get("quality_loop") or {}
    if loop.get("version") != QUALITY_LOOP_VERSION:
        raise ValueError("Quality loop v1 is required before approval/publishing")
    issues = loop.get("blocking_issues") or []
    if issues:
        codes = ", ".join(str(item.get("code") or "blocking_issue") for item in issues)
        raise ValueError(f"Quality loop has blocking issues: {codes}")
    if not loop.get("passed"):
        raise ValueError(loop.get("reason") or "Quality loop did not pass")


def run_quality_loop(db: Session, post: Post) -> dict[str, Any]:
    started = datetime.now(UTC)
    topic = post.topic
    try:
        evidence = build_evidence_pack(post, topic)
        meaning = build_meaning_card(post, topic, evidence)
        claim_result = claim_check(post, evidence, meaning)
        issues = _blocking_issues(post, evidence, claim_result)
        chief = build_chief_editor_v2(evidence, claim_result, issues)
        llm_runs = ((post.structured_outputs_json or {}).get("trace") or {}).get("runs") or []
        llm_calls = len(llm_runs)
        if llm_calls > MAX_LLM_CALLS_PER_POST:
            issues.append(_issue("quality_loop_error", f"LLM calls exceeded limit: {llm_calls}/{MAX_LLM_CALLS_PER_POST}", fix="Сократить pipeline или отправить человеку."))
            chief = build_chief_editor_v2(evidence, claim_result, issues)
        rewrite_attempts = int((post.structured_outputs_json or {}).get("rewrite_attempts_used") or 0)
        if MAX_REWRITES_PER_POST > 0 and rewrite_attempts > MAX_REWRITES_PER_POST:
            issues.append(_issue("quality_loop_error", "Rewrite attempts exceeded v1 limit.", fix="Отправить человеку."))
            chief = build_chief_editor_v2(evidence, claim_result, issues)

        suggested_status = "needs_review"
        if chief.decision == "approved":
            suggested_status = "needs_review"
        elif chief.decision in {"rewrite_required", "needs_human"}:
            suggested_status = "needs_human"
        elif chief.decision == "rejected":
            suggested_status = "rejected"

        elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        passed = chief.decision == "approved" and not issues
        verdict = quality_verdict(chief, evidence, issues)
        loop = {
            "version": QUALITY_LOOP_VERSION,
            "passed": passed,
            "suggested_status": suggested_status,
            "blocking_issues": [issue.model_dump(mode="json") for issue in issues],
            "cost": {
                "tokens_input": int(post.tokens_input or 0),
                "tokens_output": int(post.tokens_output or 0),
                "estimated_cost_usd": float(post.estimated_cost_usd or 0),
                "llm_calls": llm_calls,
                "max_llm_calls": MAX_LLM_CALLS_PER_POST,
                "rewrite_attempts": rewrite_attempts,
                "max_rewrites": MAX_REWRITES_PER_POST,
                "rewrite_limit_active": MAX_REWRITES_PER_POST > 0,
            },
            "elapsed_ms": elapsed_ms,
            "reason": chief.recommended_fix if issues else "Quality loop v1 passed.",
            "verdict": verdict,
        }
        post.quality_verdict = verdict
        post.structured_outputs_json = {
            **(post.structured_outputs_json or {}),
            "source_tiers": {
                "primary_source": evidence.primary_source,
                "credible_secondary": evidence.credible_secondary_sources,
                "low_confidence": evidence.low_confidence_sources,
            },
            "evidence_pack": evidence.model_dump(mode="json"),
            "meaning_card": meaning.model_dump(mode="json"),
            "draft_claim_check": claim_result.model_dump(mode="json"),
            "chief_editor_v2": chief.model_dump(mode="json"),
            "quality_loop": loop,
        }
        post.status_reason = "Quality loop passed; human approval required." if passed else f"Quality loop requires attention: {loop['reason']}"
        post.quality_reason = post.quality_reason or loop["reason"]
        log_activity(
            db,
            actor_type="agent",
            actor_id=None,
            event_type="quality_loop_completed",
            entity_type="post",
            entity_id=post.id,
            message=f"Quality loop v1 completed for post #{post.id}: {chief.decision}.",
            metadata={"passed": passed, "blocking_codes": [issue.code for issue in issues], "suggested_status": suggested_status},
        )
        return loop
    except Exception as exc:
        issue = _issue("quality_loop_error", f"Quality loop failed: {exc}", fix="Проверить ошибку и прогнать quality-check вручную.")
        loop = {
            "version": QUALITY_LOOP_VERSION,
            "passed": False,
            "suggested_status": "needs_human",
            "blocking_issues": [issue.model_dump(mode="json")],
            "cost": {
                "tokens_input": int(post.tokens_input or 0),
                "tokens_output": int(post.tokens_output or 0),
                "estimated_cost_usd": float(post.estimated_cost_usd or 0),
                "llm_calls": len(((post.structured_outputs_json or {}).get("trace") or {}).get("runs") or []),
                "max_llm_calls": MAX_LLM_CALLS_PER_POST,
                "rewrite_attempts": int((post.structured_outputs_json or {}).get("rewrite_attempts_used") or 0),
                "max_rewrites": MAX_REWRITES_PER_POST,
                "rewrite_limit_active": MAX_REWRITES_PER_POST > 0,
            },
            "elapsed_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
            "reason": "quality_loop_error",
        }
        post.quality_verdict = "NEEDS_REVIEW"
        post.structured_outputs_json = {**(post.structured_outputs_json or {}), "quality_loop": loop, "chief_editor_v2": {"version": QUALITY_LOOP_VERSION, "decision": "needs_human", "reasons": ["quality_loop_error"], "blocking_issues": [issue.model_dump(mode="json")], "recommended_fix": issue.recommended_fix, "confidence": 0}}
        post.status = "needs_review"
        post.status_reason = "quality_loop_error"
        log_activity(
            db,
            actor_type="agent",
            actor_id=None,
            event_type="quality_loop_failed",
            entity_type="post",
            entity_id=post.id,
            message=f"Quality loop v1 failed for post #{post.id}: {exc}",
            metadata={"error": str(exc)[:500]},
        )
        return loop
