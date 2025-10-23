import math
from typing import Dict
from datetime import datetime, timezone

class LinkBudgetCalculator:
    """Calculate RF link budget parameters for ISS communications"""
    
    # Physical constants
    SPEED_OF_LIGHT = 299792.458  # km/s
    BOLTZMANN_CONSTANT = 1.380649e-23  # J/K
    
    # ISS Communication parameters
    ISS_TRANSMIT_POWER_DBM = 43.0  # dBm
    ISS_ANTENNA_GAIN_DBI = 12.0    # dBi
    GROUND_ANTENNA_GAIN_DBI = 18.0  # dBi
    SYSTEM_NOISE_TEMP_K = 125.0     # Kelvin
    
    # Frequency parameters (Amateur radio band)
    DOWNLINK_FREQ_MHZ = 145.800  # MHz (ISS to Ground)
    UPLINK_FREQ_MHZ = 145.200    # MHz (Ground to ISS - Region 1)
    
    # System parameters
    CABLE_LOSS_DB = 2.0  # dB (coax cable losses)
    MISC_LOSSES_DB = 3.0  # dB (connectors, weather, etc.)
    
    def __init__(self):
        pass
    
    def calculate_free_space_path_loss(self, distance_km: float, frequency_mhz: float) -> float:
        """
        Calculate Free Space Path Loss (FSPL)
        FSPL(dB) = 20*log10(distance_km) + 20*log10(freq_MHz) + 32.45
        """
        if distance_km <= 0:
            return 0.0
        
        fspl = 20 * math.log10(distance_km) + 20 * math.log10(frequency_mhz) + 32.45
        return float(fspl)
    
    def calculate_atmospheric_attenuation(self, elevation_degrees: float) -> float:
        """
        Calculate atmospheric attenuation based on elevation angle
        Higher loss near horizon due to longer path through atmosphere
        """
        if elevation_degrees < 0:
            return 50.0  # Very high loss below horizon
        
        if elevation_degrees >= 90:
            return 0.5  # Minimal loss straight up
        
        # Approximate atmospheric loss (dB)
        # Uses exponential model: more atmosphere = more loss
        elevation_rad = math.radians(elevation_degrees)
        path_length_factor = 1.0 / math.sin(elevation_rad) if elevation_rad > 0 else 10.0
        
        # Base atmospheric loss at zenith + path length scaling
        base_loss = 0.5  # dB at 90° elevation
        atm_loss = base_loss * min(path_length_factor, 10.0)
        
        return float(atm_loss)
    
    def calculate_doppler_shift(self, radial_velocity_kmps: float, frequency_mhz: float) -> float:
        """
        Calculate Doppler frequency shift
        Δf = (radial_velocity / speed_of_light) * carrier_frequency
        Returns shift in kHz
        """
        # Convert frequency to Hz
        frequency_hz = frequency_mhz * 1e6
        
        # Calculate Doppler shift in Hz
        doppler_hz = (radial_velocity_kmps / self.SPEED_OF_LIGHT) * frequency_hz
        
        # Convert to kHz
        doppler_khz = doppler_hz / 1000.0
        
        return float(doppler_khz)
    
    def calculate_noise_floor(self, bandwidth_hz: float = 12500) -> float:
        """
        Calculate system noise floor
        Noise Power (dBm) = 10*log10(k*T*B*1000) where:
        k = Boltzmann constant
        T = System noise temperature (K)
        B = Bandwidth (Hz)
        """
        noise_power_watts = self.BOLTZMANN_CONSTANT * self.SYSTEM_NOISE_TEMP_K * bandwidth_hz
        noise_power_dbm = 10 * math.log10(noise_power_watts * 1000)
        return float(noise_power_dbm)
    
    def calculate_link_budget(self, range_km: float, elevation_degrees: float, 
                         radial_velocity_kmps: float) -> Dict:
        """
        Calculate complete link budget for ISS downlink
        radial_velocity_kmps: positive = receding, negative = approaching
        """
        
        # 1. Calculate Free Space Path Loss
        fspl = self.calculate_free_space_path_loss(range_km, self.DOWNLINK_FREQ_MHZ)
        
        # 2. Calculate atmospheric attenuation
        atm_loss = self.calculate_atmospheric_attenuation(elevation_degrees)
        
        # 3. Calculate received signal strength
        received_power_dbm = (
            self.ISS_TRANSMIT_POWER_DBM +
            self.ISS_ANTENNA_GAIN_DBI +
            self.GROUND_ANTENNA_GAIN_DBI -
            fspl -
            atm_loss -
            self.CABLE_LOSS_DB -
            self.MISC_LOSSES_DB
        )
        
        # 4. Calculate noise floor
        noise_floor_dbm = self.calculate_noise_floor()
        
        # 5. Calculate Signal-to-Noise Ratio (SNR)
        snr_db = received_power_dbm - noise_floor_dbm
        
        # 6. Calculate Doppler shift using actual radial velocity
        # Note: radial_velocity is positive when receding, negative when approaching
        # For Doppler: positive velocity = red shift (positive Doppler)
        #              negative velocity = blue shift (negative Doppler)
        doppler_khz = self.calculate_doppler_shift(radial_velocity_kmps, self.DOWNLINK_FREQ_MHZ)
        
        # 7. Calculate latency (speed of light delay)
        latency_ms = (range_km / self.SPEED_OF_LIGHT) * 1000
        
        # 8. Determine connection state
        if elevation_degrees < 0:
            connection_state = "IDLE"
        elif snr_db >= 10:
            connection_state = "ACQUIRED"
        elif snr_db >= 3:
            connection_state = "DEGRADED"
        else:
            connection_state = "IDLE"
        
        return {
            "signal_strength_dbm": round(received_power_dbm, 2),
            "snr_db": round(snr_db, 2),
            "connection_state": connection_state,
            "latency_ms": round(latency_ms, 3),
            "doppler_shift_khz": round(doppler_khz, 3),
            "range_km": round(range_km, 2),
            "elevation_deg": round(elevation_degrees, 2),
            "fspl_db": round(fspl, 2),
            "atmospheric_loss_db": round(atm_loss, 2),
            "noise_floor_dbm": round(noise_floor_dbm, 2),
            "radial_velocity_kmps": round(radial_velocity_kmps, 3)
        }