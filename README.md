# ISS Communication Simulator

## Associated Publication: [arXiv Link](https://arxiv.org/abs/2605.21624) (see also [how to cite](#how-to-cite))

### Conference Presentation: [ISORC 2026](https://mcscert.github.io/isorc2026/), [Slides](https://www.canva.com/design/DAHKHKZv03s/WDXtx7XuIHjvnx4t1wGeBg/view?utlId=h0c8d706b8f)
### Demo Link: [ISS Simulator Demo](https://youtu.be/nzh2T8YPaEc?si=2Gu9HnW4LvIJG84V)

## Introduction

This project is a comprehensive simulation of the International Space Station's (ISS) communication systems, focusing on the implementation of Delay/Disruption Tolerant Networking (DTN) protocols. It provides a real-time visualization of orbital mechanics, link budget calculations, and the "store-and-forward" data transmission paradigm used in space communications. The simulator is designed to demonstrate how data is reliably transmitted between ground stations and the ISS despite intermittent connectivity, high latency, and variable link quality.

The system is built using a modern tech stack:
- **Backend**: Python with FastAPI for the API and WebSocket server, utilizing `Skyfield` for high-precision orbital tracking (SGP4) and `Mininet` (optional) for realistic network emulation.
- **Frontend**: React (Vite) with TypeScript, using `Three.js` for 3D globe visualization, `Recharts` for real-time analytics, and `Tailwind CSS` for a responsive UI.
- **Protocols**: Implements a simulation of the Bundle Protocol (RFC 5050/9171) with support for custody transfer, fragmentation, and priority queuing.

