# Mininet Setup Guide

This project uses Mininet for network simulation. Mininet requires Linux, so on Windows you'll need to use WSL2 or Docker.

## WSL2 (Recommended for Windows)

### Prerequisites
- Windows 10/11 with WSL2 installed
- Ubuntu 20.04 or 22.04 in WSL2wsl --install

### Installation Steps

1. **Install WSL2** (if not already installed):
   ```powershell
   wsl --install
   ```

2. **Install Mininet in WSL2**:
   ```bash
   # Update package list
   sudo apt-get update
   
   # Install dependencies
   sudo apt-get install -y git python3-pip python3-dev build-essential
   
   # Install Mininet
   git clone https://github.com/mininet/mininet.git
   
   # Install Python bindings
   pip3 install mininet
   ```

3. **Verify Installation**:
   ```bash
   sudo mn --test pingall
   ```

4. **Install Python Dependencies**:
   ```bash
   cd /path/to/iss-simulator/backend
   pip3 install -r requirements.txt
   ```

## Notes
- The simulator will create a network topology with ISS and ground stations
- Network links are dynamically updated based on orbital calculations
- All network traffic uses real TCP sockets with configurable noise/delay

