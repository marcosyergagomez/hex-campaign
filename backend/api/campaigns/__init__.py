"""HTTP adapters. Lobby, invites, and the live table each have their own router."""

from fastapi import APIRouter

from api.campaigns.invites import router as invites_router
from api.campaigns.lobby import router as lobby_router
from api.campaigns.table import router as table_router

router = APIRouter()
router.include_router(lobby_router)
router.include_router(invites_router)
router.include_router(table_router)
