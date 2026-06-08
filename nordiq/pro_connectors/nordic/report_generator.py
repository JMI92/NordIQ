"""Nordic standard report file generator — implemented in build step 6."""

from nordiq.calculators.base import EPRObligation
from nordiq.pro_connectors.base import ReportFile


class NordicReportGenerator:
    """Generates Nordic standard XML/Excel report files. Implemented in build step 6."""

    def generate(self, obligation: EPRObligation, output_dir: str) -> ReportFile:
        raise NotImplementedError("NordicReportGenerator implemented in build step 6")
