"""Shared test fixtures for Lambda worker tests.

Uses moto to mock AWS services (S3, SQS, Rekognition).
"""

import json
import os

import boto3
import pytest
from moto import mock_aws

# Set environment variables before importing handlers
os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"
os.environ["AWS_REGION"] = "ap-south-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["S3_ASSETS_BUCKET"] = "test-automind-assets"
os.environ["SQS_PROCESSING_QUEUE_URL"] = ""


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"


@pytest.fixture
def s3_client(aws_credentials):
    """Create a mocked S3 client and bucket."""
    with mock_aws():
        client = boto3.client("s3", region_name="ap-south-1")
        client.create_bucket(
            Bucket="test-automind-assets",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        yield client


@pytest.fixture
def sqs_client(aws_credentials):
    """Create a mocked SQS client and queue."""
    with mock_aws():
        client = boto3.client("sqs", region_name="ap-south-1")
        queue = client.create_queue(QueueName="test-processing-queue")
        os.environ["SQS_PROCESSING_QUEUE_URL"] = queue["QueueUrl"]
        yield client


@pytest.fixture
def s3_with_project_images(s3_client):
    """S3 bucket pre-populated with test project images."""
    project_id = "test-project-001"
    bucket = "test-automind-assets"

    # Upload dummy image files
    for i in range(3):
        s3_client.put_object(
            Bucket=bucket,
            Key=f"projects/{project_id}/image/room_{i}.jpg",
            Body=b"fake-image-content",
            ContentType="image/jpeg",
        )

    return project_id


@pytest.fixture
def s3_with_analysis_results(s3_client):
    """S3 bucket pre-populated with analysis results for orchestration tests."""
    project_id = "test-project-002"
    bucket = "test-automind-assets"

    image_labels = {
        "images": [
            {"key": f"projects/{project_id}/image/room_0.jpg", "labels": [
                {"Name": "Living Room", "Confidence": 95.0, "Parents": ["Room"]},
                {"Name": "Sofa", "Confidence": 92.0, "Parents": ["Furniture"]},
            ]},
        ]
    }

    pdf_data = {
        "brochures": [
            {
                "key": f"projects/{project_id}/brochure/main.pdf",
                "extracted_text": "Luxury apartment with 3BHK configuration...",
                "structured": {
                    "amenities": ["Swimming Pool", "Gym", "Club House"],
                    "specs": {"bedrooms": 3, "bathrooms": 2, "area_sqft": 1500},
                },
            }
        ],
        "floor_plan": {
            "key": f"projects/{project_id}/floor_plan/plan.pdf",
            "rooms": [
                {"name": "Living Room", "area_sqft": 350, "type": "living_room"},
                {"name": "Master Bedroom", "area_sqft": 200, "type": "bedroom"},
            ],
        },
    }

    s3_client.put_object(
        Bucket=bucket,
        Key=f"projects/{project_id}/analysis/image_labels.json",
        Body=json.dumps(image_labels),
        ContentType="application/json",
    )

    s3_client.put_object(
        Bucket=bucket,
        Key=f"projects/{project_id}/analysis/pdf_data.json",
        Body=json.dumps(pdf_data),
        ContentType="application/json",
    )

    return project_id


@pytest.fixture
def sqs_event_factory():
    """Factory for creating SQS event dicts for Lambda handlers."""

    def _create_event(job_id: str, project_id: str, job_type: str, **extra_fields) -> dict:
        body = {
            "job_id": job_id,
            "project_id": project_id,
            "job_type": job_type,
            **extra_fields,
        }
        return {
            "Records": [
                {
                    "messageId": f"msg-{job_id}",
                    "body": json.dumps(body),
                    "receiptHandle": "test-receipt",
                    "attributes": {},
                    "messageAttributes": {},
                    "md5OfBody": "",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:ap-south-1:123456789:test-queue",
                    "awsRegion": "ap-south-1",
                }
            ]
        }

    return _create_event
