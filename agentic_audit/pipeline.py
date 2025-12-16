from typing import List, Dict
from .agents.document_agent import DocumentAgent
from .agents.fraud_agent import FraudAgent
from .agents.compliance_agent import ComplianceAgent
from .agents.vendor_agent import VendorAgent
from .agents.summary_agent import SummaryAgent


class Pipeline:
    """Runs the agent pipeline on provided documents/records."""

    def __init__(self):
        self.document = DocumentAgent()
        self.fraud = FraudAgent()
        self.compliance = ComplianceAgent()
        self.vendor = VendorAgent()
        self.summary = SummaryAgent()

    def run(self, documents: List[Dict]) -> Dict:
        records = self.document.run(documents)
        fraud_findings = self.fraud.run(records)
        compliance_findings = self.compliance.run(records)
        vendor_findings = self.vendor.run(records)

        aggregated = {
            "meta": {"total": len(records)},
            "records": records,
            "fraud": fraud_findings,
            "compliance": compliance_findings,
            "vendor": vendor_findings,
        }

        summary = self.summary.run(aggregated)
        aggregated["summary"] = summary
        return aggregated
