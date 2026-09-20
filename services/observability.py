import logging
import time
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("helix_os")

class MetricsCollector:
    _metrics = {"request_count": 0, "error_count": 0, "latencies": []}

    @classmethod
    def record_request(cls, status_code: int, duration: float):
        cls._metrics["request_count"] += 1
        if status_code >= 400:
            cls._metrics["error_count"] += 1
        cls._metrics["latencies"].append(duration)

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        avg_latency = sum(cls._metrics["latencies"]) / len(cls._metrics["latencies"]) if cls._metrics["latencies"] else 0.0
        return {
            "total_requests": cls._metrics["request_count"],
            "total_errors": cls._metrics["error_count"],
            "average_latency_seconds": round(avg_latency, 4)
        }
