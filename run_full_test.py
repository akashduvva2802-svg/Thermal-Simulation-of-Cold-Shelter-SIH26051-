"""
run_full_test.py
================
Standalone end-to-end PyFluent meshing + solver test.
Bypasses the Streamlit UI to verify the entire pipeline works.

Usage:
  "D:\ANSYS Inc\ANSYS Student\v261\commonfiles\CPython\3_10\winx64\Release\python\python.exe" run_full_test.py
"""

import os
import sys
import time
import traceback

# ─── Step 0: Patch PyFluent for ANSYS 2026 R1 (v261) ───────────────────
print("=" * 70)
print("STEP 0: Patching PyFluent for ANSYS 2026 R1 compatibility")
print("=" * 70)

os.environ["AWP_ROOT242"] = os.environ.get(
    "AWP_ROOT261", r"D:\ANSYS Inc\ANSYS Student\v261"
)
os.environ["AWP_ROOT241"] = os.environ["AWP_ROOT242"]

import ansys.fluent.core as pyfluent
from ansys.fluent.core.utils.fluent_version import FluentVersion

_orig = FluentVersion._missing_

@classmethod
def _patched(cls, value):
    if str(value).startswith("26"):
        return FluentVersion.v242
    return _orig.__get__(cls)(value)

FluentVersion._missing_ = _patched
print("  [OK] Version patch applied\n")

# ─── Step 1: Generate STL geometry ─────────────────────────────────────
print("=" * 70)
print("STEP 1: Generating dome STL geometry")
print("=" * 70)

sys.path.insert(0, os.path.dirname(__file__))
from test_stl_gen import generate_conformal_stl

stl_dir = os.path.join(os.path.dirname(__file__), "geometry", "generated")
os.makedirs(stl_dir, exist_ok=True)
stl_path = os.path.join(stl_dir, "test_conformal.stl")
generate_conformal_stl(2.0, 20.0, 60, 30, stl_path)
print(f"  [OK] STL written to: {stl_path}")
print(f"  File size: {os.path.getsize(stl_path):,} bytes\n")

# ─── Step 2: Launch Fluent Meshing ─────────────────────────────────────
print("=" * 70)
print("STEP 2: Launching Fluent in meshing mode")
print("=" * 70)

meshing = pyfluent.launch_fluent(
    mode="meshing",
    precision="double",
    processor_count=2,
    start_watchdog=False,
    show_gui=True,
)
print("  [OK] Fluent meshing session launched\n")

# ─── Step 3: Watertight Meshing Workflow ───────────────────────────────
print("=" * 70)
print("STEP 3: Watertight Geometry Meshing Workflow")
print("=" * 70)

workflow = meshing.workflow
workflow.InitializeWorkflow(WorkflowType="Watertight Geometry")
print("  [OK] Workflow initialized")

# 3a. Import Geometry (STL = Mesh format)
print("  3a. Importing geometry (Mesh format)...")
workflow.TaskObject["Import Geometry"].Arguments.set_state({
    "MeshFileName": stl_path,
    "MeshUnit": "m",
    "FileFormat": "Mesh",
    "AppendMesh": False,
})
workflow.TaskObject["Import Geometry"].Execute()
print("  [OK] Geometry imported\n")

# 3b. Add Local Sizing (Skipped for faster testing)
print("  3b. Skipping Local Sizing for faster test...")
# try:
#     workflow.TaskObject["Add Local Sizing"].Arguments.set_state({
#         "AddChild": "yes",
#         "BOIExecution": "Face Size",
#         "BOIFaceLabelList": ["dome_surf"],
#         "BOIGrowthRate": 1.35,
#         "BOISize": 0.05,
#         "BOIZoneorLabel": "label",
#     })
#     workflow.TaskObject["Add Local Sizing"].AddChildAndUpdate(
#         DeferUpdate=False, RetainValues=True
#     )
#     print("  [OK] Local sizing added\n")
# except Exception as e:
#     print(f"  [WARN] Local sizing with labels failed: {e}")
#     print("  Skipping local sizing (will use global defaults)\n")

# 3c. Generate Surface Mesh
print("  3c. Generating surface mesh...")
workflow.TaskObject["Generate the Surface Mesh"].Arguments.set_state({
    "CFDSurfaceMeshControls": {"MinSize": 0.1, "MaxSize": 1.0},
})
workflow.TaskObject["Generate the Surface Mesh"].Execute()
print("  [OK] Surface mesh generated\n")

# 3d. Describe Geometry
print("  3d. Describing geometry...")
workflow.TaskObject["Describe Geometry"].Arguments.set_state({
    "SetupType": "The geometry consists of only fluid regions with no voids",
    "CappingRequired": "No",
})
workflow.TaskObject["Describe Geometry"].Execute()
print("  [OK] Geometry described\n")

