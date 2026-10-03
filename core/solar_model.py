"""
solar_model.py
==============
Solar radiation and thermal energy prediction module.
Computes:
  1. Solar irradiance on a hemispherical surface (time-varying)
  2. Thermal energy absorbed from solar radiation
  3. Heat flow through the shelter wall (conduction/convection)
  4. Inside shelter temperature prediction (lumped capacitance + refinement)
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import json
import os


@dataclass
class SolarParams:
    """Parameters for solar radiation calculation."""
    latitude: float = 23.0          # Latitude in degrees (default: ~Tropic of Cancer / India)
    day_of_year: int = 172          # Day of year (1-365), 172 = June 21 (summer solstice)
    solar_constant: float = 1361.0  # Solar constant W/m^2
    clearness_index: float = 0.75   # Atmospheric clearness (0-1)
    albedo: float = 0.2             # Ground reflectance
    start_hour: float = 6.0         # Simulation start hour (local solar time)
    end_hour: float = 18.0          # Simulation end hour
    ambient_temp_mean: float = 303.15  # Mean ambient temperature (K), ~30°C
    ambient_temp_amplitude: float = 8.0  # Diurnal temperature amplitude (K)
    wind_speed: float = 2.0         # Wind speed (m/s)


@dataclass
class ThermalResult:
    """Result from thermal energy prediction at a single time step."""
    time_s: float               # Time in seconds from start
    hour: float                 # Solar hour
    solar_altitude: float       # Solar altitude angle (degrees)
    solar_azimuth: float        # Solar azimuth angle (degrees)
    direct_irradiance: float    # Direct normal irradiance (W/m^2)
    diffuse_irradiance: float   # Diffuse irradiance (W/m^2)
    total_irradiance_on_dome: float  # Total solar irradiance on dome surface (W)
    solar_energy_absorbed: float     # Solar energy absorbed by dome surface (W)
    ambient_temp: float         # Ambient temperature (K)
    outer_surface_temp: float   # Dome outer surface temperature (K)
    inner_surface_temp: float   # Dome inner surface temperature (K)
    inside_temp: float          # Air temperature inside shelter (K)
    heat_flux_conduction: float # Conduction heat flux through wall (W/m^2)
    heat_flow_total: float      # Total heat flow into shelter (W)
    convection_outer: float     # Convection from outer surface (W)
    radiation_loss_outer: float # Radiation loss from outer surface (W)


class SolarThermalModel:
    """
    Complete solar thermal model for hemispherical dome shelter.
    
    Physics:
    - Solar position calculation (declination, hour angle, altitude)
    - Beam + diffuse irradiance on hemisphere (Liu-Jordan isotropic model)
    - Surface energy balance: q_solar = q_conduction + q_convection_out + q_radiation_out
    - Transient lumped-capacitance for internal air temperature
    """

    def __init__(
        self,
        solar_params: SolarParams,
        dome_outer_radius: float,
        dome_inner_radius: float,
        dome_thickness: float,
        shell_conductivity: float,
        shell_density: float,
        shell_specific_heat: float,
        shell_absorptivity: float,
        shell_emissivity: float,
        dome_surface_area: float,
        dome_internal_volume: float,
    ):
        self.sp = solar_params
        self.R_out = dome_outer_radius
        self.R_in = dome_inner_radius
        self.thickness = dome_thickness
        self.k = shell_conductivity
        self.rho_s = shell_density
        self.cp_s = shell_specific_heat
        self.alpha_s = shell_absorptivity
        self.eps = shell_emissivity
        self.A_out = dome_surface_area
        self.V_in = dome_internal_volume

        # Air properties (at ~300K)
        self.rho_air = 1.177
        self.cp_air = 1006.43
        self.k_air = 0.02623
        self.mu_air = 1.846e-5
        self.Pr_air = 0.707
        self.beta_air = 1 / 300.0  # Thermal expansion coefficient

        # Stefan-Boltzmann constant
        self.sigma = 5.67e-8

    def solar_declination(self, day: int) -> float:
        """Solar declination angle in radians."""
        return math.radians(23.45 * math.sin(math.radians(360 * (284 + day) / 365)))

    def solar_hour_angle(self, hour: float) -> float:
        """Hour angle in radians. Solar noon = 0."""
        return math.radians(15 * (hour - 12))

    def solar_altitude(self, day: int, hour: float) -> float:
        """Solar altitude angle above horizon (radians)."""
        lat = math.radians(self.sp.latitude)
        dec = self.solar_declination(day)
        ha = self.solar_hour_angle(hour)
        sin_alt = (math.sin(lat) * math.sin(dec) +
                   math.cos(lat) * math.cos(dec) * math.cos(ha))
        return math.asin(max(-1, min(1, sin_alt)))

    def solar_azimuth(self, day: int, hour: float) -> float:
        """Solar azimuth angle (radians from south, positive=west)."""
        lat = math.radians(self.sp.latitude)
        dec = self.solar_declination(day)
        ha = self.solar_hour_angle(hour)
        alt = self.solar_altitude(day, hour)
        cos_az = ((math.sin(dec) - math.sin(alt) * math.sin(lat)) /
                  (math.cos(alt) * math.cos(lat) + 1e-10))
        cos_az = max(-1, min(1, cos_az))
        az = math.acos(cos_az)
        if ha > 0:
            az = -az  # Afternoon: west is negative from south convention
        return az

    def direct_normal_irradiance(self, day: int, hour: float) -> float:
        """Direct normal irradiance (DNI) in W/m^2."""
        alt = self.solar_altitude(day, hour)
        if alt <= 0:
            return 0.0
        # Simple atmospheric extinction model
        air_mass = 1.0 / (math.sin(alt) + 0.50572 * (math.degrees(alt) + 6.07995) ** (-1.6364))
        air_mass = max(air_mass, 1.0)
        dni = self.sp.solar_constant * self.sp.clearness_index * math.exp(-0.185 * air_mass)
        return max(0, dni)

    def diffuse_irradiance(self, day: int, hour: float) -> float:
        """Diffuse horizontal irradiance (DHI) in W/m^2."""
        alt = self.solar_altitude(day, hour)
        if alt <= 0:
            return 0.0
        dni = self.direct_normal_irradiance(day, hour)
        ghi = dni * math.sin(alt)
        # Liu-Jordan: diffuse fraction
        kt = ghi / (self.sp.solar_constant * math.sin(alt) + 1e-10)
        kt = max(0, min(1, kt))
        if kt <= 0.22:
            fd = 1.0 - 0.09 * kt
        elif kt <= 0.80:
            fd = 0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4
        else:
            fd = 0.165
        return max(0, fd * ghi)

    def irradiance_on_hemisphere(self, day: int, hour: float) -> Tuple[float, float, float]:
        """
        Total solar irradiance intercepted by the hemispherical dome.
        
        Returns: (direct_W, diffuse_W, total_W) - power in watts on the dome surface
        
        For a hemisphere:
        - Direct beam: intercepted by projected area (circle) = π R²
        - Diffuse: received by entire upper surface = 2π R² (isotropic sky)
        - Ground reflected: view factor ~0.5 for hemisphere on ground
        """
        alt = self.solar_altitude(day, hour)
        if alt <= 0:
            return 0.0, 0.0, 0.0

        dni = self.direct_normal_irradiance(day, hour)
        dhi = self.diffuse_irradiance(day, hour)

        # Direct: projected area = π R² (circle facing sun)
        projected_area = math.pi * self.R_out ** 2
        q_direct = dni * projected_area * math.sin(alt)

        # Diffuse: isotropic model, hemisphere sees half-sky
        q_diffuse = dhi * self.A_out * 0.5

        # Ground reflected
        ghi = dni * math.sin(alt) + dhi
        q_ground_reflected = self.sp.albedo * ghi * self.A_out * 0.5 * 0.3

        total = q_direct + q_diffuse + q_ground_reflected
        return q_direct, q_diffuse, total

    def ambient_temperature(self, hour: float) -> float:
        """Diurnal ambient temperature variation (K)."""
        # Max temperature at ~14:00, min at ~06:00
        phase = (hour - 14.0) * math.pi / 12.0
        return self.sp.ambient_temp_mean - self.sp.ambient_temp_amplitude * math.cos(phase)

    def outer_convection_coefficient(self, wind_speed: float) -> float:
        """External forced convection coefficient for hemisphere in crossflow (W/m²·K)."""
        # Empirical: h = 5.7 + 3.8 * V (simple wind model for buildings)
        return 5.7 + 3.8 * wind_speed

    def inner_natural_convection_coefficient(self, dT: float) -> float:
        """Internal natural convection coefficient inside dome (W/m²·K)."""
        if abs(dT) < 0.01:
            return 2.0
        L = self.R_in  # Characteristic length
        Ra = (self.rho_air ** 2 * self.cp_air * 9.81 * abs(self.beta_air * dT) *
              L ** 3) / (self.mu_air * self.k_air)
        # Churchill-Chu for natural convection
        if Ra < 1e9:
            Nu = 0.68 + 0.67 * Ra ** 0.25 / (1 + (0.492 / self.Pr_air) ** (9/16)) ** (4/9)
        else:
            Nu = (0.825 + 0.387 * Ra ** (1/6) /
                  (1 + (0.492 / self.Pr_air) ** (9/16)) ** (8/27)) ** 2
        return max(2.0, Nu * self.k_air / L)

    def run_transient(
        self,
        dt: float = 60.0,
        initial_inside_temp: Optional[float] = None,
    ) -> List[ThermalResult]:
        """
        Run transient thermal simulation.
        
        Solves energy balance at each time step:
        
        Shell outer surface:
          q_solar_absorbed = q_cond_through_wall + q_conv_outer + q_rad_outer
          
        Shell inner surface → inside air:
          q_cond_through_wall = q_conv_inner + m_air * cp_air * dT/dt
        
        Args:
            dt: Time step (seconds)
            initial_inside_temp: Initial temperature inside shelter (K)
        
        Returns:
            List of ThermalResult for each time step
        """
        T_amb_init = self.ambient_temperature(self.sp.start_hour)
        T_in = initial_inside_temp or T_amb_init
        T_wall_out = T_amb_init
        T_wall_in = T_amb_init

        # Thermal masses
        m_shell = self.rho_s * (2/3) * math.pi * (self.R_out**3 - self.R_in**3)
        m_air = self.rho_air * self.V_in
        C_shell = m_shell * self.cp_s
        C_air = m_air * self.cp_air

        # Inner surface area (for convection inside)
        A_in = 2 * math.pi * self.R_in ** 2

        total_seconds = (self.sp.end_hour - self.sp.start_hour) * 3600
        results = []
        t = 0.0

        while t <= total_seconds:
            hour = self.sp.start_hour + t / 3600.0
            T_amb = self.ambient_temperature(hour)

            # Solar irradiance
            q_dir, q_diff, q_total_solar = self.irradiance_on_hemisphere(
                self.sp.day_of_year, hour
            )
            q_absorbed = self.alpha_s * q_total_solar

            # External convection
            h_out = self.outer_convection_coefficient(self.sp.wind_speed)
            q_conv_out = h_out * self.A_out * (T_wall_out - T_amb)

            # External radiation (safe against overflow)
            try:
                q_rad_out = self.eps * self.sigma * self.A_out * (T_wall_out**4 - T_amb**4)
            except (OverflowError, ValueError):
                q_rad_out = self.eps * self.sigma * self.A_out * 4 * T_amb**3 * (T_wall_out - T_amb)

            # Conduction through shell (spherical shell conduction)
            R_cond = (1/self.R_in - 1/self.R_out) / (4 * math.pi * self.k)
            if R_cond > 1e-12:
                q_cond = (T_wall_out - T_wall_in) / R_cond
            else:
                q_cond = self.k * self.A_out * (T_wall_out - T_wall_in) / self.thickness

            # Limit conduction to prevent numerical blow-up
            max_q_cond = 1e6  # 1 MW max
            q_cond = max(-max_q_cond, min(max_q_cond, q_cond))

            # Internal natural convection
            dT_inner = T_wall_in - T_in
            h_in = self.inner_natural_convection_coefficient(dT_inner)
            q_conv_in = h_in * A_in * (T_wall_in - T_in)

            # Inner radiation (safe against overflow)
            try:
                q_rad_in = self.eps * self.sigma * A_in * (T_wall_in**4 - T_in**4)
            except (OverflowError, ValueError):
                q_rad_in = self.eps * self.sigma * A_in * 4 * T_in**3 * (T_wall_in - T_in)

            # Energy balance on outer wall surface
            dT_wall_out = (q_absorbed - q_conv_out - q_rad_out - q_cond) * dt / (C_shell * 0.5)
            # Clamp temperature change per step to prevent instability
            dT_wall_out = max(-5.0, min(5.0, dT_wall_out))
            T_wall_out += dT_wall_out

            # Energy balance on inner wall surface
            dT_wall_in = (q_cond - q_conv_in - q_rad_in) * dt / (C_shell * 0.5)
            dT_wall_in = max(-5.0, min(5.0, dT_wall_in))
            T_wall_in += dT_wall_in

            # Energy balance on inside air
            dT_air = (q_conv_in + q_rad_in) * dt / C_air
            dT_air = max(-2.0, min(2.0, dT_air))
            T_in += dT_air

            # Safety clamp: temperatures must stay in physical range
            T_wall_out = max(150.0, min(600.0, T_wall_out))
            T_wall_in = max(150.0, min(600.0, T_wall_in))
            T_in = max(150.0, min(600.0, T_in))

            # Solar angles
            alt = self.solar_altitude(self.sp.day_of_year, hour)
            az = self.solar_azimuth(self.sp.day_of_year, hour)

            # Heat flux through wall
            heat_flux_cond = q_cond / self.A_out if self.A_out > 0 else 0

            results.append(ThermalResult(
                time_s=t,
                hour=hour,
                solar_altitude=math.degrees(alt),
                solar_azimuth=math.degrees(az),
                direct_irradiance=q_dir,
                diffuse_irradiance=q_diff,
                total_irradiance_on_dome=q_total_solar,
                solar_energy_absorbed=q_absorbed,
                ambient_temp=T_amb,
                outer_surface_temp=T_wall_out,
                inner_surface_temp=T_wall_in,
                inside_temp=T_in,
                heat_flux_conduction=heat_flux_cond,
                heat_flow_total=q_cond,
                convection_outer=q_conv_out,
                radiation_loss_outer=q_rad_out,
            ))

            t += dt

        return results

    def compute_energy_summary(self, results: List[ThermalResult]) -> dict:
        """Compute total energy summary from simulation results."""
        if not results:
            return {}

        dt = results[1].time_s - results[0].time_s if len(results) > 1 else 60.0

        total_solar_energy = sum(r.total_irradiance_on_dome * dt for r in results) / 1e6  # MJ
        total_absorbed_energy = sum(r.solar_energy_absorbed * dt for r in results) / 1e6  # MJ
        total_conducted_energy = sum(abs(r.heat_flow_total) * dt for r in results) / 1e6  # MJ
        total_conv_loss = sum(r.convection_outer * dt for r in results) / 1e6  # MJ
        total_rad_loss = sum(r.radiation_loss_outer * dt for r in results) / 1e6  # MJ

        peak_inside = max(r.inside_temp for r in results)
        peak_outside = max(r.outer_surface_temp for r in results)
        min_inside = min(r.inside_temp for r in results)
        final_inside = results[-1].inside_temp
        max_heat_flux = max(r.heat_flux_conduction for r in results)

        return {
            "total_solar_irradiation_MJ": round(total_solar_energy, 2),
            "total_solar_absorbed_MJ": round(total_absorbed_energy, 2),
            "total_conducted_through_wall_MJ": round(total_conducted_energy, 2),
            "total_convection_loss_MJ": round(total_conv_loss, 2),
            "total_radiation_loss_MJ": round(total_rad_loss, 2),
            "peak_inside_temp_K": round(peak_inside, 2),
            "peak_inside_temp_C": round(peak_inside - 273.15, 2),
            "min_inside_temp_K": round(min_inside, 2),
            "min_inside_temp_C": round(min_inside - 273.15, 2),
            "final_inside_temp_K": round(final_inside, 2),
            "final_inside_temp_C": round(final_inside - 273.15, 2),
            "peak_outer_surface_temp_K": round(peak_outside, 2),
            "peak_outer_surface_temp_C": round(peak_outside - 273.15, 2),
            "max_heat_flux_W_per_m2": round(max_heat_flux, 2),
            "simulation_duration_hours": round(
                (results[-1].time_s - results[0].time_s) / 3600, 1
            ),
        }

    def export_results_csv(self, results: List[ThermalResult], filepath: str):
        """Export results to CSV."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            headers = [
                "time_s", "hour", "solar_altitude_deg", "solar_azimuth_deg",
                "direct_irradiance_W", "diffuse_irradiance_W",
                "total_solar_on_dome_W", "solar_absorbed_W",
                "ambient_temp_K", "outer_surface_temp_K",
                "inner_surface_temp_K", "inside_temp_K",
                "heat_flux_W_per_m2", "heat_flow_total_W",
                "convection_outer_W", "radiation_loss_outer_W",
            ]
            f.write(",".join(headers) + "\n")
            for r in results:
                row = [
                    f"{r.time_s:.1f}", f"{r.hour:.4f}",
                    f"{r.solar_altitude:.2f}", f"{r.solar_azimuth:.2f}",
                    f"{r.direct_irradiance:.2f}", f"{r.diffuse_irradiance:.2f}",
                    f"{r.total_irradiance_on_dome:.2f}", f"{r.solar_energy_absorbed:.2f}",
                    f"{r.ambient_temp:.2f}", f"{r.outer_surface_temp:.2f}",
                    f"{r.inner_surface_temp:.2f}", f"{r.inside_temp:.2f}",
                    f"{r.heat_flux_conduction:.4f}", f"{r.heat_flow_total:.2f}",
                    f"{r.convection_outer:.2f}", f"{r.radiation_loss_outer:.2f}",
                ]
                f.write(",".join(row) + "\n")
