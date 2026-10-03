import streamlit as st
import os
import time
import subprocess
from PIL import Image

st.set_page_config(page_title="Dome Thermal Simulation", layout="wide")

st.title("Hemisphere Dome Thermal PyFluent Simulation")
st.markdown("""
This application runs a full end-to-end PyFluent Thermal Simulation for the Dome.
It generates the STL, meshes the geometry, configures the physics matching **Trial1_hemisphere**, solves the transient model, and plots the results!
""")

WORK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation_final")
PLOT_PATH = os.path.join(WORK_DIR, "final_results.png")
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dome_full_sim.py")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Controls")
    if st.button("Run Full PyFluent Simulation", type="primary"):
        st.info("Starting PyFluent Pipeline... (Check terminal for real-time logs)")
        
        with st.spinner("Running Geometry Generation, Meshing, and Solver via PyFluent... This may take several minutes."):
            process = subprocess.Popen(
                ["python", SCRIPT_PATH],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Simple wait (in a real app we'd stream logs to the UI)
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                st.success("Simulation Completed Successfully!")
            else:
                st.error("Simulation failed or exited with errors.")
                st.code(stderr)
                
with col2:
    st.header("Results")
    if os.path.exists(PLOT_PATH):
        st.image(Image.open(PLOT_PATH), caption="PyFluent Thermal Simulation Results")
    else:
        st.info("Results will appear here after the simulation finishes.")
