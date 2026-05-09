from __future__ import annotations

from typing import Any


PLAYBOOKS: dict[str, dict[str, Any]] = {
    "era-now": {
        "purpose": "Quickly explain important current events without panic, clickbait, or speculation.",
        "audience": "Busy readers who need context and a calm next-step view.",
        "editorial_formula": ["Что произошло", "Почему это важно", "Что может быть дальше"],
        "tone_of_voice": "Calm, concise, factual, source-aware.",
        "content_pillars": ["events", "public impact", "practical context", "what to watch next"],
        "allowed_topics": ["public news", "technology news", "economy news", "policy updates", "major research releases"],
        "forbidden_topics": ["panic framing", "unverified rumors", "partisan agitation", "graphic details"],
        "good_post_examples": ["Что произошло: ... Почему важно: ... Дальше следим за ..."],
        "bad_post_examples": ["Срочно! Всё изменилось навсегда! Без источников и с прогнозами."],
        "quality_checklist": ["names the event", "explains impact", "separates facts from uncertainty", "has a next-watch item"],
        "risk_checklist": ["no rumor as fact", "no panic language", "dates and actors are clear"],
        "required_structure": ["Что произошло", "Почему это важно", "Что дальше"],
        "banned_patterns": ["шок", "срочно без источника", "точно будет", "все пропало"],
        "cta_style": "Soft watch-next CTA.",
        "max_post_length": 1100,
        "min_editorial_value_score": 72,
    },
    "era-money": {
        "purpose": "Turn business and money facts into practical, non-advisory insight.",
        "audience": "Entrepreneurs, operators, investors, and financially curious readers.",
        "editorial_formula": ["Идея / факт", "Где здесь деньги", "Риски", "Кому полезно", "Что можно проверить самому"],
        "tone_of_voice": "Practical, sober, no financial advice.",
        "content_pillars": ["business model", "cash flow", "market signal", "risk", "self-check"],
        "allowed_topics": ["business", "markets context", "consumer finance education", "company strategy", "cost savings"],
        "forbidden_topics": ["trading signals", "guaranteed returns", "personal financial advice", "tax/legal advice"],
        "good_post_examples": ["Факт: ... Деньги здесь в ... Риск: ... Проверьте сами ..."],
        "bad_post_examples": ["Покупайте сейчас, это точно вырастет."],
        "quality_checklist": ["has money angle", "names risks", "says who benefits", "offers self-check"],
        "risk_checklist": ["no investment advice", "no guaranteed income", "no unsupported numbers"],
        "required_structure": ["Идея / факт", "Где здесь деньги", "Риски", "Кому полезно", "Что проверить"],
        "banned_patterns": ["гарантированный доход", "сигнал на покупку", "точно заработаете"],
        "cta_style": "Ask reader to verify one number or assumption.",
        "max_post_length": 1300,
        "min_editorial_value_score": 76,
    },
    "era-ai": {
        "purpose": "Explain useful AI and automation changes with practical operator value.",
        "audience": "Builders, creators, founders, operators, and AI-curious professionals.",
        "editorial_formula": ["Что появилось / изменилось", "Как это работает простыми словами", "Как применить", "Кому полезно", "Что попробовать сегодня"],
        "tone_of_voice": "Clear, hands-on, curious, realistic.",
        "content_pillars": ["new tools", "agent workflows", "automation", "implementation", "limits"],
        "allowed_topics": ["AI tools", "agents", "automation", "model updates", "workflow design"],
        "forbidden_topics": ["magic claims", "fake benchmarks", "unsafe automation", "hidden data collection"],
        "good_post_examples": ["Новое: ... Простыми словами: ... Попробуйте сегодня: ..."],
        "bad_post_examples": ["ИИ заменит всех завтра. Подробностей нет."],
        "quality_checklist": ["explains mechanism simply", "has practical use case", "names limits", "suggests a small test"],
        "risk_checklist": ["no overclaiming", "no privacy-blind advice", "no unsupported benchmarks"],
        "required_structure": ["Что изменилось", "Как работает", "Как применить", "Кому полезно", "Попробовать сегодня"],
        "banned_patterns": ["революция без деталей", "заменит всех", "100% автономно"],
        "cta_style": "One safe experiment the reader can try today.",
        "max_post_length": 1300,
        "min_editorial_value_score": 74,
    },
    "era-health": {
        "purpose": "Explain health, sleep, nutrition, habits, and research carefully without diagnosis or treatment advice.",
        "audience": "Readers who want safe everyday health context.",
        "editorial_formula": ["Что известно", "Что это значит для обычного человека", "Ограничения / что не доказано", "Безопасный практичный вывод"],
        "tone_of_voice": "Careful, evidence-aware, non-alarmist.",
        "content_pillars": ["sleep", "nutrition", "habits", "research", "safe takeaway"],
        "allowed_topics": ["general wellness", "research summaries", "habits", "sleep hygiene", "nutrition education"],
        "forbidden_topics": ["diagnosis", "dosage", "treatment instructions", "medical promises", "anti-doctor claims"],
        "good_post_examples": ["Что известно: ... Ограничение: ... Безопасный вывод: ..."],
        "bad_post_examples": ["Это лечит болезнь. Срочно отмените лекарства."],
        "quality_checklist": ["states evidence level", "names limitations", "safe practical takeaway", "no medical advice"],
        "risk_checklist": ["no diagnosis", "no dosage", "no cure claims", "human review for strong claims"],
        "required_structure": ["Что известно", "Что значит", "Ограничения", "Безопасный вывод"],
        "banned_patterns": ["лечит", "гарантирует", "заменяет врача", "дозировка"],
        "cta_style": "Suggest a low-risk habit or question for a professional.",
        "max_post_length": 1200,
        "min_editorial_value_score": 78,
    },
    "era-food": {
        "purpose": "Give useful food ideas that are tasty, repeatable, economical, and practical.",
        "audience": "People planning meals, saving time/money, or improving everyday food.",
        "editorial_formula": ["Идея блюда", "Почему это удобно/вкусно/выгодно", "Ингредиенты", "Шаги", "Вариации / польза / экономия"],
        "tone_of_voice": "Warm, practical, concrete.",
        "content_pillars": ["recipes", "meal planning", "healthy-ish food", "economy", "variations"],
        "allowed_topics": ["recipes", "meal prep", "budget cooking", "nutrition basics", "ingredient swaps"],
        "forbidden_topics": ["medical diet claims", "extreme dieting", "unsafe food handling"],
        "good_post_examples": ["Идея: ... Ингредиенты: ... Шаги: ... Вариация: ..."],
        "bad_post_examples": ["Суперфуд вылечит всё. Рецепта нет."],
        "quality_checklist": ["has ingredients", "has steps", "has variation", "explains convenience/value"],
        "risk_checklist": ["no medical diet promises", "safe food handling", "allergens if relevant"],
        "required_structure": ["Идея блюда", "Почему удобно", "Ингредиенты", "Шаги", "Вариации"],
        "banned_patterns": ["лечебная диета", "сжигает жир", "безопасно для всех"],
        "cta_style": "Invite reader to save/adapt the recipe.",
        "max_post_length": 1400,
        "min_editorial_value_score": 70,
    },
}


def channel_playbook(channel_slug: str) -> dict[str, Any]:
    return PLAYBOOKS.get(channel_slug, PLAYBOOKS["era-now"])


def playbook_summary(channel_slug: str) -> str:
    playbook = channel_playbook(channel_slug)
    return "\n".join(
        [
            f"Purpose: {playbook['purpose']}",
            f"Audience: {playbook['audience']}",
            f"Formula: {' / '.join(playbook['editorial_formula'])}",
            f"Tone: {playbook['tone_of_voice']}",
            f"Required structure: {' / '.join(playbook['required_structure'])}",
            f"Quality checklist: {'; '.join(playbook['quality_checklist'])}",
            f"Risk checklist: {'; '.join(playbook['risk_checklist'])}",
            f"Banned patterns: {'; '.join(playbook['banned_patterns'])}",
            f"CTA style: {playbook['cta_style']}",
            f"Max post length: {playbook['max_post_length']}",
            f"Min editorial value score: {playbook['min_editorial_value_score']}",
        ]
    )
