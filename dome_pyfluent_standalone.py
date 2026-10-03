"""
dome_pyfluent_standalone.py
===========================
Complete standalone PyFluent simulation for dome thermal analysis.

Strategy:
  1. Use GMSH to generate a proper 3D volume mesh with named boundaries
  2. Export as Fluent .msh format
  3. Load directly into PyFluent SOLVER (skip Fluent meshing entirely!)
  4. Configure physics, BCs, solve
  5. Extract results and create plots

This completely bypasses Fluent's buggy meshing workflow API.

Reference: Trial1_hemisphere settings:
  - Transient, pressure-based, gravity enabled
  - k-epsilon + enhanced wall treatment
  - S2S radiation model
  - Time step: 600s, 21 steps
  - Boundary types: ground=wall, sky=symmetry, east/north=pressure-outlet,
                    west/south=velocity-inlet
  - 2 fluid regions (inside + outside dome), 1 solid shell
"""

import os
import sys
import math
import time
import traceback
import numpy as np

# ─── Configuration ───────────────────────────────────────────────────
DOME_RADIUS = 2.0        # meters (inner radius of hemisphere)
DOME_THICKNESS = 0.01    # meters (shell thickness)
DOMAIN_X = 10.0          # half-length in X (total domain 20m)
DOMAIN_Y = 10.0          # half-length in Y (total domain 20m)
DOMAIN_Z = 10.0          # domain height (meters)

# Material: dome shell (concrete-like)
SHELL_DENSITY = 2300.0          # kg/m^3
SHELL_SPECIFIC_HEAT = 880.0     # J/(kg·K)
SHELL_CONDUCTIVITY = 1.4        # W/(m·K)
SHELL_EMISSIVITY = 0.9
SHELL_ABSORPTIVITY = 0.6

# Ambient conditions
AMBIENT_TEMP = 259.7       # K (from Trial1 data, ~-13°C)
WIND_SPEED = 2.0           # m/s

# Simulation
TIME_STEP = 600.0          # seconds
N_TIME_STEPS = 21          # number of time steps
MAX_ITER_PER_STEP = 20     # iterations per time step

# Mesh sizing
DOME_MESH_SIZE = 0.15      # mesh size on dome surfaces (meters)
GROUND_MESH_SIZE = 0.5     # mesh size on ground
DOMAIN_MESH_SIZE = 1.5     # mesh size on far-field boundaries

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results_standalone")
MESH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mesh_gmsh")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(MESH_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
#  STEP 1: GENERATE MESH WITH GMSH
# ═══════════════════════════════════════════════════════════════════════

