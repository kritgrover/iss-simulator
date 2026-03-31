#!/usr/bin/env python3
"""
Experiment runner for DTN simulator evaluation.
Drives the backend programmatically (no frontend) to run repeatable,
parameterized experiments and export metrics to CSV.

Uses synthetic contact windows for deterministic, reproducible results
independent of real-time orbital state.

Usage:
    python experiment_runner.py                    # run default experiments
    python experiment_runner.py --experiment E1    # run one experiment
    python experiment_runner.py --all              # run all experiments
    python experiment_runner.py --list             # list available experiments
"""
import argparse
import csv
import json
import math
import os
import random
import string
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from dtn_bundle_manager import DTNBundleManager, BundlePriority, BundleStatus, PendingAcknowledgment
from bsp_security import BSPSecurityManager
from metrics_collector import MetricsCollector

GROUND_STATIONS = [
    {"id": "toronto", "name": "Toronto", "lat": 43.6532, "lon": -79.3832},
    {"id": "london", "name": "London", "lat": 51.5074, "lon": -0.1278},
    {"id": "tokyo", "name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"id": "sydney", "name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    {"id": "washington", "name": "Washington DC", "lat": 38.9072, "lon": -77.0369},
    {"id": "singapore", "name": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"id": "bengaluru", "name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"id": "saopaulo", "name": "São Paulo", "lat": -23.5505, "lon": -46.6333},
    {"id": "moscow", "name": "Moscow", "lat": 55.7558, "lon": 37.6173},
]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "experiment_results")

# Synthetic orbital parameters (representative of real ISS orbit)
ORBITAL_PERIOD_SEC = 5520       # ~92 min
PASS_DURATION_SEC = 480         # ~8 min typical contact window
INTER_PASS_GAP_SEC = ORBITAL_PERIOD_SEC - PASS_DURATION_SEC

# Stagger passes across stations to simulate different ground track positions.
# Each station gets a different phase offset so not all stations are visible simultaneously.
STATION_PHASE_OFFSETS = {
    "toronto": 0,
    "washington": 60,
    "london": 1200,
    "moscow": 1800,
    "bengaluru": 2400,
    "singapore": 3000,
    "tokyo": 3600,
    "sydney": 4200,
    "saopaulo": 4800,
}

# Synthetic link budget for when station has ISS contact
CONTACT_DATA_RATE_BPS = 56_000  # 56 kbps (representative S-band)
CONTACT_RANGE_KM = 800.0
CONTACT_ELEVATION_DEG = 30.0
GROUND_LINK_BPS = 100_000_000   # 100 Mbps ground mesh


@dataclass
class ExperimentConfig:
    name: str
    num_bundles: int = 10
    bundle_size_bytes: int = 500
    priorities: List[str] = field(default_factory=lambda: ["NORMAL"])
    sim_duration_sec: int = 6000  # ~100 min, >1 orbit
    source_stations: Optional[List[str]] = None
    destination: str = "ISS"
    description: str = ""


def random_payload(size_bytes: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size_bytes))


def is_station_visible(station_id: str, sim_clock: float) -> bool:
    """Determine if a station has ISS contact at the given simulated time."""
    offset = STATION_PHASE_OFFSETS.get(station_id, 0)
    t = (sim_clock + offset) % ORBITAL_PERIOD_SEC
    return t < PASS_DURATION_SEC


def get_synthetic_station_data(sim_clock: float) -> Tuple[List[Dict], Dict[str, bool], List[Dict]]:
    """Build synthetic station state for the current sim clock."""
    stations_data = []
    contact_states: Dict[str, bool] = {}
    visible_stations = []

    for station in GROUND_STATIONS:
        sid = station["id"]
        visible = is_station_visible(sid, sim_clock)
        contact_states[sid] = visible

        # Compute synthetic next-pass time
        offset = STATION_PHASE_OFFSETS.get(sid, 0)
        t_in_period = (sim_clock + offset) % ORBITAL_PERIOD_SEC
        if visible:
            next_pass_min = 0
        else:
            remaining_gap = ORBITAL_PERIOD_SEC - t_in_period
            next_pass_min = max(1, int(remaining_gap / 60))

        sd = {
            "id": sid,
            "name": station["name"],
            "lat": station["lat"],
            "lon": station["lon"],
            "look_angles": {
                "elevation": CONTACT_ELEVATION_DEG if visible else -10.0,
                "range_km": CONTACT_RANGE_KM if visible else 2500.0,
                "azimuth": 180.0,
            },
            "is_visible": visible,
            "next_pass_minutes": next_pass_min,
            "next_pass_time": None,
        }
        stations_data.append(sd)
        if visible:
            visible_stations.append(sd)

    return stations_data, contact_states, visible_stations


