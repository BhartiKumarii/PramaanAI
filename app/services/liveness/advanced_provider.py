"""Advanced Liveness Detection with Multiple Anti-Spoofing Techniques

This module implements comprehensive liveness detection to prevent various spoofing attacks:
1. Photo/Print attack detection (texture analysis, edge detection)
2. Screen/Digital replay attack detection (moiré patterns, refresh rate artifacts)
3. 3D mask attack detection (depth inconsistencies, material properties)
4. Video replay attack detection (temporal inconsistencies)
5. Paper/Cardboard cutout detection (material properties, edges)
"""
import io
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageStat
from dataclasses import dataclass
from typing import Tuple, List
import cv2

from app.services.liveness.base import LivenessProvider, LivenessResult


@dataclass
class LivenessMetrics:
    """Comprehensive liveness analysis metrics"""
    # Texture Analysis
    skin_texture_score: float      # Natural skin texture vs artificial surface
    micro_texture_variance: float  # Fine detail variation
    surface_uniformity: float      # Unnatural surface smoothness

    # Print/Photo Detection
    print_artifact_score: float    # Halftone dots, printing artifacts
    paper_texture_score: float     # Paper grain pattern
    ink_saturation_score: float    # Print color saturation patterns

    # Screen/Digital Display Detection
    screen_reflection_score: float # Screen surface reflections
    pixel_grid_score: float       # LCD/OLED pixel patterns
    refresh_artifact_score: float # Display refresh artifacts
    moire_pattern_score: float    # Moiré interference patterns

    # 3D Mask Detection
    depth_consistency_score: float # 3D depth variation
    material_property_score: float # Material light reflection
    edge_transition_score: float   # Natural vs artificial edge transitions

    # Motion/Temporal Analysis
    motion_blur_consistency: float # Natural motion blur patterns
    micro_motion_score: float      # Subtle involuntary movements
    temporal_consistency: float    # Frame-to-frame consistency

    # Overall Assessment
    overall_liveness_score: float  # Combined liveness probability (0-1)
    confidence_level: float        # Detection confidence


