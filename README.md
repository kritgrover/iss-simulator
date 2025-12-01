# ISS Communication Simulator

### Demo Link: [ISS Simulator Demo](https://youtu.be/nzh2T8YPaEc?si=2Gu9HnW4LvIJG84V)

## Contributers
| Name          | UTORid   | Student Number | Email                         |
|---------------|----------|----------------|-------------------------------|
| Krit Grover   | groverk3 | 1008093643     | krit.grover@mail.utoronto.ca  |
| Ansh Aneel    | aneelans | —              | ansh.aneel@mail.utoronto.ca   |
| Ashwin Mallik | mallika7 | 1008329729     | ashwin.mallik@mail.utoronto.ca |


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
- [Features](#features)
  - [Orbital Tracking](#orbital-tracking)
  - [Link Budget Calculator](#link-budget-calculator)
  - [DTN Bundle Protocol](#dtn-bundle-protocol)
  - [Network Topology](#network-topology)
  - [Frontend Visualization](#frontend-visualization)

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
