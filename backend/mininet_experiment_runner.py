#!/usr/bin/env python3
"""
Mininet experiment runner for DTN simulator evaluation.

Runs experiments over a real Mininet topology with actual TCP sockets,
tc-shaped links, and measurable network behaviour.  Requires Linux with
Mininet installed and must be executed as root.

Usage (WSL / Linux):
    sudo -E python3 mininet_experiment_runner.py --all
    sudo -E python3 mininet_experiment_runner.py --experiment E3
    sudo -E python3 mininet_experiment_runner.py --list
"""
import argparse
import csv
import json
import os
import random
import socket
import string
import struct
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from mininet_topology import ISSTopology, create_topology
from network_dtn_manager import NetworkDTNManager
from dtn_bundle_manager import (
    DTNBundleManager, BundlePriority, BundleStatus, PendingAcknowledgment,
)
from metrics_collector import MetricsCollector

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROUND_STATIONS = [
    {"id": "toronto", "name": "Toronto", "lat": 43.6532, "lon": -79.3832},
    {"id": "london", "name": "London", "lat": 51.5074, "lon": -0.1278},
    {"id": "tokyo", "name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"id": "sydney", "name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    {"id": "washington", "name": "Washington DC", "lat": 38.9072, "lon": -77.0369},
    {"id": "singapore", "name": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"id": "bengaluru", "name": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    {"id": "saopaulo", "name": "Sao Paulo", "lat": -23.5505, "lon": -46.6333},
    {"id": "moscow", "name": "Moscow", "lat": 55.7558, "lon": 37.6173},
]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_results")

# Representative S-band ISS link parameters
ISS_BW_MBPS = 0.056       # 56 kbps
ISS_DELAY_MS = 3.0
ISS_LOSS_DEFAULT = 10.0   # 10 % baseline loss
GROUND_LINK_BPS = 100_000_000  # 100 Mbps ground mesh

# Contact window schedule (deterministic toggle)
CONTACT_UP_SEC = 120       # 2 min contact window
CONTACT_DOWN_SEC = 180     # 3 min gap between windows
CONTACT_PERIOD_SEC = CONTACT_UP_SEC + CONTACT_DOWN_SEC

# When link is "down" we set extremely degraded parameters
LINK_DOWN_BW = 0.001       # 1 kbps
LINK_DOWN_DELAY = 100.0
LINK_DOWN_LOSS = 50.0


def random_payload(size_bytes: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=size_bytes))


def _is_contact_up(wall_elapsed: float) -> bool:
    """Deterministic contact schedule based on wall-clock elapsed time."""
    phase = wall_elapsed % CONTACT_PERIOD_SEC
    return phase < CONTACT_UP_SEC


# ---------------------------------------------------------------------------
# Helpers shared across experiments
# ---------------------------------------------------------------------------

class MininetExperimentRunner:
    """Manages a Mininet topology and NetworkDTNManager for experiments."""

    def __init__(self):
        print("\n" + "=" * 70)
        print("  Initialising Mininet topology ...")
        print("=" * 70 + "\n")
        self.topology = create_topology(GROUND_STATIONS)
        self.topology.start()
        self.dtn_manager = NetworkDTNManager(GROUND_STATIONS, self.topology)
        self.dtn_manager.start_servers()
        # Give servers a moment to bind
        time.sleep(2)
        print("  Mininet ready.\n")

    def cleanup(self):
        print("\n  Cleaning up Mininet ...")
        try:
            self.dtn_manager.stop_servers()
        except Exception:
            pass
        try:
            self.topology.stop()
        except Exception:
            pass
        print("  Done.\n")

    # -- link helpers --

    def set_iss_link_up(self, loss_pct: float = ISS_LOSS_DEFAULT):
        """Set ISS link to operational parameters for all stations."""
        for station in GROUND_STATIONS:
            self.topology.update_iss_link(
                station["id"], ISS_BW_MBPS, ISS_DELAY_MS, loss_pct, log_update=False)

    def set_iss_link_down(self):
        """Degrade ISS link so traffic effectively cannot pass."""
        for station in GROUND_STATIONS:
            self.topology.update_iss_link(
                station["id"], LINK_DOWN_BW, LINK_DOWN_DELAY, LINK_DOWN_LOSS,
                log_update=False)

    def toggle_link_by_schedule(self, wall_elapsed: float, loss_pct: float = ISS_LOSS_DEFAULT):
        """Set link up or down based on deterministic contact schedule."""
        if _is_contact_up(wall_elapsed):
            self.set_iss_link_up(loss_pct)
            return True
        else:
            self.set_iss_link_down()
            return False

    # -- reset DTN state --

    def reset_dtn(self, experiment_name: str):
        """Clear bundle state and metrics between experiments."""
        self.dtn_manager.bundles.clear()
        self.dtn_manager.active_transmissions.clear()
        self.dtn_manager.pending_acknowledgments.clear()
        for sid in self.dtn_manager.station_queues:
            self.dtn_manager.station_queues[sid].clear()
        self.dtn_manager.iss_queue.clear()
        self.dtn_manager.bundle_retry_counts.clear()
        self.dtn_manager.metrics.reset(experiment_name)

    # -- main sim loop --

    def run_loop(self, duration_sec: float, bundles_to_inject: List[Dict],
                 loss_pct: float = ISS_LOSS_DEFAULT, tick_sec: float = 1.0):
        """
        Run the experiment loop for *duration_sec* wall-clock seconds.

        Toggles the ISS link on/off on a deterministic schedule, injects
        bundles at their scheduled times, and drives the DTN manager each tick.
        """
        t0 = time.time()
        bundle_idx = 0
        iteration = 0

        while True:
            elapsed = time.time() - t0
            if elapsed >= duration_sec:
                break
            iteration += 1

            # Toggle ISS link
            is_up = self.toggle_link_by_schedule(elapsed, loss_pct)

            # Build contact states
            contact_states: Dict[str, bool] = {}
            stations_data: List[Dict] = []
            for station in GROUND_STATIONS:
                sid = station["id"]
                contact_states[sid] = is_up
                stations_data.append({
                    "id": sid,
                    "name": station["name"],
                    "lat": station["lat"],
                    "lon": station["lon"],
                    "look_angles": {
                        "elevation": 30.0 if is_up else -10.0,
                        "range_km": 800.0 if is_up else 2500.0,
                        "azimuth": 180.0,
                    },
                    "is_visible": is_up,
                    "next_pass_minutes": 0 if is_up else 3,
                    "next_pass_time": None,
                })

            # Inject bundles
            while bundle_idx < len(bundles_to_inject):
                cfg = bundles_to_inject[bundle_idx]
                if elapsed >= cfg["inject_at_sec"]:
                    self.dtn_manager.create_bundle(
                        source_station=cfg["source"],
                        destination=cfg["destination"],
                        payload=cfg["payload"],
                        priority=cfg["priority"],
                    )
                    bundle_idx += 1
                else:
                    break

            # Update transmissions
            completed = self.dtn_manager.update_transmissions(tick_sec, contact_states)

            # Process completed transmissions
            for bundle_info in completed:
                bid, dr = (bundle_info if isinstance(bundle_info, tuple)
                           else (bundle_info, GROUND_LINK_BPS))
                bundle = self.dtn_manager.bundles.get(bid)
                if not bundle:
                    continue
                ack_or_nak = self.dtn_manager.complete_transmission(bid, dr)
                if ack_or_nak:
                    pending = PendingAcknowledgment(
                        bundle_id=bid,
                        from_station=bundle.current_custodian,
                        to_station=bundle.forwarded_to or "unknown",
                        transmitted_at=datetime.now(timezone.utc),
                        timeout_seconds=self.dtn_manager.ACK_TIMEOUT_SECONDS,
                        retransmission_count=0,
                        max_retries=self.dtn_manager.MAX_RETRIES,
                        data_rate_bps=dr,
                    )
                    self.dtn_manager.pending_acknowledgments[bid] = pending
                    bundle.status = BundleStatus.WAITING_ACK
                    if ack_or_nak.get("type") == "ack":
                        self.dtn_manager.process_ack(bid, ack_or_nak)
                    elif ack_or_nak.get("type") == "nak":
                        self.dtn_manager.process_nak(bid, ack_or_nak)

            # Check timeouts
            retransmitted = self.dtn_manager.check_timeouts(contact_states)
            rmap: Dict[str, Tuple[int, float]] = {}
            for info in retransmitted:
                if isinstance(info, tuple) and len(info) == 3:
                    bid, rc, dr = info
                    rmap[bid] = (rc, dr)

            # Schedule new transmissions
            active_station = None
            visible = [s for s in stations_data if s["is_visible"]]
            if visible:
                visible.sort(key=lambda s: s["look_angles"]["elevation"], reverse=True)
                active_station = visible[0]["id"]
            self._schedule_transmissions(stations_data, active_station, rmap)

            if iteration % 60 == 0:
                self.dtn_manager.cleanup_expired()

            time.sleep(tick_sec)

        # Grace period – drain remaining transmissions
        grace_start = time.time()
        while time.time() - grace_start < 30:
            elapsed = time.time() - t0
            is_up = self.toggle_link_by_schedule(elapsed, loss_pct)
            contact_states = {s["id"]: is_up for s in GROUND_STATIONS}
            stations_data_grace = [{
                "id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
                "look_angles": {"elevation": 30.0 if is_up else -10.0,
                                "range_km": 800.0, "azimuth": 180.0},
                "is_visible": is_up, "next_pass_minutes": 0 if is_up else 3,
                "next_pass_time": None,
            } for s in GROUND_STATIONS]
            completed = self.dtn_manager.update_transmissions(tick_sec, contact_states)
            for bundle_info in completed:
                bid, dr = (bundle_info if isinstance(bundle_info, tuple)
                           else (bundle_info, GROUND_LINK_BPS))
                bundle = self.dtn_manager.bundles.get(bid)
                if bundle:
                    ack_or_nak = self.dtn_manager.complete_transmission(bid, dr)
                    if ack_or_nak:
                        self.dtn_manager.pending_acknowledgments[bid] = PendingAcknowledgment(
                            bundle_id=bid,
                            from_station=bundle.current_custodian,
                            to_station=bundle.forwarded_to or "unknown",
                            transmitted_at=datetime.now(timezone.utc),
                            timeout_seconds=self.dtn_manager.ACK_TIMEOUT_SECONDS,
                            retransmission_count=0,
                            max_retries=self.dtn_manager.MAX_RETRIES,
                            data_rate_bps=dr,
                        )
                        bundle.status = BundleStatus.WAITING_ACK
                        if ack_or_nak.get("type") == "ack":
                            self.dtn_manager.process_ack(bid, ack_or_nak)
                        elif ack_or_nak.get("type") == "nak":
                            self.dtn_manager.process_nak(bid, ack_or_nak)
            self.dtn_manager.check_timeouts(contact_states)
            active_station = None
            vis = [s for s in stations_data_grace if s["is_visible"]]
            if vis:
                active_station = vis[0]["id"]
            self._schedule_transmissions(stations_data_grace, active_station, {})

            if (not self.dtn_manager.active_transmissions
                    and not self.dtn_manager.pending_acknowledgments
                    and all(not self.dtn_manager.station_queues.get(s["id"], [])
                            for s in GROUND_STATIONS)
                    and not self.dtn_manager.iss_queue):
                break
            time.sleep(tick_sec)

    def _schedule_transmissions(self, stations_data: List[Dict],
                                current_active: Optional[str],
                                rmap: Dict) -> None:
        """Schedule new transmissions for queued bundles (mirrors sim runner logic)."""
        dtn = self.dtn_manager
        data_rate_iss = ISS_BW_MBPS * 1_000_000

        if dtn.iss_queue:
            visible = [s for s in stations_data if s["is_visible"]]
            if visible:
                best = max(visible, key=lambda s: s["look_angles"]["elevation"])
                is_tx = any(t.from_station == "ISS" for t in dtn.active_transmissions.values())
                if not is_tx:
                    bid = dtn.iss_queue[0]
                    b = dtn.bundles.get(bid)
                    if b:
                        route = dtn.find_route("ISS", b.destination_station, stations_data)
                        if route and len(route) > 1:
                            b.route = route
                            dtn.start_transmission(bid, "ISS", route[1], data_rate_iss)

        for sd in stations_data:
            sid = sd["id"]
            is_visible = sd["is_visible"]
            queue = dtn.station_queues.get(sid, [])
            if not queue:
                continue

            next_bid, next_b = None, None
            for bid in queue:
                b = dtn.bundles.get(bid)
                if b and b.status not in [BundleStatus.WAITING_ACK, BundleStatus.DELIVERED, BundleStatus.EXPIRED]:
                    next_bid, next_b = bid, b
                    break
            if not next_bid:
                continue

            is_tx = any(t.from_station == sid for t in dtn.active_transmissions.values())
            is_wait = any(p.from_station == sid for p in dtn.pending_acknowledgments.values())
            if is_tx or is_wait:
                continue

            if next_b.destination_station.upper() == "ISS" and is_visible:
                rc = rmap.get(next_bid, (None,))[0] if next_bid in rmap else None
                dtn.start_transmission(next_bid, sid, "ISS", data_rate_iss, retransmission_count=rc)
                continue

            if next_b.destination_station.upper() != "ISS" or not is_visible:
                hop = dtn.get_next_hop_from_route(next_bid)
                if hop:
                    dtn.start_transmission(next_bid, sid, hop, GROUND_LINK_BPS)
                    continue
                if not next_b.route:
                    route = dtn.find_route(sid, next_b.destination_station, stations_data,
                                           visited=next_b.hops)
                    if route and len(route) > 1:
                        next_b.route = route
                        dtn.db_manager.update_bundle_route(next_bid, route)
                        dtn.start_transmission(next_bid, sid, route[1], GROUND_LINK_BPS)
                        continue

                if current_active and current_active != sid:
                    if current_active not in next_b.hops:
                        dtn.start_transmission(next_bid, sid, current_active, GROUND_LINK_BPS)
                        continue


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _export_results(dtn_manager: NetworkDTNManager, name: str, wall_time: float) -> Dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    dtn_manager.metrics.export_bundle_csv(os.path.join(OUTPUT_DIR, "{}_bundles.csv".format(name)))
    dtn_manager.metrics.export_summary_csv(os.path.join(OUTPUT_DIR, "mininet_experiment_summaries.csv"))
    summary = dtn_manager.metrics.compute_summary()
    sd = summary.to_dict()
    sd["wall_time_sec"] = round(wall_time, 1)

    print("\n" + "=" * 70)
    print("  RESULTS: {}  (wall time: {:.1f}s)".format(name, wall_time))
    print("=" * 70)
    print("  Delivery Ratio:      {:.2%} ({}/{})".format(
        summary.delivery_ratio, summary.delivered_count, summary.total_bundles))
    print("  Failed:              {}".format(summary.failed_count))
    print("  Latency (mean):      {:.1f}s".format(summary.latency_mean_sec))
    print("  Latency (median):    {:.1f}s".format(summary.latency_median_sec))
    print("  Latency (P95):       {:.1f}s".format(summary.latency_p95_sec))
    print("  Retransmissions:     {}".format(summary.total_retransmissions))
    print("  ACKs / NAKs:         {} / {}".format(summary.total_acks, summary.total_naks))
    print("  Avg hops:            {:.1f}".format(summary.avg_hop_count))
    print("  Throughput:          {:.0f} bps".format(summary.effective_throughput_bps))
    if summary.total_network_sends > 0:
        print("  --- Network-level (Mininet) ---")
        print("  Avg RTT:             {:.1f} ms".format(summary.avg_network_rtt_ms))
        print("  Median RTT:          {:.1f} ms".format(summary.median_network_rtt_ms))
        print("  P95 RTT:             {:.1f} ms".format(summary.p95_network_rtt_ms))
        print("  Net sends:           {} ({} OK, {} fail)".format(
            summary.total_network_sends, summary.total_network_successes,
            summary.total_network_sends - summary.total_network_successes))
        print("  Net delivery ratio:  {:.2%}".format(summary.network_delivery_ratio))
        print("  Observed loss rate:  {:.2%}".format(summary.observed_loss_rate))
    print("=" * 70 + "\n")

    with open(os.path.join(OUTPUT_DIR, "{}_summary.json".format(name)), "w") as f:
        json.dump(sd, f, indent=2)

    return sd


# ---------------------------------------------------------------------------
# E3: Varying Packet Loss
# ---------------------------------------------------------------------------

def run_e3(runner: MininetExperimentRunner) -> Dict:
    """Sweep tc loss from 0 % to 30 % and measure BDR at each level."""
    loss_levels = [0.0, 5.0, 10.0, 20.0, 30.0]
    combined: Dict[str, Dict] = {}

    for loss_pct in loss_levels:
        label = "E3_loss_{:.0f}pct".format(loss_pct)
        print("\n" + "=" * 70)
        print("  EXPERIMENT: {} (tc loss = {:.0f}%)".format(label, loss_pct))
        print("=" * 70 + "\n")

        runner.reset_dtn(label)

        sources = [s["id"] for s in GROUND_STATIONS]
        num_bundles = 10
        spacing = 5.0
        schedule = []
        for i in range(num_bundles):
            schedule.append({
                "inject_at_sec": spacing * (i + 1),
                "source": sources[i % len(sources)],
                "destination": "ISS",
                "payload": random_payload(500),
                "priority": "NORMAL",
            })

        t0 = time.time()
        runner.run_loop(duration_sec=90, bundles_to_inject=schedule, loss_pct=loss_pct)
        wall = time.time() - t0

        sd = _export_results(runner.dtn_manager, label, wall)
        sd["configured_loss_pct"] = loss_pct
        combined[label] = sd

    path = os.path.join(OUTPUT_DIR, "E3_varying_loss_combined.json")
    with open(path, "w") as f:
        json.dump(combined, f, indent=2)
    print("  E3 combined results -> {}".format(path))
    return combined


# ---------------------------------------------------------------------------
# E7: DTN vs TCP Comparison
# ---------------------------------------------------------------------------

def _raw_tcp_send(dest_ip: str, port: int, payload: bytes, timeout: float = 10.0) -> Dict:
    """Attempt a plain TCP send+recv to *dest_ip*:*port* and report outcome."""
    result = {"success": False, "rtt_ms": 0.0, "error": None}
    t0 = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((dest_ip, port))
        sock.sendall(payload)
        _ = sock.recv(4096)
        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["rtt_ms"] = (time.perf_counter() - t0) * 1000.0
        try:
            sock.close()
        except Exception:
            pass
    return result


def run_e7(runner: MininetExperimentRunner) -> Dict:
    """DTN vs raw TCP comparison with intermittent connectivity."""
    print("\n" + "=" * 70)
    print("  EXPERIMENT: E7 DTN vs TCP Comparison")
    print("=" * 70 + "\n")

    payload_str = random_payload(500)

    # --- Phase A: DTN delivery through intermittent link ---
    runner.reset_dtn("E7_dtn")

    schedule = [{
        "inject_at_sec": 2.0,
        "source": "toronto",
        "destination": "ISS",
        "payload": payload_str,
        "priority": "NORMAL",
    }]

    t0 = time.time()
    runner.run_loop(duration_sec=90, bundles_to_inject=schedule, loss_pct=ISS_LOSS_DEFAULT)
    dtn_wall = time.time() - t0
    dtn_summary = runner.dtn_manager.metrics.compute_summary().to_dict()
    dtn_summary["wall_time_sec"] = round(dtn_wall, 1)

    # --- Phase B: Raw TCP attempts with link toggling ---
    tcp_results = []
    iss_ip = runner.topology.get_node_ip("iss")
    if iss_ip:
        iss_ip = iss_ip.split("/")[0]

    num_tcp_attempts = 5
    tcp_start = time.time()
    for i in range(num_tcp_attempts):
        elapsed = time.time() - tcp_start
        is_up = _is_contact_up(elapsed)
        if is_up:
            runner.set_iss_link_up()
        else:
            runner.set_iss_link_down()

        if iss_ip:
            res = _raw_tcp_send(iss_ip, 5000, payload_str.encode("utf-8"), timeout=10.0)
        else:
            res = {"success": False, "rtt_ms": 0.0, "error": "no ISS IP"}
        res["link_up"] = is_up
        res["attempt"] = i + 1
        tcp_results.append(res)
        print("    TCP attempt {}: link_up={} success={} rtt={:.1f}ms err={}".format(
            i + 1, is_up, res["success"], res["rtt_ms"], res.get("error")))
        time.sleep(CONTACT_PERIOD_SEC / num_tcp_attempts)

    tcp_successes = sum(1 for r in tcp_results if r["success"])

    combined = {
        "dtn": dtn_summary,
        "tcp": {
            "attempts": num_tcp_attempts,
            "successes": tcp_successes,
            "delivery_ratio": round(tcp_successes / num_tcp_attempts, 4) if num_tcp_attempts else 0,
            "details": tcp_results,
        },
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "E7_dtn_vs_tcp.json")
    with open(path, "w") as f:
        json.dump(combined, f, indent=2, default=str)

    print("\n  E7 Results:")
    print("    DTN delivery ratio: {:.2%}".format(dtn_summary.get("delivery_ratio", 0)))
    print("    TCP delivery ratio: {:.2%}  ({}/{})".format(
        combined["tcp"]["delivery_ratio"], tcp_successes, num_tcp_attempts))
    print("  Saved -> {}\n".format(path))
    return combined


# ---------------------------------------------------------------------------
# E8: Mininet Baseline (comparable to E1 simulation)
# ---------------------------------------------------------------------------

def run_e8(runner: MininetExperimentRunner) -> Dict:
    """Baseline Mininet experiment comparable to E1 simulation."""
    name = "E8_mininet_baseline"
    print("\n" + "=" * 70)
    print("  EXPERIMENT: {} ".format(name))
    print("  20 bundles, S-band link params, toggled contact windows")
    print("=" * 70 + "\n")

    runner.reset_dtn(name)

    sources = [s["id"] for s in GROUND_STATIONS]
    num_bundles = 20
    spacing = 5.0
    schedule = []
    for i in range(num_bundles):
        schedule.append({
            "inject_at_sec": spacing * (i + 1),
            "source": sources[i % len(sources)],
            "destination": "ISS",
            "payload": random_payload(500),
            "priority": "NORMAL",
        })

    t0 = time.time()
    runner.run_loop(duration_sec=120, bundles_to_inject=schedule, loss_pct=ISS_LOSS_DEFAULT)
    wall = time.time() - t0

    return _export_results(runner.dtn_manager, name, wall)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EXPERIMENT_NAMES = {
    "E3": "Varying packet loss (sweep 0-30%)",
    "E7": "DTN vs raw TCP comparison",
    "E8": "Mininet baseline (comparable to simulation E1)",
}


def main():
    parser = argparse.ArgumentParser(description="Mininet DTN Experiment Runner")
    parser.add_argument("--experiment", "-e", type=str, default=None,
                        help="Run a single experiment (E3, E7, E8)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List available experiments")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Run all experiments")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable Mininet experiments:")
        for k, desc in EXPERIMENT_NAMES.items():
            print("  {:<10} {}".format(k, desc))
        return

    if os.geteuid() != 0:
        print("ERROR: This script must be run as root (sudo).")
        print("Usage: sudo -E python3 mininet_experiment_runner.py --all")
        sys.exit(1)

    runner = MininetExperimentRunner()
    all_results = {}

    try:
        if args.experiment:
            key = args.experiment.upper()
            if key == "E3":
                all_results["E3"] = run_e3(runner)
            elif key == "E7":
                all_results["E7"] = run_e7(runner)
            elif key == "E8":
                all_results["E8"] = run_e8(runner)
            else:
                print("Unknown experiment: {}. Available: {}".format(
                    args.experiment, ", ".join(EXPERIMENT_NAMES.keys())))
                runner.cleanup()
                sys.exit(1)
        elif args.all:
            all_results["E8"] = run_e8(runner)
            all_results["E3"] = run_e3(runner)
            all_results["E7"] = run_e7(runner)
        else:
            all_results["E8"] = run_e8(runner)

        if all_results:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            path = os.path.join(OUTPUT_DIR, "mininet_all_summaries.json")
            with open(path, "w") as f:
                json.dump(all_results, f, indent=2, default=str)
            print("\nAll Mininet results saved to {}".format(path))

    finally:
        runner.cleanup()


if __name__ == "__main__":
    main()