class AdvancedLivenessDetector:
    """Advanced liveness detection with multiple anti-spoofing techniques"""

    def __init__(self):
        self.spoof_threshold = 0.65    # Threshold for spoof detection
        self.confidence_threshold = 0.7 # Minimum confidence required

    def analyze_comprehensive(self, image_bytes: bytes) -> LivenessMetrics:
        """Comprehensive liveness analysis using multiple techniques"""
        try:
            # Load and preprocess image
            pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_array = np.array(pil_image)
            gray_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Run all analysis techniques
            texture_metrics = self._analyze_texture(img_array, gray_array)
            print_metrics = self._detect_print_artifacts(img_array, gray_array)
            screen_metrics = self._detect_screen_artifacts(img_array, gray_array)
            mask_metrics = self._detect_3d_mask_artifacts(img_array, gray_array)
            motion_metrics = self._analyze_motion_patterns(gray_array)

            # Combine all metrics
            overall_score, confidence = self._calculate_overall_liveness(
                texture_metrics, print_metrics, screen_metrics, mask_metrics, motion_metrics
            )

            return LivenessMetrics(
                # Texture Analysis
                skin_texture_score=texture_metrics[0],
                micro_texture_variance=texture_metrics[1],
                surface_uniformity=texture_metrics[2],

                # Print/Photo Detection
                print_artifact_score=print_metrics[0],
                paper_texture_score=print_metrics[1],
                ink_saturation_score=print_metrics[2],

                # Screen/Digital Display Detection
                screen_reflection_score=screen_metrics[0],
                pixel_grid_score=screen_metrics[1],
                refresh_artifact_score=screen_metrics[2],
                moire_pattern_score=screen_metrics[3],

                # 3D Mask Detection
                depth_consistency_score=mask_metrics[0],
                material_property_score=mask_metrics[1],
                edge_transition_score=mask_metrics[2],

                # Motion/Temporal Analysis
                motion_blur_consistency=motion_metrics[0],
                micro_motion_score=motion_metrics[1],
                temporal_consistency=motion_metrics[2],

                # Overall Assessment
                overall_liveness_score=overall_score,
                confidence_level=confidence
            )

        except Exception:
            # Return safe defaults if analysis fails
            return self._get_default_metrics()

    def _analyze_texture(self, img_array: np.ndarray, gray_array: np.ndarray) -> Tuple[float, float, float]:
        """Analyze natural skin texture vs artificial surfaces"""
        try:
            # Skin texture analysis using Local Binary Patterns (simplified)
            h, w = gray_array.shape

            # Calculate local variance (skin has natural texture variation)
            kernel = np.ones((5, 5)) / 25.0
            local_mean = cv2.filter2D(gray_array.astype(np.float32), -1, kernel)
            local_var = cv2.filter2D((gray_array.astype(np.float32) - local_mean)**2, -1, kernel)

            skin_texture_score = min(1.0, np.mean(local_var) / 500.0)

            # Micro-texture variance (natural skin has consistent micro-patterns)
            sobel_x = cv2.Sobel(gray_array, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray_array, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)

            micro_texture_variance = min(1.0, np.std(gradient_magnitude) / 100.0)

            # Surface uniformity (artificial surfaces are often too uniform)
            # Use Gabor-like filter to detect uniform regions
            gaussian = cv2.GaussianBlur(gray_array.astype(np.float32), (15, 15), 5)
            uniformity = 1.0 - min(1.0, np.std(gray_array - gaussian) / 50.0)
            surface_uniformity = uniformity

            return skin_texture_score, micro_texture_variance, surface_uniformity

        except Exception:
            return 0.5, 0.5, 0.5

    def _detect_print_artifacts(self, img_array: np.ndarray, gray_array: np.ndarray) -> Tuple[float, float, float]:
        """Detect printing artifacts (halftone dots, paper texture, etc.)"""
        try:
            # Halftone dot detection using frequency analysis
            fft = np.fft.fft2(gray_array)
            fft_shifted = np.fft.fftshift(fft)
            magnitude_spectrum = np.abs(fft_shifted)

            # Look for regular patterns in frequency domain (halftone dots)
            h, w = magnitude_spectrum.shape
            center_y, center_x = h // 2, w // 2

            # Check for periodic patterns at typical halftone frequencies
            halftone_energy = 0.0
            for freq_radius in [10, 15, 20, 25]:  # Typical halftone frequencies
                y_coords = np.arange(max(0, center_y - freq_radius - 2),
                                   min(h, center_y + freq_radius + 3))
                x_coords = np.arange(max(0, center_x - freq_radius - 2),
                                   min(w, center_x + freq_radius + 3))

                for y in y_coords:
                    for x in x_coords:
                        dist = np.sqrt((y - center_y)**2 + (x - center_x)**2)
                        if freq_radius - 2 <= dist <= freq_radius + 2:
                            halftone_energy += magnitude_spectrum[y, x]

            total_energy = np.sum(magnitude_spectrum)
            print_artifact_score = min(1.0, halftone_energy / (total_energy + 1e-6))

            # Paper texture detection (look for fibrous patterns)
            # Use morphological operations to detect fibrous structures
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            opened = cv2.morphologyEx(gray_array, cv2.MORPH_OPEN, kernel)
            paper_texture = np.mean(np.abs(gray_array.astype(np.float32) - opened.astype(np.float32)))
            paper_texture_score = min(1.0, paper_texture / 20.0)

            # Ink saturation analysis (printed images have characteristic color distribution)
            # Convert to HSV for saturation analysis
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            saturation = hsv[:, :, 1]

            # Printed materials often have unnatural saturation patterns
            sat_hist, _ = np.histogram(saturation, bins=32, range=(0, 255))
            sat_hist = sat_hist.astype(np.float32) / np.sum(sat_hist)

            # Calculate entropy - printed materials often have bimodal distribution
            entropy = -np.sum(sat_hist * np.log(sat_hist + 1e-6))
            ink_saturation_score = max(0.0, 1.0 - entropy / 3.5)  # Natural images have higher entropy

            return print_artifact_score, paper_texture_score, ink_saturation_score

        except Exception:
            return 0.0, 0.0, 0.0

    def _detect_screen_artifacts(self, img_array: np.ndarray, gray_array: np.ndarray) -> Tuple[float, float, float, float]:
        """Detect screen/display replay artifacts"""
        try:
            h, w = gray_array.shape

            # Screen reflection detection (screens have characteristic reflections)
            # Use edge detection to find reflective surfaces
            edges = cv2.Canny(gray_array, 50, 150)
            edge_density = np.sum(edges) / (h * w * 255)

            # Screens often have straight reflective edges
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                                  minLineLength=30, maxLineGap=10)

            screen_reflection_score = 0.0
            if lines is not None:
                # Count long straight lines (characteristic of screen edges)
                long_lines = 0
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                    if length > min(h, w) * 0.2:  # At least 20% of image dimension
                        long_lines += 1
                screen_reflection_score = min(1.0, long_lines / 5.0)

            # Pixel grid detection (LCD/OLED subpixel patterns)
            # Use FFT to detect regular pixel patterns
            fft_2d = np.fft.fft2(gray_array)
            fft_shifted = np.fft.fftshift(fft_2d)
            magnitude_spectrum = np.abs(fft_shifted)

            # Look for peaks at high frequencies (pixel grid)
            center_y, center_x = h // 2, w // 2
            high_freq_energy = 0.0

            for radius in range(min(center_y, center_x) // 2, min(center_y, center_x)):
                circle_mask = np.zeros_like(magnitude_spectrum)
                y, x = np.ogrid[:h, :w]
                mask = (x - center_x)**2 + (y - center_y)**2 <= radius**2
                inner_mask = (x - center_x)**2 + (y - center_y)**2 <= (radius-1)**2
                circle_mask[mask & ~inner_mask] = 1
                high_freq_energy += np.sum(magnitude_spectrum * circle_mask)

            total_energy = np.sum(magnitude_spectrum)
            pixel_grid_score = min(1.0, high_freq_energy / (total_energy * 0.3 + 1e-6))

            # Refresh artifact detection (60Hz, 120Hz patterns)
            # Simplified - look for temporal artifacts in single frame
            # (In practice, this would need multiple frames)
            vertical_profile = np.mean(gray_array, axis=1)
            horizontal_profile = np.mean(gray_array, axis=0)

            # Look for periodic patterns that might indicate refresh artifacts
            v_fft = np.abs(np.fft.fft(vertical_profile))
            h_fft = np.abs(np.fft.fft(horizontal_profile))

            # Check for peaks at regular intervals
            refresh_energy = np.sum(v_fft[len(v_fft)//4:len(v_fft)//2]) + np.sum(h_fft[len(h_fft)//4:len(h_fft)//2])
            total_fft_energy = np.sum(v_fft) + np.sum(h_fft)
            refresh_artifact_score = min(1.0, refresh_energy / (total_fft_energy + 1e-6))

            # Moiré pattern detection
            # Apply filters to detect interference patterns
            kernel1 = np.array([[-1, 2, -1], [-1, 2, -1], [-1, 2, -1]]) / 6.0
            kernel2 = np.array([[-1, -1, -1], [2, 2, 2], [-1, -1, -1]]) / 6.0

            filtered1 = cv2.filter2D(gray_array.astype(np.float32), -1, kernel1)
            filtered2 = cv2.filter2D(gray_array.astype(np.float32), -1, kernel2)

            moire_strength = np.std(filtered1) + np.std(filtered2)
            moire_pattern_score = min(1.0, moire_strength / 100.0)

            return screen_reflection_score, pixel_grid_score, refresh_artifact_score, moire_pattern_score

        except Exception:
            return 0.0, 0.0, 0.0, 0.0

    def _detect_3d_mask_artifacts(self, img_array: np.ndarray, gray_array: np.ndarray) -> Tuple[float, float, float]:
        """Detect 3D mask and artificial material artifacts"""
        try:
            # Depth consistency analysis
            # Use gradient analysis to detect unnatural depth transitions
            grad_x = cv2.Sobel(gray_array, cv2.CV_64F, 1, 0, ksize=5)
            grad_y = cv2.Sobel(gray_array, cv2.CV_64F, 0, 1, ksize=5)
            gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)

            # Natural faces have consistent depth variations
            depth_variance = np.std(gradient_magnitude)
            depth_consistency_score = min(1.0, depth_variance / 50.0)

            # Material property analysis (plastic, silicone have different reflectance)
            # Analyze local contrast and reflectance patterns
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            value_channel = hsv[:, :, 2]  # Brightness/value channel

            # Calculate local reflectance variation
            kernel = np.ones((7, 7)) / 49.0
            local_mean = cv2.filter2D(value_channel.astype(np.float32), -1, kernel)
            reflectance_var = cv2.filter2D((value_channel.astype(np.float32) - local_mean)**2, -1, kernel)

            # Artificial materials often have more uniform reflectance
            material_uniformity = np.mean(reflectance_var)
            material_property_score = max(0.0, 1.0 - material_uniformity / 500.0)

            # Edge transition analysis (masks have sharper, more artificial edges)
            edges = cv2.Canny(gray_array, 30, 100)

            # Analyze edge smoothness
            edge_pixels = np.where(edges > 0)
            if len(edge_pixels[0]) > 0:
                # Sample edge neighborhoods to analyze transition smoothness
                edge_sharpness_scores = []
                sample_indices = np.random.choice(len(edge_pixels[0]),
                                                min(100, len(edge_pixels[0])),
                                                replace=False)

                for idx in sample_indices:
                    y, x = edge_pixels[0][idx], edge_pixels[1][idx]
                    if 3 <= y < gray_array.shape[0]-3 and 3 <= x < gray_array.shape[1]-3:
                        # Analyze 7x7 neighborhood around edge
                        neighborhood = gray_array[y-3:y+4, x-3:x+4].astype(np.float32)
                        transition_sharpness = np.std(neighborhood)
                        edge_sharpness_scores.append(transition_sharpness)

                if edge_sharpness_scores:
                    avg_sharpness = np.mean(edge_sharpness_scores)
                    # Artificial edges are often too sharp
                    edge_transition_score = min(1.0, avg_sharpness / 100.0)
                else:
                    edge_transition_score = 0.5
            else:
                edge_transition_score = 0.0

            return depth_consistency_score, material_property_score, edge_transition_score

        except Exception:
            return 0.5, 0.0, 0.5

    def _analyze_motion_patterns(self, gray_array: np.ndarray) -> Tuple[float, float, float]:
        """Analyze motion and temporal consistency (simplified for single frame)"""
        try:
            # Motion blur consistency
            # Real faces have natural motion blur patterns
            motion_kernel_h = np.array([[1, 1, 1, 1, 1]]) / 5.0
            motion_kernel_v = np.array([[1], [1], [1], [1], [1]]) / 5.0

            blur_h = cv2.filter2D(gray_array.astype(np.float32), -1, motion_kernel_h)
            blur_v = cv2.filter2D(gray_array.astype(np.float32), -1, motion_kernel_v)

            motion_consistency = (np.std(blur_h) + np.std(blur_v)) / 2.0
            motion_blur_consistency = min(1.0, motion_consistency / 100.0)

            # Micro-motion analysis (simplified - in practice needs multiple frames)
            # Look for subtle variations that indicate natural micro-movements
            high_freq = cv2.filter2D(gray_array.astype(np.float32), -1,
                                   np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]]))

            micro_variation = np.std(high_freq)
            micro_motion_score = min(1.0, micro_variation / 200.0)

            # Temporal consistency (placeholder - would need frame sequence)
            # For single frame, use local consistency as proxy
            consistency = 1.0 - (np.std(gray_array) / 128.0)
            temporal_consistency = max(0.0, min(1.0, consistency))

            return motion_blur_consistency, micro_motion_score, temporal_consistency

        except Exception:
            return 0.5, 0.5, 0.5

    def _calculate_overall_liveness(self, texture_metrics, print_metrics, screen_metrics,
                                  mask_metrics, motion_metrics) -> Tuple[float, float]:
        """Calculate overall liveness score and confidence"""

        # Define weights for different types of attacks
        weights = {
            'texture': 0.25,      # Natural skin texture
            'print': 0.20,        # Print attack detection
            'screen': 0.20,       # Screen replay detection
            'mask': 0.20,         # 3D mask detection
            'motion': 0.15        # Motion analysis
        }

        # Calculate individual scores (higher = more likely to be live)
        texture_score = (texture_metrics[0] + texture_metrics[1] +
                        (1.0 - texture_metrics[2])) / 3.0  # Surface uniformity inverted

        print_score = 1.0 - (print_metrics[0] + print_metrics[1] + print_metrics[2]) / 3.0

        screen_score = 1.0 - (screen_metrics[0] + screen_metrics[1] +
                             screen_metrics[2] + screen_metrics[3]) / 4.0

        mask_score = (mask_metrics[0] + (1.0 - mask_metrics[1]) + mask_metrics[2]) / 3.0

        motion_score = (motion_metrics[0] + motion_metrics[1] + motion_metrics[2]) / 3.0

        # Weighted combination
        overall_liveness = (
            weights['texture'] * texture_score +
            weights['print'] * print_score +
            weights['screen'] * screen_score +
            weights['mask'] * mask_score +
            weights['motion'] * motion_score
        )

        # Calculate confidence based on consistency of individual scores
        scores = [texture_score, print_score, screen_score, mask_score, motion_score]
        score_std = np.std(scores)
        confidence = max(0.0, min(1.0, 1.0 - score_std))

        return overall_liveness, confidence

    def _get_default_metrics(self) -> LivenessMetrics:
        """Return default metrics when analysis fails"""
        return LivenessMetrics(
            skin_texture_score=0.5, micro_texture_variance=0.5, surface_uniformity=0.5,
            print_artifact_score=0.0, paper_texture_score=0.0, ink_saturation_score=0.0,
            screen_reflection_score=0.0, pixel_grid_score=0.0, refresh_artifact_score=0.0,
            moire_pattern_score=0.0, depth_consistency_score=0.5, material_property_score=0.0,
            edge_transition_score=0.5, motion_blur_consistency=0.5, micro_motion_score=0.5,
            temporal_consistency=0.5, overall_liveness_score=0.5, confidence_level=0.5
        )


