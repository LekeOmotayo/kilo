"""
TokenOps Repository for telemetry, metrics, and financial ROI aggregations.
"""

from typing import Any, Dict, List
from app.services.tokenops import tokenops_service


class TokenOpsRepository:
    """Repository managing financial analytics, token usage meters, and model rates."""

    def __init__(self, service=tokenops_service):
        self.service = service

    def get_summary(self) -> Dict[str, Any]:
        """Fetch cumulative TokenOps savings, hit counts, and financial stats."""
        return self.service.get_summary()

    def get_model_rates(self) -> Dict[str, Any]:
        """Fetch per-model pricing rates and tier mappings."""
        return self.service.get_model_rates()

    def export_metrics(self) -> bytes:
        """Export raw Prometheus metrics buffer."""
        return self.service.export_prometheus_metrics()