def _process_completed(dtn_manager: DTNBundleManager, completed: list) -> None:
    for bundle_info in completed:
        bundle_id, data_rate_bps = (bundle_info if isinstance(bundle_info, tuple)
                                    else (bundle_info, GROUND_LINK_BPS))
        bundle = dtn_manager.bundles.get(bundle_id)
        if not bundle:
            continue
        ack_or_nak = dtn_manager.complete_transmission(bundle_id, data_rate_bps)
        if ack_or_nak:
            pending_ack = PendingAcknowledgment(
                bundle_id=bundle_id,
                from_station=bundle.current_custodian,
                to_station=bundle.forwarded_to or "unknown",
                transmitted_at=datetime.now(timezone.utc),
                timeout_seconds=dtn_manager.ACK_TIMEOUT_SECONDS,
                retransmission_count=0,
                max_retries=dtn_manager.MAX_RETRIES,
                data_rate_bps=data_rate_bps,
            )
            dtn_manager.pending_acknowledgments[bundle_id] = pending_ack
            bundle.status = BundleStatus.WAITING_ACK
            if ack_or_nak.get("type") == "ack":
                dtn_manager.process_ack(bundle_id, ack_or_nak)
            elif ack_or_nak.get("type") == "nak":
                dtn_manager.process_nak(bundle_id, ack_or_nak)


def _schedule_transmissions(dtn_manager: DTNBundleManager, stations_data: List[Dict],
                            current_active_station: Optional[str],
                            retransmission_map: Dict) -> None:
    """Schedule new transmissions for queued bundles."""
    # ISS queue first
    if dtn_manager.iss_queue:
        visible = [s for s in stations_data if s["is_visible"]]
        if visible:
            best = max(visible, key=lambda s: s["look_angles"]["elevation"])
            is_tx = any(t.from_station == "ISS" for t in dtn_manager.active_transmissions.values())
            if not is_tx:
                bid = dtn_manager.iss_queue[0]
                b = dtn_manager.bundles.get(bid)
                if b:
                    route = dtn_manager.find_route("ISS", b.destination_station, stations_data)
                    if route and len(route) > 1:
                        b.route = route
                        dtn_manager.start_transmission(bid, "ISS", route[1], CONTACT_DATA_RATE_BPS)

    for sd in stations_data:
        sid = sd["id"]
        is_visible = sd["is_visible"]
        queue = dtn_manager.station_queues.get(sid, [])
        if not queue:
            continue

        next_bid, next_b = None, None
        for bid in queue:
            b = dtn_manager.bundles.get(bid)
            if b and b.status not in [BundleStatus.WAITING_ACK, BundleStatus.DELIVERED, BundleStatus.EXPIRED]:
                next_bid, next_b = bid, b
                break
        if not next_bid:
            continue

        is_tx = any(t.from_station == sid for t in dtn_manager.active_transmissions.values())
        is_wait = any(p.from_station == sid for p in dtn_manager.pending_acknowledgments.values())
        if is_tx or is_wait:
            continue

        # Direct to ISS if visible
        if next_b.destination_station.upper() == "ISS" and is_visible:
            rc = retransmission_map.get(next_bid, (None,))[0] if next_bid in retransmission_map else None
            dtn_manager.start_transmission(next_bid, sid, "ISS", CONTACT_DATA_RATE_BPS, retransmission_count=rc)
            continue

        # Forward along route or calculate one
        if next_b.destination_station.upper() != "ISS" or not is_visible:
            hop = dtn_manager.get_next_hop_from_route(next_bid)
            if hop:
                dtn_manager.start_transmission(next_bid, sid, hop, GROUND_LINK_BPS)
                continue
            if not next_b.route:
                route = dtn_manager.find_route(sid, next_b.destination_station, stations_data, visited=next_b.hops)
                if route and len(route) > 1:
                    next_b.route = route
                    dtn_manager.db_manager.update_bundle_route(next_bid, route)
                    dtn_manager.start_transmission(next_bid, sid, route[1], GROUND_LINK_BPS)
                    continue

            if current_active_station and current_active_station != sid:
                if current_active_station not in next_b.hops:
                    dtn_manager.start_transmission(next_bid, sid, current_active_station, GROUND_LINK_BPS)
                    continue


