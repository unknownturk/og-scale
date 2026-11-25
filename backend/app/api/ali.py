"""Routen für AliRemote."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..ali import service
from ..auth import require_key
from ..store import NotFound

router = APIRouter(prefix="/ali", dependencies=[Depends(require_key)])


def _do(action):
    try:
        action()
    except NotFound:
        raise HTTPException(404, "Nicht gefunden")
    except service.AliPlanError as exc:
        raise HTTPException(409, str(exc))
    return service.overview()


@router.get("")
def overview():
    return service.overview()


class AccountIn(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    nicheId: str
    deviceId: str


@router.post("/accounts", status_code=201)
def add_account(body: AccountIn):
    return _do(lambda: service.add_account(body.username, body.nicheId, body.deviceId))


class CreatedIn(BaseModel):
    course: Literal["pdf_v1", "native_7"]


@router.post("/accounts/{account_id}/created")
def created(account_id: str, body: CreatedIn):
    return _do(lambda: service.confirm_created(account_id, body.course))


class ArmedIn(BaseModel):
    armed: bool


@router.post("/accounts/{account_id}/armed")
def armed(account_id: str, body: ArmedIn):
    return _do(lambda: service.set_armed(account_id, body.armed))


@router.delete("/accounts/{account_id}")
def remove(account_id: str):
    return _do(lambda: service.remove_account(account_id))


class StopIn(BaseModel):
    stopped: bool


@router.post("/stop")
def stop(body: StopIn):
    service.set_stopped(body.stopped)
    return service.overview()


class ResolveIn(BaseModel):
    outcome: Literal["happened", "not_happened"]


@router.post("/slots/{slot_id}/resolve")
def resolve(slot_id: str, body: ResolveIn):
    return _do(lambda: service.resolve(slot_id, body.outcome))


@router.post("/slots/{slot_id}/replan")
def replan(slot_id: str):
    return _do(lambda: service.replan(slot_id))


@router.post("/slots/{slot_id}/skip")
def skip(slot_id: str):
    return _do(lambda: service.skip(slot_id))
