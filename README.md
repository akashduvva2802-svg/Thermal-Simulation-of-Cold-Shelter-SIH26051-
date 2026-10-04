# ThermaCore: Automated Software Model for On-Demand PCM Shelter Design

![SIH2026](https://img.shields.io/badge/Smart_India_Hackathon-SIH26051-orange?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-red?style=for-the-badge)
![Ansys](https://img.shields.io/badge/Ansys-PyFluent-yellow?style=for-the-badge)

**Problem Statement:** SIH26051 - *Software Based Model Development for Design of Area Specific Shelter for Thermal Comfort Maintenance.*  
**Team:** Elite Exchangers

---

## 📖 Project Overview
Designing thermal shelters for extreme, high-altitude climates like Ladakh currently relies on manual, expert-driven CFD modeling or highly inefficient sensible heat structures. **ThermaCore** is a full-stack, AI-integrated software model that completely automates the design, simulation, and business analysis of area-specific passive shelters. 

Our application abstracts the complexity of computational fluid dynamics (CFD) by utilizing an **Ansys PyFluent backend** wrapped in a **Streamlit web interface**. It parametrically optimizes Phase Change Material (PCM) deployment, geometric shapes, and optical properties to ensure a zero-fossil-fuel, self-sustaining thermal environment.

---

## 🚀 Key Innovations & Engineering Domains

### 1. Mechanical & Chemical Engineering (Material Science)
*   **Sodium Acetate Trihydrate (SAT):** We engineered an inorganic PCM envelope housed in modular **Aluminum cartridges** (solving corrosion and low thermal conductivity).
*   **Chemical Stabilization:** The software models the integration of **Borax** (nucleating agent) and **CMC** (thickening agent) to prevent phase segregation and nucleation failure.
*   **On-Demand Heat (Supercooling):** Simulates the integration of a **Piezoelectric trigger**, utilizing the supercooling property of SAT to release massive latent heat strictly on-demand at critical nighttime hours.
*   **Advanced Optics:** Employs the **Discrete Ordinates (DO) Radiation Model** to account for wavelength-dependent emissivity/absorptivity of specific exterior and interior shelter coatings.

### 2. Computer Science & Automation (The Software)
*   **PyFluent Backend:** Fully automated Watertight Geometry meshing (Poly-hexcore), initialization, and execution of the **Ansys Solidification and Melting Model** with $k-\omega$ SST turbulence.
*   **Live Residual & Profile Monitoring:** An integrated dashboard that actively extracts PyFluent event callbacks, allowing engineers to track solver convergence, heat flux, and transient temperature profiles in real-time.
*   **Real-Time Data Integration:** Parses live meteorological data (ERA5) for dynamic boundary condition generation (solar irradiance, ambient temps, wind vectors).

### 3. Industrial Deployment & Market Analytics
The software features dynamic demographic targeting and trade-off analytics:
*   **Soldiers & Border Personnel:** Optimizes for double-skin insulated envelopes (minimized U-value) to completely neutralize cold stress in high-altitude deployments.
*   **Local Families & Nomads:** Evaluates Earth-wall hybrid shelters with localized ventilation to maintain Indoor Air Quality (IAQ) alongside PCM implementation.
*   **Trekkers & Disaster Relief:** Optimizes for foldable frame shelters, sacrificing thermal mass for rapid deployment.
*   **Parametric Trade-off Analysis:** Plots the Pareto frontier balancing Thermal Efficiency (e.g., Ovoid geometry) vs. Deployability (e.g., Quonset flat-pack integration).
*   **Energy Savings & ROI:** Mathematically calculates the offset of kerosene fuel (replacing dangerous 'Bukhari' braziers), validating the economic footprint based on capacity and land coverage.

---

## 📂 Repository Structure

```text
dome_thermal_sim/
│
├── app.py                     # Main Streamlit Frontend Application
├── requirements.txt           # Python dependencies
├── core/                      # Core simulation scripts
│   ├── dome_full_sim.py       # PyFluent automation script (Solidification/Melting)
│   └── physics_setup.py       # DO Radiation and Material property definitions
├── ui/                        # Streamlit dashboard components
│   └── live_monitoring.py     # Live residual and profile tracking plots
├── geometry/                  # CAD and geometric boundary profiles
└── results/                   # Output CSVs, transient data, and trade-off analytics
```

---

## ⚙️ Installation & Usage

### Prerequisites
*   Python 3.10 or 3.11
*   Ansys Fluent (Student or Enterprise license configured in PATH)

### Setup Instructions
1. Clone the repository and navigate to the project folder:
   ```bash
   cd dome_thermal_sim
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the ThermaCore application:
   ```bash
   streamlit run app.py
   ```

### Workflow
1. **Input Parameters:** Open the web UI and input GPS coordinates, target demographic, and shelter capacity.
2. **Automated Simulation:** The software fetches ERA5 weather data and silently triggers the Ansys PyFluent solver.
3. **Live Monitoring:** Watch the CFD residuals and internal temperature predictions generate in real-time.
4. **Decision Dashboard:** Review the generated trade-off analytics, ROI, and optimized PCM mass required for the specified location.
