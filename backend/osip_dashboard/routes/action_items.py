"""Operational action items - risk breach exceptions, accounting close steps,
and future domain to-dos. See ActionItem's docstring in persistence/models.py
for why this is a separate model from the DQ issue models.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from osip_dashboard.api_schemas import (
    ActionItemAssignRequest,
    ActionItemCreateRequest,
    ActionItemListResponse,
    ActionItemReopenRequest,
    ActionItemResolveRequest,
    ActionItemResponse,
)
from osip_dashboard.identity import get_actor, require_domain, require_role
from osip_dashboard.services.action_items import (
    action_item_payload,
    assign_action_item,
    create_action_item,
    get_action_item,
    list_action_items,
    reopen_action_item,
    resolve_action_item,
)
from osip_dashboard.services.workflow import Actor


router = APIRouter(tags=["action-items"])


def _session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(_session)]
ActorDep = Annotated[Actor, Depends(get_actor)]


def _get_or_404(session: Session, item_id: UUID):
    item = get_action_item(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Пункт не найден")
    return item


def _get_authorized_or_404(session: Session, actor: Actor, item_id: UUID):
    """Load an action item and enforce its domain scope in one call - use
    this everywhere a single item needs to be fetched by id, instead of
    chaining ``_get_or_404``/``require_domain`` by hand. See the identical
    reasoning on ``_load_authorized_dataset`` in routes/multi_source.py.
    """
    item = _get_or_404(session, item_id)
    require_domain(actor, item.domain)
    return item


@router.post("/action-items", response_model=ActionItemResponse, status_code=201, operation_id="createActionItem")
def create_item(body: ActionItemCreateRequest, session: SessionDep, actor: ActorDep):
    require_role(actor, "reviewer")
    require_domain(actor, body.domain)
    item = create_action_item(
        session,
        domain=body.domain,
        kind=body.kind,
        title=body.title,
        created_by=actor.actor_id,
        dataset_type=body.dataset_type,
        scope_code=body.scope_code,
        reference_key=body.reference_key,
    )
    session.commit()
    return action_item_payload(item)


@router.get("/action-items", response_model=ActionItemListResponse, operation_id="listActionItems")
def list_items(
    session: SessionDep,
    actor: ActorDep,
    domain: str | None = Query(default=None),
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None),
):
    require_role(actor, "reader")
    require_domain(actor, domain)
    items = list_action_items(session, domain=domain, status=status, kind=kind)
    if domain is None and "*" not in actor.domains:
        items = [item for item in items if item.domain in actor.domains]
    return {"items": [action_item_payload(item) for item in items]}


@router.get("/action-items/{item_id}", response_model=ActionItemResponse, operation_id="getActionItem")
def get_item(item_id: UUID, session: SessionDep, actor: ActorDep):
    require_role(actor, "reader")
    item = _get_authorized_or_404(session, actor, item_id)
    return action_item_payload(item)


@router.post("/action-items/{item_id}/assign", response_model=ActionItemResponse, operation_id="assignActionItem")
def assign_item(item_id: UUID, body: ActionItemAssignRequest, session: SessionDep, actor: ActorDep):
    require_role(actor, "reviewer")
    item = _get_authorized_or_404(session, actor, item_id)
    try:
        due_date = date.fromisoformat(body.due_date) if body.due_date else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Некорректная дата срока устранения") from exc
    try:
        assign_action_item(
            session, item,
            owner_id=body.owner_id, due_date=due_date, reason=body.reason, actor_id=actor.actor_id,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return action_item_payload(item)


@router.post("/action-items/{item_id}/resolve", response_model=ActionItemResponse, operation_id="resolveActionItem")
def resolve_item(item_id: UUID, body: ActionItemResolveRequest, session: SessionDep, actor: ActorDep):
    require_role(actor, "reviewer")
    item = _get_authorized_or_404(session, actor, item_id)
    try:
        resolve_action_item(session, item, comment=body.comment, actor_id=actor.actor_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return action_item_payload(item)


@router.post("/action-items/{item_id}/reopen", response_model=ActionItemResponse, operation_id="reopenActionItem")
def reopen_item(item_id: UUID, body: ActionItemReopenRequest, session: SessionDep, actor: ActorDep):
    require_role(actor, "reviewer")
    item = _get_authorized_or_404(session, actor, item_id)
    try:
        reopen_action_item(session, item, reason=body.reason, actor_id=actor.actor_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return action_item_payload(item)
