from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.db import get_db
from app.models import Roadmap, User
from app.schemas import RoadmapPayload

router = APIRouter(prefix="/api/roadmaps", tags=["roadmaps"])


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _summarize(roadmap: Roadmap) -> dict[str, Any]:
    payload = roadmap.payload or {}
    nodes = payload.get("nodes") or []
    links = payload.get("links") or []
    done_count = sum(1 for n in nodes if n.get("done"))
    return {
        "id": roadmap.id,
        "name": roadmap.name,
        "updated_at": _iso(roadmap.updated_at),
        "version": roadmap.version,
        "node_count": len(nodes),
        "link_count": len(links),
        "done_count": done_count,
    }


@router.get("")
def list_roadmaps(
    _: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> JSONResponse:
    rows = session.query(Roadmap).order_by(Roadmap.id).all()
    return JSONResponse([_summarize(roadmap) for roadmap in rows])


@router.get("/{roadmap_id}")
def get_roadmap(
    roadmap_id: int,
    _: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> JSONResponse:
    roadmap = session.get(Roadmap, roadmap_id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return JSONResponse({
        "id": roadmap.id,
        "name": roadmap.name,
        "payload": roadmap.payload,
        "updated_at": _iso(roadmap.updated_at),
        "version": roadmap.version,
    })


@router.post("")
def create_roadmap(
    data: RoadmapPayload,
    _: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> JSONResponse:
    roadmap = Roadmap(name=data.name, payload=data.payload, version=0)
    session.add(roadmap)
    session.commit()
    return JSONResponse({"id": roadmap.id, "version": 0})


@router.put("/{roadmap_id}")
def update_roadmap(
    roadmap_id: int,
    data: RoadmapPayload,
    _: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> JSONResponse:
    if data.base_version is not None:
        result = session.execute(
            sa_update(Roadmap)
            .where(Roadmap.id == roadmap_id, Roadmap.version == data.base_version)
            .values(
                name=data.name,
                payload=data.payload,
                version=Roadmap.version + 1,
                updated_at=func.current_timestamp(),
            )
        )
        session.commit()
        if result.rowcount == 0:
            if session.get(Roadmap, roadmap_id) is None:
                raise HTTPException(status_code=404, detail="Roadmap not found")
            raise HTTPException(status_code=409, detail="Roadmap изменён в другом месте, обновите страницу")
        return JSONResponse({"ok": True, "version": data.base_version + 1})
    roadmap = session.get(Roadmap, roadmap_id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    session.execute(
        sa_update(Roadmap)
        .where(Roadmap.id == roadmap_id)
        .values(
            name=data.name,
            payload=data.payload,
            version=Roadmap.version + 1,
            updated_at=func.current_timestamp(),
        )
    )
    session.commit()
    return JSONResponse({"ok": True, "version": roadmap.version + 1})


@router.delete("/{roadmap_id}")
def delete_roadmap(
    roadmap_id: int,
    _: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> JSONResponse:
    deleted = session.query(Roadmap).filter(Roadmap.id == roadmap_id).delete(synchronize_session=False)
    session.commit()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return JSONResponse({"ok": True})
