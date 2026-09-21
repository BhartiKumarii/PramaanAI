#!/bin/bash
# Generate all voiceover segments using edge-tts
VENV=/tmp/videnv/bin
VOICE="en-IN-PrabhatNeural"
OUT=/home/bharti/PramaanAI/video/audio

# Segment 1: Introduction (0:00-0:10)
$VENV/edge-tts --voice "$VOICE" --rate="-5%" --text \
"PramaanAI is an AI-powered document verification system designed to help authorized border officers quickly verify identity and travel documents." \
--write-media "$OUT/01_intro.mp3"

# Segment 2: Document Scanning (0:10-0:30)
$VENV/edge-tts --voice "$VOICE" --rate="-5%" --text \
"An officer starts by scanning the traveller's document using the PramaanAI mobile application. The system captures the document and extracts the required information for verification." \
--write-media "$OUT/02_scanning.mp3"

# Segment 3: Verification (0:30-0:48)
$VENV/edge-tts --voice "$VOICE" --rate="-5%" --text \
"PramaanAI checks the document details against the available registry and performs multiple verification checks. The officer receives a simple result without needing to manually inspect every detail." \
--write-media "$OUT/03_verification.mp3"

# Segment 4: Valid Document (0:48-1:05)
$VENV/edge-tts --voice "$VOICE" --rate="-5%" --text \
"For a valid document, the application clearly displays the verification status and the relevant document information. This helps make the verification process faster and more consistent." \
--write-media "$OUT/04_valid.mp3"

# Segment 5: Suspicious Document (1:05-1:25)
$VENV/edge-tts --voice "$VOICE" --rate="-5%" --text \
"Now, we scan a suspicious document. PramaanAI identifies the available signs of alteration or inconsistency and highlights the reason for the flag. The officer can immediately see that the document requires further attention." \
--write-media "$OUT/05_suspicious.mp3"

# Segment 6: Web Dashboard (1:25-1:48)
$VENV/edge-tts --voice "$VOICE" --rate="-5%" --text \
"The screening information is also available on the PramaanAI web dashboard. Authorized administrators can monitor screenings, review flagged cases, view document results, and track system activity from a central dashboard." \
--write-media "$OUT/06_dashboard.mp3"

# Segment 7: Closing (1:48-2:00)
$VENV/edge-tts --voice "$VOICE" --rate="-5%" --text \
"PramaanAI connects the officer's mobile application with the verification server and centralized dashboard. The goal is simple: faster document verification, clearer results, and stronger support for border security." \
--write-media "$OUT/07_closing.mp3"

echo "All audio segments generated."
ls -lh "$OUT"/*.mp3
