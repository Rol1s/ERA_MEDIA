from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.all_models import Post, Source, Topic
from app.services.org import log_activity
from app.services.demo import create_demo_data

router = APIRouter()


@router.post("/demo-data")
def demo_data(db: Session = Depends(get_db)) -> dict[str, int]:
    if not settings.dev_mode:
        raise HTTPException(status_code=403, detail="DEV_MODE is disabled")
    return create_demo_data(db)


@router.delete("/demo-data")
def clear_demo_data(db: Session = Depends(get_db)) -> dict[str, int]:
    if not settings.dev_mode:
        raise HTTPException(status_code=403, detail="DEV_MODE is disabled")
    post_count = db.query(Post).filter(Post.is_demo.is_(True)).delete(synchronize_session=False)
    topic_count = db.query(Topic).filter(Topic.is_demo.is_(True)).delete(synchronize_session=False)
    source_count = db.query(Source).filter(Source.is_demo.is_(True)).delete(synchronize_session=False)
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="demo_data_cleared",
        entity_type="demo",
        entity_id=None,
        message="Demo data cleared.",
        metadata={"posts": post_count, "topics": topic_count, "sources": source_count},
    )
    db.commit()
    return {"posts": post_count, "topics": topic_count, "sources": source_count}
