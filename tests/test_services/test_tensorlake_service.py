"""
Tests for Tensorlake Service.

Tests the mock document extraction service.
"""

import pytest
from pathlib import Path

from src.services.tensorlake_service import TensorlakeService
from src.models.damage import DamageType, DamageSeverity, VehicleLocation


@pytest.fixture
def tensorlake_service():
    """Create Tensorlake service instance."""
    return TensorlakeService()


@pytest.fixture
def scenarios_dir():
    """Get scenarios directory path."""
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "sample_scenarios"


class TestTensorlakeServiceInitialization:
    """Tests for service initialization."""

    def test_initialization_default_path(self):
        """Service should initialize with default scenarios directory."""
        service = TensorlakeService()
        assert service.mock_mode is True
        assert service.scenarios_dir.exists()

    def test_initialization_custom_path(self, scenarios_dir):
        """Service should accept custom scenarios directory."""
        service = TensorlakeService(scenarios_dir=scenarios_dir)
        assert service.scenarios_dir == scenarios_dir

    def test_mock_mode_enabled(self, tensorlake_service):
        """Service should be in mock mode by default."""
        assert tensorlake_service.mock_mode is True


class TestExtractDamageAssessment:
    """Tests for damage assessment extraction."""

    def test_extract_from_scenario_file(self, tensorlake_service):
        """Should extract damage assessment from scenario file."""
        assessment = tensorlake_service.extract_damage_assessment(
            "scenario_01_minor_scratch_auto_approve.json"
        )

        assert assessment is not None
        assert assessment.damage_type == DamageType.SCRATCH
        assert assessment.severity == DamageSeverity.MINOR
        assert assessment.location == VehicleLocation.REAR_BUMPER

    def test_extract_by_claim_id(self, tensorlake_service):
        """Should find scenario by claim_id."""
        assessment = tensorlake_service.extract_damage_assessment("CLM-2026-001")

        assert assessment is not None
        assert assessment.damage_type == DamageType.SCRATCH

    def test_extract_bumper_crack_scenario(self, tensorlake_service):
        """Should extract bumper crack from scenario."""
        assessment = tensorlake_service.extract_damage_assessment(
            "scenario_02_luxury_bumper_human_review.json"
        )

        assert assessment.damage_type == DamageType.BUMPER_CRACK
        assert assessment.severity == DamageSeverity.MEDIUM
        assert assessment.location == VehicleLocation.FRONT_BUMPER

    def test_extract_with_metadata(self, tensorlake_service):
        """Should handle metadata parameter."""
        metadata = {
            "vehicle_id": "TEST-VEHICLE-001",
            "inspector_id": "INSP-999"
        }

        assessment = tensorlake_service.extract_damage_assessment(
            "scenario_01_minor_scratch_auto_approve.json",
            metadata=metadata
        )

        assert assessment is not None

    def test_extract_nonexistent_scenario(self, tensorlake_service):
        """Should return generic assessment for nonexistent scenario."""
        assessment = tensorlake_service.extract_damage_assessment(
            "nonexistent_scenario.json"
        )

        # Should return generic assessment instead of failing
        assert assessment is not None
        assert assessment.inspector_id == "TENSORLAKE_AUTO"

    def test_extract_with_invalid_input(self, tensorlake_service):
        """Should handle invalid input gracefully."""
        # Empty string should return generic assessment
        assessment = tensorlake_service.extract_damage_assessment("")

        assert assessment is not None
        assert assessment.damage_type == DamageType.SCRATCH  # Generic default


class TestExtractFromImages:
    """Tests for image-based extraction."""

    def test_extract_from_single_image(self, tensorlake_service):
        """Should extract from single image."""
        image_paths = ["damage_001.jpg"]
        vehicle_id = "VW-POLO-2023-001"

        assessment = tensorlake_service.extract_from_images(
            image_paths=image_paths,
            vehicle_id=vehicle_id
        )

        assert assessment is not None

    def test_extract_from_multiple_images(self, tensorlake_service):
        """Should extract from multiple images."""
        image_paths = [
            "damage_001_overview.jpg",
            "damage_001_detail.jpg",
            "damage_001_angle.jpg"
        ]
        vehicle_id = "VW-POLO-2023-001"

        assessment = tensorlake_service.extract_from_images(
            image_paths=image_paths,
            vehicle_id=vehicle_id,
            metadata={"location": "Munich_Airport"}
        )

        assert assessment is not None

    def test_extract_from_no_images(self, tensorlake_service):
        """Should handle empty image list."""
        assessment = tensorlake_service.extract_from_images(
            image_paths=[],
            vehicle_id="VW-POLO-2023-001"
        )

        assert assessment is not None


class TestExtractFromPDF:
    """Tests for PDF extraction."""

    def test_extract_from_pdf_report(self, tensorlake_service):
        """Should extract from PDF inspection report."""
        pdf_path = "inspection_report.pdf"

        assessment = tensorlake_service.extract_from_pdf_report(
            pdf_path=pdf_path,
            metadata={"vehicle_id": "TEST-001"}
        )

        assert assessment is not None

    def test_extract_from_pdf_with_scenario(self, tensorlake_service):
        """Should extract from PDF using scenario."""
        # Use scenario as PDF path for mock
        assessment = tensorlake_service.extract_from_pdf_report(
            pdf_path="scenario_01_minor_scratch_auto_approve.json"
        )

        assert assessment is not None
        assert assessment.damage_type == DamageType.SCRATCH


