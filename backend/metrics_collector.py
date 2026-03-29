"""
Metrics collection for DTN bundle experiments.
Tracks per-bundle and aggregate statistics for quantitative evaluation.
"""
import csv
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from statistics import mean, median, stdev


@dataclass
class BundleMetrics:
    bundle_id: str
    source: str
    destination: str
    priority: str
    created_at: float  # time.time() epoch
    plaintext_size: int = 0
    encrypted_size: int = 0
    total_wire_size: int = 0
    custody_transfer: bool = True
    fragmented: bool = False
    fragment_count: int = 1

    delivered_at: Optional[float] = None
    delivered: bool = False
    failed: bool = False
    failure_reason: Optional[str] = None
    hop_count: int = 0
    hops: List[str] = field(default_factory=list)

    retransmissions: int = 0
    custody_acks: int = 0
    custody_naks: int = 0

    encrypt_time_ms: float = 0.0
    pib_time_ms: float = 0.0
    bab_time_ms: float = 0.0
    security_overhead_bytes: int = 0

    @property
    def delivery_latency_sec(self) -> Optional[float]:
        if self.delivered_at is not None and self.created_at:
            return self.delivered_at - self.created_at
        return None


@dataclass
class ExperimentSummary:
    experiment_name: str
    total_bundles: int
    delivered_count: int
    failed_count: int
    delivery_ratio: float
    latency_mean_sec: float
    latency_median_sec: float
    latency_p95_sec: float
    latency_min_sec: float
    latency_max_sec: float
    total_retransmissions: int
    total_acks: int
    total_naks: int
    avg_hop_count: float
    avg_encrypt_time_ms: float
    avg_security_overhead_bytes: float
    effective_throughput_bps: float
    duration_sec: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "total_bundles": self.total_bundles,
            "delivered_count": self.delivered_count,
            "failed_count": self.failed_count,
            "delivery_ratio": round(self.delivery_ratio, 4),
            "latency_mean_sec": round(self.latency_mean_sec, 2),
            "latency_median_sec": round(self.latency_median_sec, 2),
            "latency_p95_sec": round(self.latency_p95_sec, 2),
            "latency_min_sec": round(self.latency_min_sec, 2),
            "latency_max_sec": round(self.latency_max_sec, 2),
            "total_retransmissions": self.total_retransmissions,
            "total_acks": self.total_acks,
            "total_naks": self.total_naks,
            "avg_hop_count": round(self.avg_hop_count, 2),
            "avg_encrypt_time_ms": round(self.avg_encrypt_time_ms, 3),
            "avg_security_overhead_bytes": round(self.avg_security_overhead_bytes, 1),
            "effective_throughput_bps": round(self.effective_throughput_bps, 2),
            "duration_sec": round(self.duration_sec, 2),
        }


