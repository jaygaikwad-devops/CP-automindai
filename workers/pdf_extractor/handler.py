"""PDF Extractor Lambda Worker.

Processes SQS messages with job_type: "pdf_extraction".
Uses AWS Textract to extract text from brochures and floor plans,
then uses Bedrock Claude to structure the data into JSON.

Requirements: 11.3, 11.7
"""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_ASSETS_BUCKET", "automind-assets")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")


def get_s3_client():
    """Create S3 client."""
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def get_textract_client():
    """Create Textract client."""
    return boto3.client("textract", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def get_bedrock_client():
    """Create Bedrock Runtime client."""
    return boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def list_files_by_prefix(s3_client, project_id: str, folder: str) -> list[str]:
    """List S3 keys under a project folder.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.
        folder: Sub-folder name (e.g., 'brochure', 'floor_plan').

    Returns:
        List of S3 object keys.
    """
    prefix = f"projects/{project_id}/{folder}/"
    keys = []

    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
                keys.append(key)

    return keys


def extract_text_from_document(textract_client, bucket: str, key: str) -> str:
    """Extract text from a document using AWS Textract.

    Args:
        textract_client: Boto3 Textract client.
        bucket: S3 bucket name.
        key: S3 object key.

    Returns:
        Extracted text as a single string.
    """
    response = textract_client.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    # Combine all LINE blocks into a single text
    lines = []
    for block in response.get("Blocks", []):
        if block["BlockType"] == "LINE":
            lines.append(block.get("Text", ""))

    return "\n".join(lines)


def structure_text_with_bedrock(bedrock_client, extracted_text: str, doc_type: str) -> dict:
    """Use Bedrock Claude to structure extracted text into JSON.

    Args:
        bedrock_client: Boto3 Bedrock Runtime client.
        extracted_text: Raw text extracted from the document.
        doc_type: Type of document ('brochure' or 'floor_plan').

    Returns:
        Structured data dict.
    """
    if doc_type == "brochure":
        prompt = f"""Analyze the following real estate brochure text and extract structured information.
Return a JSON object with the following fields:
- "amenities": list of amenities mentioned
- "specs": object with specifications (area, bedrooms, bathrooms, etc.)
- "description": brief project description
- "pricing": any pricing information found (or null if not found)

Text:
{extracted_text}

Return ONLY valid JSON, no other text."""
    else:
        prompt = f"""Analyze the following floor plan text and extract room information.
Return a JSON object with the following fields:
- "rooms": list of rooms with "name", "area_sqft" (if available), and "type"

Text:
{extracted_text}

Return ONLY valid JSON, no other text."""

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    })

    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=request_body,
    )

    response_body = json.loads(response["body"].read())
    content_text = response_body["content"][0]["text"]

    # Parse the JSON from Claude's response
    try:
        # Try to extract JSON if wrapped in code blocks
        if "```json" in content_text:
            json_str = content_text.split("```json")[1].split("```")[0].strip()
        elif "```" in content_text:
            json_str = content_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = content_text.strip()
        return json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse Bedrock response as JSON, returning raw text")
        return {"raw_response": content_text}


def store_results(s3_client, project_id: str, results: dict) -> str:
    """Store extraction results in S3.

    Args:
        s3_client: Boto3 S3 client.
        project_id: UUID of the project.
        results: Extraction results dict.

    Returns:
        S3 key where results were stored.
    """
    output_key = f"projects/{project_id}/analysis/pdf_data.json"

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=output_key,
        Body=json.dumps(results, indent=2),
        ContentType="application/json",
    )

    return output_key


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for PDF extraction.

    Processes SQS messages containing job information. For each PDF/brochure
    and floor plan in the project's S3 folder, runs Textract for text extraction
    and Bedrock Claude for structuring.

    On failure, the message returns to SQS for retry (up to 3 attempts).
    After retries exhausted, message goes to DLQ.

    Args:
        event: SQS event with Records containing message bodies.
        context: Lambda context object.

    Returns:
        Dict with statusCode and processing summary.
    """
    s3_client = get_s3_client()
    textract_client = get_textract_client()
    bedrock_client = get_bedrock_client()

    processed_jobs = []
    failed_records = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            job_id = body["job_id"]
            project_id = body["project_id"]
            job_type = body.get("job_type")

            if job_type != "pdf_extraction":
                logger.warning(
                    f"Unexpected job_type: {job_type} for job {job_id}. Skipping."
                )
                continue

            logger.info(f"Processing PDF extraction job {job_id} for project {project_id}")

            # Process brochures
            brochure_keys = list_files_by_prefix(s3_client, project_id, "brochure")
            brochures = []

            for key in brochure_keys:
                try:
                    extracted_text = extract_text_from_document(textract_client, S3_BUCKET, key)
                    structured = structure_text_with_bedrock(
                        bedrock_client, extracted_text, "brochure"
                    )
                    brochures.append({
                        "key": key,
                        "extracted_text": extracted_text,
                        "structured": structured,
                    })
                except Exception as doc_err:
                    logger.error(f"Failed to process brochure {key}: {doc_err}")
                    brochures.append({
                        "key": key,
                        "extracted_text": "",
                        "structured": {},
                        "error": str(doc_err),
                    })

            # Process floor plans
            floor_plan_keys = list_files_by_prefix(s3_client, project_id, "floor_plan")
            floor_plan_data = {}

            if floor_plan_keys:
                # Process the first floor plan (required: exactly one)
                fp_key = floor_plan_keys[0]
                try:
                    extracted_text = extract_text_from_document(
                        textract_client, S3_BUCKET, fp_key
                    )
                    structured = structure_text_with_bedrock(
                        bedrock_client, extracted_text, "floor_plan"
                    )
                    floor_plan_data = {
                        "key": fp_key,
                        "rooms": structured.get("rooms", []),
                    }
                except Exception as fp_err:
                    logger.error(f"Failed to process floor plan {fp_key}: {fp_err}")
                    floor_plan_data = {"key": fp_key, "rooms": [], "error": str(fp_err)}

            # Aggregate results
            results = {
                "brochures": brochures,
                "floor_plan": floor_plan_data,
            }

            output_key = store_results(s3_client, project_id, results)
            logger.info(
                f"Stored PDF extraction results at {output_key} "
                f"({len(brochures)} brochures, floor_plan: {bool(floor_plan_data)})"
            )

            processed_jobs.append({
                "job_id": job_id,
                "project_id": project_id,
                "brochures_processed": len(brochures),
                "has_floor_plan": bool(floor_plan_data),
                "output_key": output_key,
            })

        except Exception as e:
            logger.error(f"Failed to process record: {e}", exc_info=True)
            failed_records.append(record.get("messageId", "unknown"))
            raise

    return {
        "statusCode": 200,
        "body": {
            "processed": processed_jobs,
            "failed": failed_records,
        },
    }
