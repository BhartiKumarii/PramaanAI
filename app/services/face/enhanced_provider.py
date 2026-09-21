"""Enhanced Face Verification Provider with advanced algorithms
and comprehensive verification conditions.

This module implements all face verification requirements:
1. Face detection in documents
2. Live face matching with document photo
3. Multiple face detection
4. Partial occlusion/poor quality detection
5. Face mismatch detection
6. Spoof attempt indicators
"""
import io
import json
from dataclasses import dataclass
from typing import Optional, List, Tuple
import numpy as np
from PIL import Image, ImageStat, ImageFilter, ImageEnhance
import cv2

from app.services.face.base import FaceMatchResult, FaceProvider, FaceDetectionResult, DetectedFace, FaceDetector
from app.services.face.embedding import extract_embedding, cosine_similarity


@dataclass
class FaceQualityMetrics:
    """Comprehensive face quality assessment"""
    sharpness: float  # Laplacian variance for blur detection
    brightness: float  # Average luminance
    contrast: float   # RMS contrast
    size_pixels: int  # Face area in pixels
    pose_quality: float  # Frontal pose quality (0-1)
    eye_visibility: float  # Eye region clarity (0-1)
    mouth_visibility: float  # Mouth region clarity (0-1)


@dataclass
class SpoofIndicators:
    """Anti-spoofing detection results"""
    screen_reflection_score: float  # Screen pixel grid detection
    print_texture_score: float     # Print halftone pattern detection
    depth_consistency: float       # 3D depth indicators
    edge_artifacts: float          # Digital cutout artifacts
    motion_blur_score: float       # Unnatural motion blur
    overall_spoof_probability: float


