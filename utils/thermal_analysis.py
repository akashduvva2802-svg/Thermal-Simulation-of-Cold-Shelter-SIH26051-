"""
thermal_analysis.py
===================
Post-processing and analysis utilities for thermal simulation results.
Computes derived quantities:
  - Heat flow details for temperature difference between ambient and shelter
  - Thermal resistance network analysis
  - R-value and U-value calculations
  - Energy balance summaries
"""

import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class HeatFlowDetail:
    """Heat flow calculation between ambient and shelter at a specific time."""
    time_s: float
    ambient_temp_K: float
    shelter_temp_K: float
    delta_T: float                  # Temperature difference (K)
    conduction_resistance: float    # R_cond (K/W)
    convection_outer_resistance: float  # R_conv_out (K/W)
    convection_inner_resistance: float  # R_conv_in (K/W)
    total_resistance: float         # R_total (K/W)
    heat_flow_rate_W: float         # Q (W) through the wall
    heat_flux_W_per_m2: float       # q (W/m^2)
    u_value: float                  # Overall heat transfer coefficient (W/m^2·K)


class ThermalAnalyzer:
    """
    Performs detailed thermal analysis for dome shelters.
    """

    def __init__(
        self,
        inner_radius: float,
        outer_radius: float,
        thickness: float,
        conductivity: float,
        surface_area: float,
        internal_volume: float,
    ):
        self.R_in = inner_radius
        self.R_out = outer_radius
        self.thickness = thickness
        self.k = conductivity
        self.A = surface_area
        self.A_in = 2 * math.pi * inner_radius ** 2
        self.V = internal_volume

    def conduction_resistance_spherical(self) -> float:
        """Spherical shell conduction resistance (K/W)."""
        return (1/self.R_in - 1/self.R_out) / (4 * math.pi * self.k)

    def conduction_resistance_flat(self) -> float:
        """Flat wall approximation of conduction resistance (K/W)."""
        return self.thickness / (self.k * self.A)

    def convection_resistance(self, h: float, area: float) -> float:
        """Convection resistance (K/W) given coefficient h and area."""
        return 1.0 / (h * area)

    def overall_u_value(self, h_outer: float, h_inner: float) -> float:
        """
        Overall heat transfer coefficient (U-value) in W/(m²·K).
        U = 1 / (1/h_out + t/k + 1/h_in) for flat wall approximation.
        """
        R_total = (1/h_outer + self.thickness/self.k + 1/h_inner)
        return 1.0 / R_total

    def r_value(self, h_outer: float, h_inner: float) -> float:
        """R-value (thermal resistance per unit area) in m²·K/W."""
        return 1.0 / self.overall_u_value(h_outer, h_inner)

    def compute_heat_flow_timeseries(
        self,
        time_series: List[float],
        ambient_temps: List[float],
        shelter_temps: List[float],
        wind_speed: float = 2.0,
    ) -> List[HeatFlowDetail]:
        """
        Compute heat flow details for a time series.
        
        Args:
            time_series: Time values in seconds
            ambient_temps: Ambient temperatures in K
            shelter_temps: Shelter inside temperatures in K
            wind_speed: Wind speed in m/s for external convection
            
        Returns:
            List of HeatFlowDetail for each time step
        """
        results = []
        h_out = 5.7 + 3.8 * wind_speed  # External forced convection

        for t, T_amb, T_shelter in zip(time_series, ambient_temps, shelter_temps):
            delta_T = T_amb - T_shelter

            # Natural convection inside
            dT_inner = abs(delta_T) if abs(delta_T) > 0.1 else 0.1
            Ra = (1.177**2 * 1006.43 * 9.81 * (1/300) * dT_inner * self.R_in**3) / (1.846e-5 * 0.0242)
            if Ra < 1e9:
                Nu = 0.68 + 0.67 * Ra**0.25 / (1 + (0.492/0.707)**(9/16))**(4/9)
            else:
                Nu = (0.825 + 0.387 * Ra**(1/6) / (1 + (0.492/0.707)**(9/16))**(8/27))**2
            h_in = max(2.0, Nu * 0.0242 / self.R_in)

            # Resistances
            R_conv_out = self.convection_resistance(h_out, self.A)
            R_cond = self.conduction_resistance_spherical()
            R_conv_in = self.convection_resistance(h_in, self.A_in)
            R_total = R_conv_out + R_cond + R_conv_in

            # Heat flow
            Q = delta_T / R_total if R_total > 0 else 0
            q = Q / self.A if self.A > 0 else 0
            U = 1.0 / (R_total * self.A) if R_total > 0 and self.A > 0 else 0

            results.append(HeatFlowDetail(
                time_s=t,
                ambient_temp_K=T_amb,
                shelter_temp_K=T_shelter,
                delta_T=delta_T,
                conduction_resistance=R_cond,
                convection_outer_resistance=R_conv_out,
                convection_inner_resistance=R_conv_in,
                total_resistance=R_total,
                heat_flow_rate_W=Q,
                heat_flux_W_per_m2=q,
                u_value=U,
            ))

        return results

    def compute_cumulative_energy(
        self,
        heat_flow_details: List[HeatFlowDetail],
    ) -> Dict[str, float]:
        """
        Compute cumulative energy transfer over the simulation period.
        
        Returns dict with energy values in kWh and MJ.
        """
        if len(heat_flow_details) < 2:
            return {}

        total_energy_J = 0.0
        heating_energy_J = 0.0
        cooling_energy_J = 0.0

        for i in range(1, len(heat_flow_details)):
            dt = heat_flow_details[i].time_s - heat_flow_details[i-1].time_s
            Q = heat_flow_details[i].heat_flow_rate_W
            energy = Q * dt
            total_energy_J += abs(energy)
            if Q > 0:
                heating_energy_J += energy
            else:
                cooling_energy_J += abs(energy)

        return {
            "total_energy_transfer_kWh": round(total_energy_J / 3.6e6, 4),
            "total_energy_transfer_MJ": round(total_energy_J / 1e6, 4),
            "heating_energy_kWh": round(heating_energy_J / 3.6e6, 4),
            "cooling_energy_kWh": round(cooling_energy_J / 3.6e6, 4),
            "average_heat_flow_W": round(
                total_energy_J / (heat_flow_details[-1].time_s - heat_flow_details[0].time_s)
                if heat_flow_details[-1].time_s > heat_flow_details[0].time_s else 0, 2
            ),
            "peak_heat_flow_W": round(
                max(abs(h.heat_flow_rate_W) for h in heat_flow_details), 2
            ),
        }

    def thermal_time_constant(self) -> float:
        """
        Thermal time constant of the shelter (seconds).
        tau = (m_air * cp_air * R_total) approximation.
        """
        m_air = 1.177 * self.V
        cp_air = 1006.43
        R_cond = self.conduction_resistance_spherical()
        return m_air * cp_air * R_cond

    @staticmethod
    def format_temperature(temp_K: float) -> str:
        """Format temperature in both K and °C."""
        return f"{temp_K:.1f} K ({temp_K - 273.15:.1f} °C)"
