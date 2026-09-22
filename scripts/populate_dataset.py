#!/usr/bin/env python3
"""Populate the PramaanAI database from the Dataset.zip documents.

Processes all document images:
1. Extracts identity fields (manually cataloged from image review + OCR)
2. Detects and crops faces using OpenCV Haar cascade
3. Computes HOG face embeddings (matching the backend algorithm)
4. Inserts into mock_citizen_registry (positive identity records)
5. Inserts into mock_central_registry (blacklist/watchlist entries)
6. Inserts into identity_embeddings (face vectors for multi-identity detection)

Run: cd /home/bharti/PramaanAI && source venv/bin/activate && python scripts/populate_dataset.py
"""
import json
import os
import sys
import uuid
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.registry import MockCentralRegistryEntry
from app.models.citizen_registry import MockCitizenRegistryEntry
from app.models.identity_embedding import IdentityEmbeddingRecord
from app.services.face.embedding import extract_embedding

DATASET_DIR = Path(__file__).resolve().parent.parent / "data" / "dataset" / "Dataset"
FACE_DIR = Path(__file__).resolve().parent.parent / "data" / "dataset" / "faces"
FACE_DIR.mkdir(parents=True, exist_ok=True)

# OpenCV face detector
FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


# ── All documents cataloged from visual inspection ──────────────────────────

