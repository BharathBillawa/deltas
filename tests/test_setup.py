"""Basic tests to verify project setup."""


def test_project_setup():
    """Verify basic project setup is working."""
    assert True


def test_sample_fixture(sample_claim_data):
    """Test that fixtures are working."""
    assert sample_claim_data["claim_id"] == "TEST-001"
    assert "vehicle_id" in sample_claim_data
