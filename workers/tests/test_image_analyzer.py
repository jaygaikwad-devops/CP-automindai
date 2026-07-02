"""Tests for image_analyzer Lambda worker.

Tests image analysis functionality with mocked AWS Rekognition responses.
"""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


# Ensure env vars are set before handler import
os.environ["S3_ASSETS_BUCKET"] = "test-automind-assets"
os.environ["AWS_REGION"] = "ap-south-1"


class TestImageAnalyzer:
    """Tests for the image_analyzer handler."""

    @mock_aws
    def test_handler_processes_images_successfully(self, sqs_event_factory):
        """Test that handler processes images and stores results in S3."""
        # Setup S3
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-001"
        # Upload test images
        for i in range(2):
            s3.put_object(
                Bucket="test-automind-assets",
                Key=f"projects/{project_id}/image/room_{i}.jpg",
                Body=b"fake-image",
            )

        # Mock Rekognition
        mock_rekog_response = {
            "Labels": [
                {"Name": "Sofa", "Confidence": 98.5, "Parents": [{"Name": "Furniture"}]},
                {"Name": "Living Room", "Confidence": 92.3, "Parents": [{"Name": "Room"}]},
                {"Name": "Blur", "Confidence": 55.0, "Parents": []},  # Below threshold
            ]
        }

        with patch("workers.image_analyzer.handler.get_rekognition_client") as mock_get_rekog:
            mock_client = MagicMock()
            mock_client.detect_labels.return_value = mock_rekog_response
            mock_get_rekog.return_value = mock_client

            from workers.image_analyzer.handler import handler

            event = sqs_event_factory("job-001", project_id, "image_analysis")
            result = handler(event, None)

        assert result["statusCode"] == 200
        assert len(result["body"]["processed"]) == 1
        assert result["body"]["processed"][0]["images_processed"] == 2

        # Verify stored results
        stored = s3.get_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
        )
        stored_data = json.loads(stored["Body"].read())
        assert len(stored_data["images"]) == 2

        # Each image should have labels above threshold only
        for image in stored_data["images"]:
            for label in image["labels"]:
                assert label["Confidence"] >= 70.0

    @mock_aws
    def test_handler_no_images_found(self, sqs_event_factory):
        """Test handler with no images in project folder."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-empty"

        from workers.image_analyzer.handler import handler

        event = sqs_event_factory("job-002", project_id, "image_analysis")

        with patch("workers.image_analyzer.handler.get_rekognition_client") as mock_get_rekog:
            mock_get_rekog.return_value = MagicMock()
            result = handler(event, None)

        assert result["statusCode"] == 200
        assert result["body"]["processed"][0]["images_processed"] == 0

        # Empty results should still be stored
        stored = s3.get_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
        )
        stored_data = json.loads(stored["Body"].read())
        assert stored_data == {"images": []}

    @mock_aws
    def test_handler_skips_wrong_job_type(self, sqs_event_factory):
        """Test that handler skips messages with wrong job_type."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        from workers.image_analyzer.handler import handler

        event = sqs_event_factory("job-003", "proj-x", "pdf_extraction")

        with patch("workers.image_analyzer.handler.get_rekognition_client") as mock_get_rekog:
            mock_get_rekog.return_value = MagicMock()
            result = handler(event, None)

        assert result["statusCode"] == 200
        assert result["body"]["processed"] == []

    @mock_aws
    def test_handler_filters_labels_by_confidence(self, sqs_event_factory):
        """Test that labels below 70% confidence are filtered out."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-filter"
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/image/test.png",
            Body=b"fake",
        )

        mock_response = {
            "Labels": [
                {"Name": "HighConf", "Confidence": 95.0, "Parents": []},
                {"Name": "MedConf", "Confidence": 70.1, "Parents": []},
                {"Name": "LowConf", "Confidence": 69.9, "Parents": []},
                {"Name": "VeryLow", "Confidence": 30.0, "Parents": []},
            ]
        }

        with patch("workers.image_analyzer.handler.get_rekognition_client") as mock_get_rekog:
            mock_client = MagicMock()
            mock_client.detect_labels.return_value = mock_response
            mock_get_rekog.return_value = mock_client

            from workers.image_analyzer.handler import handler

            event = sqs_event_factory("job-004", project_id, "image_analysis")
            result = handler(event, None)

        stored = s3.get_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
        )
        stored_data = json.loads(stored["Body"].read())

        labels = stored_data["images"][0]["labels"]
        label_names = [l["Name"] for l in labels]
        assert "HighConf" in label_names
        assert "MedConf" in label_names
        assert "LowConf" not in label_names
        assert "VeryLow" not in label_names

    @mock_aws
    def test_handler_partial_failure_continues(self, sqs_event_factory):
        """Test that failure on one image doesn't stop processing others."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-partial"
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/image/good.jpg",
            Body=b"fake",
        )
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/image/bad.jpg",
            Body=b"fake",
        )

        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            key = kwargs["Image"]["S3Object"]["Name"]
            if "bad" in key:
                raise Exception("Rekognition error")
            return {"Labels": [{"Name": "OK", "Confidence": 90.0, "Parents": []}]}

        with patch("workers.image_analyzer.handler.get_rekognition_client") as mock_get_rekog:
            mock_client = MagicMock()
            mock_client.detect_labels.side_effect = side_effect
            mock_get_rekog.return_value = mock_client

            from workers.image_analyzer.handler import handler

            event = sqs_event_factory("job-005", project_id, "image_analysis")
            result = handler(event, None)

        # Should still succeed and store partial results
        assert result["statusCode"] == 200
        stored = s3.get_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
        )
        stored_data = json.loads(stored["Body"].read())
        assert len(stored_data["images"]) == 2
        # One should have an error
        errors = [img for img in stored_data["images"] if "error" in img]
        assert len(errors) == 1
