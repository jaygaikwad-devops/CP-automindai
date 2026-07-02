"""Image Analyzer Lambda Worker.

Processes SQS messages with job_type: "image_analysis".
Uses AWS Rekognition to detect labels on project images and stores
results in S3 as structured JSON.

Requirements: 11.2, 11.7
"""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_ASSETS_BUCKET", "automind-assets")
CONFIDENCE_THRESHOLD = 70.0


def get_s3_client():
    """Create S3 client."""
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def get_rekognition_client():
    """Create Rekognition client."""
    return boto3.client("rekognition", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def list_project_images(s3_client, project_id: str) -> list[str]:
    """List all image keys in the project's image folder.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.

    Returns:
        List of S3 object keys for images.
    """
    prefix = f"projects/{project_id}/image/"
    keys = []

    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Only include image files
            if key.lower().endswith((".jpg", ".jpeg", ".png")):
                keys.append(key)

    return keys


def analyze_image(rekognition_client, bucket: str, key: str) -> dict[str, Any]:
    """Run Rekognition DetectLabels on a single image.

    Args:
        rekognition_client: Boto3 Rekognition client.
        bucket: S3 bucket name.
        key: S3 object key.

    Returns:
        Dict with image key and detected labels above confidence threshold.
    """
    response = rekognition_client.detect_labels(
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        MaxLabels=50,
        MinConfidence=CONFIDENCE_THRESHOLD,
    )

    labels = []
    for label in response.get("Labels", []):
        if label["Confidence"] >= CONFIDENCE_THRESHOLD:
            labels.append({
                "Name": label["Name"],
                "Confidence": round(label["Confidence"], 2),
                "Parents": [p["Name"] for p in label.get("Parents", [])],
            })

    return {"key": key, "labels": labels}


def store_results(s3_client, project_id: str, results: list[dict]) -> str:
    """Store analysis results in S3.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.
        results: List of image analysis results.

    Returns:
        S3 key where results were stored.
    """
    output_key = f"projects/{project_id}/analysis/image_labels.json"
    output_data = {"images": results}

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=output_key,
        Body=json.dumps(output_data, indent=2),
        ContentType="application/json",
    )

    return output_key


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for image analysis.

    Processes SQS messages containing job information. For each image
    in the project's S3 folder, runs Rekognition DetectLabels and
    stores aggregated results.

    On failure, the message returns to SQS for retry (up to 3 attempts
    configured in CDK). After retries exhausted, message goes to DLQ.

    Args:
        event: SQS event with Records containing message bodies.
        context: Lambda context object.

    Returns:
        Dict with statusCode and processing summary.
    """
    s3_client = get_s3_client()
    rekognition_client = get_rekognition_client()

    processed_jobs = []
    failed_records = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            job_id = body["job_id"]
            project_id = body["project_id"]
            job_type = body.get("job_type")

            if job_type != "image_analysis":
                logger.warning(
                    f"Unexpected job_type: {job_type} for job {job_id}. Skipping."
                )
                continue

            logger.info(f"Processing image analysis job {job_id} for project {project_id}")

            # List all images in the project folder
            image_keys = list_project_images(s3_client, project_id)

            if not image_keys:
                logger.warning(f"No images found for project {project_id}")
                # Store empty results
                store_results(s3_client, project_id, [])
                processed_jobs.append({"job_id": job_id, "images_processed": 0})
                continue

            # Analyze each image
            results = []
            for key in image_keys:
                try:
                    result = analyze_image(rekognition_client, S3_BUCKET, key)
                    results.append(result)
                except Exception as img_err:
                    logger.error(f"Failed to analyze image {key}: {img_err}")
                    # Continue with other images; partial results are still useful
                    results.append({"key": key, "labels": [], "error": str(img_err)})

            # Store aggregated results
            output_key = store_results(s3_client, project_id, results)
            logger.info(
                f"Stored image analysis results at {output_key} "
                f"({len(results)} images processed)"
            )

            processed_jobs.append({
                "job_id": job_id,
                "project_id": project_id,
                "images_processed": len(results),
                "output_key": output_key,
            })

        except Exception as e:
            logger.error(f"Failed to process record: {e}", exc_info=True)
            # Re-raise to let SQS retry the message
            # After 3 retries, message goes to DLQ
            failed_records.append(record.get("messageId", "unknown"))
            raise

    return {
        "statusCode": 200,
        "body": {
            "processed": processed_jobs,
            "failed": failed_records,
        },
    }
