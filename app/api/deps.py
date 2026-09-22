from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.blockchain.base import BlockchainService
from app.services.blockchain.local_hash_chain import LocalHashChainBlockchainService
from app.services.deepfake.base import DeepfakeProvider
from app.services.deepfake.advanced_provider import AdvancedDeepfakeProvider
from app.services.face.base import FaceDetector, FaceProvider
from app.services.face.blazeface_detector import BlazeFaceDetector
from app.services.face.mobilefacenet_provider import MobileFaceNetProvider
from app.services.liveness.base import LivenessProvider
from app.services.liveness.advanced_provider import AdvancedLivenessProvider
from app.services.ocr.base import OCRProvider
from app.services.ocr.paddleocr_provider import PaddleOCRProvider
from app.services.risk.base import RiskEngine
from app.services.risk.engine import DefaultRiskEngine
from app.services.tampering.base import TamperingProvider
from app.services.tampering.forensics_provider import ComprehensiveForensicsProvider
from app.services.validation.base import ValidationEngine
from app.services.validation.engine import DefaultValidationEngine


@lru_cache
def get_ocr_provider() -> OCRProvider:
    return PaddleOCRProvider()


@lru_cache
def get_validation_engine() -> ValidationEngine:
    return DefaultValidationEngine()


@lru_cache
def get_tampering_provider() -> TamperingProvider:
    return ComprehensiveForensicsProvider()


@lru_cache
def get_face_provider() -> FaceProvider:
    return MobileFaceNetProvider()


@lru_cache
def get_face_detector() -> FaceDetector:
    return BlazeFaceDetector()


@lru_cache
def get_risk_engine() -> RiskEngine:
    return DefaultRiskEngine()


@lru_cache
def get_deepfake_provider() -> DeepfakeProvider:
    return AdvancedDeepfakeProvider()


@lru_cache
def get_liveness_provider() -> LivenessProvider:
    return AdvancedLivenessProvider()


def get_blockchain_service(db: Session = Depends(get_db)) -> BlockchainService:
    return LocalHashChainBlockchainService(db)