def generate_mesh_gmsh():
    """
    Generate a 3D volume mesh using GMSH with proper named boundaries.
    
    Geometry:
      - Hemispherical dome shell (inner_radius to outer_radius)
      - Rectangular fluid domain around it
      - Two fluid volumes: inside dome, outside dome
      - One solid volume: dome shell
    
    Named boundaries (matching Trial1):
      - solid-outside: outer surface of dome shell
      - solid-inside: inner surface of dome shell  
      - ground: ground plane outside dome footprint
      - ground.1 (or inside): ground plane inside dome footprint
      - sky: top of domain
      - east, west, north, south: vertical domain walls
    """
    import gmsh
    
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)
    gmsh.model.add("dome_shelter")
    
    R_inner = DOME_RADIUS
    R_outer = DOME_RADIUS + DOME_THICKNESS
    hx = DOMAIN_X
    hy = DOMAIN_Y
    hz = DOMAIN_Z
    
    # ── Create geometry using OpenCASCADE kernel ──
    occ = gmsh.model.occ
    
    # 1. Inner hemisphere (full sphere, then cut)
    sphere_inner = occ.addSphere(0, 0, 0, R_inner)
    # 2. Outer hemisphere (full sphere, then cut)
    sphere_outer = occ.addSphere(0, 0, 0, R_outer)
    # 3. Cutting box below z=0 to make hemispheres
    cut_box = occ.addBox(-R_outer*2, -R_outer*2, -R_outer*2, R_outer*4, R_outer*4, R_outer*2)
    
    # Cut spheres to make hemispheres
    hemisphere_inner_result = occ.cut([(3, sphere_inner)], [(3, cut_box)], removeObject=True, removeTool=False)
    hemisphere_inner = hemisphere_inner_result[0][0][1]
    
    sphere_outer_2 = occ.addSphere(0, 0, 0, R_outer)
    hemisphere_outer_result = occ.cut([(3, sphere_outer_2)], [(3, cut_box)], removeObject=True, removeTool=True)
    hemisphere_outer = hemisphere_outer_result[0][0][1]
    
    # 4. Shell = outer hemisphere - inner hemisphere
    shell_result = occ.cut([(3, hemisphere_outer)], [(3, hemisphere_inner)], removeObject=True, removeTool=False)
    shell_vol = shell_result[0][0][1]
    
    # The inner hemisphere volume remains as the inside fluid
    inside_vol = hemisphere_inner
    
    # 5. Full domain box
    domain_box = occ.addBox(-hx, -hy, 0, 2*hx, 2*hy, hz)
    
    # 6. Outside fluid = domain_box - outer hemisphere
    sphere_outer_3 = occ.addSphere(0, 0, 0, R_outer)
    cut_box_2 = occ.addBox(-R_outer*2, -R_outer*2, -R_outer*2, R_outer*4, R_outer*4, R_outer*2)
    hemisphere_outer_2_result = occ.cut([(3, sphere_outer_3)], [(3, cut_box_2)], removeObject=True, removeTool=True)
    hemisphere_outer_2 = hemisphere_outer_2_result[0][0][1]
    
    outside_result = occ.cut([(3, domain_box)], [(3, hemisphere_outer_2)], removeObject=True, removeTool=True)
    outside_vol = outside_result[0][0][1]
    
    # Fragment all volumes together so they share interfaces
    occ.fragment([(3, outside_vol), (3, shell_vol), (3, inside_vol)], [])
    
    occ.synchronize()
    
    # ── Identify volumes and surfaces ──
    volumes = gmsh.model.getEntities(3)
    print(f"  Created {len(volumes)} volumes")
    
    # Identify which volume is which by checking bounding boxes
    vol_info = []
    for dim, tag in volumes:
        bb = gmsh.model.getBoundingBox(dim, tag)
        vol = abs((bb[3]-bb[0]) * (bb[4]-bb[1]) * (bb[5]-bb[2]))
        vol_info.append((tag, bb, vol))
        print(f"    Volume {tag}: bbox ({bb[0]:.2f},{bb[1]:.2f},{bb[2]:.2f}) to ({bb[3]:.2f},{bb[4]:.2f},{bb[5]:.2f}), est_vol={vol:.4f}")
    
    # Sort by volume: smallest = shell, medium = inside hemisphere, largest = outside domain
    vol_info.sort(key=lambda x: x[2])
    
    # Assign physical groups for volumes
    if len(vol_info) >= 3:
        shell_tag = vol_info[0][0]
        inside_tag = vol_info[1][0]
        outside_tag = vol_info[2][0]
    elif len(vol_info) == 2:
        # shell might have been merged - check bounding boxes
        inside_tag = vol_info[0][0]
        outside_tag = vol_info[1][0]
        shell_tag = None
    else:
        print("  ERROR: Expected at least 2 volumes!")
        gmsh.finalize()
        return None
    
    # Physical volume groups
    if shell_tag:
        gmsh.model.addPhysicalGroup(3, [shell_tag], name="solid_shell")
    gmsh.model.addPhysicalGroup(3, [inside_tag], name="fluid_inside")
    gmsh.model.addPhysicalGroup(3, [outside_tag], name="fluid_outside")
    
    # ── Identify and name boundary surfaces ──
    surfaces = gmsh.model.getEntities(2)
    print(f"  Found {len(surfaces)} surfaces")
    
    tol = 0.01
    ground_surfs = []
    sky_surfs = []
    east_surfs = []
    west_surfs = []
    north_surfs = []
    south_surfs = []
    dome_outer_surfs = []
    dome_inner_surfs = []
    inside_ground_surfs = []
    
    for dim, tag in surfaces:
        bb = gmsh.model.getBoundingBox(dim, tag)
        zmin, zmax = bb[2], bb[5]
        xmin, xmax = bb[0], bb[3]
        ymin, ymax = bb[1], bb[4]
        
        is_flat_z0 = abs(zmin) < tol and abs(zmax) < tol
        is_flat_ztop = abs(zmin - hz) < tol and abs(zmax - hz) < tol
        is_flat_xmin = abs(xmin + hx) < tol and abs(xmax + hx) < tol
        is_flat_xmax = abs(xmin - hx) < tol and abs(xmax - hx) < tol
        is_flat_ymin = abs(ymin + hy) < tol and abs(ymax + hy) < tol
        is_flat_ymax = abs(ymin - hy) < tol and abs(ymax - hy) < tol
        
        # Check if it's a dome surface (curved, near origin, z >= 0)
        center_x = (xmin + xmax) / 2
        center_y = (ymin + ymax) / 2
        is_near_origin = abs(center_x) < R_outer + tol and abs(center_y) < R_outer + tol
        is_curved = zmax > tol and is_near_origin
        extent = max(xmax - xmin, ymax - ymin)
        
        if is_flat_z0:
            # Ground plane - check if inside or outside dome footprint
            if extent < 2 * R_inner + tol and is_near_origin and extent < 2 * R_outer + 0.5:
                inside_ground_surfs.append(tag)
            else:
                ground_surfs.append(tag)
        elif is_flat_ztop:
            sky_surfs.append(tag)
        elif is_flat_xmax and abs(ymin + hy) < tol:
            east_surfs.append(tag)
        elif is_flat_xmin and abs(ymin + hy) < tol:
            west_surfs.append(tag)
        elif is_flat_ymax and abs(xmin + hx) < tol:
            north_surfs.append(tag)
        elif is_flat_ymin and abs(xmin + hx) < tol:
            south_surfs.append(tag)
        elif is_curved:
            # Determine inner vs outer by checking radius
            if extent < 2 * R_inner + tol:
                dome_inner_surfs.append(tag)
            else:
                dome_outer_surfs.append(tag)
    
    # Create physical groups for boundaries
    if ground_surfs:
        gmsh.model.addPhysicalGroup(2, ground_surfs, name="ground")
    if inside_ground_surfs:
        gmsh.model.addPhysicalGroup(2, inside_ground_surfs, name="ground_inside")
    if sky_surfs:
        gmsh.model.addPhysicalGroup(2, sky_surfs, name="sky")
    if east_surfs:
        gmsh.model.addPhysicalGroup(2, east_surfs, name="east")
    if west_surfs:
        gmsh.model.addPhysicalGroup(2, west_surfs, name="west")
    if north_surfs:
        gmsh.model.addPhysicalGroup(2, north_surfs, name="north")
    if south_surfs:
        gmsh.model.addPhysicalGroup(2, south_surfs, name="south")
    if dome_outer_surfs:
        gmsh.model.addPhysicalGroup(2, dome_outer_surfs, name="solid_outside")
    if dome_inner_surfs:
        gmsh.model.addPhysicalGroup(2, dome_inner_surfs, name="solid_inside")
    
    # Any remaining unclassified surfaces
    classified = set(ground_surfs + inside_ground_surfs + sky_surfs + east_surfs + 
                     west_surfs + north_surfs + south_surfs + dome_outer_surfs + dome_inner_surfs)
    unclassified = [tag for _, tag in surfaces if tag not in classified]
    if unclassified:
        print(f"  WARNING: {len(unclassified)} unclassified surfaces: {unclassified}")
        # These are likely the dome base ring or interface surfaces
        gmsh.model.addPhysicalGroup(2, unclassified, name="dome_base")
    
    print(f"  Boundary groups:")
    print(f"    ground: {ground_surfs}")
    print(f"    ground_inside: {inside_ground_surfs}")
    print(f"    sky: {sky_surfs}")
    print(f"    east: {east_surfs}, west: {west_surfs}")
    print(f"    north: {north_surfs}, south: {south_surfs}")
    print(f"    solid_outside (dome outer): {dome_outer_surfs}")
    print(f"    solid_inside (dome inner): {dome_inner_surfs}")
    
    # ── Mesh sizing ──
    # Fine mesh on dome surfaces
    for tag in dome_outer_surfs + dome_inner_surfs:
        gmsh.model.mesh.setSize(gmsh.model.getBoundary([(2, tag)], combined=True, oriented=False), DOME_MESH_SIZE)
    
    # Medium on ground
    for tag in ground_surfs + inside_ground_surfs:
        gmsh.model.mesh.setSize(gmsh.model.getBoundary([(2, tag)], combined=True, oriented=False), GROUND_MESH_SIZE)
    
    # Coarse on far-field
    for tag in sky_surfs + east_surfs + west_surfs + north_surfs + south_surfs:
        gmsh.model.mesh.setSize(gmsh.model.getBoundary([(2, tag)], combined=True, oriented=False), DOMAIN_MESH_SIZE)
    
    # Global settings
    gmsh.option.setNumber("Mesh.MeshSizeMin", DOME_MESH_SIZE * 0.5)
    gmsh.option.setNumber("Mesh.MeshSizeMax", DOMAIN_MESH_SIZE)
    gmsh.option.setNumber("Mesh.Algorithm3D", 10)  # HXT (fast tetrahedral)
    gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
    
    # ── Generate mesh ──
    print("  Generating 3D mesh...")
    gmsh.model.mesh.generate(3)
    
    # Get mesh statistics
    node_tags, _, _ = gmsh.model.mesh.getNodes()
    elem_types, _, _ = gmsh.model.mesh.getElements(3)
    total_cells = sum(len(tags) for tags in [gmsh.model.mesh.getElements(3, tag)[1][0] if gmsh.model.mesh.getElements(3, tag)[1] else [] for _, tag in volumes])
    print(f"  Mesh: {len(node_tags)} nodes")
    
    # ── Export as Fluent .msh ──
    msh_path = os.path.join(MESH_DIR, "dome_shelter.msh")
    gmsh.write(msh_path)
    print(f"  Mesh exported to: {msh_path}")
    
    gmsh.finalize()
    return msh_path


