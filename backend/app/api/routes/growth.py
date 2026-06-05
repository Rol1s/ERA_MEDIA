from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import Channel, FunnelAsset, GrowthCampaign, Post, SeedingRun, TrafficSource
from app.services.org import log_activity

router = APIRouter()


SCHEME_DAY_CHANNEL = {
    "name": "Схема дня",
    "slug": "scheme-day",
    "category": "earning",
    "description": "Денежный MAX-канал: разборы заработка, трафика, партнерок, подработок, чужих воронок и скама без обещаний гарантированного дохода.",
    "tone_of_voice": "Жестко, практично, предпринимательски, без мотивационной воды и без обещаний гарантированного дохода.",
    "audience_description": "Люди, которые ищут первые или дополнительные деньги в интернете и хотят понимать механику трафика, офферов и рисков.",
    "topics_allowed": ["заработок", "трафик", "партнерки", "подработки", "лидогенерация", "разбор воронок", "антискам"],
    "topics_forbidden": ["гарантированный доход", "финансовые гарантии", "обман", "массовый спам", "покупные базы контактов", "обход банов"],
    "posting_frequency_per_day": 3,
    "daily_post_limit": 5,
    "publish_mode": "manual",
    "auto_publish_enabled": False,
    "risk_threshold": 0.25,
    "channel_mode": "growth",
    "status": "active",
}

DEFAULT_OFFER = (
    "Каждый день разбираем одну денежную схему: где взять трафик, что продавать, "
    "сколько там денег, где риск и где развод. Без мотивационной воды."
)

SEED_TRAFFIC_SOURCES = [
    ("MAX: тематические чаты про заработок", "max", "comments", "high", "Только ручные комментарии по теме; без массовых одинаковых рассылок."),
    ("Telegram: комменты под постами про деньги", "telegram", "comments", "medium", "Вести на конкретный разбор, не на общий канал."),
    ("VK: обсуждения под новостями про работу и деньги", "vk", "comments", "medium", "Использовать мягкие вбросы и прокладки."),
    ("Городские/районные чаты", "mixed", "local_chats", "medium", "Подходит для тем про подработку и быстрые деньги; без обещаний дохода."),
    ("Личные страницы-прокладки", "mixed", "landing", "low", "Публиковать короткие лид-магниты и вести в MAX."),
]

DAILY_TOPICS = [
    {
        "title": "Как каналы про заработок набирают людей на обещании 300к",
        "hook": "Деньги там часто не в самой схеме, а в продаже надежды тем, кто ищет быстрый вход.",
        "angle": "разбор чужой воронки",
    },
    {
        "title": "5 способов найти первые 10-30к без найма и офиса",
        "hook": "Быстрый вход обычно там, где бизнесу нужен простой результат: заявки, контент, отзывы, оформление, поиск.",
        "angle": "лид-магнит",
    },
    {
        "title": "Где взять первый трафик без рекламного бюджета",
        "hook": "Если денег на рекламу нет, платишь временем: комментариями, прокладками, ручными заходами и тестом офферов.",
        "angle": "growth-инструкция",
    },
]

SEED_COMMENTS = [
    "Там деньги не в обещанных 300к, а в воронке. Разобрали механику без сказок: {url}",
    "Если видите закрытый канал с розыгрышем, смотрите не на приз, а на то, куда вас ведут дальше: {url}",
    "Новичков чаще всего ловят не на схему, а на надежду быстро выйти в деньги. Короткий разбор: {url}",
    "Первый трафик без бюджета есть, но он покупается временем и аккаунтами, а не магией. Разложили: {url}",
    "Перед тем как верить очередному заработку без вложений, посмотрите, где там реально появляется маржа: {url}",
    "Рабочая схема начинается с трафика и оффера. Если одного из пунктов нет, это прогрев. Разбор: {url}",
    "Каналы про быстрый доход почти всегда продают не работу, а вход в воронку. Вот как это устроено: {url}",
    "Есть нормальные способы заработать первые деньги, но они выглядят скучнее, чем обещания на скринах. Список здесь: {url}",
    "Самый важный вопрос: кто платит и за какой результат. Без этого перед вами не схема, а сказка: {url}",
    "Разобрали, что можно повторить маленькими руками, а где вас просто ведут как лида: {url}",
]


class SeedingRunCreate(BaseModel):
    campaign_id: int
    asset_id: int | None = None
    traffic_source_id: int | None = None
    platform: str = "manual"
    placements_count: int = 0
    link_clicks: int = 0
    joins: int = 0
    bans: int = 0
    complaints: int = 0
    result: str = "unknown"
    notes: str = ""


