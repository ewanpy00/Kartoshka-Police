from fastapi import APIRouter, Depends

from app import watch
from app.admin import cases
from app.auth import require_write_token
from app.evidence import routes as evidence_routes
from app.graph import routes as graph_routes
from app.helplines import routes as helplines_routes
from app.takedown import routes as takedown_routes

router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_write_token)])

for module in (evidence_routes, cases, graph_routes, takedown_routes, helplines_routes, watch):
    router.include_router(module.router)
