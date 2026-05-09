from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import Channel
from app.schemas.channel import ChannelCreate, ChannelRead, ChannelUpdate
from app.services.org import log_activity

router = APIRouter()


@router.get("", response_model=list[ChannelRead])
def list_channels(db: Session = Depends(get_db)) -> list[Channel]:
    return list(db.execute(select(Channel).order_by(Channel.id)).scalars())


@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db)) -> Channel:
    channel = Channel(**payload.model_dump())
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/{channel_id}", response_model=ChannelRead)
def get_channel(channel_id: int, db: Session = Depends(get_db)) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelRead)
def update_channel(channel_id: int, payload: ChannelUpdate, db: Session = Depends(get_db)) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(channel, key, value)
    if channel.publish_mode == "auto":
        channel.auto_publish_enabled = False
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="channel_updated",
        entity_type="channel",
        entity_id=channel.id,
        message=f"Channel updated: {channel.name}",
    )
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(channel_id: int, db: Session = Depends(get_db)) -> None:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    log_activity(
        db,
        actor_type="human",
        actor_id=None,
        event_type="channel_deleted",
        entity_type="channel",
        entity_id=channel.id,
        message=f"Channel deleted: {channel.name}",
    )
    db.delete(channel)
    db.commit()