class GeneratePackRequest(BaseModel):
    topic: str | None = None
    target_url: str = ""
    create_post: bool = True
    comments_count: int = Field(default=10, ge=1, le=30)


def _channel_payload(channel: Channel | None) -> dict[str, Any] | None:
    if channel is None:
        return None
    return {
        "id": channel.id,
        "name": channel.name,
        "slug": channel.slug,
        "category": channel.category,
        "description": channel.description,
        "tone_of_voice": channel.tone_of_voice,
        "audience_description": channel.audience_description,
        "topics_allowed": channel.topics_allowed or [],
        "topics_forbidden": channel.topics_forbidden or [],
        "posting_frequency_per_day": channel.posting_frequency_per_day,
        "daily_post_limit": channel.daily_post_limit,
        "publish_mode": channel.publish_mode,
        "auto_publish_enabled": channel.auto_publish_enabled,
        "risk_threshold": channel.risk_threshold,
        "channel_mode": channel.channel_mode,
        "status": channel.status,
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }


def _campaign_payload(campaign: GrowthCampaign) -> dict[str, Any]:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "target_channel_id": campaign.target_channel_id,
        "target_channel": _channel_payload(campaign.target_channel),
        "goal": campaign.goal,
        "offer": campaign.offer,
        "audience": campaign.audience,
        "tone": campaign.tone,
        "risk_level": campaign.risk_level,
        "status": campaign.status,
        "hypothesis_json": campaign.hypothesis_json or {},
        "kpi_json": campaign.kpi_json or {},
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
    }