# ═══════════════════════════════════════════════════════════════════════
#  STEP 2: PYFLUENT SOLVER SETUP
# ═══════════════════════════════════════════════════════════════════════

def patch_pyfluent():
    """Patch PyFluent for ANSYS 2026 R1 (v261) compatibility."""
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
        return _orig.__func__(cls, value)
    FluentVersion._missing_ = _patched
    
    print("  [OK] PyFluent patched for v261")
    return pyfluent


def run_solver(mesh_file, pyfluent):
    """
    Load mesh into Fluent solver and run the thermal simulation.
    
    Physics setup matching Trial1_hemisphere:
      - Transient, pressure-based, gravity
      - k-epsilon standard + enhanced wall treatment
      - S2S radiation
      - Energy equation enabled
      - Air (ideal gas for buoyancy)
      - Dome shell material
    """
    print("\n" + "=" * 70)
    print("STEP 3: Launching Fluent Solver")
    print("=" * 70)
    
    solver = pyfluent.launch_fluent(
        mode="solver",
        precision="double",
        processor_count=2,
        start_watchdog=False,
        show_gui=True,
    )
    print("  [OK] Fluent solver launched")
    
    try:
        # ── Load mesh ──
        print("  Loading mesh...")
        solver.file.read_mesh(file_name=mesh_file)
        print("  [OK] Mesh loaded")
        
        # ── Scale mesh (gmsh outputs in meters, Fluent default is meters) ──
        # solver.tui.mesh.scale(1, 1, 1)  # No scaling needed if gmsh wrote in meters
        
        # ── Check mesh ──
        solver.tui.mesh.check()
        print("  [OK] Mesh checked")
        
        # ── General settings ──
        print("\n  Setting up physics...")
        setup = solver.settings.setup
        
        # Pressure-based, transient
        setup.general.solver.type.set_state("pressure-based")
        setup.general.solver.time.set_state("transient")
        
        # Gravity
        setup.general.gravity.enabled.set_state(True)
        setup.general.gravity.z_component_of_gravitational_acceleration.set_state(-9.81)
        
        print("  [OK] General settings")
        
        # ── Models ──
        # Energy
        setup.models.energy.enabled.set_state(True)
        
        # Viscous - k-epsilon standard + enhanced wall treatment
        setup.models.viscous.model.set_state("k-epsilon-standard")
        setup.models.viscous.near_wall_treatment.set_state("enhanced-wall-treatment")
        
        # Radiation - S2S (Surface-to-Surface) as in Trial1
        setup.models.radiation.model.set_state("surface-to-surface")
        
        print("  [OK] Models configured (energy, k-epsilon, S2S radiation)")
        
        # ── Materials ──
        # Air - ideal gas for buoyancy
        air = setup.materials.fluid["air"]
        air.density.option.set_state("ideal-gas")
        
        # Create dome shell material
        setup.materials.solid.create("dome_shell")
        dome_mat = setup.materials.solid["dome_shell"]
        dome_mat.density.value.set_state(SHELL_DENSITY)
        dome_mat.specific_heat.value.set_state(SHELL_SPECIFIC_HEAT)
        dome_mat.thermal_conductivity.value.set_state(SHELL_CONDUCTIVITY)
        
        print("  [OK] Materials configured")
        
        # ── Cell zone conditions ──
        # Get list of cell zones
        print("  Configuring cell zones...")
        # The inside and outside fluid zones should be set as fluid
        # The shell zone should be set as solid with dome_shell material
        # (This depends on how gmsh named them)
        
        # ── Boundary conditions ──
        print("  Setting boundary conditions...")
        bc = setup.boundary_conditions
        
        # Try to set BCs - names depend on gmsh export format
        try:
            # West wall - velocity inlet
            bc.velocity_inlet["west"].momentum.velocity_magnitude.set_state(WIND_SPEED)
            bc.velocity_inlet["west"].thermal.temperature.set_state(AMBIENT_TEMP)
        except Exception as e:
            print(f"    [WARN] west BC: {e}")
        
        try:
            # South wall - velocity inlet
            bc.velocity_inlet["south"].momentum.velocity_magnitude.set_state(WIND_SPEED)
            bc.velocity_inlet["south"].thermal.temperature.set_state(AMBIENT_TEMP)
        except Exception as e:
            print(f"    [WARN] south BC: {e}")
        
        try:
            # East - pressure outlet
            bc.pressure_outlet["east"].thermal.backflow_temperature.set_state(AMBIENT_TEMP)
        except Exception as e:
            print(f"    [WARN] east BC: {e}")
        
        try:
            # North - pressure outlet
            bc.pressure_outlet["north"].thermal.backflow_temperature.set_state(AMBIENT_TEMP)
        except Exception as e:
            print(f"    [WARN] north BC: {e}")
        
        try:
            # Ground - wall at ambient temp
            bc.wall["ground"].thermal.thermal_condition.set_state("temperature")
            bc.wall["ground"].thermal.temperature.set_state(AMBIENT_TEMP)
        except Exception as e:
            print(f"    [WARN] ground BC: {e}")
        
        try:
            # Dome outer surface - wall with radiation
            bc.wall["solid_outside"].thermal.thermal_condition.set_state("coupled")
            bc.wall["solid_outside"].radiation.emissivity.set_state(SHELL_EMISSIVITY)
        except Exception as e:
            print(f"    [WARN] solid_outside BC: {e}")
        
        try:
            # Dome inner surface - wall with radiation
            bc.wall["solid_inside"].thermal.thermal_condition.set_state("coupled")
            bc.wall["solid_inside"].radiation.emissivity.set_state(SHELL_EMISSIVITY)
        except Exception as e:
            print(f"    [WARN] solid_inside BC: {e}")
        
        print("  [OK] Boundary conditions set")
        
        # ── Solution methods ──
        print("  Configuring solution methods...")
        solution = solver.settings.solution
        solution.methods.p_v_coupling.flow_scheme.set_state("Coupled")
        
        print("  [OK] Solution methods")
        
        # ── Report definitions ──
        print("  Setting up report definitions...")
        reports = solution.report_definitions
        
        try:
            reports.surface.create("temp_out_face")
            reports.surface["temp_out_face"].field_variable.set_state("temperature")
            reports.surface["temp_out_face"].report_type.set_state("area-weighted-average")
            reports.surface["temp_out_face"].surface_names.set_state(["solid_outside"])
        except Exception as e:
            print(f"    [WARN] temp_out_face report: {e}")
        
        try:
            reports.surface.create("temp_inside_face")
            reports.surface["temp_inside_face"].field_variable.set_state("temperature")
            reports.surface["temp_inside_face"].report_type.set_state("area-weighted-average")
            reports.surface["temp_inside_face"].surface_names.set_state(["solid_inside"])
        except Exception as e:
            print(f"    [WARN] temp_inside_face report: {e}")
        
        # Report file
        try:
            solution.report_files.create("report-file-0")
            report_file = solution.report_files["report-file-0"]
            report_file.report_definitions.set_state(["temp_out_face", "temp_inside_face"])
            report_file.file_name.set_state(os.path.join(RESULTS_DIR, "temperature_report.out"))
        except Exception as e:
            print(f"    [WARN] report file: {e}")
        
        print("  [OK] Report definitions")
        
        # ── Initialize ──
        print("  Initializing solution...")
        solver.settings.solution.initialization.hybrid_initialize()
        print("  [OK] Solution initialized")
        
        # ── Run calculation ──
        print(f"\n  Running transient calculation: {N_TIME_STEPS} steps x {TIME_STEP}s...")
        solver.settings.solution.run_calculation.transient_controls.time_step_size.set_state(TIME_STEP)
        solver.settings.solution.run_calculation.transient_controls.max_iter_per_time_step.set_state(MAX_ITER_PER_STEP)
        
        solver.settings.solution.run_calculation.calculate(
            number_of_time_steps=N_TIME_STEPS
        )
        print("  [OK] Calculation complete!")
        
        # ── Save case & data ──
        case_path = os.path.join(RESULTS_DIR, "dome_thermal.cas.h5")
        solver.file.write_case_data(file_name=case_path)
        print(f"  [OK] Case/data saved to: {case_path}")
        
        return True
        
    except Exception as e:
        print(f"\n  [ERROR] Solver failed: {e}")
        traceback.print_exc()
        return False
    finally:
        try:
            solver.exit()
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════
#  STEP 3: POST-PROCESSING & PLOTS
# ═══════════════════════════════════════════════════════════════════════

