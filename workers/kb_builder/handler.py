"""KB Builder Lambda Worker.

Processes SQS messages with job_type: "kb_building".
Reads tour-script.json and pdf_data.json from S3, creates or updates
a Bedrock Knowledge Base data source, and starts ingestion.

Requirements: 11.5, 11.6
"""

import json
import logging
import os
import time
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_ASSETS_BUCKET", "automind-assets")
KB_ID = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID", "")
MAX_POLL_SECONDS = 300  # 5 minutes max wait for ingestion
POLL_INTERVAL_SECONDS = 10
POLL_BACKOFF_FACTOR = 1.5


def get_s3_client():
    """Create S3 client."""
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def get_bedrock_agent_client():
    """Create Bedrock Agent client for Knowledge Base operations."""
    return boto3.client("bedrock-agent", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def read_json_from_s3(s3_client, key: str) -> dict:
    """Read and parse a JSON file from S3.

    Args:
        s3_client: Boto3 S3 client.
        key: S3 object key.

    Returns:
        Parsed JSON dict.
    """
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    content = response["Body"].read().decode("utf-8")
    return json.loads(content)


def get_or_create_data_source(bedrock_agent_client, knowledge_base_id: str, project_id: str) -> str:
    """Get existing or create a new data source for the project.

    Args:
        bedrock_agent_client: Boto3 Bedrock Agent client.
        knowledge_base_id: Knowledge Base ID.
        project_id: UUID of the project.

    Returns:
        Data source ID.
    """
    # List existing data sources to check if one exists for this project
    try:
        response = bedrock_agent_client.list_data_sources(
            knowledgeBaseId=knowledge_base_id,
        )

        for ds in response.get("dataSourceSummaries", []):
            if project_id in ds.get("name", ""):
                logger.info(f"Found existing data source for project {project_id}: {ds['dataSourceId']}")
                return ds["dataSourceId"]
    except Exception as e:
        logger.warning(f"Error listing data sources: {e}")

    # Create new data source pointing to the project's S3 prefix
    response = bedrock_agent_client.create_data_source(
        knowledgeBaseId=knowledge_base_id,
        name=f"project-{project_id}",
        description=f"Data source for project {project_id}",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{S3_BUCKET}",
                "inclusionPrefixes": [f"projects/{project_id}/"],
            },
        },
    )

    data_source_id = response["dataSource"]["dataSourceId"]
    logger.info(f"Created new data source for project {project_id}: {data_source_id}")
    return data_source_id


def start_and_wait_for_ingestion(
    bedrock_agent_client, knowledge_base_id: str, data_source_id: str
) -> str:
    """Start an ingestion job and wait for completion with backoff.

    Args:
        bedrock_agent_client: Boto3 Bedrock Agent client.
        knowledge_base_id: Knowledge Base ID.
        data_source_id: Data source ID to ingest.

    Returns:
        Ingestion job status.

    Raises:
        TimeoutError: If ingestion doesn't complete within MAX_POLL_SECONDS.
        RuntimeError: If ingestion fails.
    """
    # Start ingestion
    response = bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id,
    )

    ingestion_job_id = response["ingestionJob"]["ingestionJobId"]
    logger.info(f"Started ingestion job: {ingestion_job_id}")

    # Poll with exponential backoff
    elapsed = 0
    interval = POLL_INTERVAL_SECONDS

    while elapsed < MAX_POLL_SECONDS:
        time.sleep(interval)
        elapsed += interval

        status_response = bedrock_agent_client.get_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            ingestionJobId=ingestion_job_id,
        )

        status = status_response["ingestionJob"]["status"]
        logger.info(f"Ingestion job {ingestion_job_id} status: {status} (elapsed: {elapsed}s)")

        if status == "COMPLETE":
            return status
        elif status in ("FAILED", "STOPPED"):
            failure_reasons = status_response["ingestionJob"].get("failureReasons", [])
            raise RuntimeError(
                f"Ingestion job failed with status {status}: {failure_reasons}"
            )

        # Exponential backoff
        interval = min(interval * POLL_BACKOFF_FACTOR, 30)

    raise TimeoutError(
        f"Ingestion job {ingestion_job_id} did not complete within {MAX_POLL_SECONDS}s"
    )


def store_kb_status(s3_client, project_id: str, kb_id: str, data_source_id: str) -> None:
    """Store Knowledge Base status in S3.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.
        kb_id: Knowledge Base ID.
        data_source_id: Data source ID.
    """
    status_data = {
        "kb_id": kb_id,
        "data_source_id": data_source_id,
        "project_id": project_id,
        "status": "ready",
        "ingestion_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=f"projects/{project_id}/analysis/kb_status.json",
        Body=json.dumps(status_data, indent=2),
        ContentType="application/json",
    )


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for Knowledge Base building.

    Reads tour-script.json and pdf_data.json from S3, creates or updates
    a Bedrock Knowledge Base data source, starts ingestion, and waits
    for completion. Updates project status to 'tour_ready' upon success.

    On failure, the message returns to SQS for retry (up to 3 attempts).

    Args:
        event: SQS event with Records containing message bodies.
        context: Lambda context object.

    Returns:
        Dict with statusCode and processing summary.
    """
    s3_client = get_s3_client()
    bedrock_agent_client = get_bedrock_agent_client()

    processed_jobs = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            job_id = body["job_id"]
            project_id = body["project_id"]
            job_type = body.get("job_type")

            if job_type != "kb_building":
                logger.warning(
                    f"Unexpected job_type: {job_type} for job {job_id}. Skipping."
                )
                continue

            logger.info(f"Processing KB building job {job_id} for project {project_id}")

            # Verify prerequisite files exist
            tour_script_key = f"projects/{project_id}/tour-script.json"
            pdf_data_key = f"projects/{project_id}/analysis/pdf_data.json"

            # Read to verify existence (will raise if not found)
            read_json_from_s3(s3_client, tour_script_key)
            read_json_from_s3(s3_client, pdf_data_key)

            knowledge_base_id = KB_ID
            if not knowledge_base_id:
                logger.error("BEDROCK_KNOWLEDGE_BASE_ID not configured")
                raise ValueError("BEDROCK_KNOWLEDGE_BASE_ID environment variable is required")

            # Create or update data source
            data_source_id = get_or_create_data_source(
                bedrock_agent_client, knowledge_base_id, project_id
            )

            # Start ingestion and wait for completion
            ingestion_status = start_and_wait_for_ingestion(
                bedrock_agent_client, knowledge_base_id, data_source_id
            )

            # Store KB status
            store_kb_status(s3_client, project_id, knowledge_base_id, data_source_id)

            logger.info(
                f"KB building complete for project {project_id}. "
                f"Status: {ingestion_status}"
            )

            processed_jobs.append({
                "job_id": job_id,
                "project_id": project_id,
                "kb_id": knowledge_base_id,
                "data_source_id": data_source_id,
                "ingestion_status": ingestion_status,
            })

        except Exception as e:
            logger.error(f"Failed to process KB building: {e}", exc_info=True)
            raise

    return {
        "statusCode": 200,
        "body": {"processed": processed_jobs},
    }