def _asset_payload(asset: FunnelAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "campaign_id": asset.campaign_id,
        "post_id": asset.post_id,
        "asset_type": asset.asset_type,
        "platform": asset.platform,
        "title": asset.title,
        "text": asset.text,
        "cta": asset.cta,
        "target_url": asset.target_url,
        "risk_notes": asset.risk_notes,
        "status": asset.status,
        "metadata_json": asset.metadata_json or {},
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


def _traffic_source_payload(source: TrafficSource) -> dict[str, Any]:
    return {
        "id": source.id,
        "name": source.name,
        "platform": source.platform,
        "category": source.category,
        "url": source.url,
        "risk_level": source.risk_level,
        "notes": source.notes,
        "status": source.status,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def _seeding_run_payload(run: SeedingRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "campaign_id": run.campaign_id,
        "asset_id": run.asset_id,
        "traffic_source_id": run.traffic_source_id,
        "platform": run.platform,
        "placements_count": run.placements_count,
        "link_clicks": run.link_clicks,
        "joins": run.joins,
        "bans": run.bans,
        "complaints": run.complaints,
        "result": run.result,
        "notes": run.notes,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _ensure_scheme_day_channel(db: Session) -> Channel:
    channel = db.execute(select(Channel).where(Channel.slug == SCHEME_DAY_CHANNEL["slug"])).scalar_one_or_none()
    if channel is None:
        channel = Channel(**SCHEME_DAY_CHANNEL)
        db.add(channel)
        db.flush()
    else:
        for key, value in SCHEME_DAY_CHANNEL.items():
            if key in {"name", "slug"}:
                continue
            setattr(channel, key, value)
    return channel


def _ensure_campaign(db: Session, channel: Channel) -> GrowthCampaign:
    campaign = db.execute(select(GrowthCampaign).where(GrowthCampaign.name == "Схема дня / запуск")).scalar_one_or_none()
    if campaign is None:
        campaign = GrowthCampaign(
            name="Схема дня / запуск",
            target_channel_id=channel.id,
            goal="subscribers_then_monetization",
            offer=DEFAULT_OFFER,
            audience="Новички и практики, которые ищут заработок, трафик, подработки и хотят отличать рабочие механики от развода.",
            tone="Жестко, коротко, с цифрами, рисками и механикой. Никаких гарантий дохода.",
            risk_level="controlled_gray",
            hypothesis_json={
                "funnel": "hook -> landing/growth post -> MAX subscribe -> monetization",
                "positioning": "денежные схемы без мотивационной воды и без обещаний гарантированного дохода",
                "guardrails": ["no guaranteed income", "no bought contact bases", "no mass spam automation", "manual operator seeding only"],
            },
            kpi_json={"week_1": {"placements": 150, "clicks": 50, "joins": 15}, "decision": "scale/edit/kill"},
        )
        db.add(campaign)
        db.flush()
    else:
        campaign.target_channel_id = channel.id
        campaign.status = "active"
    return campaign


def _ensure_traffic_sources(db: Session) -> list[TrafficSource]:
    created: list[TrafficSource] = []
    for name, platform, category, risk_level, notes in SEED_TRAFFIC_SOURCES:
        source = db.execute(select(TrafficSource).where(TrafficSource.name == name)).scalar_one_or_none()
        if source is None:
            source = TrafficSource(name=name, platform=platform, category=category, risk_level=risk_level, notes=notes, status="active")
            db.add(source)
        else:
            source.platform = platform
            source.category = category
            source.risk_level = risk_level
            source.notes = notes
            source.status = "active"
        created.append(source)
    db.flush()
    return created


def _post_text_for_topic(title: str, hook: str) -> str:
    return (
        f"{title}\n\n"
        f"{hook}\n\n"
        "Разбираем по простой схеме: где берется трафик, что человеку продают, "
        "кто зарабатывает, где риск и что можно повторить маленькими руками. "
        "Без обещаний легких денег и без скринов ради прогрева.\n\n"
        "Если хотите видеть такие разборы каждый день, оставайтесь в канале."
    )


def _create_asset(db: Session, campaign: GrowthCampaign, *, asset_type: str, title: str, text: str, target_url: str, post_id: int | None = None, platform: str = "max", cta: str = "") -> FunnelAsset:
    asset = FunnelAsset(
        campaign_id=campaign.id,
        post_id=post_id,
        asset_type=asset_type,
        platform=platform,
        title=title,
        text=text,
        cta=cta,
        target_url=target_url,
        risk_notes="Операторский посев: использовать только по теме, без массовых одинаковых рассылок и без обещаний гарантированного дохода.",
        status="draft",
        metadata_json={"generated_at": datetime.now(UTC).isoformat()},
    )
    db.add(asset)
    db.flush()
    return asset


def _build_summary(db: Session) -> dict[str, Any]:
    campaigns = list(db.execute(select(GrowthCampaign).order_by(GrowthCampaign.id)).scalars())
    assets = list(db.execute(select(FunnelAsset).order_by(FunnelAsset.created_at.desc(), FunnelAsset.id.desc()).limit(80)).scalars())
    sources = list(db.execute(select(TrafficSource).order_by(TrafficSource.id)).scalars())
    runs = list(db.execute(select(SeedingRun).order_by(SeedingRun.created_at.desc(), SeedingRun.id.desc()).limit(40)).scalars())
    totals = {
        "campaigns": len(campaigns),
        "assets": db.scalar(select(func.count()).select_from(FunnelAsset)) or 0,
        "placements": db.scalar(select(func.coalesce(func.sum(SeedingRun.placements_count), 0))) or 0,
        "clicks": db.scalar(select(func.coalesce(func.sum(SeedingRun.link_clicks), 0))) or 0,
        "joins": db.scalar(select(func.coalesce(func.sum(SeedingRun.joins), 0))) or 0,
        "bans": db.scalar(select(func.coalesce(func.sum(SeedingRun.bans), 0))) or 0,
        "complaints": db.scalar(select(func.coalesce(func.sum(SeedingRun.complaints), 0))) or 0,
    }
    return {
        "campaigns": [_campaign_payload(campaign) for campaign in campaigns],
        "assets": [_asset_payload(asset) for asset in assets],
        "traffic_sources": [_traffic_source_payload(source) for source in sources],
        "seeding_runs": [_seeding_run_payload(run) for run in runs],
        "totals": totals,
        "safety": {
            "publishing": "manual_only",
            "forbidden": ["guaranteed income claims", "bought contact bases", "mass unsolicited invites", "ban evasion"],
            "allowed": ["manual contextual comments", "landing posts", "offer tests", "daily metrics"],
        },
    }


@router.get("", response_model=None)
def growth_dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    return _build_summary(db)


@router.post("/bootstrap", response_model=None)
def bootstrap_growth(db: Session = Depends(get_db)) -> dict[str, Any]:
    channel = _ensure_scheme_day_channel(db)
    campaign = _ensure_campaign(db, channel)
    traffic_sources = _ensure_traffic_sources(db)
    if not db.execute(select(FunnelAsset).where(FunnelAsset.campaign_id == campaign.id)).first():
        _create_asset(
            db,
            campaign,
            asset_type="pinned_intro",
            title="Закреп: Схема дня",
            text=(
                "Тут не обещают легкие 300к. Тут разбирают, где они вообще появляются.\n\n"
                "Каждый день берем одну денежную тему и раскладываем: где берется трафик, что продают, "
                "сколько там грязными, где банят, где разводят новичков и что можно повторить маленькими руками."
            ),
            target_url="",
            cta="Остаться в канале и смотреть ежедневные разборы.",
        )
    log_activity(
        db,
        actor_type="operator",
        actor_id=None,
        event_type="growth_bootstrap",
        entity_type="growth_campaign",
        entity_id=campaign.id,
        message="Growth-контур Схема дня создан/обновлен.",
        metadata={"channel_id": channel.id, "traffic_sources": len(traffic_sources)},
    )
    db.commit()
    return _build_summary(db)


@router.post("/campaigns/{campaign_id}/generate-pack", response_model=None)
def generate_growth_pack(campaign_id: int, payload: GeneratePackRequest | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = payload or GeneratePackRequest()
    campaign = db.get(GrowthCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Growth campaign not found")
    channel = campaign.target_channel or _ensure_scheme_day_channel(db)
    selected = next((item for item in DAILY_TOPICS if payload.topic and payload.topic.lower() in item["title"].lower()), DAILY_TOPICS[date.today().toordinal() % len(DAILY_TOPICS)])
    title = payload.topic or selected["title"]
    hook = selected["hook"]
    target_url = payload.target_url.strip()
    post: Post | None = None
    if payload.create_post:
        post = Post(
            channel_id=channel.id,
            title=title[:300],
            body=_post_text_for_topic(title, hook),
            source_urls=[],
            post_type="GROWTH_LEAD_MAGNET",
            status="draft",
            risk_score=0.25,
            quality_score=70,
            status_reason="Growth draft generated for manual review and seeding.",
            risk_reason="No guaranteed income claim; manual seeding only.",
            quality_reason="Lead-magnet format: hook, mechanics, risk, CTA.",
            created_by_agent="growth_director",
            generation_mode="template",
            provider="template",
            model="growth-pack-v1",
            publishable=False,
            non_publishable_reason="Manual review required before any public posting.",
            structured_outputs_json={"growth_campaign_id": campaign.id, "angle": selected["angle"], "hook": hook},
        )
        db.add(post)
        db.flush()
    landing = _create_asset(
        db,
        campaign,
        asset_type="landing_post",
        title=title,
        text=_post_text_for_topic(title, hook),
        target_url=target_url,
        post_id=post.id if post else None,
        cta="Читать разбор в MAX и подписаться на ежедневные схемы.",
    )
    comments = []
    display_url = target_url or "[ссылка на MAX-пост]"
    for text in SEED_COMMENTS[: payload.comments_count]:
        comments.append(
            _create_asset(
                db,
                campaign,
                asset_type="seed_comment",
                title=f"Вброс: {title[:80]}",
                text=text.format(url=display_url),
                target_url=target_url,
                platform="mixed",
                cta="Перевести в конкретный разбор, не в общий спам.",
            )
        )
    log_activity(
        db,
        actor_type="agent",
        actor_id=None,
        event_type="growth_pack_generated",
        entity_type="growth_campaign",
        entity_id=campaign.id,
        message=f"Generated growth pack for {campaign.name}: {title}",
        metadata={"post_id": post.id if post else None, "asset_ids": [landing.id] + [asset.id for asset in comments]},
    )
    db.commit()
    return {"post_id": post.id if post else None, "landing_asset": _asset_payload(landing), "seed_comments": [_asset_payload(asset) for asset in comments], "dashboard": _build_summary(db)}


@router.post("/seeding-runs", response_model=None)
def record_seeding_run(payload: SeedingRunCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    campaign = db.get(GrowthCampaign, payload.campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Growth campaign not found")
    run = SeedingRun(**payload.model_dump())
    db.add(run)
    db.flush()
    log_activity(
        db,
        actor_type="operator",
        actor_id=None,
        event_type="seeding_run_recorded",
        entity_type="growth_campaign",
        entity_id=campaign.id,
        message=f"Seeding run recorded: {run.placements_count} placements, {run.joins} joins.",
        metadata={"run_id": run.id, "clicks": run.link_clicks, "bans": run.bans, "complaints": run.complaints},
    )
    db.commit()
    return {"seeding_run": _seeding_run_payload(run), "dashboard": _build_summary(db)}
