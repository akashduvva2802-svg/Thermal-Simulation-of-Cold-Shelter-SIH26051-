"""Quick smoke test for the dome thermal simulation modules."""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.material_database import MaterialManager
from core.geometry_generator import DomeGeometryParams, INNER_RADIUS_OPTIONS, THICKNESS_OPTIONS
from core.solar_model import SolarParams, SolarThermalModel
from utils.thermal_analysis import ThermalAnalyzer

print("=" * 60)
print("  DOME THERMAL SIMULATION — SMOKE TEST")
print("=" * 60)

# 1. Material database
mm = MaterialManager()
print(f"\n[1] Materials loaded: {len(mm.list_all())} total")
steel = mm.get("mild_steel")
print(f"    Mild Steel: ρ={steel.density} kg/m³, k={steel.thermal_conductivity} W/(m·K)")

# 2. Geometry
geom = DomeGeometryParams(inner_radius=2.0, thickness=0.01)
print(f"\n[2] Geometry: R_in={geom.inner_radius}m, t={geom.thickness}m")
print(f"    Outer radius: {geom.outer_radius}m")
print(f"    Surface area: {geom.dome_surface_area:.2f} m²")
print(f"    Internal volume: {geom.dome_volume_internal:.2f} m³")
print(f"    Available radius options: {INNER_RADIUS_OPTIONS}")
print(f"    Available thickness options: {THICKNESS_OPTIONS}")

# 3. Solar model — run 12-hour simulation
solar = SolarParams(
    latitude=23.0, day_of_year=172,
    ambient_temp_mean=303.15, ambient_temp_amplitude=8.0,
    wind_speed=2.0, start_hour=6.0, end_hour=18.0,
)
model = SolarThermalModel(
    solar_params=solar,
    dome_outer_radius=geom.outer_radius,
    dome_inner_radius=geom.inner_radius,
    dome_thickness=geom.thickness,
    shell_conductivity=steel.thermal_conductivity,
    shell_density=steel.density,
    shell_specific_heat=steel.specific_heat,
    shell_absorptivity=steel.absorptivity,
    shell_emissivity=steel.emissivity,
    dome_surface_area=geom.dome_surface_area,
    dome_internal_volume=geom.dome_volume_internal,
)

print(f"\n[3] Running 12-hour transient simulation (dt=60s)...")
results = model.run_transient(dt=60.0)
print(f"    Time steps computed: {len(results)}")
print(f"    Time range: {results[0].time_s}s → {results[-1].time_s}s ({(results[-1].time_s)/3600:.1f} hours)")

# Temperature summary
T_in = [r.inside_temp for r in results]
T_out = [r.outer_surface_temp for r in results]
T_amb = [r.ambient_temp for r in results]
print(f"\n    Inside Temp:  min={min(T_in):.1f}K ({min(T_in)-273.15:.1f}°C) → max={max(T_in):.1f}K ({max(T_in)-273.15:.1f}°C)")
print(f"    Outer Surface: min={min(T_out):.1f}K → max={max(T_out):.1f}K")
print(f"    Ambient:      min={min(T_amb):.1f}K → max={max(T_amb):.1f}K")

# Energy summary
energy = model.compute_energy_summary(results)
print(f"\n[4] Energy Summary:")
print(f"    Total solar irradiation: {energy['total_solar_irradiation_MJ']} MJ")
print(f"    Solar absorbed:          {energy['total_solar_absorbed_MJ']} MJ")
print(f"    Conducted through wall:  {energy['total_conducted_through_wall_MJ']} MJ")
print(f"    Peak inside temp:        {energy['peak_inside_temp_C']}°C")
print(f"    Max heat flux:           {energy['max_heat_flux_W_per_m2']} W/m²")

# 5. Heat flow analysis
analyzer = ThermalAnalyzer(
    inner_radius=geom.inner_radius, outer_radius=geom.outer_radius,
    thickness=geom.thickness, conductivity=steel.thermal_conductivity,
    surface_area=geom.dome_surface_area, internal_volume=geom.dome_volume_internal,
)
heat_flows = analyzer.compute_heat_flow_timeseries(
    time_series=[r.time_s for r in results],
    ambient_temps=T_amb, shelter_temps=T_in, wind_speed=2.0,
)
cum_energy = analyzer.compute_cumulative_energy(heat_flows)
print(f"\n[5] Heat Flow Analysis:")
print(f"    Total energy transfer: {cum_energy.get('total_energy_transfer_kWh', 0)} kWh")
print(f"    Average heat flow:     {cum_energy.get('average_heat_flow_W', 0)} W")
print(f"    Peak heat flow:        {cum_energy.get('peak_heat_flow_W', 0)} W")
print(f"    Thermal time constant:  {analyzer.thermal_time_constant():.1f} s ({analyzer.thermal_time_constant()/60:.1f} min)")

# 6. CSV export
csv_path = os.path.join(os.path.dirname(__file__), "results", "test_results.csv")
model.export_results_csv(results, csv_path)
print(f"\n[6] Results exported to: {csv_path}")

print("\n" + "=" * 60)
print("  ✅ ALL TESTS PASSED — Simulation engine is working!")
print("=" * 60)
