"""Tests for pipeline orchestrator.

Tests pipeline sequencing logic and status management.
"""

import json
import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

os.environ["S3_ASSETS_BUCKET"] = "test-automind-assets"
os.environ["AWS_REGION"] = "ap-south-1"


class TestArePrerequisitesComplete:
    """Tests for the are_prerequisites_complete function."""

    @mock_aws
    def test_prerequisites_met_when_both_files_exist(self):
        """Test that prerequisites are met when both analysis files exist."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-prereq-ok"

        # Create both prerequisite files
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
            Body=json.dumps({"images": []}),
        )
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/pdf_data.json",
            Body=json.dumps({"brochures": []}),
        )

        from workers.orchestrator.handler import STEP_PREREQUISITES, are_prerequisites_complete

        result = are_prerequisites_complete(
            s3, project_id, STEP_PREREQUISITES["tour_sequencing"]
        )
        assert result is True

    @mock_aws
    def test_prerequisites_not_met_when_image_labels_missing(self):
        """Test that prerequisites fail when image_labels.json is missing."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-prereq-no-img"

        # Only create pdf_data
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/pdf_data.json",
            Body=json.dumps({"brochures": []}),
        )

        from workers.orchestrator.handler import STEP_PREREQUISITES, are_prerequisites_complete

        result = are_prerequisites_complete(
            s3, project_id, STEP_PREREQUISITES["tour_sequencing"]
        )
        assert result is False

    @mock_aws
    def test_prerequisites_not_met_when_pdf_data_missing(self):
        """Test that prerequisites fail when pdf_data.json is missing."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-prereq-no-pdf"

        # Only create image_labels
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
            Body=json.dumps({"images": []}),
        )

        from workers.orchestrator.handler import STEP_PREREQUISITES, are_prerequisites_complete

        result = are_prerequisites_complete(
            s3, project_id, STEP_PREREQUISITES["tour_sequencing"]
        )
        assert result is False

    @mock_aws
    def test_prerequisites_not_met_when_both_missing(self):
        """Test that prerequisites fail when both files are missing."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-prereq-empty"

        from workers.orchestrator.handler import STEP_PREREQUISITES, are_prerequisites_complete

        result = are_prerequisites_complete(
            s3, project_id, STEP_PREREQUISITES["tour_sequencing"]
        )
        assert result is False