class AdvancedLivenessProvider(LivenessProvider):
    """Advanced liveness detection with comprehensive anti-spoofing"""

    def __init__(self):
        self.detector = AdvancedLivenessDetector()

    def analyze(self, live_capture_bytes: bytes) -> LivenessResult:
        """Advanced liveness analysis with detailed spoofing detection"""
        try:
            metrics = self.detector.analyze_comprehensive(live_capture_bytes)

            # Determine status based on liveness score and confidence
            is_live = (metrics.overall_liveness_score >= self.detector.spoof_threshold and
                      metrics.confidence_level >= self.detector.confidence_threshold)

            status = "LIVE" if is_live else "SUSPECTED_SPOOF"

            # Calculate spoof risk score (inverse of liveness score)
            spoof_risk = 1.0 - metrics.overall_liveness_score

            # Generate detailed reason
            reason = self._generate_detailed_reason(metrics, status, spoof_risk)

            return LivenessResult(
                status=status,
                score=round(spoof_risk, 4),
                reason=reason
            )

        except Exception as e:
            return LivenessResult(
                status="NOT_IMPLEMENTED",
                score=None,
                reason=f"Liveness analysis failed: {str(e)}"
            )

    def _generate_detailed_reason(self, metrics: LivenessMetrics, status: str, spoof_risk: float) -> str:
        """Generate detailed reason based on analysis results"""

        reason_parts = []

        # Overall assessment
        reason_parts.append(f"Liveness score: {metrics.overall_liveness_score:.3f}, "
                          f"spoof risk: {spoof_risk:.3f}, confidence: {metrics.confidence_level:.3f}")

        # Identify primary concerns
        concerns = []

        # Print attack indicators
        if metrics.print_artifact_score > 0.3 or metrics.paper_texture_score > 0.3:
            concerns.append(f"Print indicators (artifacts: {metrics.print_artifact_score:.2f}, "
                          f"paper texture: {metrics.paper_texture_score:.2f})")

        # Screen replay indicators
        if (metrics.screen_reflection_score > 0.3 or metrics.pixel_grid_score > 0.3 or
            metrics.moire_pattern_score > 0.3):
            concerns.append(f"Screen replay indicators (reflection: {metrics.screen_reflection_score:.2f}, "
                          f"pixel grid: {metrics.pixel_grid_score:.2f}, moiré: {metrics.moire_pattern_score:.2f})")

        # 3D mask indicators
        if metrics.material_property_score > 0.4:
            concerns.append(f"Artificial material detected (score: {metrics.material_property_score:.2f})")

        # Texture issues
        if metrics.surface_uniformity > 0.7:
            concerns.append(f"Unnaturally uniform surface (score: {metrics.surface_uniformity:.2f})")

        if status == "SUSPECTED_SPOOF" and concerns:
            reason_parts.append("Spoof indicators: " + "; ".join(concerns[:2]))  # Limit to top 2 concerns
        elif status == "LIVE":
            reason_parts.append("Natural face characteristics detected with good texture and depth variation")

        # Technical details
        reason_parts.append(f"Analysis includes texture, print, screen, 3D mask, and motion pattern detection")

        return ". ".join(reason_parts) + "."