"""Alle Routen für Models, Nischen und Aufträge."""

from fastapi import APIRouter, Depends, HTTPException

from .. import jobs, llm
from ..auth import require_key
from ..niches import service as niches
from ..store import CONTENT, MODELS, NICHES, NotFound, get_store
from . import schemas

router = APIRouter(dependencies=[Depends(require_key)])


def _get(table, record_id):
    try:
        return get_store().get(table, record_id)
    except NotFound:
        raise HTTPException(404, "Nicht gefunden")


def _need_llm():
    if not llm.configured():
        raise HTTPException(503, "Die KI ist nicht eingerichtet (OPENROUTER_API_KEY fehlt)")


# --- Aufträge: was die Hintergrundarbeit wirklich tut -----------------------
@jobs.handler("niches_generate")
def _job_generate(payload):
    created = niches.generate(payload["modelId"], payload["count"])
    return {"nicheIds": [n["id"] for n in created], "count": len(created)}


@jobs.handler("niche_from_brief")
def _job_brief(payload):
    created = niches.generate_from_brief(payload["modelId"], payload["brief"])
    return {"nicheIds": [created["id"]], "count": 1}


@jobs.handler("niche_improve")
def _job_improve(payload):
    return {"nicheId": payload["nicheId"], "proposal": niches.propose_improvement(payload["nicheId"], payload["hint"])}


# --- Models -----------------------------------------------------------------
@router.get("/models")
def list_models():
    store = get_store()
    counts = {}
    for niche in store.list(NICHES):
        bucket = counts.setdefault(niche["modelId"], {"Proposed": 0, "Approved": 0, "Rejected": 0})
        bucket[niche.get("status") or "Proposed"] = bucket.get(niche.get("status") or "Proposed", 0) + 1
    return [{**m, "nicheCounts": counts.get(m["id"], {"Proposed": 0, "Approved": 0, "Rejected": 0})} for m in store.list(MODELS)]


@router.post("/models", status_code=201)
def create_model(body: schemas.ModelIn):
    return get_store().create(MODELS, body.model_dump())


@router.get("/models/{model_id}")
def get_model(model_id: str):
    return _get(MODELS, model_id)


@router.patch("/models/{model_id}")
def update_model(model_id: str, body: schemas.ModelPatch):
    _get(MODELS, model_id)
    return get_store().update(MODELS, model_id, body.model_dump(exclude_none=True))


@router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: str):
    _get(MODELS, model_id)
    if get_store().list(NICHES, {"modelId": model_id}):
        raise HTTPException(409, "Dieses Model hat noch Nischen. Lösche zuerst die Nischen.")
    if get_store().list(CONTENT, {"modelId": model_id}):
        raise HTTPException(409, "Dieses Model hat noch Content. Lösche zuerst den Content.")
    get_store().delete(MODELS, model_id)


# --- Nischen ----------------------------------------------------------------
@router.get("/models/{model_id}/niches")
def list_niches(model_id: str):
    _get(MODELS, model_id)
    return get_store().list(NICHES, {"modelId": model_id})


@router.post("/models/{model_id}/niches/generate", status_code=202)
def generate_niches(model_id: str, body: schemas.GenerateIn):
    _get(MODELS, model_id)
    _need_llm()
    return jobs.start("niches_generate", {"modelId": model_id, "count": body.count}, subject=model_id)


@router.post("/models/{model_id}/niches/from-brief", status_code=202)
def niche_from_brief(model_id: str, body: schemas.BriefIn):
    _get(MODELS, model_id)
    _need_llm()
    return jobs.start("niche_from_brief", {"modelId": model_id, "brief": body.brief}, subject=model_id)


@router.get("/niches/{niche_id}")
def get_niche(niche_id: str):
    return _get(NICHES, niche_id)


@router.patch("/niches/{niche_id}")
def update_niche(niche_id: str, body: schemas.NichePatch):
    _get(NICHES, niche_id)
    return get_store().update(NICHES, niche_id, body.model_dump(exclude_none=True))


@router.post("/niches/{niche_id}/status")
def set_status(niche_id: str, body: schemas.StatusIn):
    _get(NICHES, niche_id)
    return get_store().update(NICHES, niche_id, {"status": body.status})


@router.post("/niches/{niche_id}/improve", status_code=202)
def improve_niche(niche_id: str, body: schemas.ImproveIn):
    niche = _get(NICHES, niche_id)
    _need_llm()
    return jobs.start("niche_improve", {"nicheId": niche_id, "hint": body.hint}, subject=niche["modelId"])


@router.delete("/niches/{niche_id}", status_code=204)
def delete_niche(niche_id: str):
    _get(NICHES, niche_id)
    if get_store().list(CONTENT, {"nicheId": niche_id}):
        raise HTTPException(409, "Aus dieser Nische ist schon Content entstanden. Lehne sie ab, statt sie zu löschen.")
    get_store().delete(NICHES, niche_id)


# --- Aufträge ---------------------------------------------------------------
@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Auftrag nicht gefunden")
    return job


@router.get("/jobs")
def active_jobs(subject: str = ""):
    return jobs.active(subject or None)
