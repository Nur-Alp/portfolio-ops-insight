"""Demo-persona login for the self-issued 'demo' identity provider."""

from fastapi import APIRouter

from osip_dashboard import api_handlers as handlers
from osip_dashboard.api_schemas import DemoLoginResponse


router = APIRouter(tags=["auth"])

router.add_api_route(
    "/auth/demo-login",
    handlers.demo_login,
    methods=["POST"],
    response_model=DemoLoginResponse,
    summary="Exchange demo-persona credentials for a session token",
    operation_id="demoLogin",
)
