#!/usr/bin/env python
"""
Demo script for Tensorlake document extraction service.

Shows how the mock service extracts damage assessments from scenarios.
"""

import logging
from pathlib import Path

from src.services.tensorlake_service import TensorlakeService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Demo Tensorlake service capabilities."""
    print("\n" + "=" * 70)
    print("TENSORLAKE DOCUMENT EXTRACTION DEMO")
    print("=" * 70)

    # Initialize service
    service = TensorlakeService()
    print(f"\nService initialized (mock_mode={service.mock_mode})")

    # Demo 1: Extract from scenario file
    print("\n" + "-" * 70)
    print("Demo 1: Extract damage assessment from scenario file")
    print("-" * 70)

    assessment = service.extract_damage_assessment(
        "scenario_01_minor_scratch_auto_approve.json"
    )

    print(f"\nDamage Type: {assessment.damage_type.value}")
    print(f"Severity: {assessment.severity.value}")
    print(f"Location: {assessment.location.value}")
    print(f"Description: {assessment.description}")
    print(f"Affected Parts: {', '.join(assessment.affected_parts)}")

    # Get confidence scores
    confidence = service.get_extraction_confidence(assessment)
    print(f"\nConfidence Scores:")
    for field, score in confidence.items():
        print(f"  - {field}: {score:.1%}")

    # Demo 2: Extract from multiple images
    print("\n" + "-" * 70)
    print("Demo 2: Extract from multiple vehicle images")
    print("-" * 70)

    image_paths = [
        "damage_002_crack.jpg",
        "damage_002_front.jpg"
    ]

    assessment = service.extract_from_images(
        image_paths=image_paths,
        vehicle_id="AUDI-A6-2019-004",
        metadata={"location": "Berlin_City"}
    )

    print(f"\nExtracted from {len(image_paths)} images:")
    print(f"Damage: {assessment.damage_type.value} ({assessment.severity.value})")
    print(f"Location: {assessment.location.value}")

    # Demo 3: Batch extraction
    print("\n" + "-" * 70)
    print("Demo 3: Batch extraction from multiple sources")
    print("-" * 70)

    sources = [
        {"input_source": "scenario_01_minor_scratch_auto_approve.json"},
        {"input_source": "scenario_02_luxury_bumper_human_review.json"},
        {"input_source": "scenario_03_pattern_detection_frequent_damage.json"},
    ]

    assessments = service.batch_extract(sources)

    print(f"\nProcessed {len(assessments)} claims:")
    for i, assessment in enumerate(assessments, 1):
        print(f"  {i}. {assessment.damage_type.value} - {assessment.severity.value}")

    # Demo 4: Image quality validation
    print("\n" + "-" * 70)
    print("Demo 4: Image quality validation")
    print("-" * 70)

    quality = service.validate_image_quality("test_damage_photo.jpg")

    print(f"\nQuality Check:")
    print(f"  Valid: {quality['valid']}")
    print(f"  Resolution: {quality['resolution']}")
    print(f"  Lighting: {quality['lighting']}")
    print(f"  Blur Score: {quality['blur_score']}")

    # Demo 5: Extract by claim ID
    print("\n" + "-" * 70)
    print("Demo 5: Extract by searching claim_id")
    print("-" * 70)

    assessment = service.extract_damage_assessment("CLM-2026-002")

    print(f"\nFound scenario for claim CLM-2026-002:")
    print(f"Damage: {assessment.damage_type.value}")
    print(f"Inspector: {assessment.inspector_id}")

    # Summary
    print("\n" + "=" * 70)
    print("TENSORLAKE INTEGRATION NOTES")
    print("=" * 70)
    print("""
In production, TensorlakeService would:
  - Accept S3 URIs or image uploads
  - Call real Tensorlake API for document processing
  - Return structured extraction with confidence scores
  - Handle PDF inspection reports
  - Validate image quality before processing
  - Support batch processing for efficiency

Current mock implementation:
  - Loads from scenario JSON files
  - Simulates Tensorlake API behavior
  - Returns realistic confidence scores
  - Demonstrates integration pattern

To switch to production:
  - Set mock_mode=False
  - Implement _real_extract() with Tensorlake SDK
  - Configure Tensorlake API credentials
  - Deploy in SIXT VPC for security
    """)


if __name__ == "__main__":
    main()
