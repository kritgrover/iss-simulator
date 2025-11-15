# Mininet Network Simulation Usage Guide

This guide explains how to use the Mininet network simulation integration for the ISS Simulator.

## Overview

The Mininet integration replaces dictionary-based simulation with real network simulation using:
- Real TCP sockets for bundle transmission
- Configurable bandwidth, delay, and packet loss on links
- Dynamic link parameter updates based on orbital calculations
- Real network noise affecting bundle transmission

## Architecture

### Components

1. **ISSTopology** (`mininet_topology.py`)
   - Creates network topology with ISS and ground stations
   - Manages partial mesh ground station network
   - Handles dynamic ISS link parameter updates

2. **LinkParameterManager** (`link_parameter_manager.py`)
   - Converts link budget calculations to Mininet parameters
   - Maps SNR to packet loss rates
   - Calculates delays from range

3. **NetworkDTNManager** (`network_dtn_manager.py`)
   - Extends DTNBundleManager to use real sockets
   - Handles bundle transmission over TCP
   - Processes ACK/NAK messages

4. **Node Endpoints** (`mininet_nodes/`)
   - `dtn_server.py`: Server running in each Mininet node
   - `dtn_client.py`: Client utility for testing

## Usage

### Enabling Mininet Mode

Set the `USE_MININET` environment variable:

```bash
sudo USE_MININET=true python3 main.py
```

### Running Without Mininet (Simulation Mode)

By default, the system runs in simulation mode (no Mininet required):

```bash
python3 main.py
```
