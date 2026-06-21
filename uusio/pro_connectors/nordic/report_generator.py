"""Nordic PRO report file generator.

Generates two files per obligation:
  1. <obligation_id>_<country>_<period>.csv  — machine-readable weight+fee summary
     accepted by all four Nordic PRO portals for manual upload
  2. <obligation_id>_<country>_<period>_manifest.json — full calculation snapshot
     stored alongside the CSV for audit reproducibility

The CSV layout follows the Nordic Packaging Alliance common reporting template
(simplified — real PROs may require portal-specific formats; subclass and override
generate() to produce those).

No network calls are made here — file I/O only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from uusio.calculators.base import EPRObligation
from uusio.pro_connectors.base import ReportFile

# Column order mandated by the Nordic common reporting template
CSV_COLUMNS = [
    "country_code",
    "pro_id",
    "product_category",
    "reporting_period_start",
    "reporting_period_end",
    "material_type",
    "weight_kg",
    "rate_per_kg",
    "fee_amount",
    "currency",
]


class NordicReportGenerator:
    """Generates Nordic standard CSV + JSON manifest report files.

    Args:
        output_dir: Directory where report files are written.
                    Created automatically if it does not exist.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)

    def generate(self, obligation: EPRObligation) -> ReportFile:
        """Write report files for the obligation and return a ReportFile descriptor.

        The returned ReportFile points to the CSV file (primary submission artefact).
        The JSON manifest is written to the same directory with a _manifest.json suffix.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        period = obligation.reporting_period
        base_name = (
            f"{obligation.pro_id}"
            f"_{obligation.country_code}"
            f"_{obligation.product_category.value}"
            f"_{period.start.isoformat()}"
            f"_{period.end.isoformat()}"
        )

        csv_path = self.output_dir / f"{base_name}.csv"
        manifest_path = self.output_dir / f"{base_name}_manifest.json"

        self._write_csv(obligation, csv_path)
        self._write_manifest(obligation, manifest_path)

        checksum = _sha256(csv_path)

        from uusio.core.config import get_settings
        settings = get_settings()
        if settings.use_s3 and settings.s3_bucket:
            from uusio.storage import s3 as s3_storage
            s3_key = f"reports/{base_name}.csv"
            manifest_key = f"reports/{base_name}_manifest.json"
            s3_uri = s3_storage.upload_file(str(csv_path), s3_key)
            s3_storage.upload_file(str(manifest_path), manifest_key)
            # Clean up local temp files
            csv_path.unlink(missing_ok=True)
            manifest_path.unlink(missing_ok=True)
            return ReportFile(
                file_path=s3_uri,
                file_format="csv",
                checksum=checksum,
                obligation_id=_obligation_key(obligation),
            )

        return ReportFile(
            file_path=str(csv_path),
            file_format="csv",
            checksum=checksum,
            obligation_id=_obligation_key(obligation),
        )

    # ------------------------------------------------------------------

    def _write_csv(self, obligation: EPRObligation, path: Path) -> None:
        snap = obligation.calculation_snapshot
        rates_used = snap.get("rates_used", {})
        fee_by_material = snap.get("fee_by_material", {})
        period = obligation.reporting_period

        rows = []
        for material, weight in obligation.weight_by_material.items():
            rows.append({
                "country_code": obligation.country_code,
                "pro_id": obligation.pro_id,
                "product_category": obligation.product_category.value,
                "reporting_period_start": period.start.isoformat(),
                "reporting_period_end": period.end.isoformat(),
                "material_type": material,
                "weight_kg": str(weight),
                "rate_per_kg": rates_used.get(material, ""),
                "fee_amount": fee_by_material.get(material, ""),
                "currency": obligation.currency,
            })

        # Summary totals row
        rows.append({
            "country_code": obligation.country_code,
            "pro_id": obligation.pro_id,
            "product_category": obligation.product_category.value,
            "reporting_period_start": period.start.isoformat(),
            "reporting_period_end": period.end.isoformat(),
            "material_type": "TOTAL",
            "weight_kg": str(obligation.total_weight_kg),
            "rate_per_kg": "",
            "fee_amount": str(obligation.fee_amount),
            "currency": obligation.currency,
        })

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def _write_manifest(self, obligation: EPRObligation, path: Path) -> None:
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "obligation_id": _obligation_key(obligation),
            "pro_id": obligation.pro_id,
            "country_code": obligation.country_code,
            "product_category": obligation.product_category.value,
            "currency": obligation.currency,
            "total_weight_kg": str(obligation.total_weight_kg),
            "total_fee": str(obligation.fee_amount),
            "calculation_snapshot": obligation.calculation_snapshot,
        }
        with path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)


def _obligation_key(obligation: EPRObligation) -> str:
    period = obligation.reporting_period
    return (
        f"{obligation.country_code}"
        f"_{obligation.product_category.value}"
        f"_{period.start.isoformat()}"
        f"_{period.end.isoformat()}"
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