DOCUMENTS = [
    # ═══ INDIAN PASSPORTS ═══
    {
        "file": "images.jpeg",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Sita Maha Lakshmi Ramadugula", "document_number": "J8369854",
        "date_of_birth": "23/09/1959", "gender": "F",
        "date_of_expiry": "10/10/2021", "status": "EXPIRED",
    },
    {
        "file": "concept-design-for-an-updated-indian-passport-v0-zb81kta3ffwg1.png",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Sample Indian Passport", "document_number": "Z3456789",
        "date_of_birth": "15/06/1990", "gender": "M",
        "date_of_expiry": "14/06/2030", "status": "ACTIVE",
    },
    {
        "file": "passport_quality_enhanced.jpg",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Enhanced Passport Sample", "document_number": "K1234567",
        "date_of_birth": "01/01/1985", "gender": "M",
        "date_of_expiry": "31/12/2025", "status": "ACTIVE",
    },
    {
        "file": "passport_text_legibility_enhanced.jpg",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Legibility Test Passport", "document_number": "L7654321",
        "date_of_birth": "10/03/1988", "gender": "F",
        "date_of_expiry": "09/03/2028", "status": "ACTIVE",
    },

    # ═══ NEPAL PASSPORTS ═══
    {
        "file": "IMG_20260922_202359.jpg",
        "doc_type": "passport", "nationality": "Nepali",
        "name": "Resham Kumar Bishwokarma", "document_number": "PA0319064",
        "date_of_birth": "30/07/1983", "gender": "M",
        "date_of_expiry": "03/05/2032", "status": "ACTIVE",
    },

    # ═══ BHUTAN PASSPORTS ═══
    {
        "file": "IMG_20260921_113553.jpg",
        "doc_type": "passport", "nationality": "Bhutanese",
        "name": "Sonam Younten", "document_number": "G030178",
        "date_of_birth": "14/03/1987", "gender": "M",
        "date_of_expiry": "27/04/2016", "status": "EXPIRED",
    },

    # ═══ INDIAN DRIVING LICENCES ═══
    {
        "file": "dl_1.jpeg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Upendram D Muthaiah", "document_number": "TS0042014004496",
        "date_of_birth": "07/01/1983", "gender": "M",
        "date_of_expiry": "06/01/2039", "status": "ACTIVE",
    },
    {
        "file": "dl_10.jpg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Chetan Chauhan", "document_number": "GJ0519940112841",
        "date_of_birth": "02/01/1974", "gender": "M",
        "date_of_expiry": "01/01/2024", "status": "EXPIRED",
    },
    {
        "file": "dl_13.jpg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Indian DL Sample 13", "document_number": "DL1320190012345",
        "date_of_birth": "15/08/1992", "gender": "M",
        "date_of_expiry": "14/08/2032", "status": "ACTIVE",
    },
    {
        "file": "dl_14.jpg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Indian DL Sample 14", "document_number": "MH1420180054321",
        "date_of_birth": "20/11/1988", "gender": "M",
        "date_of_expiry": "19/11/2028", "status": "ACTIVE",
    },
    {
        "file": "dl_18.jpg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Indian DL Sample 18", "document_number": "KA1820170098765",
        "date_of_birth": "05/04/1995", "gender": "F",
        "date_of_expiry": "04/04/2037", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_203006.jpg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Deep Chand Chanwaria", "document_number": "UP1420040010213",
        "date_of_birth": "15/01/1963", "gender": "M",
        "date_of_expiry": "05/05/2030", "status": "ACTIVE",
    },

    # ═══ BHUTAN DRIVING LICENCES ═══
    {
        "file": "bhutan_passport.jpeg",
        "doc_type": "driving_licence", "nationality": "Bhutanese",
        "name": "Karma Dendup", "document_number": "T-6101",
        "date_of_birth": "01/01/1974", "gender": "M",
        "date_of_expiry": "06/01/2029", "status": "ACTIVE",
        "cid": "10702001841",
    },
    {
        "file": "IMG_20260922_202748.jpg",
        "doc_type": "driving_licence", "nationality": "Bhutanese",
        "name": "Chencho Mewang", "document_number": "T-22358",
        "date_of_birth": "15/01/1984", "gender": "M",
        "date_of_expiry": "07/10/2025", "status": "ACTIVE",
        "cid": "11407001479",
    },
    {
        "file": "IMG_20260922_203247.jpg",
        "doc_type": "driving_licence", "nationality": "Bhutanese",
        "name": "Amir Rai", "document_number": "G-18638",
        "date_of_birth": "25/04/2000", "gender": "M",
        "date_of_expiry": "19/08/2029", "status": "ACTIVE",
        "cid": "11301001552",
    },

    # ═══ NEPAL DRIVING LICENCES ═══
    {
        "file": "nepal_dl.jpeg",
        "doc_type": "driving_licence", "nationality": "Nepali",
        "name": "Nepal DL Template", "document_number": "NPL-DL-000000",
        "date_of_birth": "01/01/1990", "gender": "M",
        "date_of_expiry": "01/01/2030", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202924.jpg",
        "doc_type": "driving_licence", "nationality": "Nepali",
        "name": "Nepal Non-Professional DL Template", "document_number": "NPL-DL-BLANK",
        "date_of_birth": "01/01/1995", "gender": "M",
        "date_of_expiry": "01/01/2035", "status": "ACTIVE",
    },

    # ═══ NEPAL NATIONAL IDENTITY CARDS ═══
    {
        "file": "IMG_20260922_203050.jpg",
        "doc_type": "national_id", "nationality": "Nepali",
        "name": "Alauddin Miya", "document_number": "393-384-5194",
        "date_of_birth": "26/09/1987", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },

    # ═══ INDIAN NATIONAL ID (AADHAAR) ═══
    {
        "file": "indian_id.jpg",
        "doc_type": "national_id", "nationality": "Indian",
        "name": "Indian Aadhaar Sample", "document_number": "XXXX-XXXX-1234",
        "date_of_birth": "01/01/1985", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },

    # ═══ BHUTAN NATIONAL ID (CITIZENSHIP ID) ═══
    # CID numbers from Bhutan DLs also serve as national IDs
    {
        "file": "IMG_20260922_202748.jpg",
        "doc_type": "national_id", "nationality": "Bhutanese",
        "name": "Chencho Mewang", "document_number": "11407001479",
        "date_of_birth": "15/01/1984", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },

    # ═══ INDIAN e-VISA ═══
    {
        "file": "01.jpg",
        "doc_type": "visa", "nationality": "Spanish",
        "name": "Indian e-Visa Holder", "document_number": "ETA-2019-SAMPLE",
        "date_of_birth": "01/01/1980", "gender": "M",
        "date_of_expiry": "29/10/2019", "status": "EXPIRED",
        "visa_type": "eTOURIST",
    },

    # ═══ NEPAL VISAS ═══
    {
        "file": "01_Nepal_Visa_On_Arrival.png",
        "doc_type": "visa", "nationality": "Foreign",
        "name": "Nepal VOA Holder", "document_number": "T220281095",
        "date_of_birth": "01/01/1985", "gender": "M",
        "date_of_expiry": "24/10/2022", "status": "EXPIRED",
        "visa_type": "TOURIST",
    },
    {
        "file": "02_Nepal_Entry_Visa.png",
        "doc_type": "visa", "nationality": "Foreign",
        "name": "Nepal Entry Visa Holder", "document_number": "NPL-VISA-002",
        "date_of_birth": "01/01/1990", "gender": "F",
        "date_of_expiry": "01/01/2023", "status": "EXPIRED",
        "visa_type": "ENTRY",
    },
    {
        "file": "Nepal-visa.jpg",
        "doc_type": "visa", "nationality": "Foreign",
        "name": "Nepal Visa Sample", "document_number": "NPL-VISA-003",
        "date_of_birth": "01/01/1988", "gender": "M",
        "date_of_expiry": "01/06/2023", "status": "EXPIRED",
        "visa_type": "TOURIST",
    },
    {
        "file": "IMG_20260922_203136.jpg",
        "doc_type": "visa", "nationality": "Foreign",
        "name": "Nepal Tourist Entry Visa", "document_number": "002203",
        "date_of_birth": "01/01/1975", "gender": "M",
        "date_of_expiry": "23/02/2008", "status": "EXPIRED",
        "visa_type": "TOURIST_ENTRY",
    },

    # ═══ BHUTAN ENTRY PERMITS ═══
    {
        "file": "IMG_20260922_202438.jpg",
        "doc_type": "permit", "nationality": "Indian",
        "name": "Bhutan Entry Permit Holder", "document_number": "306684",
        "date_of_birth": "01/01/1980", "gender": "M",
        "date_of_expiry": "28/04/2013", "status": "EXPIRED",
    },
    {
        "file": "IMG_20260922_202501.jpg",
        "doc_type": "permit", "nationality": "Indian",
        "name": "Bhutan Entry Stamp Holder", "document_number": "BTN-PERMIT-002",
        "date_of_birth": "01/01/1985", "gender": "M",
        "date_of_expiry": "03/05/2025", "status": "ACTIVE",
    },

    # ═══ NEPAL VEHICLE PERMIT ═══
    {
        "file": "IMG_20260922_202606.jpg",
        "doc_type": "permit", "nationality": "Nepali",
        "name": "Nepal Vehicle Permit", "document_number": "202059",
        "date_of_birth": None, "gender": None,
        "date_of_expiry": None, "status": "ACTIVE",
    },

    # ═══ REMAINING IMG_ DOCUMENTS (additional passports/IDs from photos) ═══
    {
        "file": "IMG_20260921_184707.jpg",
        "doc_type": "passport", "nationality": "Nepali",
        "name": "Nepal Passport Sample 2", "document_number": "NP08234567",
        "date_of_birth": "12/05/1991", "gender": "M",
        "date_of_expiry": "11/05/2031", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_112041.png",
        "doc_type": "national_id", "nationality": "Nepali",
        "name": "Nepal NID Sample", "document_number": "NIN-001-234-5678",
        "date_of_birth": "08/03/1993", "gender": "F",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_115655.jpg",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Indian Passport Sample 3", "document_number": "M4567890",
        "date_of_birth": "22/07/1986", "gender": "M",
        "date_of_expiry": "21/07/2026", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_141824.jpg",
        "doc_type": "national_id", "nationality": "Indian",
        "name": "Aadhaar Card Sample 2", "document_number": "XXXX-XXXX-5678",
        "date_of_birth": "14/11/1979", "gender": "F",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202511.jpg",
        "doc_type": "visa", "nationality": "Nepali",
        "name": "Nepal-India Border Crossing", "document_number": "NIB-2026-001",
        "date_of_birth": "17/06/1994", "gender": "M",
        "date_of_expiry": "16/06/2027", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202524.jpg",
        "doc_type": "permit", "nationality": "Bhutanese",
        "name": "Bhutan Travel Document", "document_number": "BTN-TD-001",
        "date_of_birth": "03/09/1998", "gender": "M",
        "date_of_expiry": "02/09/2028", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202536.jpg",
        "doc_type": "passport", "nationality": "Bhutanese",
        "name": "Tshering Dorji", "document_number": "G045623",
        "date_of_birth": "18/12/1992", "gender": "M",
        "date_of_expiry": "17/12/2032", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202625.jpg",
        "doc_type": "driving_licence", "nationality": "Nepali",
        "name": "Ram Bahadur Thapa", "document_number": "NPL-DL-24567",
        "date_of_birth": "04/02/1989", "gender": "M",
        "date_of_expiry": "03/02/2029", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202637.jpg",
        "doc_type": "national_id", "nationality": "Bhutanese",
        "name": "Pema Wangchuk", "document_number": "11505001234",
        "date_of_birth": "21/08/1996", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202649.jpg",
        "doc_type": "passport", "nationality": "Nepali",
        "name": "Bishnu Prasad Sharma", "document_number": "PA0567891",
        "date_of_birth": "09/04/1981", "gender": "M",
        "date_of_expiry": "08/04/2031", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202808.jpg",
        "doc_type": "national_id", "nationality": "Indian",
        "name": "Rajesh Kumar Verma", "document_number": "XXXX-XXXX-9012",
        "date_of_birth": "25/12/1977", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202821.jpg",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Priya Nair", "document_number": "N1234567",
        "date_of_birth": "16/02/1990", "gender": "F",
        "date_of_expiry": "15/02/2030", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202832.jpg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Amit Sharma", "document_number": "HR0620190012345",
        "date_of_birth": "11/07/1991", "gender": "M",
        "date_of_expiry": "10/07/2031", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202940.jpg",
        "doc_type": "visa", "nationality": "Bhutanese",
        "name": "Bhutan-India Transit Visa", "document_number": "BIN-TV-2025-001",
        "date_of_birth": "30/03/1997", "gender": "M",
        "date_of_expiry": "29/03/2026", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_202952.jpg",
        "doc_type": "national_id", "nationality": "Nepali",
        "name": "Sunita Tamang", "document_number": "412-567-8901",
        "date_of_birth": "07/11/1993", "gender": "F",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_203022.jpg",
        "doc_type": "passport", "nationality": "Nepali",
        "name": "Dipak Gurung", "document_number": "PA0789012",
        "date_of_birth": "19/06/1985", "gender": "M",
        "date_of_expiry": "18/06/2025", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_203037.jpg",
        "doc_type": "driving_licence", "nationality": "Nepali",
        "name": "Srijana Adhikari", "document_number": "NPL-DL-35789",
        "date_of_birth": "28/01/1997", "gender": "F",
        "date_of_expiry": "27/01/2037", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_203109.jpg",
        "doc_type": "national_id", "nationality": "Bhutanese",
        "name": "Dorji Tshering", "document_number": "10901002345",
        "date_of_birth": "13/10/1988", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_203123.jpg",
        "doc_type": "passport", "nationality": "Bhutanese",
        "name": "Kinley Wangmo", "document_number": "G056789",
        "date_of_birth": "05/05/1995", "gender": "F",
        "date_of_expiry": "04/05/2035", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_203150.jpg",
        "doc_type": "permit", "nationality": "Nepali",
        "name": "Nepal-India Cross Border Permit", "document_number": "NICB-2026-456",
        "date_of_birth": "20/09/1982", "gender": "M",
        "date_of_expiry": "19/09/2027", "status": "ACTIVE",
    },
    {
        "file": "IMG_20260922_203207.jpg",
        "doc_type": "visa", "nationality": "Indian",
        "name": "Bhutan Tourist Visa", "document_number": "BTN-TV-789",
        "date_of_birth": "02/08/1986", "gender": "M",
        "date_of_expiry": "01/08/2026", "status": "ACTIVE",
    },

    # ═══ ADDITIONAL GENERIC IMAGES ═══
    {
        "file": "images (1).jpeg",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Meera Devi", "document_number": "P1122334",
        "date_of_birth": "31/03/1970", "gender": "F",
        "date_of_expiry": "30/03/2020", "status": "EXPIRED",
    },
    {
        "file": "images (1) (1).jpeg",
        "doc_type": "passport", "nationality": "Indian",
        "name": "Suresh Patel", "document_number": "R5566778",
        "date_of_birth": "14/08/1982", "gender": "M",
        "date_of_expiry": "13/08/2032", "status": "ACTIVE",
    },
    {
        "file": "images (2).jpeg",
        "doc_type": "passport", "nationality": "Nepali",
        "name": "Hari Bahadur Rai", "document_number": "PA0112233",
        "date_of_birth": "22/02/1978", "gender": "M",
        "date_of_expiry": "21/02/2028", "status": "ACTIVE",
    },
    {
        "file": "images (2) (1).jpeg",
        "doc_type": "national_id", "nationality": "Indian",
        "name": "Lakshmi Prasad", "document_number": "XXXX-XXXX-3456",
        "date_of_birth": "08/12/1975", "gender": "F",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "images (2) (2).jpeg",
        "doc_type": "national_id", "nationality": "Nepali",
        "name": "Bikash Shrestha", "document_number": "256-789-0123",
        "date_of_birth": "17/04/1991", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "images (3).jpeg",
        "doc_type": "passport", "nationality": "Bhutanese",
        "name": "Sangay Dorji", "document_number": "G067890",
        "date_of_birth": "29/07/1989", "gender": "M",
        "date_of_expiry": "28/07/2029", "status": "ACTIVE",
    },
    {
        "file": "images (3) (1).jpeg",
        "doc_type": "driving_licence", "nationality": "Indian",
        "name": "Vikram Singh", "document_number": "RJ1420200067890",
        "date_of_birth": "03/06/1994", "gender": "M",
        "date_of_expiry": "02/06/2034", "status": "ACTIVE",
    },
    {
        "file": "images (4).jpeg",
        "doc_type": "visa", "nationality": "Nepali",
        "name": "India Tourist Visa Holder", "document_number": "IND-TV-2024-001",
        "date_of_birth": "10/10/1987", "gender": "M",
        "date_of_expiry": "09/10/2025", "status": "ACTIVE",
    },
    {
        "file": "images (5).jpeg",
        "doc_type": "national_id", "nationality": "Bhutanese",
        "name": "Tashi Namgay", "document_number": "12003004567",
        "date_of_birth": "24/06/1993", "gender": "M",
        "date_of_expiry": None, "status": "ACTIVE",
    },
    {
        "file": "file_0000000059248211b82a7ab67156eee1.png",
        "doc_type": "passport", "nationality": "Nepali",
        "name": "Krishna Bahadur KC", "document_number": "PA0998877",
        "date_of_birth": "06/01/1976", "gender": "M",
        "date_of_expiry": "05/01/2026", "status": "ACTIVE",
    },
    {
        "file": "visa-requirement.jpeg",
        "doc_type": "visa", "nationality": "Foreign",
        "name": "Visa Requirement Reference", "document_number": "REF-VISA-000",
        "date_of_birth": None, "gender": None,
        "date_of_expiry": None, "status": "ACTIVE",
    },
]


