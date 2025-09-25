from fastapi import APIRouter
from ..logging_setup import get_logger
from ..store import get_session
from ..models import Feedback, UserPrefs
from ..schema import FeedbackIn
from ..ranker import apply_feedback

logger = get_logger("quantum_daily.routes.feedback")

router = APIRouter(prefix="/feedback")

@router.post("")
def post_feedback(body: FeedbackIn):
    logger.info(f"Feedback received: article={body.article_id} signal={body.signal} aspect={body.aspect}")
    with get_session() as s:
        s.add(Feedback(article_id=body.article_id, signal=body.signal, aspect=body.aspect))
        s.commit()
        prefs = s.exec(select(UserPrefs)).first()
        prefs = apply_feedback(prefs, [body])
        s.add(prefs); s.commit()
    return {"ok": True}
