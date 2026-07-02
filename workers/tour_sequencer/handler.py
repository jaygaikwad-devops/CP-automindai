"""Tour Sequencer Lambda Worker.

Processes SQS messages with job_type: "tour_sequencing".
Reads image analysis and PDF extraction results from S3,
uses Bedrock Claude to generate a Tour_Script JSON.

Requirements: 11.4, 15.1
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
SQS_QUEUE_URL = os.environ.get("SQS_PROCESSING_QUEUE_URL", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")


def get_s3_client():
    """Create S3 client."""
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def get_sqs_client():
    """Create SQS client."""
    return boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def get_bedrock_client():
    """Create Bedrock Runtime client."""
    return boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


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


def generate_tour_script(bedrock_client, image_labels: dict, pdf_data: dict, project_id: str) -> dict:
    """Use Bedrock Claude to generate a Tour_Script JSON.

    Args:
        bedrock_client: Boto3 Bedrock Runtime client.
        image_labels: Image analysis results with labels.
        pdf_data: PDF extraction results with structured data.
        project_id: UUID of the project.

    Returns:
        Tour_Script JSON dict.
    """
    prompt = f"""You are a real estate virtual tour script generator. Based on the following image analysis 
and brochure data, generate a Tour_Script JSON for a virtual property tour.

Image Analysis Data:
{json.dumps(image_labels, indent=2)}

Brochure/Floor Plan Data:
{json.dumps(pdf_data, indent=2)}

Generate a Tour_Script JSON with this EXACT schema:
{{
    "schema_version": "1.0.0",
    "project_id": "{project_id}",
    "project_name": "<extract from brochure data>",
    "total_rooms": <number of rooms>,
    "estimated_duration_seconds": <total narration time>,
    "rooms": [
        {{
            "index": 0,
            "id": "<room_type_snake_case>",
            "name": "<Room Display Name>",
            "room_type": "<living_room|bedroom|kitchen|bathroom|balcony|dining|study|entrance|other>",
            "narration": {{
                "text": "<engaging 2-3 sentence description of the room>",
                "duration_seconds": 30,
                "language": "en"
            }},
            "visuals": {{
                "primary_image_url": "<s3 key of matching image>",
                "thumbnail_url": "<same or thumbnail version>",
                "labels": ["<detected labels>"],
                "dimensions": {{}}
            }},
            "features": [
                {{"name": "<feature>", "category": "<furniture|fixture|design|view|amenity>"}}
            ],
            "transition": {{
                "type": "<slide_left|slide_right|fade|zoom>",
                "duration_ms": 300
            }}
        }}
    ],
    "metadata": {{
        "generated_at": "<ISO timestamp>",
        "pipeline_version": "1.0.0",
        "source_assets": {{
            "images_count": <n>,
            "brochures_count": <n>
        }}
    }}
}}

RULES:
1. Map each image to a room based on its detected labels
2. Group related images into single rooms
3. Order rooms logically: entrance → living → kitchen → bedrooms → bathrooms → balcony
4. Write engaging narration as if "Priya" the AI avatar is guiding the tour
5. The rooms array MUST NOT be empty - include at least one room
6. Return ONLY valid JSON, no other text

Return the Tour_Script JSON:"""

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    })

    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=request_body,
    )

    response_body = json.loads(response["body"].read())
    content_text = response_body["content"][0]["text"]

    # Parse JSON from response
    try:
        if "```json" in content_text:
            json_str = content_text.split("```json")[1].split("```")[0].strip()
        elif "```" in content_text:
            json_str = content_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = content_text.strip()
        return json.loads(json_str)
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"Failed to parse Tour_Script from Bedrock response: {e}")
        raise ValueError(f"Invalid Tour_Script JSON from Bedrock: {e}")


def validate_tour_script(tour_script: dict) -> list[str]:
    """Validate Tour_Script against basic schema rules.

    Args:
        tour_script: Tour_Script dict to validate.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []

    # Required top-level fields
    required_fields = ["schema_version", "project_id", "total_rooms", "rooms"]
    for field in required_fields:
        if field not in tour_script:
            errors.append(f"Missing required field: {field}")

    # Rooms array must not be empty
    rooms = tour_script.get("rooms", [])
    if not isinstance(rooms, list) or len(rooms) == 0:
        errors.append("rooms array must not be empty")
        return errors

    # Validate each room
    required_room_fields = ["index", "id", "name", "room_type", "narration"]
    for i, room in enumerate(rooms):
        for field in required_room_fields:
            if field not in room:
                errors.append(f"Room {i}: missing required field '{field}'")

        # Narration must have text
        narration = room.get("narration", {})
        if not narration.get("text"):
            errors.append(f"Room {i}: narration.text is required")

    return errors