class MetricsCollector:
    """Collects per-bundle metrics and computes aggregate experiment summaries."""

    def __init__(self, experiment_name: str = "default"):
        self.experiment_name = experiment_name
        self._metrics: Dict[str, BundleMetrics] = {}
        self._start_time: float = time.time()
        self._enabled = True
        self._sim_clock: Optional[float] = None  # if set, overrides time.time()

    def _now(self) -> float:
        return self._sim_clock if self._sim_clock is not None else time.time()

    def set_sim_clock(self, t: float) -> None:
        """Set simulated clock (seconds). Overrides wall clock for timestamps."""
        self._sim_clock = t

    def reset(self, experiment_name: Optional[str] = None):
        self._metrics.clear()
        self._start_time = self._now()
        if experiment_name:
            self.experiment_name = experiment_name

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    # ---- Event hooks ----

    def on_bundle_created(self, bundle_id: str, source: str, destination: str,
                          priority: str, plaintext_size: int, encrypted_size: int,
                          total_wire_size: int, fragmented: bool = False,
                          fragment_count: int = 1,
                          custody_transfer: bool = True) -> None:
        if not self._enabled:
            return
        self._metrics[bundle_id] = BundleMetrics(
            bundle_id=bundle_id,
            source=source,
            destination=destination,
            priority=priority,
            created_at=self._now(),
            plaintext_size=plaintext_size,
            encrypted_size=encrypted_size,
            total_wire_size=total_wire_size,
            fragmented=fragmented,
            fragment_count=fragment_count,
            custody_transfer=custody_transfer,
        )

    def on_bundle_delivered(self, bundle_id: str, hops: List[str]) -> None:
        if not self._enabled:
            return
        m = self._metrics.get(bundle_id)
        if m:
            m.delivered = True
            m.delivered_at = self._now()
            m.hops = list(hops)
            m.hop_count = max(0, len(hops) - 1)

    def on_bundle_failed(self, bundle_id: str, reason: str) -> None:
        if not self._enabled:
            return
        m = self._metrics.get(bundle_id)
        if m:
            m.failed = True
            m.failure_reason = reason

    def on_ack_received(self, bundle_id: str) -> None:
        if not self._enabled:
            return
        m = self._metrics.get(bundle_id)
        if m:
            m.custody_acks += 1

    def on_nak_received(self, bundle_id: str) -> None:
        if not self._enabled:
            return
        m = self._metrics.get(bundle_id)
        if m:
            m.custody_naks += 1

    def on_retransmission(self, bundle_id: str) -> None:
        if not self._enabled:
            return
        m = self._metrics.get(bundle_id)
        if m:
            m.retransmissions += 1

    def on_security_measured(self, bundle_id: str, encrypt_time_ms: float,
                             pib_time_ms: float, bab_time_ms: float,
                             overhead_bytes: int) -> None:
        if not self._enabled:
            return
        m = self._metrics.get(bundle_id)
        if m:
            m.encrypt_time_ms = encrypt_time_ms
            m.pib_time_ms = pib_time_ms
            m.bab_time_ms = bab_time_ms
            m.security_overhead_bytes = overhead_bytes

    # ---- Summaries ----

    def _percentile(self, sorted_data: List[float], pct: float) -> float:
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * (pct / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

    def compute_summary(self) -> ExperimentSummary:
        all_metrics = list(self._metrics.values())
        total = len(all_metrics)
        delivered = [m for m in all_metrics if m.delivered]
        failed = [m for m in all_metrics if m.failed]

        latencies = sorted(
            [m.delivery_latency_sec for m in delivered if m.delivery_latency_sec is not None]
        )
        duration = self._now() - self._start_time

        total_payload_delivered = sum(m.plaintext_size for m in delivered)
        effective_throughput = (total_payload_delivered * 8 / duration) if duration > 0 else 0.0

        return ExperimentSummary(
            experiment_name=self.experiment_name,
            total_bundles=total,
            delivered_count=len(delivered),
            failed_count=len(failed),
            delivery_ratio=len(delivered) / total if total > 0 else 0.0,
            latency_mean_sec=mean(latencies) if latencies else 0.0,
            latency_median_sec=median(latencies) if latencies else 0.0,
            latency_p95_sec=self._percentile(latencies, 95) if latencies else 0.0,
            latency_min_sec=min(latencies) if latencies else 0.0,
            latency_max_sec=max(latencies) if latencies else 0.0,
            total_retransmissions=sum(m.retransmissions for m in all_metrics),
            total_acks=sum(m.custody_acks for m in all_metrics),
            total_naks=sum(m.custody_naks for m in all_metrics),
            avg_hop_count=mean([m.hop_count for m in delivered]) if delivered else 0.0,
            avg_encrypt_time_ms=mean([m.encrypt_time_ms for m in all_metrics]) if all_metrics else 0.0,
            avg_security_overhead_bytes=mean([m.security_overhead_bytes for m in all_metrics]) if all_metrics else 0.0,
            effective_throughput_bps=effective_throughput,
            duration_sec=duration,
        )

    # ---- Export ----

    def export_bundle_csv(self, path: str) -> None:
        """Export per-bundle metrics to CSV."""
        fieldnames = [
            "bundle_id", "source", "destination", "priority",
            "created_at", "delivered_at", "delivered", "failed", "failure_reason",
            "delivery_latency_sec", "hop_count", "hops",
            "plaintext_size", "encrypted_size", "total_wire_size",
            "security_overhead_bytes", "encrypt_time_ms", "pib_time_ms", "bab_time_ms",
            "retransmissions", "custody_acks", "custody_naks",
            "fragmented", "fragment_count", "custody_transfer",
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in self._metrics.values():
                writer.writerow({
                    "bundle_id": m.bundle_id,
                    "source": m.source,
                    "destination": m.destination,
                    "priority": m.priority,
                    "created_at": m.created_at,
                    "delivered_at": m.delivered_at or "",
                    "delivered": m.delivered,
                    "failed": m.failed,
                    "failure_reason": m.failure_reason or "",
                    "delivery_latency_sec": m.delivery_latency_sec or "",
                    "hop_count": m.hop_count,
                    "hops": json.dumps(m.hops),
                    "plaintext_size": m.plaintext_size,
                    "encrypted_size": m.encrypted_size,
                    "total_wire_size": m.total_wire_size,
                    "security_overhead_bytes": m.security_overhead_bytes,
                    "encrypt_time_ms": m.encrypt_time_ms,
                    "pib_time_ms": m.pib_time_ms,
                    "bab_time_ms": m.bab_time_ms,
                    "retransmissions": m.retransmissions,
                    "custody_acks": m.custody_acks,
                    "custody_naks": m.custody_naks,
                    "fragmented": m.fragmented,
                    "fragment_count": m.fragment_count,
                    "custody_transfer": m.custody_transfer,
                })

    def export_summary_csv(self, path: str) -> None:
        """Append experiment summary as one row to a CSV."""
        summary = self.compute_summary()
        d = summary.to_dict()
        file_exists = False
        try:
            with open(path, "r"):
                file_exists = True
        except FileNotFoundError:
            pass

        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(d.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(d)

    def get_all_metrics(self) -> List[BundleMetrics]:
        return list(self._metrics.values())
