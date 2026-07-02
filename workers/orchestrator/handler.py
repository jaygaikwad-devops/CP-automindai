"""Pipeline Orchestrator Lambda Worker.

A dispatcher that routes SQS messages to the correct next pipeline step.
Tracks pipeline status and checks prerequisites before advancing stages.

Requirements: 11.6, 11.7, 11.8
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_ASSETS_BUCKET", "automind-assets")

# Pipeline step ordering
PIPELINE_STEPS = [
    "image_analysis",
    "pdf_extraction",
    "tour_sequencing",
    "kb_building",
    "tour_ready",
]

# Prerequisites mapping: step -> required files in S3
STEP_PREREQUISITES = {
    "tour_sequencing": [
        "projects/{project_id}/analysis/image_labels.json",
        "projects/{project_id}/analysis/pdf_data.json",
    ],
    "kb_building": [
        "projects/{project_id}/tour-script.json",
        "projects/{project_id}/analysis/pdf_data.json",
    ],
}


def get_s3_client():
    """Create S3 client."""
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def get_sqs_client():
    """Create SQS client."""
    return boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def s3_object_exists(s3_client, key: str) -> bool:
    """Check if an S3 object exists.

    Args:
        s3_client: Boto3 S3 client.
        key: S3 object key.

    Returns:
        True if object exists, False otherwise.
    """
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except s3_client.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def are_prerequisites_complete(s3_client, project_id: str, required_steps: list[str]) -> bool:
    """Verify that prerequisite files exist in S3 before advancing pipeline.

    Checks that both image_labels.json and pdf_data.json (or other required files)
    exist before allowing the next step to proceed.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.
        required_steps: List of S3 key templates (with {project_id} placeholder).

    Returns:
        True if all prerequisite files exist, False otherwise.
    """
    for step_template in required_steps:
        key = step_template.format(project_id=project_id)
        if not s3_object_exists(s3_client, key):
            logger.info(f"Prerequisite not met: {key} does not exist")
            return False

    return True


def get_pipeline_status(s3_client, project_id: str) -> dict:
    """Read current pipeline status from S3.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.

    Returns:
        Pipeline status dict or empty dict if not found.
    """
    key = f"projects/{project_id}/analysis/pipeline_status.json"
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except s3_client.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return {}
        raise


def update_pipeline_status(
    s3_client, project_id: str, step: str, status: str, details: dict | None = None
) -> dict:
    """Update pipeline status in S3.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.
        step: Current pipeline step name.
        status: Status string (e.g., 'completed', 'in_progress', 'failed').
        details: Optional additional details.

    Returns:
        Updated status dict.
    """
    current_status = get_pipeline_status(s3_client, project_id)

    if "steps" not in current_status:
        current_status = {
            "project_id": project_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": {},
            "current_step": step,
            "overall_status": "in_progress",
        }

    current_status["steps"][step] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **(details or {}),
    }
    current_status["current_step"] = step
    current_status["last_updated"] = datetime.now(timezone.utc).isoformat()

    if status == "completed" and step == "kb_building":
        current_status["overall_status"] = "tour_ready"
        current_status["completed_at"] = datetime.now(timezone.utc).isoformat()

    key = f"projects/{project_id}/analysis/pipeline_status.json"
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(current_status, indent=2),
        ContentType="application/json",
    )

    return current_status


def send_sqs_message(sqs_client, job_type: str, project_id: str, parent_job_id: str = "") -> str:
    """Send an SQS message to trigger the next pipeline step.

    Args:
        sqs_client: Boto3 SQS client.
        job_type: The job type for the next step.
        project_id: UUID of the project.
        parent_job_id: ID of the parent job that triggered this.

    Returns:
        The new job ID.
    """
    queue_url = os.environ.get("SQS_PROCESSING_QUEUE_URL", "")
    if not queue_url:
        logger.warning("SQS_PROCESSING_QUEUE_URL not set, skipping message send")
        return ""

    new_job_id = str(uuid.uuid4())
    message = {
        "job_id": new_job_id,
        "project_id": project_id,
        "job_type": job_type,
        "parent_job_id": parent_job_id,
    }

    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message),
    )

    logger.info(f"Sent {job_type} message for project {project_id} (job: {new_job_id})")
    return new_job_id


def dispatch_next_step(
    s3_client, sqs_client, project_id: str, completed_step: str, job_id: str
) -> dict:
    """Determine and dispatch the next pipeline step based on completion.

    Logic:
    - After image_analysis completes: check if pdf_extraction also done,
      if so send tour_sequencing
    - After pdf_extraction completes: check if image_analysis also done,
      if so send tour_sequencing
    - After tour_sequencing completes: send kb_building
    - After kb_building completes: mark project as tour_ready

    Args:
        s3_client: Boto3 S3 client.
        sqs_client: Boto3 SQS client.
        project_id: UUID of the project.
        completed_step: The step that just completed.
        job_id: Current job ID.

    Returns:
        Dict with next_step and status information.
    """
    result = {"completed_step": completed_step, "next_step": None}

    if completed_step in ("image_analysis", "pdf_extraction"):
        # Check if both prerequisites for tour_sequencing are met
        prerequisites = STEP_PREREQUISITES["tour_sequencing"]
        if are_prerequisites_complete(s3_client, project_id, prerequisites):
            new_job_id = send_sqs_message(sqs_client, "tour_sequencing", project_id, job_id)
            result["next_step"] = "tour_sequencing"
            result["next_job_id"] = new_job_id
            update_pipeline_status(s3_client, project_id, "tour_sequencing", "queued")
        else:
            logger.info(
                f"Prerequisites for tour_sequencing not yet met for project {project_id}. "
                f"Waiting for other step to complete."
            )
            result["next_step"] = "waiting_for_prerequisites"

    elif completed_step == "tour_sequencing":
        new_job_id = send_sqs_message(sqs_client, "kb_building", project_id, job_id)
        result["next_step"] = "kb_building"
        result["next_job_id"] = new_job_id
        update_pipeline_status(s3_client, project_id, "kb_building", "queued")

    elif completed_step == "kb_building":
        result["next_step"] = "tour_ready"
        update_pipeline_status(s3_client, project_id, "kb_building", "completed")

    return result


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for pipeline orchestration.

    Routes SQS messages to trigger the correct next step based on what
    just completed. Manages pipeline status tracking in S3.

    Message body format:
    {
        "job_id": "uuid",
        "project_id": "uuid",
        "job_type": "step_complete",
        "completed_step": "image_analysis|pdf_extraction|tour_sequencing|kb_building"
    }

    Args:
        event: SQS event with Records containing message bodies.
        context: Lambda context object.

    Returns:
        Dict with statusCode and dispatch summary.
    """
    s3_client = get_s3_client()
    sqs_client = get_sqs_client()

    dispatched = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            job_id = body["job_id"]
            project_id = body["project_id"]
            completed_step = body.get("completed_step", body.get("job_type", ""))

            logger.info(
                f"Orchestrator received: step={completed_step}, "
                f"project={project_id}, job={job_id}"
            )

            # Update status for the completed step
            update_pipeline_status(s3_client, project_id, completed_step, "completed")

            # Dispatch next step
            result = dispatch_next_step(s3_client, sqs_client, project_id, completed_step, job_id)
            dispatched.append(result)

            logger.info(f"Dispatch result: {result}")

        except Exception as e:
            logger.error(f"Failed to process orchestration message: {e}", exc_info=True)
            raise

    return {
        "statusCode": 200,
        "body": {"dispatched": dispatched},
    }
