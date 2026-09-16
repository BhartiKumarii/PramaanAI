"""Public (no-auth) checkpoint listing — the Android login screen's
checkpoint dropdown needs this before the officer has a token. Read-only,
non-sensitive (code/name/location only), so no auth dependency here;
admin's create/manage operations stay under /admin/checkpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.checkpoint import Checkpoint
from app.schemas.admin import CheckpointResponse

router = APIRouter(prefix="/checkpoints", tags=["checkpoints"])


@router.get("", response_model=list[CheckpointResponse], summary="List active checkpoints for login/registration dropdowns")
def list_active_checkpoints(db: Session = Depends(get_db)) -> list[CheckpointResponse]:
    checkpoints = list(db.query(Checkpoint).filter(Checkpoint.is_active.is_(True)).order_by(Checkpoint.code).all())
    return [
        CheckpointResponse(id=str(c.id), code=c.code, name=c.name, location=c.location, is_active=c.is_active)
        for c in checkpoints
    ]
