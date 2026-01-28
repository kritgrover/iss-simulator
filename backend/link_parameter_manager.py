"""
Link Parameter Manager

Converts link budget calculations to Mininet link parameters:
- SNR -> Packet loss rate
- Range -> Delay (speed of light)
- Data rate -> Bandwidth
- SNR -> Jitter (delay variation)
"""

import math
from typing import Dict


class LinkParameterManager:
    """Manages conversion from link budget to Mininet link parameters"""
    
    # Speed of light in km/s
    SPEED_OF_LIGHT_KMPS = 299792.458
    
    # Minimum viable bandwidth
    MIN_BANDWIDTH_MBPS = 0.001 # 1 kbps
    
    # Maximum packet loss
    MAX_LOSS_PERCENT = 50.0
    
    def __init__(self):
        pass
    
    def snr_to_packet_loss(self, snr_db: float) -> float:
        """
        Convert SNR (dB) to packet loss percentage
        
        Mapping:
        - SNR < 0 dB: Very high loss (30-50%)
        - SNR 0-3 dB: High loss (10-30%)
        - SNR 3-6 dB: Moderate loss (5-10%)
        - SNR 6-10 dB: Low loss (1-5%)
        - SNR > 10 dB: Very low loss (0.1-1%)
        
        Args:
            snr_db: Signal-to-noise ratio in dB
            
        Returns:
            Packet loss percentage (0-50)
        """
        # Packet loss percentage based on SNR
        if snr_db < 0:
            loss = 30.0 + (abs(snr_db) / 10.0) * 20.0
            return min(loss, self.MAX_LOSS_PERCENT)
        elif snr_db < 3:
            loss = 30.0 - (snr_db / 3.0) * 20.0
            return max(loss, 10.0)
        elif snr_db < 6:
            loss = 10.0 - ((snr_db - 3.0) / 3.0) * 5.0
            return max(loss, 5.0)
        elif snr_db < 10:
            loss = 5.0 - ((snr_db - 6.0) / 4.0) * 4.0
            return max(loss, 1.0)
        else:
            if snr_db >= 20:
                return 0.1
            loss = 1.0 - ((snr_db - 10.0) / 10.0) * 0.9
            return max(loss, 0.1)
    
    def range_to_delay(self, range_km: float) -> float:
        """
        Convert range to one-way delay (speed of light)
        
        Args:
            range_km: Distance in kilometers
            
        Returns:
            Delay in milliseconds
        """
        if range_km <= 0:
            return 0.0
        
        # One-way delay = distance / speed_of_light
        delay_seconds = range_km / self.SPEED_OF_LIGHT_KMPS
        delay_ms = delay_seconds * 1000.0
        
        return delay_ms
    
    def data_rate_to_bandwidth(self, data_rate_bps: float) -> float:
        """
        Convert data rate to bandwidth for Mininet
        
        Args:
            data_rate_bps: Data rate in bits per second
            
        Returns:
            Bandwidth in Mbps
        """
        if data_rate_bps <= 0:
            return self.MIN_BANDWIDTH_MBPS
        
        # Convert bps to Mbps
        bandwidth_mbps = data_rate_bps / 1_000_000.0
        
        return max(bandwidth_mbps, self.MIN_BANDWIDTH_MBPS)
    
    def snr_to_jitter(self, snr_db: float, base_delay_ms: float) -> float:
        """
        Calculate delay jitter based on SNR
        
        Higher SNR = lower jitter
        Lower SNR = higher jitter (signal instability)
        
        Args:
            snr_db: Signal-to-noise ratio in dB
            base_delay_ms: Base delay in milliseconds
            
        Returns:
            Jitter in milliseconds (±variation)
        """
        # Jitter percentage based on SNR
        if snr_db < 0:
            jitter_percent = 0.20
        elif snr_db < 3:
            jitter_percent = 0.15
        elif snr_db < 6:
            jitter_percent = 0.10
        elif snr_db < 10:
            jitter_percent = 0.05
        else:
            jitter_percent = 0.02
        
        jitter_ms = base_delay_ms * jitter_percent
        return jitter_ms
    
    def link_budget_to_mininet_params(self, link_budget: Dict) -> Dict:
        """
        Convert link budget dictionary to Mininet link parameters
        
        Args:
            link_budget: Dictionary from LinkBudgetCalculator with keys:
                - snr_db: Signal-to-noise ratio
                - range_km: Distance
                - data_rate_bps: Data rate
                - connection_state: "ACQUIRED", "DEGRADED", or "IDLE"
                
        Returns:
            Dictionary with Mininet link parameters:
                - bandwidth_mbps: Link bandwidth
                - delay_ms: One-way delay
                - loss_percent: Packet loss percentage
                - jitter_ms: Delay jitter
        """
        snr_db = link_budget.get("snr_db", -50.0)
        range_km = link_budget.get("range_km", 0.0)
        data_rate_bps = link_budget.get("data_rate_bps", 0.0)
        connection_state = link_budget.get("connection_state", "IDLE")
        
        # If link is idle, set minimal parameters
        if connection_state == "IDLE" or snr_db < 0:
            return {
                "bandwidth_mbps": self.MIN_BANDWIDTH_MBPS,
                "delay_ms": self.range_to_delay(range_km) if range_km > 0 else 100.0,
                "loss_percent": self.MAX_LOSS_PERCENT,
                "jitter_ms": 10.0
            }
        
        # Calculate parameters
        bandwidth_mbps = self.data_rate_to_bandwidth(data_rate_bps)
        delay_ms = self.range_to_delay(range_km)
        loss_percent = self.snr_to_packet_loss(snr_db)
        jitter_ms = self.snr_to_jitter(snr_db, delay_ms)
        
        return {
            "bandwidth_mbps": bandwidth_mbps,
            "delay_ms": delay_ms,
            "loss_percent": loss_percent,
            "jitter_ms": jitter_ms
        }
