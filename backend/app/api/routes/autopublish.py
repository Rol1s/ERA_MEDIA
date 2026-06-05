from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auto_publisher import publish_ready_posts

router = APIRouter()


class AutoPublishRunRequest(BaseModel):
    dry_run: bool = False


@router.post("/autopublish/run")
def run_autopublish(payload: AutoPublishRunRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    return publish_ready_posts(db, dry_run=payload.dry_run)