Inspired by the research on DTN for space internetworking: [NASA DTN Paper](https://www.nasa.gov/wp-content/uploads/2023/09/dtn-tutorial-v3.2-0.pdf)

## Table of Contents

- [Installation](#installation)
  - [WSL Setup](#wsl-setup)
  - [Python Requirements](#python-requirements)
  - [Node.js Requirements](#nodejs-requirements)
  - [Mininet Setup](#mininet-setup)
- [Running the Application](#running-the-application)
  - [Non-Mininet Mode (Simulation Only)](#non-mininet-mode-simulation-only)
  - [Mininet Mode (Network Emulation)](#mininet-mode-network-emulation)
- [Batch experiments (evaluation runners)](#batch-experiments-evaluation-runners)
  - [Simulation experiments (`experiment_runner.py`)](#simulation-experiments-experiment_runnerpy)
  - [Mininet experiments (`mininet_experiment_runner.py`)](#mininet-experiments-mininet_experiment_runnerpy)
- [Features](#features)
  - [Orbital Tracking](#orbital-tracking)
  - [Link Budget Calculator](#link-budget-calculator)
  - [DTN Bundle Protocol](#dtn-bundle-protocol)
  - [Network Topology](#network-topology)
  - [Frontend Visualization](#frontend-visualization)
- [How to Cite](#how-to-cite)

## Installation

### WSL Setup
For users on Windows, it is highly recommended to use Windows Subsystem for Linux (WSL2) to run the backend, especially if you intend to use the Mininet features, as Mininet requires a Linux kernel.
1. Open PowerShell as Administrator and run: `wsl --install`
2. Restart your computer if prompted.
3. Install a Linux distribution (e.g., Ubuntu) from the Microsoft Store.

### Python Requirements
Navigate to the `backend` directory and install the required dependencies. It's recommended to use a virtual environment.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows Git Bash: source venv/Scripts/activate
```

Important: requirements.txt does not include Mininet, because Mininet cannot be installed via pip.
Install Mininet separately using apt if needed.

Now install backend dependencies:
```bash
pip install -r requirements.txt
```

### Node.js Requirements
Navigate to the root directory (where package.json is located) and install the frontend dependencies.
```bash
npm install
```
If npm is not available on your system, install Node.js using NVM instead:
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install --lts
  ```
Then re-run:
```
npm install
```
### Mininet Setup
If you plan to run the network emulation mode:
1. Ensure you are on a Linux environment (native or WSL2).
2. Install Mininet and Open vSwitch:
```bash
sudo apt-get update
sudo apt-get install mininet openvswitch-switch
```
## Running the Application
### Non-Mininet Mode (Simulation Only)
This mode runs the backend using pure Python simulation for logic, without creating virtual network interfaces. Ideal for development on non-Linux systems or for testing logic.

Backend:
```bash
# From the root directory
cd backend
source venv/bin/activate
python main.py
```
The server will start on http://0.0.0.0:8000.

Frontend:
```bash
# From the root directory
npm run dev
```
Access the application at http://localhost:8080.
### Mininet Mode (Network Emulation)
This mode uses Mininet to create a realistic network topology with virtual hosts, switches, and links that have dynamic bandwidth, delay, and loss properties based on the physics simulation.\

Backend (Requires Root/Sudo):
```bash
# From the root directory
cd backend
sudo -E USE_MININET=true python3 main.py
```
Note: Use sudo -E to preserve environment variables when enabling Mininet.

Frontend:
```bash
npm run dev
```

## Batch experiments (evaluation runners)

These scripts run the DTN stack **without the web frontend** to produce repeatable metrics (delivery ratio, latency, retransmissions, hop counts, and more). Results are written under `backend/experiment_results/` (CSVs, per-experiment JSON summaries, and optional combined JSON when you run everything).

### Simulation experiments (`experiment_runner.py`)

**What it does:** Drives `DTNBundleManager` in pure Python using **synthetic ISS contact windows** (staggered passes, fixed orbit period). Simulated time advances quickly with no wall-clock sleep, so runs are deterministic and independent of live TLEs or `main.py`.

**Requirements:** Activate the backend venv and run from `backend/` (no root, no Mininet):

```bash
cd backend
source venv/bin/activate   # Windows Git Bash: source venv/Scripts/activate
```

| Command | Behavior |
|--------|----------|
| `python experiment_runner.py` | Default “quick” run: **E1** baseline simulation plus **E4** standalone BSP security-overhead benchmark. |
| `python experiment_runner.py --all` / `-a` | Runs the full simulation suite: **E1**, custody on/off (**E2**), **E4**, fragmentation (**E5**), and scale (**E6**); writes `all_summaries.json`. Experiments are keyed **E1**, **E2_on**, **E2_off**, **E4**, **E5_frag_1k**, etc. |
| `python experiment_runner.py --experiment E1` / `-e E1` | Single experiment: pass the id shown by `--list` (e.g. **E1**, **E2_custody_on**, **E5_frag_1k**; matching is case-insensitive). |
| `python experiment_runner.py --list` / `-l` | Prints available experiment keys and short descriptions (includes **E4_standalone**). |

Use `--experiment E4` (or `E4_STANDALONE`) for **BSP-only** encrypt/PIB/BAB timing and payload overhead CSV (`E4_security_overhead.csv`), without a full bundle simulation loop.

### Mininet experiments (`mininet_experiment_runner.py`)

**What it does:** Brings up the real **Mininet** topology (`NetworkDTNManager`, TCP between nodes, **tc**-shaped ISS and ground links). Contact is modeled on a **deterministic wall-clock schedule** (link up/down), so experiments reflect actual socket traffic and RTT/loss statistics from the collector.

**Requirements:** **Linux or WSL2**, Mininet installed ([Mininet Setup](#mininet-setup)), and **root** so Mininet and Open vSwitch can run:

```bash
cd backend
sudo -E python3 mininet_experiment_runner.py --list
```

(`sudo -E` preserves environment variables such as `PATH` or a venv if needed.)

| Command | Behavior |
|--------|----------|
| `sudo -E python3 mininet_experiment_runner.py` | **Default:** runs **E8** Mininet baseline (≈20 bundles, comparable in spirit to simulation E1). |
| `sudo -E python3 mininet_experiment_runner.py --all` / `-a` | Runs **E8** (baseline), **E3** (packet-loss sweep 0–30%), then **E7** (DTN vs raw TCP under intermittent link). Writes `mininet_all_summaries.json`. |
| `sudo -E python3 mininet_experiment_runner.py --experiment E3` / `-e E3` | Single experiment: **E3** loss sweep, **E7** DTN vs TCP, or **E8** baseline. |
| `sudo -E python3 mininet_experiment_runner.py --list` / `-l` | Lists **E3**, **E7**, **E8** with one-line descriptions. |

**E3** exports a combined JSON (`E3_varying_loss_combined.json`). **E7** writes `E7_dtn_vs_tcp.json`. Per-run bundle CSVs and `mininet_experiment_summaries.csv` are updated like the simulation runner’s outputs.

## Features
### Orbital Tracking
The OrbitalTracker component (backend/orbital_tracker.py) uses the Skyfield library and SGP4 propagation to calculate the real-time position of the ISS based on Two-Line Element (TLE) sets. It predicts satellite passes for ground stations, calculates Acquisition of Signal (AOS) and Loss of Signal (LOS) times, and determines precise look angles (azimuth, elevation) and range for radio contacts.

- TLE Caching: The TLEFetcher component (backend/tle_fetcher.py) ensures the application works offline or during API outages by caching TLE data from CelesTrak locally (iss_tle_cache.txt) for up to 6 hours, automatically refreshing when stale.

### Link Budget Calculator
The LinkBudgetCalculator (backend/link_budget_calculator.py) simulates the physics of radio frequency (RF) communication. It considers factors such as free-space path loss, atmospheric attenuation, antenna gains, and transmitter power to estimate the Received Signal Strength Indicator (RSSI) and Signal-to-Noise Ratio (SNR). These metrics dynamically determine the achievable data rate (modulation coding scheme) during a pass.

### DTN Bundle Protocol
The core of the simulation is the DTNBundleManager (backend/dtn_bundle_manager.py), which implements the "Store-and-Forward" mechanism. It handles:

- Bundle Creation: Encapsulating data with source, destination, lifetime (TTL), and priority.
- Custody Transfer: Ensuring reliability by holding a bundle until the next hop acknowledges receipt (ACK/NAK).
- Routing: Determining the best path through the ground station mesh network or directly to the ISS based on contact windows.
- Persistence: Uses SQLite (backend/database.py) to store bundle states, ensuring data integrity and recovery if the backend service restarts or crashes.

### Network Topology
When running in Mininet mode, backend/mininet_topology.py builds a virtual network where:
- The ISS and Ground Stations are distinct network hosts with their own IP stacks.
- Links between the ISS and ground stations are dynamically reconfigured in real-time using Traffic Control (tc) to match the physics-calculated bandwidth, delay, and packet loss.
- Ground stations are connected in a partial mesh topology, allowing bundles to be routed between stations (e.g., London -> Toronto -> ISS) to find the optimal uplink window.

### Frontend Visualization
- 3D Globe: Visualizes the ISS orbit, coverage cone, and ground stations in real-time.
- ISS View: A dedicated component (SkyView) featuring a real-time ESA ISS tracker and live 4K video feeds from the station's external cameras.
- Traffic Flow Monitor: Detailed analytics dashboard tracking uplink/downlink bandwidth usage, visual bundle queue depth, and historical transmission performance.
- Link Analysis: Charts tracking SNR, Doppler shift, and data rates.
- Network Graph: A node-link diagram showing the connectivity between ground stations and the active mesh topology.
- Message Exchange: An interface to send text messages (bundles) and watch them propagate through the network, queue at stations, and eventually be delivered.
- Station Management: Interactive control allowing operators to switch active ground stations to inspect specific link metrics and manage local queues.

## How to Cite
### BibTeX
```
@misc{grover2026opensourceframeworkemulatedelay,
      title={An Open-Source Framework to Emulate Delay and Disruption Tolerant Networks for International Space Station Communication}, 
      author={Krit Grover and Marcelo Ponce},
      year={2026},
      eprint={2605.21624},
      archivePrefix={arXiv},
      primaryClass={cs.NI},
      url={https://arxiv.org/abs/2605.21624}, 
}
```

For other formats you can use websites like Scribbr and paste the arXiv link to generate the citation.