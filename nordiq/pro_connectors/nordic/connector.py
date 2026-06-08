"""Nordic PRO connector — implemented in build step 6/9."""

from nordiq.calculators.base import EPRObligation
from nordiq.pro_connectors.base import BasePROConnector, ReportFile, SubmissionResult, SubmissionStatus


class NordicPROConnector(BasePROConnector):
    """Connector for the Nordic PRO framework (FI/SE/NO/DK). Implemented in build step 6."""

    pro_id = "nordic_pro"
    pro_name = "Nordic PRO Framework"
    country_codes = ["FI", "SE", "NO", "DK"]

    def generate_report(self, obligation: EPRObligation) -> ReportFile:
        raise NotImplementedError("NordicPROConnector implemented in build step 6")

    def submit_report(self, report: ReportFile, obligation: EPRObligation) -> SubmissionResult:
        raise NotImplementedError("NordicPROConnector implemented in build step 9")

    def check_submission_status(self, submission_id: str) -> SubmissionStatus:
        raise NotImplementedError("NordicPROConnector implemented in build step 9")