class TestBatchExtract:
    """Tests for batch extraction."""

    def test_batch_extract_multiple_sources(self, tensorlake_service):
        """Should process multiple sources in batch."""
        sources = [
            {"input_source": "scenario_01_minor_scratch_auto_approve.json"},
            {"input_source": "scenario_02_luxury_bumper_human_review.json"},
            {"input_source": "CLM-2026-003"}
        ]

        assessments = tensorlake_service.batch_extract(sources)

        assert len(assessments) == 3
        assert all(a is not None for a in assessments)
        assert assessments[0].damage_type == DamageType.SCRATCH
        assert assessments[1].damage_type == DamageType.BUMPER_CRACK

    def test_batch_extract_with_failures(self, tensorlake_service):
        """Should continue processing even if some fail."""
        sources = [
            {"input_source": "scenario_01_minor_scratch_auto_approve.json"},
            {"input_source": "invalid_source_xyz.json"},  # Will fail
            {"input_source": "CLM-2026-001"}
        ]

        assessments = tensorlake_service.batch_extract(sources)

        # Should still return 3 assessments (with generic for failed)
        assert len(assessments) == 3
        assert all(a is not None for a in assessments)

    def test_batch_extract_empty_list(self, tensorlake_service):
        """Should handle empty source list."""
        assessments = tensorlake_service.batch_extract([])
        assert len(assessments) == 0


class TestExtractionConfidence:
    """Tests for confidence scoring."""

    def test_get_extraction_confidence(self, tensorlake_service):
        """Should return confidence scores."""
        assessment = tensorlake_service.extract_damage_assessment(
            "scenario_01_minor_scratch_auto_approve.json"
        )

        confidence = tensorlake_service.get_extraction_confidence(assessment)

        assert "damage_type" in confidence
        assert "severity" in confidence
        assert "location" in confidence
        assert "overall" in confidence

        # All scores should be between 0 and 1
        assert all(0.0 <= score <= 1.0 for score in confidence.values())

    def test_confidence_scores_realistic(self, tensorlake_service):
        """Confidence scores should be realistic (high for mock)."""
        assessment = tensorlake_service.extract_damage_assessment(
            "scenario_01_minor_scratch_auto_approve.json"
        )

        confidence = tensorlake_service.get_extraction_confidence(assessment)

        # Mock confidence should be high
        assert confidence["overall"] > 0.9


class TestImageQuality:
    """Tests for image quality validation."""

    def test_validate_image_quality(self, tensorlake_service):
        """Should validate image quality."""
        quality = tensorlake_service.validate_image_quality("test_image.jpg")

        assert "valid" in quality
        assert "resolution" in quality
        assert "lighting" in quality

    def test_validate_returns_valid(self, tensorlake_service):
        """Mock validation should return valid."""
        quality = tensorlake_service.validate_image_quality("test_image.jpg")
        assert quality["valid"] is True


class TestRealMode:
    """Tests for real mode (not implemented)."""

    def test_real_mode_not_implemented(self):
        """Real mode should raise NotImplementedError."""
        service = TensorlakeService()
        service.mock_mode = False

        with pytest.raises(NotImplementedError):
            service.extract_damage_assessment("test_input")


class TestScenarioFileFinding:
    """Tests for scenario file finding logic."""

    def test_find_scenario_by_filename(self, tensorlake_service):
        """Should find scenario by exact filename."""
        scenario = tensorlake_service._find_scenario_file(
            "scenario_01_minor_scratch_auto_approve.json"
        )
        assert scenario is not None
        assert scenario.exists()

    def test_find_scenario_without_extension(self, tensorlake_service):
        """Should find scenario without .json extension."""
        scenario = tensorlake_service._find_scenario_file(
            "scenario_01_minor_scratch_auto_approve"
        )
        assert scenario is not None
        assert scenario.exists()

    def test_find_scenario_by_claim_id(self, tensorlake_service):
        """Should find scenario by searching claim_id."""
        scenario = tensorlake_service._find_scenario_file("CLM-2026-001")
        assert scenario is not None
        assert scenario.exists()

    def test_find_nonexistent_scenario(self, tensorlake_service):
        """Should return None for nonexistent scenario."""
        scenario = tensorlake_service._find_scenario_file("does_not_exist.json")
        assert scenario is None


class TestGenericAssessment:
    """Tests for generic assessment creation."""

    def test_create_generic_assessment_no_metadata(self, tensorlake_service):
        """Should create generic assessment without metadata."""
        assessment = tensorlake_service._create_generic_assessment()

        assert assessment.damage_type == DamageType.SCRATCH
        assert assessment.severity == DamageSeverity.MINOR
        assert assessment.inspector_id == "TENSORLAKE_AUTO"

    def test_create_generic_assessment_with_metadata(self, tensorlake_service):
        """Should use metadata when creating generic assessment."""
        metadata = {
            "photos": ["photo1.jpg", "photo2.jpg"],
            "inspector_id": "INSP-999"
        }

        assessment = tensorlake_service._create_generic_assessment(metadata)

        assert assessment.photos == ["photo1.jpg", "photo2.jpg"]
        assert assessment.inspector_id == "INSP-999"