# 3e. Update Boundaries
print("  3e. Updating boundaries...")
workflow.TaskObject["Update Boundaries"].Arguments.set_state({
    "BoundaryLabelList": ["west", "south", "east", "ground_inside", "ground_outside", "north", "sky", "dome_surf"],
    "BoundaryLabelTypeList": [
        "velocity-inlet", "velocity-inlet", "pressure-outlet", 
        "wall", "wall", "pressure-outlet", "pressure-outlet", "wall"
    ],
})
workflow.TaskObject["Update Boundaries"].Execute()
print("  [OK] Boundaries updated\n")

# 3f. Update Regions
print("  3f. Updating regions...")
workflow.TaskObject["Create Regions"].Arguments.set_state({
    "NumberOfFlowVolumes": 2,
})
workflow.TaskObject["Create Regions"].Execute()
workflow.TaskObject["Update Regions"].Execute()
workflow.TaskObject["Update Regions"].Execute()
print("  [OK] Regions updated\n")

# 3g. Add Boundary Layers
print("  3g. Adding boundary layers...")
try:
    workflow.TaskObject["Add Boundary Layers"].Arguments.set_state({
        "NumberOfLayers": 5,
    })
    workflow.TaskObject["Add Boundary Layers"].AddChildAndUpdate(
        DeferUpdate=False, RetainValues=True
    )
    print("  [OK] Boundary layers added\n")
except Exception as e:
    print(f"  [WARN] Boundary layers failed: {e}")
    print("  Continuing without boundary layers\n")

# 3h. Generate Volume Mesh
print("  3h. Generating volume mesh...")
workflow.TaskObject["Generate the Volume Mesh"].Arguments.set_state({
    "VolumeFill": "poly-hexcore",
})
workflow.TaskObject["Generate the Volume Mesh"].Execute()
print("  [OK] Volume mesh generated!\n")

# ─── Step 4: Switch to Solver ──────────────────────────────────────────
print("=" * 70)
print("STEP 4: Switching to solver mode")
print("=" * 70)

solver = meshing.switch_to_solver()
print("  [OK] Switched to solver mode\n")

# ─── Step 5: Setup Physics ─────────────────────────────────────────────
print("=" * 70)
print("STEP 5: Setting up physics models")
print("=" * 70)

setup = solver.settings.setup

# 5a. General
print("  5a. General settings (pressure-based, transient)...")
setup.general.solver.type.set_state("pressure-based")
setup.general.solver.time.set_state("transient")
print("  [OK] General settings\n")

# 5b. Gravity
print("  5b. Enabling gravity...")
setup.general.gravity.enabled.set_state(True)
setup.general.gravity.x_component_of_gravitational_acceleration.set_state(0.0)
setup.general.gravity.y_component_of_gravitational_acceleration.set_state(0.0)
setup.general.gravity.z_component_of_gravitational_acceleration.set_state(-9.81)
print("  [OK] Gravity enabled (0, 0, -9.81)\n")

# 5c. Turbulence
print("  5c. Turbulence model (k-epsilon)...")
setup.models.viscous.model.set_state("k-epsilon-standard")
setup.models.viscous.near_wall_treatment.set_state("enhanced-wall-treatment")
print("  [OK] k-epsilon with enhanced wall treatment\n")

# 5d. Energy
print("  5d. Energy equation...")
setup.models.energy.enabled.set_state(True)
print("  [OK] Energy enabled\n")

# 5e. Radiation (DO with solar)
print("  5e. Radiation model (Discrete Ordinates + Solar)...")
try:
    setup.models.radiation.model.set_state("discrete-ordinates")
    setup.models.radiation.do.solar_irradiation.set_state(True)
    print("  [OK] DO + Solar radiation\n")
except Exception as e:
    print(f"  [WARN] Radiation setup: {e}")
    print("  Continuing without radiation model\n")

# ─── Step 6: Materials ─────────────────────────────────────────────────
print("=" * 70)
print("STEP 6: Setting up materials")
print("=" * 70)

# 6a. Air (ideal gas for buoyancy)
print("  6a. Air properties (ideal gas)...")
try:
    air = setup.materials.fluid["air"]
    air.density.option.set_state("ideal-gas")
    air.specific_heat.value.set_state(1006.43)
    air.thermal_conductivity.value.set_state(0.0242)
    air.viscosity.value.set_state(1.789e-5)
    print("  [OK] Air configured\n")
except Exception as e:
    print(f"  [WARN] Air setup: {e}\n")

# 6b. Shell material (mild steel)
print("  6b. Shell material (mild_steel)...")
try:
    setup.materials.solid.create("mild_steel")
    mat = setup.materials.solid["mild_steel"]
    mat.density.value.set_state(7850.0)
    mat.specific_heat.value.set_state(500.0)
    mat.thermal_conductivity.value.set_state(50.0)
    print("  [OK] mild_steel material created\n")
