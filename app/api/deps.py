from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.blockchain.base import BlockchainService
from app.services.blockchain.local_hash_chain import LocalHashChainBlockchainService
from app.services.deepfake.base import DeepfakeProvider
from app.services.deepfake.heuristic_provider import HeuristicDeepfakeProvider
from app.services.face.base import FaceProvider
from app.services.face.classical_provider import ClassicalFaceProvider
from app.services.liveness.base import LivenessProvider
from app.services.liveness.heuristic_provider import HeuristicLivenessProvider
from app.services.ocr.base import OCRProvider
from app.services.ocr.tesseract_provider import TesseractOCRProvider
from app.services.risk.base import RiskEngine
from app.services.risk.engine import DefaultRiskEngine
from app.services.tampering.base import TamperingProvider
from app.services.tampering.pillow_provider import ELATamperingProvider
from app.services.validation.base import ValidationEngine
from app.services.validation.engine import DefaultValidationEngine


@lru_cache
def get_ocr_provider() -> OCRProvider:
    return TesseractOCRProvider()


@lru_cache
def get_validation_engine() -> ValidationEngine:
    return DefaultValidationEngine()


@lru_cache
def get_tampering_provider() -> TamperingProvider:
    return ELATamperingProvider()


@lru_cache
def get_face_provider() -> FaceProvider:
    return ClassicalFaceProvider()


@lru_cache
def get_risk_engine() -> RiskEngine:
    return DefaultRiskEngine()


@lru_cache
def get_deepfake_provider() -> DeepfakeProvider:
    return HeuristicDeepfakeProvider()


@lru_cache
def get_liveness_provider() -> LivenessProvider:
    return HeuristicLivenessProvider()


def get_blockchain_service(db: Session = Depends(get_db)) -> BlockchainService:
    # Not lru_cache'd — needs a fresh per-request db session, unlike the
    # stateless algorithmic providers above.
    return LocalHashChainBlockchainService(db)