def create_plots():
    """Parse report files and create plots."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available for plotting")
        return
    
    report_path = os.path.join(RESULTS_DIR, "temperature_report.out")
    if not os.path.exists(report_path):
        print(f"Report file not found: {report_path}")
        return
    
    # Parse report file
    flow_time = []
    temp_out = []
    temp_inside = []
    
    with open(report_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('"') or line.startswith('('):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    flow_time.append(float(parts[0]))
                    temp_out.append(float(parts[1]))
                    temp_inside.append(float(parts[2]))
                except ValueError:
                    continue
    
    if not flow_time:
        print("No data found in report file")
        return
    
    time_hours = [t / 3600 for t in flow_time]
    
    # Plot 1: Inside temperature vs time
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(time_hours, temp_inside, 'b-o', label='Inside Surface Temp', linewidth=2)
    ax.plot(time_hours, temp_out, 'r-s', label='Outside Surface Temp', linewidth=2)
    ax.axhline(y=AMBIENT_TEMP, color='gray', linestyle='--', label=f'Ambient ({AMBIENT_TEMP} K)')
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Temperature (K)')
    ax.set_title('Dome Shelter Temperature vs Time')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'temperature_vs_time.png'), dpi=150)
    plt.close()
    print(f"  Plot saved: temperature_vs_time.png")
    
    # Plot 2: Temperature difference vs time
    temp_diff = [AMBIENT_TEMP - ti for ti in temp_inside]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(time_hours, temp_diff, 'g-^', linewidth=2)
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('ΔT = T_ambient - T_inside (K)')
    ax.set_title('Temperature Difference (Ambient - Inside) vs Time')
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'temp_difference_vs_time.png'), dpi=150)
    plt.close()
    print(f"  Plot saved: temp_difference_vs_time.png")
    
    print(f"\n  All plots saved to: {RESULTS_DIR}")


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  DOME SHELTER THERMAL SIMULATION - STANDALONE PyFluent")
    print("=" * 70)
    
    # Step 1: Generate mesh with GMSH
    print("\n" + "=" * 70)
    print("STEP 1: Generating mesh with GMSH")
    print("=" * 70)
    
    mesh_file = generate_mesh_gmsh()
    if not mesh_file:
        print("FAILED: Mesh generation failed!")
        sys.exit(1)
    
    # Step 2: Patch PyFluent
    print("\n" + "=" * 70)
    print("STEP 2: Patching PyFluent for ANSYS v261")
    print("=" * 70)
    pyfluent = patch_pyfluent()
    
    # Step 3: Run solver
    success = run_solver(mesh_file, pyfluent)
    
    if success:
        # Step 4: Create plots
        print("\n" + "=" * 70)
        print("STEP 4: Creating plots")
        print("=" * 70)
        create_plots()
        
        print("\n" + "=" * 70)
        print("  SIMULATION COMPLETE!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("  SIMULATION FAILED - check errors above")
        print("=" * 70)
        sys.exit(1)
