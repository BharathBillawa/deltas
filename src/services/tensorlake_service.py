"""
Tensorlake Service - Mock document extraction service.

Mock implementation simulating Tensorlake's document processing API.
In production, this would integrate with the real Tensorlake SDK.

Tensorlake Context:
- Document processing partner (CTO directly involved)
- Runs in SIXT VPC for data security
- Extracts structured data from images/documents
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.models.damage import DamageAssessment, DamageType, DamageSeverity, VehicleLocation

logger = logging.getLogger(__name__)


class TensorlakeService:
    """
    Mock Tensorlake document extraction service.

    Simulates extracting damage assessment from images/documents.
    In production, this would call the real Tensorlake API.

    Features:
    - Extract damage details from photos
    - Parse inspection reports
    - Return structured DamageAssessment
    - Mock implementation using scenario files
    """

    def __init__(self, scenarios_dir: Optional[Path] = None):
        """
        Initialize Tensorlake service.

        Args:
            scenarios_dir: Directory containing scenario files (for mock)
        """
        if scenarios_dir is None:
            project_root = Path(__file__).parent.parent.parent
            scenarios_dir = project_root / "data" / "sample_scenarios"

        self.scenarios_dir = scenarios_dir
        self.mock_mode = True  # Set to False when using real Tensorlake API

        logger.info(f"Tensorlake service initialized (mock_mode={self.mock_mode})")

    def extract_damage_assessment(
        self,
        input_source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DamageAssessment:
        """
        Extract damage assessment from input source.

        In production:
        - input_source: S3 URI, local path, or base64 encoded image
        - Calls Tensorlake API with image/document
        - Returns structured damage assessment

        Mock implementation:
        - input_source: scenario file path or claim_id
        - Loads from scenario JSON files
        - Returns mock damage assessment

        Args:
            input_source: Image/document source (S3 URI, path, or scenario ID)
            metadata: Optional metadata (vehicle_id, inspector_id, etc.)

        Returns:
            DamageAssessment: Structured damage details

        Raises:
            ValueError: If input source not found or invalid
        """
        if self.mock_mode:
            return self._mock_extract(input_source, metadata)
        else:
            return self._real_extract(input_source, metadata)

    def _mock_extract(
        self,
        input_source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DamageAssessment:
        """
        Mock extraction from scenario files.

        Args:
            input_source: Scenario file name or claim_id
            metadata: Optional metadata

        Returns:
            DamageAssessment from scenario file
        """
        logger.info(f"Mock extraction from: {input_source}")

        # Handle empty or invalid input
        if not input_source or not input_source.strip():
            logger.warning("Empty input source, returning generic assessment")
            return self._create_generic_assessment(metadata)

        # Try to find scenario file
        scenario_file = self._find_scenario_file(input_source)

        if not scenario_file:
            # Return a generic damage assessment
            logger.info(f"No scenario found for {input_source}, returning generic assessment")
            return self._create_generic_assessment(metadata)

        # Load scenario
        try:
            with open(scenario_file) as f:
                scenario_data = json.load(f)

            assessment_data = scenario_data["damage_claim"]["damage_assessment"]

            # Build DamageAssessment
            assessment = DamageAssessment(
                damage_type=DamageType(assessment_data["damage_type"]),
                severity=DamageSeverity(assessment_data["severity"]),
                location=VehicleLocation(assessment_data["location"]),
                description=assessment_data["description"],
                affected_parts=assessment_data["affected_parts"],
                photos=assessment_data.get("photos", []),
                inspector_id=assessment_data.get("inspector_id", "TENSORLAKE_AUTO"),
                inspector_notes=assessment_data.get("inspector_notes")
            )

            logger.info(
                f"Extracted: {assessment.damage_type.value} "
                f"({assessment.severity.value}) at {assessment.location.value}"
            )

            return assessment

        except Exception as e:
            logger.error(f"Error loading scenario {scenario_file}: {e}")
            raise ValueError(f"Failed to extract damage assessment: {e}")

    def _find_scenario_file(self, input_source: str) -> Optional[Path]:
        """
        Find scenario file by various identifiers.

        Args:
            input_source: File name, claim_id, or partial match

        Returns:
            Path to scenario file or None
        """
        # Direct file path
        if Path(input_source).exists():
            return Path(input_source)

        # Check scenarios directory
        if not self.scenarios_dir.exists():
            return None

        # Try exact filename
        exact_match = self.scenarios_dir / input_source
        if exact_match.exists():
            return exact_match

        # Try with .json extension
        if not input_source.endswith(".json"):
            with_ext = self.scenarios_dir / f"{input_source}.json"
            if with_ext.exists():
                return with_ext

        # Search for claim_id in scenario files
        for scenario_file in self.scenarios_dir.glob("*.json"):
            try:
                with open(scenario_file) as f:
                    data = json.load(f)
                    claim_id = data.get("damage_claim", {}).get("claim_id", "")
                    if claim_id == input_source:
                        return scenario_file
            except (json.JSONDecodeError, KeyError, IOError):
                continue

        return None

    def _create_generic_assessment(
        self,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DamageAssessment:
        """
        Create a generic damage assessment when no specific data available.

        Args:
            metadata: Optional metadata with hints

        Returns:
            Generic DamageAssessment
        """
        return DamageAssessment(
            damage_type=DamageType.SCRATCH,
            severity=DamageSeverity.MINOR,
            location=VehicleLocation.REAR_BUMPER,
            description="Generic damage assessment from image analysis",
            affected_parts=["bumper"],
            photos=metadata.get("photos", []) if metadata else [],
            inspector_id=metadata.get("inspector_id", "TENSORLAKE_AUTO") if metadata else "TENSORLAKE_AUTO",
            inspector_notes="Automatically extracted by Tensorlake (mock)"
        )

    def _real_extract(
        self,
        input_source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DamageAssessment:
        """
        Real Tensorlake API extraction (not implemented).

        This would integrate with the actual Tensorlake SDK.

        Args:
            input_source: S3 URI or image path
            metadata: Request metadata

        Returns:
            DamageAssessment from Tensorlake API
        """
        raise NotImplementedError(
            "Real Tensorlake integration not implemented. "
            "Set mock_mode=True or implement Tensorlake SDK integration."
        )

    def extract_from_images(
        self,
        image_paths: List[str],
        vehicle_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DamageAssessment:
        """
        Extract damage assessment from multiple images.

        In production, this would:
        - Upload images to Tensorlake
        - Process all images together for better accuracy
        - Return consolidated assessment

        Args:
            image_paths: List of image paths/URIs
            vehicle_id: Vehicle identifier
            metadata: Additional context

        Returns:
            Consolidated DamageAssessment
        """
        logger.info(f"Extracting from {len(image_paths)} images for vehicle {vehicle_id}")

        # In mock mode, just use the first image or vehicle_id
        input_source = image_paths[0] if image_paths else vehicle_id

        combined_metadata = metadata or {}
        combined_metadata["vehicle_id"] = vehicle_id
        combined_metadata["photos"] = image_paths
        combined_metadata["image_count"] = len(image_paths)

        return self.extract_damage_assessment(input_source, combined_metadata)

    def extract_from_pdf_report(
        self,
        pdf_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DamageAssessment:
        """
        Extract damage assessment from PDF inspection report.

        Tensorlake excels at document processing.

        Args:
            pdf_path: Path to PDF inspection report
            metadata: Additional context

        Returns:
            DamageAssessment extracted from PDF
        """
        logger.info(f"Extracting from PDF report: {pdf_path}")

        # In mock mode, treat PDF path as input source
        return self.extract_damage_assessment(pdf_path, metadata)

    def batch_extract(
        self,
        sources: List[Dict[str, Any]]
    ) -> List[DamageAssessment]:
        """
        Batch extraction for multiple claims.

        Efficient processing of multiple documents/images.

        Args:
            sources: List of source dicts with 'input_source' and optional 'metadata'

        Returns:
            List of DamageAssessments
        """
        logger.info(f"Batch extraction: {len(sources)} items")

        results = []
        for source in sources:
            try:
                assessment = self.extract_damage_assessment(
                    input_source=source.get("input_source", ""),
                    metadata=source.get("metadata")
                )
                results.append(assessment)
            except Exception as e:
                logger.error(f"Batch extraction failed for {source}: {e}")
                # Add generic assessment on failure
                results.append(self._create_generic_assessment(source.get("metadata")))

        return results

    def get_extraction_confidence(
        self,
        assessment: DamageAssessment
    ) -> Dict[str, float]:
        """
        Get confidence scores for extracted fields.

        In production, Tensorlake returns confidence scores for each field.

        Args:
            assessment: The damage assessment

        Returns:
            Dict of field names to confidence scores (0.0 to 1.0)
        """
        # Mock confidence scores
        if self.mock_mode:
            return {
                "damage_type": 0.95,
                "severity": 0.92,
                "location": 0.98,
                "affected_parts": 0.88,
                "overall": 0.93
            }

        # Real implementation would return actual Tensorlake confidence scores
        return {}

    def validate_image_quality(
        self,
        image_path: str
    ) -> Dict[str, Any]:
        """
        Validate image quality before processing.

        Checks if image is suitable for damage assessment.

        Args:
            image_path: Path to image

        Returns:
            Dict with quality metrics and pass/fail status
        """
        # Mock quality check
        return {
            "valid": True,
            "resolution": "sufficient",
            "lighting": "good",
            "blur_score": 0.05,
            "recommendations": []
        }