def send_next_step_message(sqs_client, job_id: str, project_id: str) -> None:
    """Send SQS message to trigger the next pipeline step (kb_building).

    Args:
        sqs_client: Boto3 SQS client.
        job_id: Current job UUID.
        project_id: Project UUID.
    """
    if not SQS_QUEUE_URL:
        logger.warning("SQS_PROCESSING_QUEUE_URL not set, skipping next step message")
        return

    message = {
        "job_id": str(uuid.uuid4()),
        "project_id": project_id,
        "job_type": "kb_building",
        "parent_job_id": job_id,
    }

    sqs_client.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(message),
    )

    logger.info(f"Sent kb_building message for project {project_id}")


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for tour sequencing.

    Reads image_labels.json and pdf_data.json from S3, generates a
    Tour_Script using Bedrock Claude, validates it, and stores in S3.
    Then sends SQS message for the next pipeline step (kb_building).

    On failure, the message returns to SQS for retry (up to 3 attempts).

    Args:
        event: SQS event with Records containing message bodies.
        context: Lambda context object.

    Returns:
        Dict with statusCode and processing summary.
    """
    s3_client = get_s3_client()
    sqs_client = get_sqs_client()
    bedrock_client = get_bedrock_client()

    processed_jobs = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            job_id = body["job_id"]
            project_id = body["project_id"]
            job_type = body.get("job_type")

            if job_type != "tour_sequencing":
                logger.warning(
                    f"Unexpected job_type: {job_type} for job {job_id}. Skipping."
                )
                continue

            logger.info(f"Processing tour sequencing job {job_id} for project {project_id}")

            # Read prerequisite data from S3
            image_labels_key = f"projects/{project_id}/analysis/image_labels.json"
            pdf_data_key = f"projects/{project_id}/analysis/pdf_data.json"

            image_labels = read_json_from_s3(s3_client, image_labels_key)
            pdf_data = read_json_from_s3(s3_client, pdf_data_key)

            # Generate Tour_Script using Bedrock
            tour_script = generate_tour_script(
                bedrock_client, image_labels, pdf_data, project_id
            )

            # Ensure metadata is populated
            if "metadata" not in tour_script:
                tour_script["metadata"] = {}
            tour_script["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
            tour_script["metadata"]["pipeline_version"] = "1.0.0"
            tour_script["metadata"]["source_assets"] = {
                "images_count": len(image_labels.get("images", [])),
                "brochures_count": len(pdf_data.get("brochures", [])),
            }

            # Validate the generated Tour_Script
            validation_errors = validate_tour_script(tour_script)
            if validation_errors:
                error_msg = f"Tour_Script validation failed: {validation_errors}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Store Tour_Script in S3
            output_key = f"projects/{project_id}/tour-script.json"
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=output_key,
                Body=json.dumps(tour_script, indent=2),
                ContentType="application/json",
            )

            logger.info(
                f"Stored Tour_Script at {output_key} "
                f"({tour_script.get('total_rooms', 0)} rooms)"
            )

            # Send next step message
            send_next_step_message(sqs_client, job_id, project_id)

            processed_jobs.append({
                "job_id": job_id,
                "project_id": project_id,
                "rooms_generated": len(tour_script.get("rooms", [])),
                "output_key": output_key,
            })

        except Exception as e:
            logger.error(f"Failed to process tour sequencing: {e}", exc_info=True)
            raise

    return {
        "statusCode": 200,
        "body": {"processed": processed_jobs},
    }