except Exception as e:
    print(f"  [WARN] Material setup: {e}\n")

# ─── Step 7: Boundary Conditions ───────────────────────────────────────
print("=" * 70)
print("STEP 7: Setting boundary conditions")
print("=" * 70)

# First, let's see what zones actually exist
print("  Discovering available zones...")
try:
    bc = setup.boundary_conditions
    vi_zones = list(bc.velocity_inlet.keys()) if hasattr(bc, 'velocity_inlet') else []
    po_zones = list(bc.pressure_outlet.keys()) if hasattr(bc, 'pressure_outlet') else []
    wall_zones = list(bc.wall.keys()) if hasattr(bc, 'wall') else []
    print(f"    velocity-inlet zones: {vi_zones}")
    print(f"    pressure-outlet zones: {po_zones}")
    print(f"    wall zones: {wall_zones}")
except Exception as e:
    print(f"  [WARN] Zone discovery: {e}")

ambient_temp = 300.0  # K
wind_speed = 2.0  # m/s

# Set BCs on whatever zones exist
for zone_name in vi_zones:
    try:
        inlet = bc.velocity_inlet[zone_name]
        inlet.momentum.velocity_magnitude.set_state(wind_speed)
        inlet.thermal.temperature.set_state(ambient_temp)
        print(f"  [OK] velocity-inlet: {zone_name}")
    except Exception as e:
        print(f"  [WARN] {zone_name}: {e}")

for zone_name in po_zones:
    try:
        outlet = bc.pressure_outlet[zone_name]
        outlet.thermal.backflow_total_temperature.set_state(ambient_temp)
        print(f"  [OK] pressure-outlet: {zone_name}")
    except Exception as e:
        print(f"  [WARN] {zone_name}: {e}")

for zone_name in wall_zones:
    try:
        wall = bc.wall[zone_name]
        wall.thermal.thermal_bc.set_state("Temperature")
        wall.thermal.temperature.set_state(ambient_temp)
        print(f"  [OK] wall (T={ambient_temp}K): {zone_name}")
    except Exception as e:
        print(f"  [WARN] {zone_name}: {e}")

print()

# ─── Step 8: Solution Methods ──────────────────────────────────────────
print("=" * 70)
print("STEP 8: Solution methods")
print("=" * 70)

try:
    solution = solver.settings.solution
    solution.methods.p_v_coupling.flow_scheme.set_state("SIMPLE")
    print("  [OK] SIMPLE scheme")
except Exception as e:
    print(f"  [WARN] Solution methods: {e}")
print()

# ─── Step 9: Initialize ────────────────────────────────────────────────
print("=" * 70)
print("STEP 9: Initializing solution")
print("=" * 70)

try:
    solver.settings.solution.initialization.initialize(
        method="hybrid-initialization"
    )
    print("  [OK] Hybrid initialization complete\n")
except Exception as e:
    print(f"  [WARN] Hybrid init failed: {e}")
    try:
        solver.settings.solution.initialization.initialize(
            method="standard-initialization"
        )
        print("  [OK] Standard initialization complete\n")
    except Exception as e2:
        print(f"  [ERROR] All initialization failed: {e2}\n")

# ─── Step 10: Run 5 time steps (test) ─────────────────────────────────
print("=" * 70)
print("STEP 10: Running 5 test time steps (dt=1.0s)")
print("=" * 70)

try:
    calc = solver.settings.solution.run_calculation
    calc.transient_controls.time_step_size.set_state(1.0)
    calc.transient_controls.max_iterations_per_time_step.set_state(20)
    calc.dual_time_iterate(
        number_of_time_steps=5,
        max_iterations_per_time_step=20,
    )
    print("  [OK] 5 time steps completed!\n")
except Exception as e:
    print(f"  [ERROR] Calculation failed: {e}\n")

# ─── Step 11: Save ─────────────────────────────────────────────────────
print("=" * 70)
print("STEP 11: Saving case & data")
print("=" * 70)

results_dir = os.path.join(os.path.dirname(__file__), "results", "test_run")
os.makedirs(results_dir, exist_ok=True)
case_path = os.path.join(results_dir, "dome_thermal_test.cas.h5")

try:
    solver.file.write_case_data(file_name=case_path)
    print(f"  [OK] Saved to: {case_path}\n")
except Exception as e:
    print(f"  [WARN] Save failed: {e}\n")

# ─── Cleanup ───────────────────────────────────────────────────────────
print("=" * 70)
print("STEP 12: Cleaning up")
print("=" * 70)

try:
    solver.exit()
    print("  [OK] Solver session closed\n")
except Exception as e:
    print(f"  [WARN] Close: {e}\n")

print("=" * 70)
print("TEST COMPLETE!")
print("=" * 70)
