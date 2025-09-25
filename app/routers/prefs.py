from fastapi import APIRouter
from ..logging_setup import get_logger
from ..store import get_session
from ..models import UserPrefs
from ..schema import PrefsIn
from sqlmodel import select

logger = get_logger("quantum_daily.routes.prefs")

router = APIRouter(prefix="/prefs")

@router.post("")
def update_prefs(body: PrefsIn):
    logger.info("Updating preferences")
    with get_session() as s:
        prefs = s.exec(select(UserPrefs)).first() or UserPrefs()
        if body.industry_weight is not None and body.tech_weight is not None:
            total = max(1e-6, body.industry_weight + body.tech_weight)
            prefs.industry_weight = body.industry_weight / total
            prefs.tech_weight = body.tech_weight / total
        if body.email is not None:
            prefs.email = body.email
        if body.send_hour_local is not None:
            prefs.send_hour_local = int(body.send_hour_local)
        s.add(prefs); s.commit()
    return {"ok": True}
