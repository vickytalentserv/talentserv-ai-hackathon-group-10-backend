import csv
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from app.models import Property
from app.schemas import PropertyCsvRow


@dataclass
class FileIngestResult:
    filename: str
    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class IngestResult:
    files: list[FileIngestResult] = field(default_factory=list)

    @property
    def files_processed(self) -> int:
        return len(self.files)

    @property
    def rows_read(self) -> int:
        return sum(file.rows_read for file in self.files)

    @property
    def rows_inserted(self) -> int:
        return sum(file.rows_inserted for file in self.files)

    @property
    def rows_updated(self) -> int:
        return sum(file.rows_updated for file in self.files)

    @property
    def rows_skipped(self) -> int:
        return sum(file.rows_skipped for file in self.files)

    @property
    def errors(self) -> list[str]:
        return [error for file in self.files for error in file.errors]


class IngestionService:
    CSV_GLOB = "*_fallback.csv"

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def ingest_all(self, db: Session) -> IngestResult:
        result = IngestResult()
        csv_files = sorted(self.data_dir.glob(self.CSV_GLOB))

        if not csv_files:
            result.files.append(
                FileIngestResult(
                    filename=str(self.data_dir),
                    errors=[f"No CSV files matching {self.CSV_GLOB} in {self.data_dir}"],
                )
            )
            return result

        for csv_path in csv_files:
            file_result = self.ingest_file(db, csv_path)
            result.files.append(file_result)

        return result

    def ingest_file(self, db: Session, csv_path: Path) -> FileIngestResult:
        file_result = FileIngestResult(filename=csv_path.name)

        if not csv_path.exists():
            file_result.errors.append(f"File not found: {csv_path}")
            return file_result

        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                file_result.errors.append("CSV file is missing a header row")
                return file_result

            validated_rows: list[PropertyCsvRow] = []
            for line_number, raw_row in enumerate(reader, start=2):
                file_result.rows_read += 1
                try:
                    validated_rows.append(PropertyCsvRow.model_validate(raw_row))
                except ValidationError as exc:
                    file_result.rows_skipped += 1
                    file_result.errors.append(
                        f"{csv_path.name}:{line_number} validation failed: {exc.errors()[0]['msg']}"
                    )

            inserted, updated = self._bulk_upsert(db, validated_rows)
            file_result.rows_inserted = inserted
            file_result.rows_updated = updated

        return file_result

    def _bulk_upsert(self, db: Session, rows: list[PropertyCsvRow]) -> tuple[int, int]:
        inserted = 0
        updated = 0

        for row in rows:
            payload = row.model_dump(mode="json")
            stmt = insert(Property).values(**payload)
            update_payload = {
                key: getattr(stmt.inserted, key)
                for key in payload
                if key not in {"source", "external_id"}
            }
            update_payload["updated_at"] = func.now()
            stmt = stmt.on_duplicate_key_update(**update_payload)
            result = db.execute(stmt)

            if result.rowcount == 1:
                inserted += 1
            elif result.rowcount == 2:
                updated += 1

        db.commit()
        return inserted, updated
