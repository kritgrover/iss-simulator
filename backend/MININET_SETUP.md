# Mininet Setup Guide

This project uses Mininet for network simulation. Mininet requires Linux, so on Windows you'll need to use WSL2 or Docker.

## Option 1: WSL2 (Recommended for Windows)

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
   cd mininet
   git checkout 2.3.1
   util/install.sh -a
   
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

## Option 2: Docker

### Prerequisites
- Docker Desktop installed

### Installation Steps

1. **Create Dockerfile**:
   ```dockerfile
   FROM ubuntu:22.04
   RUN apt-get update && apt-get install -y \
       git python3-pip python3-dev build-essential \
       && git clone https://github.com/mininet/mininet.git \
       && cd mininet && git checkout 2.3.1 && util/install.sh -a \
       && pip3 install mininet
   ```

2. **Build and Run**:
   ```bash
   docker build -t iss-simulator-mininet .
   docker run -it --privileged --rm iss-simulator-mininet
   ```

## Troubleshooting

### Permission Denied Errors
- Mininet requires root/sudo privileges
- Use `sudo` when running the backend

### Network Namespace Errors
- Ensure you're running with `--privileged` in Docker
- In WSL2, ensure you have proper permissions

### Import Errors
- Verify Mininet is installed: `python3 -c "import mininet"`
- Check Python path: `python3 -c "import sys; print(sys.path)"`

## Notes
- The simulator will create a network topology with ISS and ground stations
- Network links are dynamically updated based on orbital calculations
- All network traffic uses real TCP sockets with configurable noise/delay

