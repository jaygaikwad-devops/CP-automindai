"""Property-based test for pipeline sequencing constraint.

**Property 26: Pipeline Sequencing Constraint**
Generate random completion orderings of image_analyzer and pdf_extractor.
Assert: tour_sequencer executes only after both have completed successfully.

**Validates: Requirements 11.4**

Uses hypothesis to verify that tour_sequencer is never dispatched unless
both image_labels.json AND pdf_data.json exist in S3.
"""

import json
import os
from enum import Enum

import boto3
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from moto import mock_aws

os.environ["S3_ASSETS_BUCKET"] = "test-automind-assets"
os.environ["AWS_REGION"] = "ap-south-1"
os.environ["SQS_PROCESSING_QUEUE_URL"] = ""


class CompletionStep(Enum):
    """Possible pipeline step completions."""
    IMAGE_ANALYSIS = "image_analysis"
    PDF_EXTRACTION = "pdf_extraction"


# Strategy: generate random orderings of which steps have completed
completion_states = st.fixed_dictionaries({
    "image_analysis_complete": st.booleans(),
    "pdf_extraction_complete": st.booleans(),
})

# Strategy: generate random sequences of step completions
completion_orderings = st.lists(
    st.sampled_from([CompletionStep.IMAGE_ANALYSIS, CompletionStep.PDF_EXTRACTION]),
    min_size=1,
    max_size=10,
)


class TestPipelineSequencingProperty:
    """Property-based tests for pipeline sequencing constraints.

    **Validates: Requirements 11.4**
    """

    @given(state=completion_states)
    @settings(max_examples=100, deadline=None)
    def test_tour_sequencer_only_after_both_complete(self, state):
        """Property 26: tour_sequencer executes only after BOTH image_analyzer
        AND pdf_extractor have completed successfully.

        **Validates: Requirements 11.4**

        For any combination of completion states:
        - If both are complete → tour_sequencing should be dispatched
        - If either is incomplete → tour_sequencing should NOT be dispatched
        """
        with mock_aws():
            s3 = boto3.client("s3", region_name="ap-south-1")
            s3.create_bucket(
                Bucket="test-automind-assets",
                CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
            )

            project_id = "prop-test-project"

            # Set up S3 based on completion state
            if state["image_analysis_complete"]:
                s3.put_object(
                    Bucket="test-automind-assets",
                    Key=f"projects/{project_id}/analysis/image_labels.json",
                    Body=json.dumps({"images": [{"key": "test.jpg", "labels": []}]}),
                )

            if state["pdf_extraction_complete"]:
                s3.put_object(
                    Bucket="test-automind-assets",
                    Key=f"projects/{project_id}/analysis/pdf_data.json",
                    Body=json.dumps({"brochures": [], "floor_plan": {}}),
                )

            from workers.orchestrator.handler import (
                STEP_PREREQUISITES,
                are_prerequisites_complete,
            )

            result = are_prerequisites_complete(
                s3, project_id, STEP_PREREQUISITES["tour_sequencing"]
            )

            # THE PROPERTY: tour_sequencing prerequisites are met IFF both steps complete
            both_complete = state["image_analysis_complete"] and state["pdf_extraction_complete"]
            assert result == both_complete, (
                f"Expected prerequisites_complete={both_complete} but got {result}. "
                f"State: image={state['image_analysis_complete']}, "
                f"pdf={state['pdf_extraction_complete']}"
            )

    @given(ordering=completion_orderings)
    @settings(max_examples=50, deadline=None)
    def test_sequencing_respects_ordering(self, ordering):
        """Property: Regardless of the order steps complete in, tour_sequencing
        is only triggered when BOTH are done.

        **Validates: Requirements 11.4**

        Simulates a sequence of step completions and verifies that
        tour_sequencing is dispatched exactly when both prerequisites exist.
        """
        with mock_aws():
            s3 = boto3.client("s3", region_name="ap-south-1")
            s3.create_bucket(
                Bucket="test-automind-assets",
                CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
            )
            sqs = boto3.client("sqs", region_name="ap-south-1")
            queue = sqs.create_queue(QueueName="prop-test-queue")
            os.environ["SQS_PROCESSING_QUEUE_URL"] = queue["QueueUrl"]

            project_id = "prop-ordering-test"
            completed_steps = set()
            tour_sequencing_dispatched = False

            from workers.orchestrator.handler import dispatch_next_step

            for step in ordering:
                # Simulate step completion by writing its output file
                if step == CompletionStep.IMAGE_ANALYSIS:
                    s3.put_object(
                        Bucket="test-automind-assets",
                        Key=f"projects/{project_id}/analysis/image_labels.json",
                        Body=json.dumps({"images": []}),
                    )
                    completed_steps.add("image_analysis")
                elif step == CompletionStep.PDF_EXTRACTION:
                    s3.put_object(
                        Bucket="test-automind-assets",
                        Key=f"projects/{project_id}/analysis/pdf_data.json",
                        Body=json.dumps({"brochures": []}),
                    )
                    completed_steps.add("pdf_extraction")

                result = dispatch_next_step(
                    s3, sqs, project_id, step.value, f"job-{step.value}"
                )

                if result["next_step"] == "tour_sequencing":
                    tour_sequencing_dispatched = True
                    # THE PROPERTY: only dispatched when both are done
                    assert "image_analysis" in completed_steps, (
                        "tour_sequencing dispatched without image_analysis complete"
                    )
                    assert "pdf_extraction" in completed_steps, (
                        "tour_sequencing dispatched without pdf_extraction complete"
                    )

            # If both completed at some point, tour_sequencing should have been dispatched
            both_completed = (
                "image_analysis" in completed_steps and "pdf_extraction" in completed_steps
            )
            if both_completed:
                assert tour_sequencing_dispatched, (
                    "Both steps completed but tour_sequencing was never dispatched"
                )
