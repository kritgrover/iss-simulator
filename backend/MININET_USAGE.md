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
export USE_MININET=true
python3 main.py
```

Or run directly:
```bash
USE_MININET=true python3 main.py
```

### Running Without Mininet (Simulation Mode)

By default, the system runs in simulation mode (no Mininet required):

```bash
python3 main.py
```

## Topology Design

### Ground Station Network
- **Partial Mesh**: Each station connects to 3 nearest neighbors (geographic proximity)
- **High Bandwidth**: 100 Mbps ground links
- **Low Delay**: 50ms base delay
- **Low Loss**: 0.01% packet loss

### ISS Links
- **Dynamic**: Created/updated based on visibility
- **Bandwidth**: Calculated from link budget (data rate)
- **Delay**: Based on range (speed of light)
- **Loss**: Mapped from SNR (poor SNR = high loss)

## Link Parameter Mapping

### SNR to Packet Loss
- SNR < 0 dB: 30-50% loss
- SNR 0-3 dB: 10-30% loss
- SNR 3-6 dB: 5-10% loss
- SNR 6-10 dB: 1-5% loss
- SNR > 10 dB: 0.1-1% loss

### Range to Delay
- Delay (ms) = Range (km) / Speed of Light (km/s) * 1000

### Data Rate to Bandwidth
- Bandwidth (Mbps) = Data Rate (bps) / 1,000,000

## Testing

Run the test suite:

```bash
cd backend
python3 test_mininet_integration.py
```

Tests include:
1. Topology creation
2. Link parameter conversion
3. Checksum verification
4. Bundle transmission (requires Mininet)

## Network Protocol

### Bundle Message Format
```json
{
  "type": "bundle",
  "bundle": {
    "bundle_id": "...",
    "source_station": "...",
    "destination_station": "...",
    "payload": "...",
    "priority": "NORMAL",
    "checksum": 1234567890,
    "size_bytes": 1024
  }
}
```

### ACK Message Format
```json
{
  "type": "ack",
  "bundle_id": "...",
  "checksum": 1234567890
}
```

### NAK Message Format
```json
{
  "type": "nak",
  "bundle_id": "...",
  "reason": "checksum_mismatch",
  "expected_checksum": 1234567890,
  "received_checksum": 9876543210
}
```

## Troubleshooting

### Mininet Not Available
- Ensure Mininet is installed (see `MININET_SETUP.md`)
- Check that you're running on Linux/WSL2
- Verify Mininet import: `python3 -c "import mininet"`

### Permission Errors
- Mininet requires root privileges
- Run with `sudo`: `sudo python3 main.py`

### Network Errors
- Check firewall settings
- Verify port 5000 is available
- Ensure topology is started before sending bundles

### Link Parameters Not Updating
- Check that `USE_MININET=true` is set
- Verify orbital tracking is running
- Check logs for link update messages

## Performance Considerations

### Simulation Mode vs Mininet Mode

**Simulation Mode:**
- Faster execution
- No network overhead
- Good for development/testing
- No real network effects

**Mininet Mode:**
- Realistic network simulation
- Actual TCP sockets
- Real delays and packet loss
- Better for validation
- Requires root privileges

## Integration with Existing Code

The Mininet integration is designed to be backward compatible:
- Existing DTN logic continues to work
- WebSocket frontend unchanged
- API endpoints unchanged
- Falls back to simulation if Mininet unavailable

## Next Steps

1. Test in WSL2/Docker environment
2. Verify link parameter updates
3. Test bundle transmission with noise
4. Validate checksum/ACK/NAK functionality
5. Monitor network performance

