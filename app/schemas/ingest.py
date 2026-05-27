from pydantic import BaseModel, Field


class IngestFileResult(BaseModel):
    filename: str
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    errors: list[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    files_processed: int
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    files: list[IngestFileResult]
    errors: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    dataset_type: str
    filename: str
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    errors: list[str] = Field(default_factory=list)
