from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.admin import verify_ingest_api_key
from app.auth.dependencies import get_or_create_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import IngestFileResult, IngestResponse, UploadResponse
from app.schemas.property import ListingStatus
from app.schemas.scrape import ScrapeRequest, ScrapeResponse, ScrapeSourceResult
from app.services.ingestion import IngestionService
from app.services.scraping import ScrapeOrchestrator, SUPPORTED_SCRAPE_SOURCES
from app.services.upload_parser import SUPPORTED_DATASET_TYPES

router = APIRouter(prefix="/api/v1/data", tags=["data"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/ingest", response_model=IngestResponse)
def ingest_fallback_data(
    _: None = Depends(verify_ingest_api_key),
    db: Session = Depends(get_db),
) -> IngestResponse:
    service = IngestionService(Path(settings.data_dir))
    result = service.ingest_all(db)

    return IngestResponse(
        files_processed=result.files_processed,
        rows_read=result.rows_read,
        rows_inserted=result.rows_inserted,
        rows_updated=result.rows_updated,
        rows_skipped=result.rows_skipped,
        files=[
            IngestFileResult(
                filename=file.filename,
                rows_read=file.rows_read,
                rows_inserted=file.rows_inserted,
                rows_updated=file.rows_updated,
                rows_skipped=file.rows_skipped,
                errors=file.errors,
            )
            for file in result.files
        ],
        errors=result.errors,
    )


@router.get("/upload/templates/{dataset_type}")
def get_upload_template(dataset_type: str) -> dict[str, object]:
    if dataset_type not in SUPPORTED_DATASET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset type '{dataset_type}'",
        )

    if dataset_type == "properties":
        return {
            "dataset_type": dataset_type,
            "table": "properties",
            "columns": [
                "external_id",
                "source",
                "source_url",
                "title",
                "description",
                "address",
                "city",
                "state",
                "zip_code",
                "price",
                "bedrooms",
                "bathrooms",
                "square_feet",
                "property_type",
                "listing_status",
                "latitude",
                "longitude",
            ],
            "notes": [
                "Prices must be in INR (full rupees for sale, monthly rupees for rent).",
                "property_type: apartment, house, villa, flat, condo, townhome",
                "listing_status: for_sale or for_rent",
                "Rows upsert on (source, external_id).",
            ],
        }

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_type: str = Form(default="properties"),
    _: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB upload limit",
        )

    service = IngestionService(Path(settings.data_dir))
    result = service.ingest_upload(
        db,
        filename=file.filename,
        content=content,
        dataset_type=dataset_type.strip().lower(),
    )

    return UploadResponse(
        dataset_type=dataset_type.strip().lower(),
        filename=result.filename,
        rows_read=result.rows_read,
        rows_inserted=result.rows_inserted,
        rows_updated=result.rows_updated,
        rows_skipped=result.rows_skipped,
        errors=result.errors,
    )


@router.get("/scrape/sources")
def list_scrape_sources() -> dict[str, object]:
    return {
        "sources": sorted(SUPPORTED_SCRAPE_SOURCES.keys()),
        "notes": [
            "Scraping checks robots.txt and rate-limits requests.",
            "Many listing sites block bots or require JavaScript — CSV upload remains the primary fallback.",
            "See docs/COMPLIANCE.md for legal and ethical usage.",
        ],
    }


@router.post("/scrape", response_model=ScrapeResponse)
def scrape_live_listings(
    payload: ScrapeRequest,
    _: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> ScrapeResponse:
    if not settings.scrape_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Live scraping is disabled on this server (SCRAPE_ENABLED=false)",
        )

    ingestion = IngestionService(Path(settings.data_dir))
    orchestrator = ScrapeOrchestrator(ingestion, delay_seconds=settings.scrape_delay_seconds)
    listing_status = ListingStatus(payload.listing_status)

    result = orchestrator.run(
        db,
        sources=payload.sources,
        city=payload.city,
        listing_status=listing_status,
        max_results=payload.max_results,
    )

    return ScrapeResponse(
        city=payload.city,
        listing_status=payload.listing_status,
        rows_read=result.rows_read,
        rows_inserted=result.rows_inserted,
        rows_updated=result.rows_updated,
        rows_skipped=result.rows_skipped,
        sources=[
            ScrapeSourceResult(
                source=source.source,
                fetched=source.fetched,
                parsed=len(source.rows),
                blocked_by_robots=source.blocked_by_robots,
                errors=source.errors,
            )
            for source in result.sources
        ],
        errors=result.errors,
    )
