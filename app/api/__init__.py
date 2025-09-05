from fastapi import APIRouter
from app.api.endpoints import auth, content, database, migration, social, game, search, music, admin, subscription, cache

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(content.router, prefix="/content", tags=["Content"])
api_router.include_router(game.router, prefix="/games", tags=["Games"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(social.router, prefix="/social", tags=["Social"])
api_router.include_router(database.router, prefix="/database", tags=["Database"])
api_router.include_router(migration.router, prefix="/migration", tags=["Migration"])
api_router.include_router(music.router, prefix="/music", tags=["Music"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(subscription.router, prefix="/subscription", tags=["Subscriptions"])
api_router.include_router(cache.router, prefix="/cache", tags=["Cache"])