class EnhancedFaceDetector(FaceDetector):
    """Advanced face detection with quality assessment and spoof detection"""

    def __init__(self):
        # Load OpenCV's DNN face detector (more robust than Haar cascades)
        self.net = self._load_face_detector()
        self.confidence_threshold = 0.5

    def _load_face_detector(self):
        """Load face detection model - using alternative methods for OpenCV 5.0+"""
        try:
            # Try multiple approaches for face detection

            # Method 1: Try traditional CascadeClassifier (older OpenCV)
            if hasattr(cv2, 'CascadeClassifier'):
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                if not face_cascade.empty():
                    return face_cascade

            # Method 2: If no proper face detector available, return None
            # This will cause face verification to fail gracefully rather than
            # using fake contour-based detection that can match non-faces
            print("WARNING: No proper face detector available. Face detection will be unavailable.")
            return None

        except Exception as e:
            print(f"Face detector loading failed: {e}")
            # Return None instead of fake detector
            return None

    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        """Detect faces with comprehensive quality and spoof assessment"""
        try:
            print(f"[DEBUG] Face detection starting...")
            # Convert bytes to PIL Image
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_array = np.array(pil_image)
            print(f"[DEBUG] Image loaded: {img_array.shape} (H, W, C)")

            # Convert to OpenCV format
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            height, width = gray.shape
            print(f"[DEBUG] Grayscale image: {width}x{height}")

            detected_faces = []

            if self.net is not None:
                print(f"[DEBUG] Face detector type: {type(self.net)} - {self.net}")
                # Use Haar cascade for face detection
                print(f"[DEBUG] Using Haar cascade face detection...")
                # Try multiple parameter sets for better detection on document photos
                faces = []

                # Try different parameter combinations optimized for document photos
                param_sets = [
                    # (scaleFactor, minNeighbors, minSize, maxSize)
                    (1.1, 3, (80, 80), (400, 400)),  # Document photo size
                    (1.05, 3, (60, 60), (500, 500)), # Slightly smaller
                    (1.3, 4, (100, 100), (350, 350)),# Larger faces only
                    (1.1, 4, (50, 50), (300, 300)),  # Fallback
                    (1.05, 2, (40, 40), (600, 600)), # Very permissive fallback
                ]

                for i, (scale, neighbors, min_size, max_size) in enumerate(param_sets):
                    print(f"[DEBUG] Trying parameter set {i+1}: scale={scale}, neighbors={neighbors}, minSize={min_size}")
                    if max_size:
                        detected = self.net.detectMultiScale(
                            gray, scaleFactor=scale, minNeighbors=neighbors,
                            minSize=min_size, maxSize=max_size
                        )
                    else:
                        detected = self.net.detectMultiScale(
                            gray, scaleFactor=scale, minNeighbors=neighbors,
                            minSize=min_size
                        )

                    print(f"[DEBUG] Parameter set {i+1} detected {len(detected)} faces")
                    if len(detected) > 0:
                        faces = detected
                        print(f"[DEBUG] Using faces from parameter set {i+1}")
                        break

                print(f"[DEBUG] Haar cascade final result: {len(faces)} faces")
            else:
                print(f"[DEBUG] No proper face detector available - cannot detect faces")
                faces = []

            # Process and validate detected faces
            print(f"[DEBUG] Processing {len(faces)} detected faces...")
            for i, face_rect in enumerate(faces):
                x, y, w, h = map(int, face_rect)
                print(f"[DEBUG] Face {i}: ({x}, {y}) {w}x{h}")

                # Validate that this is likely a real face
                if not self._validate_face_detection(gray, x, y, w, h):
                    print(f"[DEBUG] Face {i}: failed validation - likely not a face")
                    continue

                # Check if face touches image edges
                touches_edge = (
                    x <= 5 or y <= 5 or
                    (x + w) >= (width - 5) or
                    (y + h) >= (height - 5)
                )

                # Calculate confidence based on face size and position
                face_area = w * h
                image_area = width * height
                size_ratio = face_area / image_area

                print(f"[DEBUG] Face {i}: area={face_area}, ratio={size_ratio:.4f}, touches_edge={touches_edge}")

                # Confidence based on size (faces should be reasonable size)
                # Adjusted thresholds for document photos where faces can be smaller
                if 0.002 <= size_ratio <= 0.8:  # 0.2% to 80% of image (more permissive for documents)
                    confidence = min(0.95, 0.5 + size_ratio * 20)  # Adjusted scaling for smaller faces
                    print(f"[DEBUG] Face {i}: size ratio OK, confidence={confidence:.3f}")
                else:
                    confidence = 0.3  # Too small or too large
                    print(f"[DEBUG] Face {i}: size ratio BAD ({size_ratio:.4f}), confidence={confidence:.3f}")

                # Only accept faces with reasonable confidence
                if confidence >= 0.4:
                    detected_faces.append(DetectedFace(
                        location={"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                        confidence=confidence,
                        touches_edge=touches_edge
                    ))
                    print(f"[DEBUG] Face {i}: accepted with confidence {confidence:.3f}")
                else:
                    print(f"[DEBUG] Face {i}: rejected due to low confidence {confidence:.3f}")

            print(f"[DEBUG] Final detected_faces count: {len(detected_faces)}")

            # Determine status and reason
            if len(detected_faces) == 0:
                return FaceDetectionResult(
                    status="NO_FACE",
                    faces=[],
                    reason="No faces detected in the image. Please ensure the document contains a clear facial photograph."
                )
            elif len(detected_faces) == 1:
                face = detected_faces[0]
                if face.touches_edge:
                    reason = f"Single face detected but appears cropped (touches image edge). Face quality may be compromised."
                elif face.confidence < 0.6:
                    reason = f"Single face detected but with low confidence ({face.confidence:.2f}). Image quality may be poor."
                else:
                    reason = f"Single face detected with good confidence ({face.confidence:.2f}). Ready for verification."

                return FaceDetectionResult(
                    status="SINGLE_FACE",
                    faces=detected_faces,
                    reason=reason
                )
            else:
                return FaceDetectionResult(
                    status="MULTIPLE_FACES",
                    faces=detected_faces,
                    reason=f"Multiple faces detected ({len(detected_faces)} faces). Document should contain only one person's photograph."
                )

        except Exception as e:
            return FaceDetectionResult(
                status="ERROR",
                faces=[],
                reason=f"Face detection failed: {str(e)}"
            )

    def assess_face_quality(self, image_bytes: bytes, face_bbox: dict) -> FaceQualityMetrics:
        """Comprehensive face quality assessment"""
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            # Extract face region
            x, y, w, h = face_bbox['x'], face_bbox['y'], face_bbox['width'], face_bbox['height']
            face_crop = pil_image.crop((x, y, x + w, y + h))

            # Convert to grayscale for analysis
            gray_face = face_crop.convert('L')
            face_array = np.array(gray_face, dtype=np.float64)

            # Calculate sharpness (Laplacian variance)
            laplacian = cv2.Laplacian(face_array.astype(np.uint8), cv2.CV_64F)
            sharpness = float(laplacian.var())

            # Calculate brightness and contrast
            stats = ImageStat.Stat(gray_face)
            brightness = stats.mean[0] / 255.0
            contrast = stats.stddev[0] / 255.0

            # Face size in pixels
            size_pixels = w * h

            # Simple pose quality (based on face symmetry)
            left_half = face_array[:, :w//2]
            right_half = np.fliplr(face_array[:, w//2:])
            min_width = min(left_half.shape[1], right_half.shape[1])
            left_half = left_half[:, :min_width]
            right_half = right_half[:, :min_width]

            symmetry_diff = np.mean(np.abs(left_half - right_half))
            pose_quality = max(0.0, 1.0 - (symmetry_diff / 128.0))

            # Eye and mouth visibility (simplified region analysis)
            eye_region = face_array[:h//3, :]  # Top third for eyes
            mouth_region = face_array[2*h//3:, :]  # Bottom third for mouth

            eye_visibility = min(1.0, np.var(eye_region) / 1000.0)
            mouth_visibility = min(1.0, np.var(mouth_region) / 1000.0)

            return FaceQualityMetrics(
                sharpness=sharpness,
                brightness=brightness,
                contrast=contrast,
                size_pixels=size_pixels,
                pose_quality=pose_quality,
                eye_visibility=eye_visibility,
                mouth_visibility=mouth_visibility
            )

        except Exception:
            # Return default values if analysis fails
            return FaceQualityMetrics(
                sharpness=0.0, brightness=0.5, contrast=0.5, size_pixels=0,
                pose_quality=0.5, eye_visibility=0.5, mouth_visibility=0.5
            )

    def detect_spoof_indicators(self, image_bytes: bytes, face_bbox: dict) -> SpoofIndicators:
        """Detect various spoofing attempt indicators"""
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            # Extract face region
            x, y, w, h = face_bbox['x'], face_bbox['y'], face_bbox['width'], face_bbox['height']
            face_crop = pil_image.crop((x, y, x + w, y + h))
            face_array = np.array(face_crop.convert('L'), dtype=np.float64)

            # Screen reflection detection (look for pixel grid patterns)
            fft = np.fft.fft2(face_array)
            fft_shifted = np.fft.fftshift(fft)
            magnitude_spectrum = np.abs(fft_shifted)

            # Look for regular patterns in frequency domain
            h_freq, w_freq = magnitude_spectrum.shape
            center_y, center_x = h_freq // 2, w_freq // 2

            # Check for high energy at regular intervals (screen pixels)
            screen_energy = 0.0
            for i in range(1, min(10, min(center_y, center_x))):
                # Check cardinal and diagonal directions
                screen_energy += magnitude_spectrum[center_y + i, center_x]
                screen_energy += magnitude_spectrum[center_y - i, center_x]
                screen_energy += magnitude_spectrum[center_y, center_x + i]
                screen_energy += magnitude_spectrum[center_y, center_x - i]

            total_energy = np.sum(magnitude_spectrum)
            screen_reflection_score = min(1.0, screen_energy / (total_energy + 1e-6))

            # Print texture detection (look for halftone patterns)
            # Use Laplacian to detect regular dot patterns
            laplacian = cv2.Laplacian(face_array.astype(np.uint8), cv2.CV_64F)
            print_variance = np.var(laplacian)
            print_texture_score = min(1.0, print_variance / 10000.0)

            # Depth consistency (simplified - look for unnatural flatness)
            gradient_x = np.gradient(face_array, axis=1)
            gradient_y = np.gradient(face_array, axis=0)
            gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
            depth_consistency = min(1.0, np.std(gradient_magnitude) / 100.0)

            # Edge artifacts detection
            edges = cv2.Canny(face_array.astype(np.uint8), 50, 150)
            edge_density = np.sum(edges) / (w * h * 255)
            edge_artifacts = min(1.0, edge_density * 5)

            # Motion blur detection (look for directional blur)
            kernel_h = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]])
            kernel_v = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]])

            blur_h = cv2.filter2D(face_array.astype(np.uint8), -1, kernel_h)
            blur_v = cv2.filter2D(face_array.astype(np.uint8), -1, kernel_v)

            motion_blur_score = min(1.0, (np.var(blur_h) + np.var(blur_v)) / 20000.0)

            # Overall spoof probability (weighted combination)
            overall_spoof_probability = (
                screen_reflection_score * 0.3 +
                print_texture_score * 0.2 +
                (1.0 - depth_consistency) * 0.2 +
                edge_artifacts * 0.15 +
                motion_blur_score * 0.15
            )

            return SpoofIndicators(
                screen_reflection_score=screen_reflection_score,
                print_texture_score=print_texture_score,
                depth_consistency=depth_consistency,
                edge_artifacts=edge_artifacts,
                motion_blur_score=motion_blur_score,
                overall_spoof_probability=overall_spoof_probability
            )

        except Exception:
            # Return neutral values if analysis fails
            return SpoofIndicators(
                screen_reflection_score=0.0,
                print_texture_score=0.0,
                depth_consistency=0.5,
                edge_artifacts=0.0,
                motion_blur_score=0.0,
                overall_spoof_probability=0.0
            )

    def _validate_face_detection(self, gray: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
        """Validate that a detected region likely contains a real face using image analysis"""
        try:
            # Extract the detected region
            region = gray[y:y+h, x:x+w]

            # Basic size and aspect ratio checks
            if w < 40 or h < 40 or w > 800 or h > 800:
                return False

            aspect_ratio = w / h
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                return False

            # Variance check - faces should have moderate texture variance
            variance = np.var(region.astype(np.float64))
            if variance < 100 or variance > 5000:
                return False

            # Edge density check - faces should have reasonable edge structure
            edges = cv2.Canny(region, 30, 100) if hasattr(cv2, 'Canny') else region * 0
            edge_density = np.sum(edges) / (w * h * 255) if hasattr(cv2, 'Canny') else 0.2
            if edge_density < 0.05 or edge_density > 0.6:
                return False

            # Brightness check - faces shouldn't be completely dark or bright
            mean_brightness = np.mean(region)
            if mean_brightness < 20 or mean_brightness > 235:
                return False

            return True

        except Exception as e:
            print(f"Face validation failed: {e}")
            return False


class EnhancedFaceProvider(FaceProvider):
    """Enhanced face verification with comprehensive checks"""

    def __init__(self):
        self.detector = EnhancedFaceDetector()
        # Aligned with ClassicalFaceProvider threshold for consistency
        self.match_threshold = 0.75  # Matches calibrated threshold from AT&T/Olivetti dataset
        self.quality_threshold = 0.4  # Minimum quality score
        self.spoof_threshold = 0.6    # Maximum spoof probability

    def verify(self, document_face: bytes, presented_face: bytes) -> FaceMatchResult:
        """Enhanced face verification with quality and spoof checking"""

        print(f"[DEBUG] Face verification started")
        print(f"[DEBUG] Document image size: {len(document_face)} bytes")
        print(f"[DEBUG] Live image size: {len(presented_face)} bytes")

        # Step 1: Detect faces in both images
        doc_detection = self.detector.detect(document_face)
        live_detection = self.detector.detect(presented_face)

        print(f"[DEBUG] Document face detection: {doc_detection.status}")
        if doc_detection.faces:
            print(f"[DEBUG] Document faces found: {len(doc_detection.faces)}")
            for i, face in enumerate(doc_detection.faces):
                print(f"[DEBUG] Document face {i}: location {face.location}, confidence {face.confidence:.3f}")

        print(f"[DEBUG] Live face detection: {live_detection.status}")
        if live_detection.faces:
            print(f"[DEBUG] Live faces found: {len(live_detection.faces)}")
            for i, face in enumerate(live_detection.faces):
                print(f"[DEBUG] Live face {i}: location {face.location}, confidence {face.confidence:.3f}")

        # Check face detection results
        if doc_detection.status == "NO_FACE":
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason="No face detected in document image. Please ensure document contains a clear facial photograph.",
                location=None
            )

        if live_detection.status == "NO_FACE":
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason="No face detected in live capture. Please ensure camera captures your face clearly.",
                location=None
            )

        # Handle multiple faces by selecting the best one (for document photos this is common)
        if doc_detection.status == "MULTIPLE_FACES":
            print(f"[DEBUG] Multiple document faces detected, selecting best one...")
            # Sort by confidence and select the best face
            doc_face = max(doc_detection.faces, key=lambda f: f.confidence)
            print(f"[DEBUG] Selected document face: confidence {doc_face.confidence:.3f}")
        elif doc_detection.status == "SINGLE_FACE":
            doc_face = doc_detection.faces[0]
        else:
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason="No face detected in document image. Please ensure document contains a clear facial photograph.",
                location=None
            )

        if live_detection.status == "MULTIPLE_FACES":
            print(f"[DEBUG] Multiple live faces detected, selecting best one...")
            # For live capture, multiple faces might indicate group photo - be more cautious
            if len(live_detection.faces) > 2:
                return FaceMatchResult(
                    match=False,
                    similarity=0.0,
                    confidence=0.0,
                    reason=f"Too many faces detected in live capture ({len(live_detection.faces)} faces). Please ensure only your face is visible.",
                    location=live_detection.faces[0].location
                )
            # Select the best face
            live_face = max(live_detection.faces, key=lambda f: f.confidence)
            print(f"[DEBUG] Selected live face: confidence {live_face.confidence:.3f}")
        elif live_detection.status == "SINGLE_FACE":
            live_face = live_detection.faces[0]
        else:
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason="No face detected in live capture. Please ensure camera captures your face clearly.",
                location=None
            )

        # Step 2: Quality assessment
        doc_quality = self.detector.assess_face_quality(document_face, doc_face.location)
        live_quality = self.detector.assess_face_quality(presented_face, live_face.location)

        # Check minimum quality requirements
        doc_quality_score = self._calculate_overall_quality(doc_quality)
        live_quality_score = self._calculate_overall_quality(live_quality)

        if doc_quality_score < self.quality_threshold:
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason=f"Document face quality too poor for verification (score: {doc_quality_score:.2f}). Poor lighting, blur, or image quality detected.",
                location=doc_face.location
            )

        if live_quality_score < self.quality_threshold:
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason=f"Live face quality too poor for verification (score: {live_quality_score:.2f}). Please improve lighting and camera stability.",
                location=live_face.location
            )

        # Step 3: Spoof detection on live capture
        spoof_indicators = self.detector.detect_spoof_indicators(presented_face, live_face.location)

        if spoof_indicators.overall_spoof_probability > self.spoof_threshold:
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason=f"Possible spoof attempt detected (probability: {spoof_indicators.overall_spoof_probability:.2f}). Live capture appears to be a photo, screen, or printed image.",
                location=live_face.location
            )

        # Step 4: Face embedding and matching
        try:
            # Extract embeddings from the detected face regions
            doc_box = (doc_face.location['x'], doc_face.location['y'],
                      doc_face.location['x'] + doc_face.location['width'],
                      doc_face.location['y'] + doc_face.location['height'])
            live_box = (live_face.location['x'], live_face.location['y'],
                       live_face.location['x'] + live_face.location['width'],
                       live_face.location['y'] + live_face.location['height'])

            print(f"[DEBUG] Document face box: {doc_box}")
            print(f"[DEBUG] Live face box: {live_box}")

            print(f"[DEBUG] Extracting document face embedding...")
            doc_embedding = extract_embedding(document_face, box=doc_box)
            print(f"[DEBUG] Document embedding length: {len(doc_embedding) if doc_embedding else 0}")

            print(f"[DEBUG] Extracting live face embedding...")
            live_embedding = extract_embedding(presented_face, box=live_box)
            print(f"[DEBUG] Live embedding length: {len(live_embedding) if live_embedding else 0}")

            # Calculate similarity
            print(f"[DEBUG] Calculating cosine similarity...")
            similarity = cosine_similarity(doc_embedding, live_embedding)
            print(f"[DEBUG] Raw similarity: {similarity:.6f}")
            print(f"[DEBUG] Threshold: {self.match_threshold:.6f}")
            print(f"[DEBUG] Match: {similarity >= self.match_threshold}")

            # Determine match based on threshold
            match = similarity >= self.match_threshold

            # Calculate confidence with quality adjustment
            base_confidence = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
            quality_adjustment = (doc_quality_score + live_quality_score) / 2.0
            spoof_adjustment = 1.0 - spoof_indicators.overall_spoof_probability

            adjusted_confidence = base_confidence * quality_adjustment * spoof_adjustment

            # Generate detailed reason
            if match:
                reason = f"Face match confirmed: similarity {similarity:.4f} above threshold {self.match_threshold:.4f}. "
                reason += f"Document quality: {doc_quality_score:.2f}, Live quality: {live_quality_score:.2f}, "
                reason += f"Spoof probability: {spoof_indicators.overall_spoof_probability:.2f}"
            else:
                reason = f"Face mismatch: similarity {similarity:.4f} below threshold {self.match_threshold:.4f}. "

                # Provide specific guidance based on similarity level
                if similarity < 0.3:
                    reason += "Faces appear to be different persons."
                elif similarity < 0.6:
                    reason += "Faces show significant differences. Verify identity manually."
                else:
                    reason += "Faces are similar but below confidence threshold. Manual review recommended."

            return FaceMatchResult(
                match=match,
                similarity=round(similarity, 4),
                confidence=round(adjusted_confidence, 4),
                reason=reason,
                location=live_face.location
            )

        except Exception as e:
            return FaceMatchResult(
                match=False,
                similarity=0.0,
                confidence=0.0,
                reason=f"Face verification failed due to processing error: {str(e)}",
                location=None
            )

    def _calculate_overall_quality(self, quality: FaceQualityMetrics) -> float:
        """Calculate overall quality score from individual metrics"""
        # Weighted combination of quality factors
        weights = {
            'sharpness': 0.25,    # Blur detection
            'brightness': 0.15,   # Proper lighting
            'contrast': 0.15,     # Good contrast
            'size': 0.2,         # Adequate size
            'pose': 0.1,         # Frontal pose
            'eye_visibility': 0.075,
            'mouth_visibility': 0.075
        }

        # Normalize sharpness (typical range 0-1000)
        sharpness_norm = min(1.0, quality.sharpness / 500.0)

        # Normalize brightness (optimal around 0.4-0.7)
        brightness_norm = 1.0 - abs(quality.brightness - 0.55) / 0.55
        brightness_norm = max(0.0, brightness_norm)

        # Normalize contrast (higher is generally better, up to a point)
        contrast_norm = min(1.0, quality.contrast / 0.3)

        # Normalize size (prefer faces that are 5-50% of image)
        size_norm = 1.0
        if quality.size_pixels < 2500:  # Too small (50x50)
            size_norm = quality.size_pixels / 2500.0
        elif quality.size_pixels > 250000:  # Too large (500x500)
            size_norm = 250000.0 / quality.size_pixels

        overall_quality = (
            weights['sharpness'] * sharpness_norm +
            weights['brightness'] * brightness_norm +
            weights['contrast'] * contrast_norm +
            weights['size'] * size_norm +
            weights['pose'] * quality.pose_quality +
            weights['eye_visibility'] * quality.eye_visibility +
            weights['mouth_visibility'] * quality.mouth_visibility
        )

        return min(1.0, overall_quality)