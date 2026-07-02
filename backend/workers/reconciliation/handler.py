"""DynamoDB-to-RDS Reconciliation Lambda.

Scheduled every 5 minutes via CloudWatch Events. Queries DynamoDB GSI1
for sessions updated in the last 10 minutes and ensures corresponding
RDS leads rows exist and are up-to-date. Emits CloudWatch metrics for
any reconciliation gaps detected.
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuration from environment
import os

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE_NAME", "automind_sessions")
RDS_SECRET_ARN = os.environ.get("RDS_SECRET_ARN", "")
RDS_CLUSTER_ARN = os.environ.get("RDS_CLUSTER_ARN", "")
RDS_DATABASE = os.environ.get("RDS_DATABASE", "automind")
METRIC_NAMESPACE = "AutoMind/Reconciliation"
LOOKBACK_MINUTES = 10


def handler(event: dict, context: Any) -> dict:
    """Lambda entry point — triggered every 5 min by CloudWatch Events.

    Queries DynamoDB for recently-updated sessions, checks if corresponding
    RDS rows exist with matching data, and upserts any missing/stale rows.

    Args:
        event: CloudWatch Events scheduled event payload.
        context: Lambda context object.

    Returns:
        Summary dict with counts of checked, gaps, and upserted sessions.
    """
    logger.info("Reconciliation Lambda started")
    start_time = time.time()

    try:
        # Get recently-updated sessions from DynamoDB
        sessions = _get_recent_sessions()
        logger.info(f"Found {len(sessions)} sessions updated in last {LOOKBACK_MINUTES} minutes")

        gaps_found = 0
        upserted = 0

        for session in sessions:
            session_id = session.get("session_id", "")
            if not session_id:
                continue

            # Check if RDS has matching row
            is_synced = _check_rds_sync(session)
            if not is_synced:
                gaps_found += 1
                success = _upsert_rds_row(session)
                if success:
                    upserted += 1

        # Emit CloudWatch metrics
        _emit_metrics(
            sessions_checked=len(sessions),
            gaps_found=gaps_found,
            upserted=upserted,
            duration_ms=int((time.time() - start_time) * 1000),
        )

        result = {
            "sessions_checked": len(sessions),
            "gaps_found": gaps_found,
            "upserted": upserted,
            "duration_ms": int((time.time() - start_time) * 1000),
        }

        logger.info(f"Reconciliation complete: {json.dumps(result)}")
        return result

    except Exception as e:
        logger.error(f"Reconciliation failed: {e}", exc_info=True)
        _emit_metrics(
            sessions_checked=0,
            gaps_found=-1,
            upserted=0,
            duration_ms=int((time.time() - start_time) * 1000),
            error=True,
        )
        raise


def _get_recent_sessions() -> list[dict[str, Any]]:
    """Query DynamoDB GSI1 for sessions updated in the last 10 minutes.

    Scans the table for sessions with updated_at within the lookback window.
    In production, this would use a GSI with a timestamp-based sort key.

    Returns:
        List of session dicts with relevant fields.
    """
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    cutoff_iso = cutoff.isoformat()

    # Scan for recently updated sessions (in production, use GSI with time-based SK)
    # For now, scan with filter — acceptable at low scale with 5-min intervals
    response = table.scan(
        FilterExpression="#sk = :meta AND #ca >= :cutoff",
        ExpressionAttributeNames={
            "#sk": "SK",
            "#ca": "created_at",
        },
        ExpressionAttributeValues={
            ":meta": "META",
            ":cutoff": cutoff_iso,
        },
        ProjectionExpression=(
            "session_id, cp_id, project_id, score, classification, "
            "signals, created_at, buyer_name, buyer_phone"
        ),
    )

    sessions = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="#sk = :meta AND #ca >= :cutoff",
            ExpressionAttributeNames={
                "#sk": "SK",
                "#ca": "created_at",
            },
            ExpressionAttributeValues={
                ":meta": "META",
                ":cutoff": cutoff_iso,
            },
            ProjectionExpression=(
                "session_id, cp_id, project_id, score, classification, "
                "signals, created_at, buyer_name, buyer_phone"
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        sessions.extend(response.get("Items", []))

    return sessions


def _check_rds_sync(session: dict[str, Any]) -> bool:
    """Check if RDS leads row exists and matches DynamoDB data.

    Uses RDS Data API for serverless Aurora access.

    Args:
        session: DynamoDB session data dict.

    Returns:
        True if RDS row exists with matching score, False otherwise.
    """
    if not RDS_CLUSTER_ARN or not RDS_SECRET_ARN:
        # RDS not configured — treat as gap
        return False

    try:
        rds_data = boto3.client("rds-data", region_name=AWS_REGION)
        session_id = session["session_id"]

        response = rds_data.execute_statement(
            resourceArn=RDS_CLUSTER_ARN,
            secretArn=RDS_SECRET_ARN,
            database=RDS_DATABASE,
            sql="SELECT score, classification FROM leads WHERE session_id = :session_id",
            parameters=[
                {"name": "session_id", "value": {"stringValue": session_id}},
            ],
        )

        records = response.get("records", [])
        if not records:
            return False

        # Compare score
        rds_score = records[0][0].get("longValue", 0)
        ddb_score = int(session.get("score", 0))

        return rds_score == ddb_score

    except Exception as e:
        logger.warning(f"RDS check failed for session {session.get('session_id')}: {e}")
        return False


def _upsert_rds_row(session: dict[str, Any]) -> bool:
    """Upsert a leads row in RDS from DynamoDB session data.

    Args:
        session: DynamoDB session data dict.

    Returns:
        True if upsert succeeded, False otherwise.
    """
    if not RDS_CLUSTER_ARN or not RDS_SECRET_ARN:
        logger.warning("RDS not configured — skipping upsert")
        return False

    try:
        rds_data = boto3.client("rds-data", region_name=AWS_REGION)

        session_id = session["session_id"]
        cp_id = session.get("cp_id", "")
        project_id = session.get("project_id", "")
        score = int(session.get("score", 0))
        classification = session.get("classification", "browsing")
        signals = json.dumps(session.get("signals", {}))
        buyer_name = session.get("buyer_name", "")
        buyer_phone = session.get("buyer_phone", "")
        now = datetime.now(timezone.utc).isoformat()

        sql = """
            INSERT INTO leads (session_id, cp_id, project_id, score, classification,
                              signals, buyer_name, buyer_phone, updated_at)
            VALUES (:session_id, :cp_id, :project_id, :score, :classification,
                    :signals::jsonb, :buyer_name, :buyer_phone, :updated_at)
            ON CONFLICT (session_id)
            DO UPDATE SET
                score = :score,
                classification = :classification,
                signals = :signals::jsonb,
                buyer_name = :buyer_name,
                buyer_phone = :buyer_phone,
                updated_at = :updated_at
        """

        rds_data.execute_statement(
            resourceArn=RDS_CLUSTER_ARN,
            secretArn=RDS_SECRET_ARN,
            database=RDS_DATABASE,
            sql=sql,
            parameters=[
                {"name": "session_id", "value": {"stringValue": session_id}},
                {"name": "cp_id", "value": {"stringValue": cp_id}},
                {"name": "project_id", "value": {"stringValue": project_id}},
                {"name": "score", "value": {"longValue": score}},
                {"name": "classification", "value": {"stringValue": classification}},
                {"name": "signals", "value": {"stringValue": signals}},
                {"name": "buyer_name", "value": {"stringValue": buyer_name}},
                {"name": "buyer_phone", "value": {"stringValue": buyer_phone}},
                {"name": "updated_at", "value": {"stringValue": now}},
            ],
        )

        logger.info(f"Upserted RDS row for session {session_id}")
        return True

    except Exception as e:
        logger.error(f"RDS upsert failed for session {session.get('session_id')}: {e}")
        return False


def _emit_metrics(
    sessions_checked: int,
    gaps_found: int,
    upserted: int,
    duration_ms: int,
    error: bool = False,
) -> None:
    """Emit CloudWatch metrics for reconciliation run.

    Args:
        sessions_checked: Number of sessions checked.
        gaps_found: Number of gaps detected.
        upserted: Number of rows upserted.
        duration_ms: Execution duration in milliseconds.
        error: Whether the run errored.
    """
    try:
        cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)

        metrics = [
            {
                "MetricName": "SessionsChecked",
                "Value": sessions_checked,
                "Unit": "Count",
            },
            {
                "MetricName": "GapsFound",
                "Value": max(gaps_found, 0),
                "Unit": "Count",
            },
            {
                "MetricName": "RowsUpserted",
                "Value": upserted,
                "Unit": "Count",
            },
            {
                "MetricName": "ExecutionDuration",
                "Value": duration_ms,
                "Unit": "Milliseconds",
            },
        ]

        if error:
            metrics.append({
                "MetricName": "Errors",
                "Value": 1,
                "Unit": "Count",
            })

        cloudwatch.put_metric_data(
            Namespace=METRIC_NAMESPACE,
            MetricData=[
                {
                    **m,
                    "Timestamp": datetime.now(timezone.utc),
                    "Dimensions": [
                        {"Name": "Environment", "Value": os.environ.get("ENVIRONMENT", "dev")},
                    ],
                }
                for m in metrics
            ],
        )

    except Exception as e:
        # Metrics are best-effort — don't fail the Lambda
        logger.warning(f"Failed to emit CloudWatch metrics: {e}")
