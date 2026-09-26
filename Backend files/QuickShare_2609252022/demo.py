from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.demo_data import seed_demo_data

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    """
    'Demo Data' button target. Creates realistic sample lost/found reports
    (including the Block B Lenovo laptop pair from the spec) and runs the
    real matching engine over them -- scores are computed, not hard-coded.
    """
    return seed_demo_data(db)
