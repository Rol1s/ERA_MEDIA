from fastapi import APIRouter

from app.api.routes import agent_runs, channels, control_plane, dashboard, dev, editions, operating_loop, org, posts, secrets, settings, source_items, sources, tasks, topics

api_router = APIRouter(prefix="/api")
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_router.include_router(editions.router, prefix="/editions", tags=["editions"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(source_items.router, prefix="/source-items", tags=["source-items"])
api_router.include_router(topics.router, prefix="/topics", tags=["topics"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(agent_runs.router, prefix="/agent-runs", tags=["agent-runs"])
api_router.include_router(dev.router, prefix="/dev", tags=["dev"])
api_router.include_router(org.router, tags=["org"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(control_plane.router, tags=["control-plane"])
api_router.include_router(operating_loop.router, tags=["operating-loop"])
api_router.include_router(secrets.router, prefix="/secrets", tags=["secrets"])
