"""Abstract PRO connector interface — implemented in build step 6/9."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from nordiq.calculators.base import EPRObligation


@dataclass
class ReportFile:
    file_path: str
    file_format: str  # "xml", "xlsx", "pdf"
    checksum: str
    obligation_id: str


@dataclass
class SubmissionResult:
    success: bool
    submission_id: str | None
    response_payload: dict
    error_message: str | None = None


@dataclass
class SubmissionStatus:
    submission_id: str
    status: str
    acknowledged: bool
    response_payload: dict


class BasePROConnector(ABC):
    pro_id: str
    pro_name: str
    country_codes: list[str]

    @abstractmethod
    def generate_report(self, obligation: EPRObligation) -> ReportFile:
        """Generate the report file(s) for submission."""
        ...

    @abstractmethod
    def submit_report(self, report: ReportFile, obligation: EPRObligation) -> SubmissionResult:
        """Submit the report to the PRO."""
        ...

    @abstractmethod
    def check_submission_status(self, submission_id: str) -> SubmissionStatus:
        """Poll the PRO for the status of a previous submission."""
        ...