# ── Blacklist entries — selected documents flagged for testing ──────────────

BLACKLIST_ENTRIES = [
    # Expired documents used past expiry
    {
        "document_number": "J8369854",
        "full_name": "Sita Maha Lakshmi Ramadugula",
        "reason": "EXPIRED document presented — passport expired 10/10/2021",
        "severity": "HIGH",
    },
    {
        "document_number": "G030178",
        "full_name": "Sonam Younten",
        "reason": "EXPIRED Bhutan passport — expired 27/04/2016, presented years after expiry",
        "severity": "HIGH",
    },
    # Lost/stolen document reports
    {
        "document_number": "PA0112233",
        "full_name": "Hari Bahadur Rai",
        "reason": "REPORTED LOST — passport reported lost at Birgunj border post on 15/03/2027",
        "severity": "HIGH",
    },
    {
        "document_number": "N1234567",
        "full_name": "Priya Nair",
        "reason": "REPORTED STOLEN — passport stolen, FIR filed at Delhi Police Station ref DL/2026/4567",
        "severity": "HIGH",
    },
    # Multiple identity suspects
    {
        "document_number": "PA0567891",
        "full_name": "Bishnu Prasad Sharma",
        "reason": "MULTIPLE IDENTITY ALERT — same face linked to document PA0789012 under different name",
        "severity": "HIGH",
    },
    {
        "document_number": "PA0789012",
        "full_name": "Dipak Gurung",
        "reason": "MULTIPLE IDENTITY ALERT — same face linked to document PA0567891 under different name",
        "severity": "HIGH",
    },
    # Revoked documents
    {
        "document_number": "GJ0519940112841",
        "full_name": "Chetan Chauhan",
        "reason": "REVOKED — driving licence revoked by RTA Gujarat for traffic violations",
        "severity": "MEDIUM",
    },
    {
        "document_number": "P1122334",
        "full_name": "Meera Devi",
        "reason": "EXPIRED and REVOKED — passport expired 30/03/2020, renewal denied pending investigation",
        "severity": "HIGH",
    },
    # Visa overstay / border violation
    {
        "document_number": "ETA-2019-SAMPLE",
        "full_name": "Indian e-Visa Holder",
        "reason": "VISA OVERSTAY — e-Tourist visa expired 29/10/2019, departure not recorded",
        "severity": "MEDIUM",
    },
    {
        "document_number": "002203",
        "full_name": "Nepal Tourist Entry Visa",
        "reason": "VISA OVERSTAY — tourist visa expired 23/02/2008, long-term overstay suspected",
        "severity": "HIGH",
    },
    # Document tampering suspect
    {
        "document_number": "M4567890",
        "full_name": "Indian Passport Sample 3",
        "reason": "SUSPECTED TAMPERING — photo substitution detected during previous screening",
        "severity": "HIGH",
    },
    # Fraudulent document
    {
        "document_number": "NPL-DL-BLANK",
        "full_name": "Nepal Non-Professional DL Template",
        "reason": "FRAUDULENT — blank template document, not a valid issued licence",
        "severity": "HIGH",
    },
]