def run_sim_loop(dtn_manager: DTNBundleManager, duration_sec: int,
                 bundle_configs: List[Dict], tick_sec: float = 1.0) -> None:
    """
    Run the simulation loop with synthetic contact windows.
    Simulated time advances by tick_sec per iteration with no wall-clock sleep.
    """
    sim_clock = 0.0
    bundle_idx = 0
    iteration = 0

    while sim_clock < duration_sec:
        iteration += 1
        sim_clock += tick_sec
        dtn_manager.metrics.set_sim_clock(sim_clock)

        # Inject bundles
        while bundle_idx < len(bundle_configs):
            cfg = bundle_configs[bundle_idx]
            if sim_clock >= cfg["inject_at_sec"]:
                dtn_manager.create_bundle(
                    source_station=cfg["source"],
                    destination=cfg["destination"],
                    payload=cfg["payload"],
                    priority=cfg["priority"],
                )
                bundle_idx += 1
            else:
                break

        stations_data, contact_states, visible_stations = get_synthetic_station_data(sim_clock)
        completed = dtn_manager.update_transmissions(tick_sec, contact_states)
        _process_completed(dtn_manager, completed)

        retransmitted = dtn_manager.check_timeouts(contact_states)
        rmap: Dict[str, Tuple[int, float]] = {}
        for info in retransmitted:
            if isinstance(info, tuple) and len(info) == 3:
                bid, rc, dr = info
                rmap[bid] = (rc, dr)

        active = None
        if visible_stations:
            visible_stations.sort(key=lambda s: s["look_angles"]["elevation"], reverse=True)
            active = visible_stations[0]["id"]

        _schedule_transmissions(dtn_manager, stations_data, active, rmap)

        if iteration % 60 == 0:
            dtn_manager.cleanup_expired()

    # Grace period
    for _ in range(int(300 / tick_sec)):
        sim_clock += tick_sec
        dtn_manager.metrics.set_sim_clock(sim_clock)
        stations_data, contact_states, visible_stations = get_synthetic_station_data(sim_clock)
        completed = dtn_manager.update_transmissions(tick_sec, contact_states)
        _process_completed(dtn_manager, completed)
        dtn_manager.check_timeouts(contact_states)
        active = visible_stations[0]["id"] if visible_stations else None
        _schedule_transmissions(dtn_manager, stations_data, active, {})
        if (not dtn_manager.active_transmissions
                and not dtn_manager.pending_acknowledgments
                and all(not dtn_manager.station_queues.get(s, []) for s in dtn_manager.stations)
                and not dtn_manager.iss_queue):
            break


# ---------------------------------------------------------------------------
# Bundle schedule helpers
# ---------------------------------------------------------------------------

def _make_bundle_schedule(config: ExperimentConfig) -> List[Dict]:
    sources = config.source_stations or [s["id"] for s in GROUND_STATIONS]
    schedule = []
    spacing = max(1.0, config.sim_duration_sec * 0.8 / max(config.num_bundles, 1))
    for i in range(config.num_bundles):
        src = sources[i % len(sources)]
        pri = config.priorities[i % len(config.priorities)]
        schedule.append({
            "inject_at_sec": spacing * (i + 1),
            "source": src,
            "destination": config.destination,
            "payload": random_payload(config.bundle_size_bytes),
            "priority": pri,
        })
    return schedule


