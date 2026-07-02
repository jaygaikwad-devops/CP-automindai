"""Tour Script Pydantic models for AutoMind AI Platform.

Defines the Tour_Script schema as Pydantic v2 models for
serialization, parsing, and validation of tour script JSON.
"""

from pydantic import BaseModel, ConfigDict


class Narration(BaseModel):
    """Narration block for a room in the tour."""

    model_config = ConfigDict(extra="ignore")

    text: str
    duration_seconds: int
    language: str = "en"


class Dimensions(BaseModel):
    """Image dimensions (optional)."""

    model_config = ConfigDict(extra="ignore")

    width: int | None = None
    height: int | None = None


class Visuals(BaseModel):
    """Visual assets for a room."""

    model_config = ConfigDict(extra="ignore")

    primary_image_url: str
    thumbnail_url: str | None = None
    labels: list[str]
    dimensions: Dimensions | None = None


class Feature(BaseModel):
    """A feature highlight within a room."""

    model_config = ConfigDict(extra="ignore")

    name: str
    category: str


class Transition(BaseModel):
    """Transition configuration between rooms."""

    model_config = ConfigDict(extra="ignore")

    type: str = "slide_left"
    duration_ms: int = 300


class Room(BaseModel):
    """A single room in the tour script."""

    model_config = ConfigDict(extra="ignore")

    index: int
    id: str
    name: str
    room_type: str
    narration: Narration
    visuals: Visuals | None = None
    features: list[Feature] = []
    transition: Transition | None = None


class SourceAssets(BaseModel):
    """Metadata about source assets processed."""

    model_config = ConfigDict(extra="ignore")

    images_processed: int | None = None
    pdfs_processed: int | None = None


class Metadata(BaseModel):
    """Tour script generation metadata."""

    model_config = ConfigDict(extra="ignore")

    generated_at: str
    pipeline_version: str
    source_assets: SourceAssets | None = None


class TourScript(BaseModel):
    """Top-level Tour Script model.

    Represents the complete tour script for a project,
    including all rooms, narration, visuals, and metadata.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: str
    project_id: str
    project_name: str
    total_rooms: int
    estimated_duration_seconds: int
    rooms: list[Room]
    metadata: Metadata | None = None
