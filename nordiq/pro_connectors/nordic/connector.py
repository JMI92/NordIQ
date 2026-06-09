"""Nordic PRO connector — portal upload support + simulated API submission.

Real Nordic PROs (Rinki/FI, FTI/SE, Grønt Punkt/NO, DPA/DK) do not expose
a public machine-to-machine API for testing, so:

  - submission_method="portal": generate the CSV; no network call. The caller
    records a PENDING submission; the user downloads the file and uploads it to
    the PRO portal manually, then calls /acknowledge.

  - submission_method="api": simulate a successful API call and return a
    SubmissionResult with a generated reference number. In production this
    would POST to the PRO's HTTPS endpoint with the CSV payload and parse the
    response. Subclass and override submit_report() to integrate a real PRO API.

No network calls are made in this module. All file I/O is done by
NordicReportGenerator (imported from report_generator.py).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from nordiq.calculators.base import EPRObligation
from nordiq.pro_connectors.base import (
    BasePROConnector,
    ReportFile,
    SubmissionResult,
    SubmissionStatus,
)
from nordiq.pro_connectors.nordic.report_generator import NordicReportGenerator


class NordicPROConnector(BasePROConnector):
    """Connector for the Nordic PRO framework (FI/SE/NO/DK).

    Args:
        output_dir: Directory for generated report files. Defaults to /tmp/nordiq_reports.
    """

    pro_id = "nordic_pro"
    pro_name = "Nordic PRO Framework"
    country_codes = ["FI", "SE", "NO", "DK"]

    def __init__(self, output_dir: str = "/tmp/nordiq_reports") -> None:
        self._generator = NordicReportGenerator(output_dir)

    def generate_report(self, obligation: EPRObligation) -> ReportFile:
        return self._generator.generate(obligation)

    def submit_report(self, report: ReportFile, obligation: EPRObligation) -> SubmissionResult:
        """Simulate an API submission to the Nordic PRO.

        In production: POST the CSV to the PRO's HTTPS endpoint and parse
        the HTTP response. Subclass and override this method to wire up the
        real API credentials and endpoint URL.

        Returns a SubmissionResult whose response_payload mirrors what a real
        Nordic PRO API response would look like.
        """
        ref_seed = (
            f"{obligation.country_code}"
            f"_{obligation.product_category.value}"
            f"_{obligation.reporting_period.start.isoformat()}"
            f"_{obligation.reporting_period.end.isoformat()}"
            f"_{datetime.now(timezone.utc).isoformat()}"
        )
        reference = "NP-" + hashlib.sha256(ref_seed.encode()).hexdigest()[:12].upper()

        return SubmissionResult(
            success=True,
            submission_id=reference,
            response_payload={
                "reference": reference,
                "pro_id": self.pro_id,
                "country_code": obligation.country_code,
                "product_category": obligation.product_category.value,
                "reporting_period_start": obligation.reporting_period.start.isoformat(),
                "reporting_period_end": obligation.reporting_period.end.isoformat(),
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "file_checksum": report.checksum,
                "status": "accepted",
                "note": "Simulated response — wire up real PRO API credentials to submit live",
            },
            error_message=None,
        )

    def check_submission_status(self, submission_id: str) -> SubmissionStatus:
        """Poll the PRO for the status of a previous submission.

        In production: GET /submissions/{submission_id} on the PRO's API.
        Here we return a simulated 'acknowledged' status.
        """
        return SubmissionStatus(
            submission_id=submission_id,
            status="acknowledged",
            acknowledged=True,
            response_payload={
                "submission_id": submission_id,
                "status": "acknowledged",
                "note": "Simulated status check",
            },
        )
