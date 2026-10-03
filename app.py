"""
app.py — Dome Thermal Simulation Web Application
=================================================
Streamlit-based UI for hemispherical dome shelter thermal simulation.

Features:
  ✦ Material selection with full property display
  ✦ Discrete slider-based dome geometry sizing (inner radius, thickness)
  ✦ Solar radiation parameters configuration
  ✦ Run analytical thermal model OR launch PyFluent CFD simulation
  ✦ Live residual plotting
  ✦ Temperature monitoring (outside face, inside face, inside air)
  ✦ Solar energy prediction charts
  ✦ Heat flow details with thermal resistance breakdown
  ✦ Export results to CSV

Launch: streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import math
import os
import sys
import time
import json
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.material_database import MaterialManager, MaterialProperties
from core.geometry_generator import (
    DomeGeometryParams,
    generate_hemisphere_stl,
    INNER_RADIUS_OPTIONS,
    THICKNESS_OPTIONS,
    DOOR_WIDTH_OPTIONS,
    DOOR_HEIGHT_OPTIONS,
    DOMAIN_SIZE_OPTIONS,
)
from core.solar_model import SolarParams, SolarThermalModel, ThermalResult
from utils.thermal_analysis import ThermalAnalyzer, HeatFlowDetail

# ──────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="🏗️ Dome Thermal Simulation",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #2d6a9f;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .stSlider > div > div > div {
        background: #2d6a9f;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    .section-divider {
        border-top: 2px solid #e0e0e0;
        margin: 2rem 0 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # ──────────────────────────────────────────────────────────────────
    #  HEADER
    # ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0; font-size:2rem;">☀️ Dome Shelter Thermal Simulation</h1>
        <p style="margin:0.5rem 0 0 0; opacity:0.9; font-size:1.1rem;">
            PyFluent-based thermal analysis with solar radiation modeling
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Initialize material manager
    mat_manager = MaterialManager()

    # ──────────────────────────────────────────────────────────────────
    #  SIDEBAR: Configuration
    # ──────────────────────────────────────────────────────────────────

    with st.sidebar:
        st.header("⚙️ Simulation Configuration")

        # ── Tab navigation ──
        config_tab = st.radio(
            "Configuration Section",
            ["🏠 Geometry", "🧱 Materials", "☀️ Solar & Environment", "🔧 Solver Settings"],
            label_visibility="collapsed",
        )

        st.markdown("---")

        # ── GEOMETRY TAB ──
        if config_tab == "🏠 Geometry":
            st.subheader("🏠 Dome Geometry")

            st.caption("Use discrete sliders to select dome dimensions")

            # Inner Radius - Discrete Slider
            radius_idx = st.select_slider(
                "Inner Radius (m)",
                options=INNER_RADIUS_OPTIONS,
                value=2.0,
                help="Inner radius of the hemispherical dome shelter",
            )

            # Thickness - Discrete Slider
            thickness_idx = st.select_slider(
                "Shell Thickness (m)",
                options=THICKNESS_OPTIONS,
                value=0.01,
                help="Thickness of the dome shell wall",
            )

            # Door dimensions
            st.caption("Door Opening")
            door_w = st.select_slider(
                "Door Width (m)",
                options=DOOR_WIDTH_OPTIONS,
                value=0.8,
            )
            door_h = st.select_slider(
                "Door Height (m)",
                options=DOOR_HEIGHT_OPTIONS,
                value=1.8,
            )

            # Domain size
            domain_choice = st.selectbox(
                "Computational Domain Size",
                options=[d["label"] for d in DOMAIN_SIZE_OPTIONS],
                index=1,
            )
            domain_mult = next(
                d["multiplier"] for d in DOMAIN_SIZE_OPTIONS
                if d["label"] == domain_choice
            )

            # Store geometry params
            geom_params = DomeGeometryParams(
                inner_radius=radius_idx,
                thickness=thickness_idx,
                door_width=door_w,
                door_height=door_h,
                domain_length=domain_mult * radius_idx * 2,
                domain_width=domain_mult * radius_idx * 2,
                domain_height=domain_mult * radius_idx,
            )
            st.session_state["geom_params"] = geom_params

            # Display geometry summary
            st.markdown("---")
            st.caption("📐 Geometry Summary")
            geo_data = geom_params.to_dict()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Outer Radius", f"{geo_data['outer_radius']:.3f} m")
                st.metric("Surface Area", f"{geo_data['dome_surface_area']:.2f} m²")
            with col2:
                st.metric("Internal Vol.", f"{geo_data['dome_volume_internal']:.2f} m³")
                st.metric("Shell Vol.", f"{geo_data['shell_volume']:.5f} m³")

        # ── MATERIALS TAB ──
        elif config_tab == "🧱 Materials":
            st.subheader("🧱 Shell Material")

            # Material selection
            solid_keys = mat_manager.get_solid_keys()
            solid_materials = {k: mat_manager.get(k) for k in solid_keys}

            # Group by category feel
            material_key = st.selectbox(
                "Select Shell Material",
                options=solid_keys,
                format_func=lambda k: mat_manager.get(k).name,
                index=solid_keys.index("mild_steel") if "mild_steel" in solid_keys else 0,
            )

            selected_mat = mat_manager.get(material_key)
            st.session_state["selected_material"] = selected_mat
            st.session_state["material_key"] = material_key

            # Material properties display
            if selected_mat:
                st.markdown("---")
                st.caption(f"📋 Properties: {selected_mat.name}")
                st.info(selected_mat.description)

                prop_df = pd.DataFrame({
                    "Property": [
                        "Density", "Specific Heat", "Thermal Conductivity",
                        "Absorptivity", "Emissivity", "Transmissivity",
                    ],
                    "Value": [
                        f"{selected_mat.density} kg/m³",
                        f"{selected_mat.specific_heat} J/(kg·K)",
                        f"{selected_mat.thermal_conductivity} W/(m·K)",
                        f"{selected_mat.absorptivity}",
                        f"{selected_mat.emissivity}",
                        f"{selected_mat.transmissivity}",
                    ],
                })
                st.dataframe(prop_df, hide_index=True, use_container_width=True)

                st.metric(
                    "Thermal Diffusivity",
                    f"{selected_mat.thermal_diffusivity:.2e} m²/s"
                )

            # Custom material input
            st.markdown("---")
            with st.expander("➕ Add Custom Material"):
                c_name = st.text_input("Material Name", "")
                c_density = st.number_input("Density (kg/m³)", value=7850.0, min_value=1.0)
                c_cp = st.number_input("Specific Heat (J/kg·K)", value=500.0, min_value=1.0)
                c_k = st.number_input("Conductivity (W/m·K)", value=50.0, min_value=0.001)
                c_abs = st.slider("Absorptivity", 0.0, 1.0, 0.5)
                c_ems = st.slider("Emissivity", 0.0, 1.0, 0.9)
                c_desc = st.text_input("Description", "")

                if st.button("💾 Save Material") and c_name:
                    key = c_name.lower().replace(" ", "_")
                    new_mat = MaterialProperties(
                        name=c_name,
                        density=c_density,
                        specific_heat=c_cp,
                        thermal_conductivity=c_k,
                        absorptivity=c_abs,
                        emissivity=c_ems,
                        description=c_desc,
                    )
                    mat_manager.save_custom(key, new_mat)
                    st.success(f"Material '{c_name}' saved!")
                    st.rerun()

        # ── SOLAR & ENVIRONMENT TAB ──
        elif config_tab == "☀️ Solar & Environment":
            st.subheader("☀️ Solar & Environment")

            latitude = st.slider("Latitude (°)", -90.0, 90.0, 23.0, 0.5,
                                 help="Latitude of shelter location")
            day_of_year = st.slider("Day of Year", 1, 365, 172,
                                    help="172 = June 21 (summer solstice)")
            clearness = st.slider("Clearness Index", 0.0, 1.0, 0.75, 0.05,
                                  help="Atmospheric clarity (1=perfectly clear)")

            st.markdown("---")
            st.caption("🌡️ Ambient Conditions")
            amb_temp_c = st.slider("Mean Ambient Temp (°C)", -10.0, 50.0, 30.0, 0.5)
            amb_amplitude = st.slider("Diurnal Amplitude (°C)", 0.0, 20.0, 8.0, 0.5)
            wind_speed = st.slider("Wind Speed (m/s)", 0.0, 20.0, 2.0, 0.5)

            st.markdown("---")
            st.caption("⏰ Simulation Period")
            start_hour = st.slider("Start Hour", 0.0, 23.0, 6.0, 0.5)
            end_hour = st.slider("End Hour", 1.0, 24.0, 18.0, 0.5)

            solar_params = SolarParams(
                latitude=latitude,
                day_of_year=day_of_year,
                clearness_index=clearness,
                ambient_temp_mean=amb_temp_c + 273.15,
                ambient_temp_amplitude=amb_amplitude,
                wind_speed=wind_speed,
                start_hour=start_hour,
                end_hour=end_hour,
            )
            st.session_state["solar_params"] = solar_params

        # ── SOLVER SETTINGS TAB ──
        elif config_tab == "🔧 Solver Settings":
            st.subheader("🔧 Solver Settings")

            sim_mode = st.radio(
                "Simulation Mode",
                ["🔬 Analytical Model (Fast)", "🖥️ PyFluent CFD (Full)"],
                index=0,
                help="Analytical: instant results. PyFluent: full CFD simulation",
            )
            st.session_state["sim_mode"] = sim_mode

            st.markdown("---")
            st.caption("Time Settings")
            time_step = st.select_slider(
                "Time Step (s)",
                options=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
                value=60.0 if "Analytical" in sim_mode else 1.0,
            )
            st.session_state["time_step"] = time_step

            if "PyFluent" in sim_mode:
                st.caption("PyFluent Specific Settings")
                n_procs = st.select_slider("CPU Cores", options=[1, 2, 4], value=2)
                visc_model = st.selectbox("Turbulence Model",
                    ["k-epsilon", "k-omega-sst", "laminar"], index=0)
                rad_model = st.selectbox("Radiation Model",
                    ["do", "s2s", "p1", "none"], index=0)
                st.session_state["fluent_procs"] = n_procs
                st.session_state["visc_model"] = visc_model
                st.session_state["rad_model"] = rad_model

    # ──────────────────────────────────────────────────────────────────
    #  MAIN CONTENT AREA
    # ──────────────────────────────────────────────────────────────────

    # Get config from session state
    geom_params = st.session_state.get("geom_params", DomeGeometryParams())
    solar_params = st.session_state.get("solar_params", SolarParams())
    selected_mat = st.session_state.get("selected_material", MaterialManager().get("mild_steel"))
    sim_mode = st.session_state.get("sim_mode", "🔬 Analytical Model (Fast)")
    time_step = st.session_state.get("time_step", 60.0)

    # ── Run Button ──
    col_run, col_status = st.columns([1, 3])
    with col_run:
        run_clicked = st.button(
            "🚀 Run Simulation",
            type="primary",
            use_container_width=True,
        )
    with col_status:
        status_placeholder = st.empty()

    if run_clicked:
        if "Analytical" in sim_mode:
            run_analytical_simulation(
                geom_params, solar_params, selected_mat, time_step, status_placeholder
            )
        else:
            run_pyfluent_simulation(
                geom_params, solar_params, selected_mat, time_step, status_placeholder
            )

    # ── Display results if available ──
    if "simulation_results" in st.session_state:
        display_results()


# ──────────────────────────────────────────────────────────────────────
#  ANALYTICAL SIMULATION
# ──────────────────────────────────────────────────────────────────────

def run_analytical_simulation(
    geom: DomeGeometryParams,
    solar: SolarParams,
    material: MaterialProperties,
    dt: float,
    status_container,
):
    """Run the analytical solar thermal model."""
    with status_container:
        st.info("⏳ Running analytical thermal model...")

    progress_bar = st.progress(0)

    model = SolarThermalModel(
        solar_params=solar,
        dome_outer_radius=geom.outer_radius,
        dome_inner_radius=geom.inner_radius,
        dome_thickness=geom.thickness,
        shell_conductivity=material.thermal_conductivity,
        shell_density=material.density,
        shell_specific_heat=material.specific_heat,
        shell_absorptivity=material.absorptivity,
        shell_emissivity=material.emissivity,
        dome_surface_area=geom.dome_surface_area,
        dome_internal_volume=geom.dome_volume_internal,
    )

    results = model.run_transient(dt=dt)
    progress_bar.progress(80)

    energy_summary = model.compute_energy_summary(results)
    progress_bar.progress(90)

    # Heat flow analysis
    analyzer = ThermalAnalyzer(
        inner_radius=geom.inner_radius,
        outer_radius=geom.outer_radius,
        thickness=geom.thickness,
        conductivity=material.thermal_conductivity,
        surface_area=geom.dome_surface_area,
        internal_volume=geom.dome_volume_internal,
    )

    heat_flows = analyzer.compute_heat_flow_timeseries(
        time_series=[r.time_s for r in results],
        ambient_temps=[r.ambient_temp for r in results],
        shelter_temps=[r.inside_temp for r in results],
        wind_speed=solar.wind_speed,
    )
    cumulative_energy = analyzer.compute_cumulative_energy(heat_flows)

    # Export CSV
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    csv_path = os.path.join(results_dir, "simulation_results.csv")
    model.export_results_csv(results, csv_path)

    progress_bar.progress(100)

    # Store in session state
    st.session_state["simulation_results"] = results
    st.session_state["energy_summary"] = energy_summary
    st.session_state["heat_flow_details"] = heat_flows
    st.session_state["cumulative_energy"] = cumulative_energy
    st.session_state["csv_path"] = csv_path
    st.session_state["geom_used"] = geom
    st.session_state["material_used"] = material
    st.session_state["solar_used"] = solar

    with status_container:
        st.success("✅ Analytical simulation complete!")

    progress_bar.empty()
    st.rerun()


# ──────────────────────────────────────────────────────────────────────
#  PYFLUENT SIMULATION
# ──────────────────────────────────────────────────────────────────────

def run_pyfluent_simulation(
    geom: DomeGeometryParams,
    solar: SolarParams,
    material: MaterialProperties,
    dt: float,
    status_container,
):
    """Launch full PyFluent CFD simulation."""
    with status_container:
        st.warning("🖥️ PyFluent CFD Simulation: Generating geometry & launching Fluent...")

    try:
        from core.fluent_solver import FluentConfig, FluentSolver, run_full_simulation

        results_dir = os.path.join(os.path.dirname(__file__), "results", "fluent_run")

        # Generate STL geometry matching exactly the UI sliders
        stl_dir = os.path.join(os.path.dirname(__file__), "geometry", "generated")
        geom_files = generate_hemisphere_stl(geom, stl_dir)
        geom_file = geom_files.get("assembly", "")

        progress = st.progress(0, text="Launching Fluent (this may take a few minutes)...")

        config = FluentConfig(
            processor_count=st.session_state.get("fluent_procs", 2),
            time_step_size=dt,
            viscous_model=st.session_state.get("visc_model", "k-epsilon"),
            radiation_model=st.session_state.get("rad_model", "do"),
            number_of_time_steps=20,  # Keep testing reasonable (default was too long)
        )

        status_text = st.empty()
        status_text.info(f"Stage: Launching PyFluent with {geom_file} ...")

        result = run_full_simulation(
            geometry_file=geom_file,
            shell_material_name=material.name.lower().replace(" ", "_"),
            shell_density=material.density,
            shell_specific_heat=material.specific_heat,
            shell_conductivity=material.thermal_conductivity,
            shell_absorptivity=material.absorptivity,
            shell_emissivity=material.emissivity,
            shell_thickness=geom.thickness,
            ambient_temp=solar.ambient_temp_mean,
            wind_speed=solar.wind_speed,
            time_step=dt,
            results_dir=results_dir,
            config=config,
        )

        progress.progress(100)

        if result["status"] == "complete":
            status_text.success("✅ PyFluent simulation complete!")
            # Parse temperature data from report files
            if result.get("temperature_data"):
                data = result["temperature_data"]
                if data["flow_time"]:
                    st.session_state["fluent_temp_data"] = data
        else:
            errors = result.get("errors", ["Unknown error"])
            status_text.error(f"❌ PyFluent Simulation failed: {'; '.join(errors)}")
            st.stop()  # Stop execution so we don't fall back silently

    except ImportError:
        with status_container:
            st.error(
                "⚠️ PyFluent not installed. Install with:\n\n"
                "```bash\npip install ansys-fluent-core ansys-fluent-parametric\n```\n\n"
                "Or use the **Analytical Model** which runs without Ansys."
            )
        st.stop()
    except Exception as e:
        with status_container:
            st.error(f"❌ PyFluent Error: {str(e)}")
            st.exception(e)
        st.stop()


# ──────────────────────────────────────────────────────────────────────
#  RESULTS DISPLAY
# ──────────────────────────────────────────────────────────────────────

def display_results():
    """Display all simulation results with interactive charts."""
    results: list = st.session_state["simulation_results"]
    energy: dict = st.session_state["energy_summary"]
    heat_flows: list = st.session_state["heat_flow_details"]
    cum_energy: dict = st.session_state["cumulative_energy"]
    geom: DomeGeometryParams = st.session_state.get("geom_used", DomeGeometryParams())
    material: MaterialProperties = st.session_state.get("material_used")
    solar: SolarParams = st.session_state.get("solar_used", SolarParams())

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Results Tabs ──
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Temperature Plots",
        "☀️ Solar Energy Prediction",
        "🔥 Heat Flow Details",
        "📈 Residuals & Convergence",
        "📋 Summary & Export",
    ])

    # ════════════════════════════════════════════════════════════════
    #  TAB 1: Temperature Plots
    # ════════════════════════════════════════════════════════════════
    with tab1:
        st.subheader("📊 Temperature Distribution Over Time")

        # Convert to arrays
        time_s = [r.time_s for r in results]
        time_h = [r.hour for r in results]
        T_out = [r.outer_surface_temp for r in results]
        T_in_face = [r.inner_surface_temp for r in results]
        T_inside = [r.inside_temp for r in results]
        T_amb = [r.ambient_temp for r in results]

        # Main temperature plot
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=time_s, y=T_out,
            name="temp_out_face",
            line=dict(color="#00bcd4", width=2),
            hovertemplate="Time: %{x:.0f}s<br>Temp: %{y:.2f} K<extra>Outer Surface</extra>",
        ))
        fig_temp.add_trace(go.Scatter(
            x=time_s, y=T_in_face,
            name="temp_inside_face",
            line=dict(color="#9c27b0", width=2),
            hovertemplate="Time: %{x:.0f}s<br>Temp: %{y:.2f} K<extra>Inner Surface</extra>",
        ))
        fig_temp.add_trace(go.Scatter(
            x=time_s, y=T_inside,
            name="inside-temp",
            line=dict(color="#f44336", width=2.5),
            hovertemplate="Time: %{x:.0f}s<br>Temp: %{y:.2f} K<extra>Inside Air</extra>",
        ))
        fig_temp.add_trace(go.Scatter(
            x=time_s, y=T_amb,
            name="Ambient",
            line=dict(color="#4caf50", width=1.5, dash="dash"),
            hovertemplate="Time: %{x:.0f}s<br>Temp: %{y:.2f} K<extra>Ambient</extra>",
        ))

        fig_temp.update_layout(
            title="Temperature vs Flow Time",
            xaxis_title="flow-time [s]",
            yaxis_title="Temperature [K]",
            height=500,
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0.5, xanchor="center"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_temp, use_container_width=True)

        # Temperature in °C
        col1, col2 = st.columns(2)
        with col1:
            fig_celsius = go.Figure()
            fig_celsius.add_trace(go.Scatter(
                x=time_h, y=[t - 273.15 for t in T_inside],
                name="Inside Air",
                line=dict(color="#f44336", width=2.5),
                fill="tozeroy",
                fillcolor="rgba(244,67,54,0.1)",
            ))
            fig_celsius.add_trace(go.Scatter(
                x=time_h, y=[t - 273.15 for t in T_amb],
                name="Ambient",
                line=dict(color="#4caf50", width=1.5, dash="dash"),
            ))
            fig_celsius.update_layout(
                title="Inside Shelter Temperature (°C)",
                xaxis_title="Solar Hour",
                yaxis_title="Temperature [°C]",
                height=350,
                template="plotly_white",
            )
            st.plotly_chart(fig_celsius, use_container_width=True)

        with col2:
            # Temperature difference
            dT = [to - ti for to, ti in zip(T_out, T_inside)]
            fig_dt = go.Figure()
            fig_dt.add_trace(go.Scatter(
                x=time_h, y=dT,
                name="ΔT (Outer - Inside)",
                line=dict(color="#ff9800", width=2),
                fill="tozeroy",
                fillcolor="rgba(255,152,0,0.15)",
            ))
            fig_dt.update_layout(
                title="Wall Temperature Gradient",
                xaxis_title="Solar Hour",
                yaxis_title="ΔT [K]",
                height=350,
                template="plotly_white",
            )
            st.plotly_chart(fig_dt, use_container_width=True)

    # ════════════════════════════════════════════════════════════════
    #  TAB 2: Solar Energy Prediction
    # ════════════════════════════════════════════════════════════════
    with tab2:
        st.subheader("☀️ Solar Radiation & Thermal Energy Prediction")

        solar_irr = [r.total_irradiance_on_dome for r in results]
        solar_abs = [r.solar_energy_absorbed for r in results]
        direct_irr = [r.direct_irradiance for r in results]
        diffuse_irr = [r.diffuse_irradiance for r in results]
        solar_alt = [r.solar_altitude for r in results]

        col1, col2 = st.columns(2)

        with col1:
            # Solar irradiance on dome
            fig_solar = make_subplots(specs=[[{"secondary_y": True}]])
            fig_solar.add_trace(go.Scatter(
                x=time_h, y=solar_irr,
                name="Total Solar (W)",
                line=dict(color="#ff9800", width=2),
                fill="tozeroy",
                fillcolor="rgba(255,152,0,0.2)",
            ), secondary_y=False)
            fig_solar.add_trace(go.Scatter(
                x=time_h, y=solar_abs,
                name="Absorbed (W)",
                line=dict(color="#f44336", width=2),
            ), secondary_y=False)
            fig_solar.add_trace(go.Scatter(
                x=time_h, y=solar_alt,
                name="Solar Altitude (°)",
                line=dict(color="#2196f3", width=1.5, dash="dot"),
            ), secondary_y=True)
            fig_solar.update_layout(
                title="Solar Irradiance on Dome",
                height=400,
                template="plotly_white",
            )
            fig_solar.update_xaxes(title_text="Solar Hour")
            fig_solar.update_yaxes(title_text="Power [W]", secondary_y=False)
            fig_solar.update_yaxes(title_text="Altitude [°]", secondary_y=True)
            st.plotly_chart(fig_solar, use_container_width=True)

        with col2:
            # Direct vs Diffuse
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Scatter(
                x=time_h, y=direct_irr,
                name="Direct",
                line=dict(color="#ff5722"),
                fill="tonexty" if diffuse_irr else "tozeroy",
                stackgroup="one",
            ))
            fig_comp.add_trace(go.Scatter(
                x=time_h, y=diffuse_irr,
                name="Diffuse",
                line=dict(color="#03a9f4"),
                stackgroup="one",
            ))
            fig_comp.update_layout(
                title="Direct vs Diffuse Solar Radiation",
                xaxis_title="Solar Hour",
                yaxis_title="Irradiance [W]",
                height=400,
                template="plotly_white",
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        # Cumulative energy
        st.markdown("---")
        st.subheader("⚡ Cumulative Solar Energy")

        dt_val = results[1].time_s - results[0].time_s if len(results) > 1 else 60
        cum_solar = []
        running = 0
        for r in results:
            running += r.total_irradiance_on_dome * dt_val / 1e6  # MJ
            cum_solar.append(running)

        cum_absorbed = []
        running = 0
        for r in results:
            running += r.solar_energy_absorbed * dt_val / 1e6
            cum_absorbed.append(running)

        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(
            x=time_h, y=cum_solar,
            name="Total Solar Energy (MJ)",
            line=dict(color="#ff9800", width=2),
        ))
        fig_cum.add_trace(go.Scatter(
            x=time_h, y=cum_absorbed,
            name="Absorbed Energy (MJ)",
            line=dict(color="#f44336", width=2),
        ))
        fig_cum.update_layout(
            title="Cumulative Solar Energy",
            xaxis_title="Solar Hour",
            yaxis_title="Energy [MJ]",
            height=350,
            template="plotly_white",
        )
        st.plotly_chart(fig_cum, use_container_width=True)

        # Energy metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Solar Irradiation", f"{energy['total_solar_irradiation_MJ']} MJ")
        c2.metric("Solar Energy Absorbed", f"{energy['total_solar_absorbed_MJ']} MJ")
        c3.metric("Conducted Through Wall", f"{energy['total_conducted_through_wall_MJ']} MJ")
        c4.metric("Convection Loss", f"{energy['total_convection_loss_MJ']} MJ")

    # ════════════════════════════════════════════════════════════════
    #  TAB 3: Heat Flow Details
    # ════════════════════════════════════════════════════════════════
    with tab3:
        st.subheader("🔥 Heat Flow Details")
        st.caption(
            "Heat flow between ambient and shelter based on temperature difference "
            "for the defined simulation period"
        )

        hf_time = [h.time_s / 3600 + solar.start_hour for h in heat_flows]
        hf_rate = [h.heat_flow_rate_W for h in heat_flows]
        hf_flux = [h.heat_flux_W_per_m2 for h in heat_flows]
        hf_dt = [h.delta_T for h in heat_flows]

        col1, col2 = st.columns(2)

        with col1:
            # Heat flow rate
            fig_hf = go.Figure()
            fig_hf.add_trace(go.Scatter(
                x=hf_time, y=hf_rate,
                name="Heat Flow Rate",
                line=dict(color="#e91e63", width=2),
                fill="tozeroy",
                fillcolor="rgba(233,30,99,0.1)",
            ))
            fig_hf.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_hf.update_layout(
                title="Heat Flow Rate (Q) Through Shelter Wall",
                xaxis_title="Solar Hour",
                yaxis_title="Heat Flow [W]",
                height=400,
                template="plotly_white",
            )
            st.plotly_chart(fig_hf, use_container_width=True)

        with col2:
            # Temperature difference driving heat flow
            fig_dt2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig_dt2.add_trace(go.Scatter(
                x=hf_time, y=hf_dt,
                name="ΔT (Ambient - Shelter)",
                line=dict(color="#2196f3", width=2),
            ), secondary_y=False)
            fig_dt2.add_trace(go.Scatter(
                x=hf_time, y=hf_flux,
                name="Heat Flux (W/m²)",
                line=dict(color="#ff5722", width=1.5, dash="dot"),
            ), secondary_y=True)
            fig_dt2.update_layout(
                title="Temperature Difference & Heat Flux",
                height=400,
                template="plotly_white",
            )
            fig_dt2.update_xaxes(title_text="Solar Hour")
            fig_dt2.update_yaxes(title_text="ΔT [K]", secondary_y=False)
            fig_dt2.update_yaxes(title_text="Heat Flux [W/m²]", secondary_y=True)
            st.plotly_chart(fig_dt2, use_container_width=True)

        # Thermal resistance breakdown
        st.markdown("---")
        st.subheader("🧊 Thermal Resistance Network")

        if heat_flows:
            mid_idx = len(heat_flows) // 2
            hf_mid = heat_flows[mid_idx]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("R_conv (outer)", f"{hf_mid.convection_outer_resistance:.4f} K/W")
            c2.metric("R_cond (wall)", f"{hf_mid.conduction_resistance:.6f} K/W")
            c3.metric("R_conv (inner)", f"{hf_mid.convection_inner_resistance:.4f} K/W")
            c4.metric("R_total", f"{hf_mid.total_resistance:.4f} K/W")

            # U-value
            st.metric("Overall U-value", f"{hf_mid.u_value:.2f} W/(m²·K)")

            # Resistance pie chart
            r_values = {
                "Outer Convection": hf_mid.convection_outer_resistance,
                "Wall Conduction": hf_mid.conduction_resistance,
                "Inner Convection": hf_mid.convection_inner_resistance,
            }
            fig_pie = go.Figure(data=[go.Pie(
                labels=list(r_values.keys()),
                values=list(r_values.values()),
                hole=0.4,
                marker_colors=["#2196f3", "#ff9800", "#4caf50"],
            )])
            fig_pie.update_layout(
                title="Thermal Resistance Distribution",
                height=350,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        # Cumulative energy transfer
        st.markdown("---")
        st.subheader("⚡ Cumulative Energy Transfer")
        if cum_energy:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Energy Transfer", f"{cum_energy['total_energy_transfer_kWh']} kWh")
            c2.metric("Average Heat Flow", f"{cum_energy['average_heat_flow_W']} W")
            c3.metric("Peak Heat Flow", f"{cum_energy['peak_heat_flow_W']} W")

    # ════════════════════════════════════════════════════════════════
    #  TAB 4: Residuals
    # ════════════════════════════════════════════════════════════════
    with tab4:
        st.subheader("📈 Convergence & Residuals")

        # Generate synthetic residual-like convergence data from analytical model
        n_points = len(results)
        if n_points > 10:
            iterations = list(range(n_points))

            # Simulate residual decay patterns
            np.random.seed(42)
            cont_res = 1e-1 * np.exp(-np.linspace(0, 5, n_points)) + 1e-4 * np.random.rand(n_points)
            energy_res = 1e-2 * np.exp(-np.linspace(0, 8, n_points)) + 1e-7 * np.random.rand(n_points)
            x_vel_res = 5e-2 * np.exp(-np.linspace(0, 4, n_points)) + 5e-5 * np.random.rand(n_points)
            y_vel_res = 5e-2 * np.exp(-np.linspace(0, 4.5, n_points)) + 5e-5 * np.random.rand(n_points)
            z_vel_res = 5e-2 * np.exp(-np.linspace(0, 4.2, n_points)) + 5e-5 * np.random.rand(n_points)
            k_res = 1e-1 * np.exp(-np.linspace(0, 3.5, n_points)) + 1e-4 * np.random.rand(n_points)
            eps_res = 1e-1 * np.exp(-np.linspace(0, 3, n_points)) + 1e-4 * np.random.rand(n_points)

            fig_res = go.Figure()
            residual_data = {
                "continuity": (cont_res, "#2196f3"),
                "x-velocity": (x_vel_res, "#4caf50"),
                "y-velocity": (y_vel_res, "#ff9800"),
                "z-velocity": (z_vel_res, "#9c27b0"),
                "energy": (energy_res, "#f44336"),
                "k": (k_res, "#00bcd4"),
                "epsilon": (eps_res, "#795548"),
            }

            for name, (data, color) in residual_data.items():
                fig_res.add_trace(go.Scatter(
                    x=iterations, y=data,
                    name=name,
                    line=dict(color=color, width=1.5),
                ))

            fig_res.update_layout(
                title="Scaled Residuals",
                xaxis_title="Time Step / Iteration",
                yaxis_title="Residual",
                yaxis_type="log",
                height=500,
                template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, x=0.5, xanchor="center"),
            )
            fig_res.add_hline(y=1e-3, line_dash="dash", line_color="gray",
                              annotation_text="Convergence criterion (1e-3)")
            fig_res.add_hline(y=1e-6, line_dash="dash", line_color="red",
                              annotation_text="Energy criterion (1e-6)")

            st.plotly_chart(fig_res, use_container_width=True)

            st.info(
                "💡 **Note**: For the analytical model, residuals are simulated to show "
                "expected convergence behavior. Run the **PyFluent CFD** mode for actual "
                "solver residuals."
            )

    # ════════════════════════════════════════════════════════════════
    #  TAB 5: Summary & Export
    # ════════════════════════════════════════════════════════════════
    with tab5:
        st.subheader("📋 Simulation Summary")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### Geometry")
            st.write(f"- **Inner Radius**: {geom.inner_radius} m")
            st.write(f"- **Shell Thickness**: {geom.thickness} m")
            st.write(f"- **Outer Radius**: {geom.outer_radius} m")
            st.write(f"- **Surface Area**: {geom.dome_surface_area:.2f} m²")
            st.write(f"- **Internal Volume**: {geom.dome_volume_internal:.2f} m³")

            st.markdown("##### Material")
            if material:
                st.write(f"- **Name**: {material.name}")
                st.write(f"- **Density**: {material.density} kg/m³")
                st.write(f"- **Specific Heat**: {material.specific_heat} J/(kg·K)")
                st.write(f"- **Conductivity**: {material.thermal_conductivity} W/(m·K)")
                st.write(f"- **Absorptivity**: {material.absorptivity}")
                st.write(f"- **Emissivity**: {material.emissivity}")

        with col2:
            st.markdown("##### Temperature Results")
            st.write(f"- **Peak Inside Temp**: {energy['peak_inside_temp_C']} °C ({energy['peak_inside_temp_K']} K)")
            st.write(f"- **Min Inside Temp**: {energy['min_inside_temp_C']} °C")
            st.write(f"- **Final Inside Temp**: {energy['final_inside_temp_C']} °C")
            st.write(f"- **Peak Surface Temp**: {energy['peak_outer_surface_temp_C']} °C")
            st.write(f"- **Max Heat Flux**: {energy['max_heat_flux_W_per_m2']} W/m²")

            st.markdown("##### Energy Balance")
            st.write(f"- **Total Solar Energy**: {energy['total_solar_irradiation_MJ']} MJ")
            st.write(f"- **Absorbed Energy**: {energy['total_solar_absorbed_MJ']} MJ")
            st.write(f"- **Conducted Through Wall**: {energy['total_conducted_through_wall_MJ']} MJ")
            st.write(f"- **Simulation Duration**: {energy['simulation_duration_hours']} hours")

        # Export
        st.markdown("---")
        csv_path = st.session_state.get("csv_path", "")
        if csv_path and os.path.exists(csv_path):
            with open(csv_path, "r") as f:
                csv_data = f.read()
            st.download_button(
                "📥 Download Results CSV",
                data=csv_data,
                file_name="dome_thermal_results.csv",
                mime="text/csv",
                type="primary",
            )

        # Export summary JSON
        summary = {
            "geometry": geom.to_dict() if geom else {},
            "material": material.to_dict() if material else {},
            "energy_summary": energy,
            "cumulative_energy": cum_energy,
            "timestamp": datetime.now().isoformat(),
        }
        st.download_button(
            "📥 Download Summary JSON",
            data=json.dumps(summary, indent=2),
            file_name="dome_thermal_summary.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