def run_experiment(config: ExperimentConfig) -> Dict:
    print(f"\n{'='*70}")
    print(f"  EXPERIMENT: {config.name}")
    print(f"  {config.description}")
    print(f"  Bundles: {config.num_bundles}, Size: {config.bundle_size_bytes}B, "
          f"SimDuration: {config.sim_duration_sec}s ({config.sim_duration_sec/60:.0f}min)")
    print(f"{'='*70}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db_path = os.path.join(OUTPUT_DIR, f"{config.name}_bundles.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    dtn_manager = DTNBundleManager(GROUND_STATIONS, mesh_connections=None, db_path=db_path)
    dtn_manager.metrics.set_sim_clock(0.0)
    dtn_manager.metrics.reset(config.name)

    schedule = _make_bundle_schedule(config)
    t0 = time.time()
    run_sim_loop(dtn_manager, config.sim_duration_sec, schedule, tick_sec=1.0)
    wall_time = time.time() - t0

    # Export
    dtn_manager.metrics.export_bundle_csv(os.path.join(OUTPUT_DIR, f"{config.name}_bundles.csv"))
    dtn_manager.metrics.export_summary_csv(os.path.join(OUTPUT_DIR, "experiment_summaries.csv"))

    summary = dtn_manager.metrics.compute_summary()
    sd = summary.to_dict()
    sd["wall_time_sec"] = round(wall_time, 1)

    print(f"\n{'='*70}")
    print(f"  RESULTS: {config.name}  (wall time: {wall_time:.1f}s)")
    print(f"{'='*70}")
    print(f"  Delivery Ratio:  {summary.delivery_ratio:.2%} ({summary.delivered_count}/{summary.total_bundles})")
    print(f"  Failed:          {summary.failed_count}")
    print(f"  Latency (mean):  {summary.latency_mean_sec:.1f}s")
    print(f"  Latency (med):   {summary.latency_median_sec:.1f}s")
    print(f"  Latency (P95):   {summary.latency_p95_sec:.1f}s")
    print(f"  Retransmissions: {summary.total_retransmissions}")
    print(f"  ACKs / NAKs:     {summary.total_acks} / {summary.total_naks}")
    print(f"  Avg hops:        {summary.avg_hop_count:.1f}")
    print(f"  Avg encrypt:     {summary.avg_encrypt_time_ms:.3f}ms")
    print(f"  Throughput:      {summary.effective_throughput_bps:.0f} bps")
    print(f"  Duration (sim):  {summary.duration_sec:.1f}s")
    print(f"{'='*70}\n")

    with open(os.path.join(OUTPUT_DIR, f"{config.name}_summary.json"), "w") as f:
        json.dump(sd, f, indent=2)

    return sd


# ---------------------------------------------------------------------------
# E4: Security overhead (standalone, no sim needed)
# ---------------------------------------------------------------------------

def run_security_overhead_standalone() -> Dict:
    print(f"\n{'='*70}")
    print(f"  EXPERIMENT: E4 Security Overhead (standalone)")
    print(f"{'='*70}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    bsp = BSPSecurityManager()
    sizes = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]
    results = []

    for size in sizes:
        payload = random_payload(size)
        pt_bytes = len(payload.encode('utf-8'))

        encrypted, pcb = bsp.encrypt_payload(payload, "toronto")
        enc_ms = bsp.last_timing["encrypt_ms"]
        enc_bytes = len(encrypted.encode('utf-8'))

        ph = bsp.get_payload_hash(encrypted)
        bsp.create_pib(ph, "toronto")
        pib_ms = bsp.last_timing["pib_create_ms"]

        bsp.create_bab({"bundle_id": "test", "source_station": "toronto",
                        "destination_station": "ISS", "payload_hash": ph},
                       "toronto", "ISS")
        bab_ms = bsp.last_timing["bab_create_ms"]

        overhead = enc_bytes - pt_bytes
        pct = (overhead / pt_bytes * 100) if pt_bytes else 0

        row = {
            "plaintext_bytes": pt_bytes, "encrypted_bytes": enc_bytes,
            "overhead_bytes": overhead, "overhead_pct": round(pct, 1),
            "encrypt_time_ms": round(enc_ms, 3),
            "pib_time_ms": round(pib_ms, 3),
            "bab_time_ms": round(bab_ms, 3),
            "total_security_time_ms": round(enc_ms + pib_ms + bab_ms, 3),
        }
        results.append(row)
        print(f"  {pt_bytes:>6}B -> {enc_bytes:>6}B  "
              f"overhead: {overhead:>5}B ({pct:5.1f}%)  "
              f"encrypt: {enc_ms:.3f}ms  PIB: {pib_ms:.3f}ms  BAB: {bab_ms:.3f}ms")

    csv_path = os.path.join(OUTPUT_DIR, "E4_security_overhead.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  Saved to {csv_path}")
    return {"rows": results}


# ---------------------------------------------------------------------------
# Experiment configs
# ---------------------------------------------------------------------------

EXPERIMENTS: Dict[str, ExperimentConfig] = {
    "E1": ExperimentConfig(
        name="E1_baseline",
        description="Baseline: 20 bundles, default settings",
        num_bundles=20, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
    "E2_custody_on": ExperimentConfig(
        name="E2_custody_on",
        description="Custody transfer ON (default)",
        num_bundles=20, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
    "E2_custody_off": ExperimentConfig(
        name="E2_custody_off",
        description="Custody transfer OFF",
        num_bundles=20, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
    "E5_frag_1k": ExperimentConfig(
        name="E5_frag_1KB",
        description="Fragmentation: 1KB payloads",
        num_bundles=10, bundle_size_bytes=1000, sim_duration_sec=6000,
    ),
    "E5_frag_4k": ExperimentConfig(
        name="E5_frag_4KB",
        description="Fragmentation: 4KB payloads (fragmented)",
        num_bundles=10, bundle_size_bytes=4000, sim_duration_sec=6000,
    ),
    "E5_frag_16k": ExperimentConfig(
        name="E5_frag_16KB",
        description="Fragmentation: 16KB payloads (heavy)",
        num_bundles=10, bundle_size_bytes=16000, sim_duration_sec=6000,
    ),
    "E6_scale_1": ExperimentConfig(
        name="E6_scale_1", description="Scale: 1 bundle",
        num_bundles=1, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
    "E6_scale_5": ExperimentConfig(
        name="E6_scale_5", description="Scale: 5 bundles",
        num_bundles=5, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
    "E6_scale_10": ExperimentConfig(
        name="E6_scale_10", description="Scale: 10 bundles",
        num_bundles=10, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
    "E6_scale_25": ExperimentConfig(
        name="E6_scale_25", description="Scale: 25 bundles",
        num_bundles=25, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
    "E6_scale_50": ExperimentConfig(
        name="E6_scale_50", description="Scale: 50 bundles",
        num_bundles=50, bundle_size_bytes=500, sim_duration_sec=6000,
    ),
}


def main():
    parser = argparse.ArgumentParser(description="DTN Experiment Runner")
    parser.add_argument("--experiment", "-e", type=str, default=None)
    parser.add_argument("--list", "-l", action="store_true")
    parser.add_argument("--all", "-a", action="store_true")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable experiments:")
        for key, cfg in EXPERIMENTS.items():
            print(f"  {key:<20} {cfg.description}")
        print(f"  {'E4_standalone':<20} Security overhead measurement")
        return

    if args.experiment:
        k = args.experiment.upper()
        if k in ("E4", "E4_STANDALONE"):
            run_security_overhead_standalone()
        elif k in EXPERIMENTS:
            run_experiment(EXPERIMENTS[k])
        else:
            print(f"Unknown: {args.experiment}. Available: {', '.join(EXPERIMENTS.keys())}, E4")
            sys.exit(1)
        return

    if args.all:
        all_results = {}
        all_results["E1"] = run_experiment(EXPERIMENTS["E1"])
        all_results["E2_on"] = run_experiment(EXPERIMENTS["E2_custody_on"])
        all_results["E2_off"] = run_experiment(EXPERIMENTS["E2_custody_off"])
        all_results["E4"] = run_security_overhead_standalone()
        for k in ["E5_frag_1k", "E5_frag_4k", "E5_frag_16k"]:
            all_results[k] = run_experiment(EXPERIMENTS[k])
        for k in ["E6_scale_1", "E6_scale_5", "E6_scale_10", "E6_scale_25", "E6_scale_50"]:
            all_results[k] = run_experiment(EXPERIMENTS[k])
        with open(os.path.join(OUTPUT_DIR, "all_summaries.json"), "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nAll results saved to {OUTPUT_DIR}/all_summaries.json")
        return

    # Default: quick validation
    run_experiment(EXPERIMENTS["E1"])
    run_security_overhead_standalone()


if __name__ == "__main__":
    main()
