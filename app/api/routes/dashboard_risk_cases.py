"""Dashboard API for displaying risk cases when officers scan documents"""

import base64
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from pydantic import BaseModel


class RiskCaseResponse(BaseModel):
    """Risk case for dashboard display"""
    case_id: str
    officer_name: str
    checkpoint: str
    timestamp: datetime
    risk_level: str  # LOW, MEDIUM, HIGH
    overall_status: str  # VERIFIED, REVIEW_REQUIRED, REJECTED
    person_name: str
    document_type: str
    document_number: str
    nationality: str

    # Risk indicators
    face_match_similarity: Optional[float]
    face_match_status: str
    liveness_status: str
    deepfake_status: str
    tampering_risk: Optional[float]

    # Images (base64 encoded for dashboard display)
    document_image: Optional[str]
    selfie_image: Optional[str]

    # Key issues
    primary_concerns: List[str]
    officer_actions_required: List[str]

    # Status flags
    reviewed: bool = False
    resolved: bool = False
    escalated: bool = False


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_cases_today: int
    high_risk_cases: int
    medium_risk_cases: int
    pending_review: int
    cases_last_hour: int
    top_risk_types: List[Dict[str, Any]]


router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# In-memory storage for demo purposes (in production, use database)
risk_cases_storage: List[Dict[str, Any]] = []


@router.post("/risk-case", summary="Store a new risk case for dashboard display")
async def store_risk_case(
    case_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Store a risk case when officer scans document and risk is detected"""

    # Add timestamp
    case_data['timestamp'] = datetime.now().isoformat()
    case_data['case_id'] = f"CASE_{len(risk_cases_storage) + 1:06d}"
    case_data['reviewed'] = False
    case_data['resolved'] = False
    case_data['escalated'] = False

    # Store in memory (in production, save to database)
    risk_cases_storage.append(case_data)

    return {"status": "success", "case_id": case_data['case_id']}


@router.get("/risk-cases", response_model=List[RiskCaseResponse])
async def get_risk_cases(
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    hours: int = Query(24, description="Cases from last N hours"),
    limit: int = Query(50, description="Maximum number of cases"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get risk cases for dashboard display"""

    # Filter cases by time
    cutoff_time = datetime.now() - timedelta(hours=hours)

    filtered_cases = []
    for case in risk_cases_storage:
        case_time = datetime.fromisoformat(case['timestamp'])

        if case_time >= cutoff_time:
            # Apply risk level filter if specified
            if risk_level is None or case.get('risk_level') == risk_level:
                filtered_cases.append(case)

    # Sort by timestamp (newest first)
    filtered_cases.sort(key=lambda x: x['timestamp'], reverse=True)

    # Limit results
    return filtered_cases[:limit]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics"""

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_ago = now - timedelta(hours=1)

    # Count cases
    total_today = 0
    high_risk = 0
    medium_risk = 0
    pending_review = 0
    last_hour = 0
    risk_types = {}

    for case in risk_cases_storage:
        case_time = datetime.fromisoformat(case['timestamp'])

        if case_time >= today_start:
            total_today += 1

            risk_level = case.get('risk_level', 'LOW')
            if risk_level == 'HIGH':
                high_risk += 1
            elif risk_level == 'MEDIUM':
                medium_risk += 1

            if not case.get('reviewed', False):
                pending_review += 1

            # Count risk types
            for concern in case.get('primary_concerns', []):
                risk_types[concern] = risk_types.get(concern, 0) + 1

        if case_time >= hour_ago:
            last_hour += 1

    # Convert risk types to list
    top_risk_types = [
        {"type": k, "count": v}
        for k, v in sorted(risk_types.items(), key=lambda x: x[1], reverse=True)
    ][:5]

    return DashboardStats(
        total_cases_today=total_today,
        high_risk_cases=high_risk,
        medium_risk_cases=medium_risk,
        pending_review=pending_review,
        cases_last_hour=last_hour,
        top_risk_types=top_risk_types
    )


@router.post("/risk-cases/{case_id}/review", summary="Mark case as reviewed")
async def mark_case_reviewed(
    case_id: str,
    review_notes: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a risk case as reviewed by an officer"""

    for case in risk_cases_storage:
        if case['case_id'] == case_id:
            case['reviewed'] = True
            case['reviewed_by'] = user.username
            case['reviewed_at'] = datetime.now().isoformat()
            case['review_notes'] = review_notes
            return {"status": "success", "message": "Case marked as reviewed"}

    return {"status": "error", "message": "Case not found"}


@router.post("/risk-cases/{case_id}/resolve", summary="Resolve a risk case")
async def resolve_case(
    case_id: str,
    resolution: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resolve a risk case"""

    for case in risk_cases_storage:
        if case['case_id'] == case_id:
            case['resolved'] = True
            case['resolved_by'] = user.username
            case['resolved_at'] = datetime.now().isoformat()
            case['resolution'] = resolution
            return {"status": "success", "message": "Case resolved"}

    return {"status": "error", "message": "Case not found"}