class TestDispatchNextStep:
    """Tests for pipeline dispatch logic."""

    @mock_aws
    def test_dispatch_tour_sequencing_after_both_complete(self):
        """Test that tour_sequencing is dispatched when both image and pdf are done."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        sqs = boto3.client("sqs", region_name="ap-south-1")
        queue = sqs.create_queue(QueueName="test-queue")
        os.environ["SQS_PROCESSING_QUEUE_URL"] = queue["QueueUrl"]

        project_id = "proj-dispatch-ok"

        # Both prerequisite files exist
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
            Body=json.dumps({"images": []}),
        )
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/pdf_data.json",
            Body=json.dumps({"brochures": []}),
        )

        from workers.orchestrator.handler import dispatch_next_step

        result = dispatch_next_step(s3, sqs, project_id, "image_analysis", "job-1")
        assert result["next_step"] == "tour_sequencing"

        # Verify SQS message was sent
        messages = sqs.receive_message(QueueUrl=queue["QueueUrl"], MaxNumberOfMessages=1)
        assert len(messages.get("Messages", [])) == 1
        msg_body = json.loads(messages["Messages"][0]["Body"])
        assert msg_body["job_type"] == "tour_sequencing"
        assert msg_body["project_id"] == project_id

    @mock_aws
    def test_dispatch_waits_when_image_not_complete(self):
        """Test that dispatch waits when only pdf is done but image isn't."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        sqs = boto3.client("sqs", region_name="ap-south-1")
        queue = sqs.create_queue(QueueName="test-queue2")
        os.environ["SQS_PROCESSING_QUEUE_URL"] = queue["QueueUrl"]

        project_id = "proj-dispatch-wait"

        # Only pdf_data exists
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/pdf_data.json",
            Body=json.dumps({"brochures": []}),
        )

        from workers.orchestrator.handler import dispatch_next_step

        result = dispatch_next_step(s3, sqs, project_id, "pdf_extraction", "job-2")
        assert result["next_step"] == "waiting_for_prerequisites"

        # No SQS message should be sent
        messages = sqs.receive_message(QueueUrl=queue["QueueUrl"], MaxNumberOfMessages=1)
        assert len(messages.get("Messages", [])) == 0

    @mock_aws
    def test_dispatch_kb_building_after_tour_sequencing(self):
        """Test that kb_building is dispatched after tour_sequencing completes."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        sqs = boto3.client("sqs", region_name="ap-south-1")
        queue = sqs.create_queue(QueueName="test-queue3")
        os.environ["SQS_PROCESSING_QUEUE_URL"] = queue["QueueUrl"]

        project_id = "proj-dispatch-tour"

        from workers.orchestrator.handler import dispatch_next_step

        result = dispatch_next_step(s3, sqs, project_id, "tour_sequencing", "job-3")
        assert result["next_step"] == "kb_building"

        messages = sqs.receive_message(QueueUrl=queue["QueueUrl"], MaxNumberOfMessages=1)
        assert len(messages.get("Messages", [])) == 1
        msg_body = json.loads(messages["Messages"][0]["Body"])
        assert msg_body["job_type"] == "kb_building"

    @mock_aws
    def test_dispatch_tour_ready_after_kb_building(self):
        """Test that project is marked tour_ready after kb_building completes."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        sqs = boto3.client("sqs", region_name="ap-south-1")
        queue = sqs.create_queue(QueueName="test-queue4")
        os.environ["SQS_PROCESSING_QUEUE_URL"] = queue["QueueUrl"]

        project_id = "proj-dispatch-ready"

        from workers.orchestrator.handler import dispatch_next_step

        result = dispatch_next_step(s3, sqs, project_id, "kb_building", "job-4")
        assert result["next_step"] == "tour_ready"

        # Verify status was updated in S3
        status = s3.get_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/pipeline_status.json",
        )
        status_data = json.loads(status["Body"].read())
        assert status_data["overall_status"] == "tour_ready"


class TestPipelineStatusTracking:
    """Tests for pipeline status updates in S3."""

    @mock_aws
    def test_update_pipeline_status_creates_file(self):
        """Test that update_pipeline_status creates status file on first call."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-status-new"

        from workers.orchestrator.handler import update_pipeline_status

        result = update_pipeline_status(s3, project_id, "image_analysis", "completed")

        assert result["project_id"] == project_id
        assert result["steps"]["image_analysis"]["status"] == "completed"
        assert result["overall_status"] == "in_progress"

    @mock_aws
    def test_update_pipeline_status_appends_steps(self):
        """Test that multiple status updates append to the same file."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )

        project_id = "proj-status-multi"

        from workers.orchestrator.handler import update_pipeline_status

        update_pipeline_status(s3, project_id, "image_analysis", "completed")
        result = update_pipeline_status(s3, project_id, "pdf_extraction", "completed")

        assert "image_analysis" in result["steps"]
        assert "pdf_extraction" in result["steps"]
        assert result["steps"]["image_analysis"]["status"] == "completed"
        assert result["steps"]["pdf_extraction"]["status"] == "completed"


class TestOrchestratorHandler:
    """Integration tests for the orchestrator handler."""

    @mock_aws
    def test_handler_processes_completion_message(self, sqs_event_factory):
        """Test full handler invocation with a step completion message."""
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        sqs = boto3.client("sqs", region_name="ap-south-1")
        queue = sqs.create_queue(QueueName="test-handler-queue")
        os.environ["SQS_PROCESSING_QUEUE_URL"] = queue["QueueUrl"]

        project_id = "proj-handler-test"

        # Both prerequisites exist
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/image_labels.json",
            Body=json.dumps({"images": []}),
        )
        s3.put_object(
            Bucket="test-automind-assets",
            Key=f"projects/{project_id}/analysis/pdf_data.json",
            Body=json.dumps({"brochures": []}),
        )

        from workers.orchestrator.handler import handler

        event = sqs_event_factory(
            "job-handler-1", project_id, "step_complete",
            completed_step="image_analysis",
        )
        result = handler(event, None)

        assert result["statusCode"] == 200
        assert result["body"]["dispatched"][0]["next_step"] == "tour_sequencing"