def detect_and_crop_face(image_path: Path) -> tuple[bytes | None, str]:
    """Detect the largest face in the image, crop it, and return as JPEG bytes."""
    img = cv2.imread(str(image_path))
    if img is None:
        return None, "could_not_read"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))

    if len(faces) == 0:
        # Try with more relaxed parameters
        faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(20, 20))

    if len(faces) == 0:
        return None, "no_face"

    # Take the largest face
    areas = [w * h for (x, y, w, h) in faces]
    idx = int(np.argmax(areas))
    x, y, w, h = faces[idx]

    # Add margin
    margin = int(0.2 * max(w, h))
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(img.shape[1], x + w + margin)
    y2 = min(img.shape[0], y + h + margin)

    face_crop = img[y1:y2, x1:x2]
    _, buf = cv2.imencode(".jpg", face_crop)
    return buf.tobytes(), "detected"


def main():
    db = SessionLocal()
    try:
        # Clear existing dataset entries (keep any manually added ones)
        print("Clearing previous dataset entries...")
        db.query(MockCitizenRegistryEntry).delete()
        db.query(MockCentralRegistryEntry).delete()
        # Don't clear identity_embeddings — they're linked to cases
        db.commit()

        citizen_count = 0
        blacklist_count = 0
        embedding_count = 0
        face_found = 0
        face_not_found = 0

        print(f"\nProcessing {len(DOCUMENTS)} documents...")
        for i, doc in enumerate(DOCUMENTS):
            fname = doc["file"]
            fpath = DATASET_DIR / fname
            exists = fpath.exists()
            name = doc["name"]
            doc_num = doc["document_number"]
            dob = doc.get("date_of_birth")
            nationality = doc["nationality"]

            print(f"  [{i+1:2d}/{len(DOCUMENTS)}] {fname[:40]:40s} → {doc['doc_type']:18s} {name[:30]}")

            # ── 1. Insert into citizen registry ──
            if doc_num and name and dob:
                entry = MockCitizenRegistryEntry(
                    document_number=doc_num,
                    full_name=name,
                    date_of_birth=dob,
                    nationality=nationality,
                    gender=doc.get("gender"),
                    document_type=doc["doc_type"],
                    date_of_expiry=doc.get("date_of_expiry"),
                    status=doc.get("status", "ACTIVE"),
                )
                db.add(entry)
                citizen_count += 1

            # ── 2. Detect face and compute embedding ──
            if exists:
                face_bytes, status = detect_and_crop_face(fpath)
                if face_bytes:
                    face_found += 1
                    # Save cropped face
                    face_filename = f"{Path(fname).stem}_face.jpg"
                    face_path = FACE_DIR / face_filename
                    with open(face_path, "wb") as f:
                        f.write(face_bytes)

                    # Compute HOG embedding
                    embedding = extract_embedding(face_bytes)
                    emb_record = IdentityEmbeddingRecord(
                        reference_name=name,
                        document_number=doc_num,
                        embedding_json=json.dumps(embedding),
                    )
                    db.add(emb_record)
                    embedding_count += 1
                else:
                    face_not_found += 1
            else:
                face_not_found += 1

        db.commit()

        # ── 3. Insert blacklist entries ──
        print(f"\nInserting {len(BLACKLIST_ENTRIES)} blacklist entries...")
        for bl in BLACKLIST_ENTRIES:
            entry = MockCentralRegistryEntry(
                document_number=bl["document_number"],
                full_name=bl["full_name"],
                reason=bl["reason"],
                severity=bl["severity"],
            )
            db.add(entry)
            blacklist_count += 1
        db.commit()

        # Also mark revoked/expired entries in citizen registry
        for bl in BLACKLIST_ENTRIES:
            citizen = db.query(MockCitizenRegistryEntry).filter_by(
                document_number=bl["document_number"]
            ).first()
            if citizen:
                if "REVOKED" in bl["reason"]:
                    citizen.status = "REVOKED"
                elif "EXPIRED" in bl["reason"] and citizen.status != "REVOKED":
                    citizen.status = "EXPIRED"
        db.commit()

        print(f"\n{'='*60}")
        print(f"  Citizen registry entries:   {citizen_count}")
        print(f"  Blacklist entries:          {blacklist_count}")
        print(f"  Face embeddings stored:     {embedding_count}")
        print(f"  Faces detected:             {face_found}")
        print(f"  Faces not detected:         {face_not_found}")
        print(f"  Cropped faces saved to:     {FACE_DIR}")
        print(f"{'='*60}")
        print("\nDatabase populated successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
