import os
import sys
import math
import subprocess
import time
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# 1. PARAMETERS
# ==============================================================================
DOME_RADIUS = 2.0
DOMAIN_SIZE = 10.0
MESH_MIN_SIZE = 0.05
MESH_MAX_SIZE = 0.5
TIME_STEP = 600
N_TIME_STEPS = 21

WORK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation_run")
os.makedirs(WORK_DIR, exist_ok=True)

STL_PATH = os.path.join(WORK_DIR, "dome_geometry.stl")
MESH_PATH = os.path.join(WORK_DIR, "dome_mesh.msh.h5")
CASE_PATH = os.path.join(WORK_DIR, "dome_solved.cas.h5")

FLUENT_EXE = r"D:\ANSYS Inc\ANSYS Student\v261\fluent\ntbin\win64\fluent.exe"

# ==============================================================================
# 2. GENERATE CONFORMAL STL
# ==============================================================================
def generate_stl(R, domain_size, n_theta, n_phi, output_path):
    print("Generating conformal STL...")
    all_triangles = {
        "dome_surf": [],
        "ground_inside": [],
        "ground_outside": [],
        "west": [],
        "east": [],
        "south": [],
        "north": [],
        "sky": []
    }
    
    def compute_normal(v1, v2, v3):
        ux, uy, uz = v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]
        vx, vy, vz = v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2]
        nx, ny, nz = uy*vz - uz*vy, uz*vx - ux*vz, ux*vy - uy*vx
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length > 0: return (nx/length, ny/length, nz/length)
        return (0,0,1)

    theta = np.linspace(0, 2*np.pi, n_theta, endpoint=False)
    phi = np.linspace(0, np.pi/2, n_phi)
    
    # 1. Dome Surface
    for i in range(n_phi - 1):
        for j in range(n_theta):
            t1, t2 = theta[j], theta[(j+1)%n_theta]
            p1, p2 = phi[i], phi[i+1]
            
            v1 = (R*math.sin(p1)*math.cos(t1), R*math.sin(p1)*math.sin(t1), R*math.cos(p1))
            v2 = (R*math.sin(p1)*math.cos(t2), R*math.sin(p1)*math.sin(t2), R*math.cos(p1))
            v3 = (R*math.sin(p2)*math.cos(t1), R*math.sin(p2)*math.sin(t1), R*math.cos(p2))
            v4 = (R*math.sin(p2)*math.cos(t2), R*math.sin(p2)*math.sin(t2), R*math.cos(p2))
            
            all_triangles["dome_surf"].append((compute_normal(v1, v2, v3), v1, v2, v3))
            all_triangles["dome_surf"].append((compute_normal(v3, v2, v4), v3, v2, v4))

    # 2. Ground inside
    for j in range(n_theta):
        t1, t2 = theta[j], theta[(j+1)%n_theta]
        v1 = (0, 0, 0)
        v2 = (R*math.cos(t2), R*math.sin(t2), 0)
        v3 = (R*math.cos(t1), R*math.sin(t1), 0)
        all_triangles["ground_inside"].append((compute_normal(v1, v2, v3), v1, v2, v3))

    # 3. Ground outside
    L = domain_size / 2.0
    corners = [(L, L, 0), (-L, L, 0), (-L, -L, 0), (L, -L, 0)]
    for j in range(n_theta):
        t1, t2 = theta[j], theta[(j+1)%n_theta]
        v_inner1 = (R*math.cos(t1), R*math.sin(t1), 0)
        v_inner2 = (R*math.cos(t2), R*math.sin(t2), 0)
        
        c1_idx = int((t1 + np.pi/4) / (np.pi/2)) % 4
        c2_idx = int((t2 + np.pi/4) / (np.pi/2)) % 4
        
        v_outer1 = corners[c1_idx]
        v_outer2 = corners[c2_idx]
        
        if c1_idx == c2_idx:
            all_triangles["ground_outside"].append((compute_normal(v_inner1, v_inner2, v_outer1), v_inner1, v_inner2, v_outer1))
        else:
            all_triangles["ground_outside"].append((compute_normal(v_inner1, v_inner2, v_outer1), v_inner1, v_inner2, v_outer1))
            all_triangles["ground_outside"].append((compute_normal(v_inner2, v_outer2, v_outer1), v_inner2, v_outer2, v_outer1))

    # 4. Domain walls
    H = domain_size / 2.0
    walls = [
        ("east",  (L, L, 0), (L, -L, 0), (L, -L, H), (L, L, H)),
        ("west",  (-L, -L, 0), (-L, L, 0), (-L, L, H), (-L, -L, H)),
        ("north", (-L, L, 0), (L, L, 0), (L, L, H), (-L, L, H)),
        ("south", (L, -L, 0), (-L, -L, 0), (-L, -L, H), (L, -L, H)),
        ("sky",   (-L, -L, H), (L, -L, H), (L, L, H), (-L, L, H))
    ]
    
    for name, v1, v2, v3, v4 in walls:
        all_triangles[name].append((compute_normal(v1, v2, v3), v1, v2, v3))
        all_triangles[name].append((compute_normal(v1, v3, v4), v1, v3, v4))

    with open(output_path, "w") as f:
        for solid_name, tris in all_triangles.items():
            if not tris: continue
            f.write(f"solid {solid_name}\n")
            for normal, v1, v2, v3 in tris:
                f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
                f.write("    outer loop\n")
                f.write(f"      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}\n")
                f.write(f"      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}\n")
                f.write(f"      vertex {v3[0]:.6e} {v3[1]:.6e} {v3[2]:.6e}\n")
                f.write("    endloop\n")
                f.write("  endfacet\n")
            f.write(f"endsolid {solid_name}\n")
            
    print(f"[OK] STL written to {output_path}")

# ==============================================================================
# 3. MESHING SCRIPT
# ==============================================================================
def run_meshing():
    journal_path = os.path.join(WORK_DIR, "meshing.jou")
    stl_path_f = STL_PATH.replace("\\", "/")
    mesh_path_f = MESH_PATH.replace("\\", "/")
    
    # Use Native Fluent Meshing TUI commands to completely avoid Watertight Geometry bugs
    journal = f"""
/file/import/cad "yes" "{stl_path_f}" "yes" "m" "yes"
/mesh/surface-mesh/create "yes" "*" "{MESH_MAX_SIZE}" "{MESH_MIN_SIZE}"
/mesh/auto-mesh "*" "yes" "poly-hexcore" "yes"
/file/write-mesh "{mesh_path_f}"
/exit
"""
    with open(journal_path, "w") as f:
        f.write(journal)
        
    print(f"Running Fluent Meshing (with GUI) from: {journal_path}")
    # Run with GUI to avoid Student License batch mode restriction!
    cmd = f'"{FLUENT_EXE}" 3ddp -t2 -meshing -wait -i "{journal_path}"'
    
    with open(os.path.join(WORK_DIR, "meshing.log"), "w") as log:
        process = subprocess.Popen(cmd, stdout=log, stderr=log, shell=True)
        process.wait()
        
    if os.path.exists(MESH_PATH):
        print("[OK] Mesh successfully created!")
    else:
        print("[ERROR] Mesh generation failed. See meshing.log")
        sys.exit(1)

# ==============================================================================
# 4. SOLVER SCRIPT
# ==============================================================================
def run_solver():
    journal_path = os.path.join(WORK_DIR, "solver.jou")
    mesh_path_f = MESH_PATH.replace("\\", "/")
    case_path_f = CASE_PATH.replace("\\", "/")
    report_file_f = os.path.join(WORK_DIR, "report-file.out").replace("\\", "/")
    
    journal = f"""
/file/read-mesh "{mesh_path_f}"

; General Settings
/define/models/solver/density-based-implicit? "no"
/define/models/solver/pressure-based? "yes"
/define/models/unsteady-1st-order? "yes"
/define/operating-conditions/gravity "yes" 0 0 -9.81

; Models
/define/models/energy? "yes"
/define/models/viscous/kw-sst? "yes"
/define/models/radiation/s2s? "yes"
/define/models/radiation/s2s-parameters/compute-vf "yes" "no"

; Materials
/define/materials/change-create air air yes ideal-gas no no no no no no
/define/materials/change-create aluminum dome-mat yes constant 2300 yes constant 880 yes constant 1.4 no no no

; Boundary Conditions
/define/boundary-conditions/modify-zones/zone-type west velocity-inlet
/define/boundary-conditions/velocity-inlet west no no yes yes no 2.0 no 0 no 260
/define/boundary-conditions/modify-zones/zone-type south velocity-inlet
/define/boundary-conditions/velocity-inlet south no no yes yes no 2.0 no 0 no 260
/define/boundary-conditions/modify-zones/zone-type east pressure-outlet
/define/boundary-conditions/pressure-outlet east yes no 0 no 260 yes no no yes
/define/boundary-conditions/modify-zones/zone-type north pressure-outlet
/define/boundary-conditions/pressure-outlet north yes no 0 no 260 yes no no yes
/define/boundary-conditions/modify-zones/zone-type sky symmetry
/define/boundary-conditions/symmetry sky
/define/boundary-conditions/wall ground_inside 0 no 0 no yes temperature no 260 no yes 1.0 no
/define/boundary-conditions/wall ground_outside 0 no 0 no yes temperature no 260 no yes 1.0 no
/define/boundary-conditions/wall dome_surf 0.01 yes dome-mat yes coupled no yes 0.9 no

; Solution Methods & Initialization
/solve/set/p-v-coupling 20 ; SIMPLE
/solve/initialize/hyb-initialization

; Report Definitions
/solve/report-definitions/add temp_dome surface-areaavg field temperature surface-names dome_surf () quit
/solve/report-files/add report-file-0 active yes file-name "{report_file_f}" report-defs temp_dome () print yes quit

; Run Calculation
/solve/set/time-step {TIME_STEP}
/solve/dual-time-iterate {N_TIME_STEPS} 20

/file/write-case-data "{case_path_f}"
/exit
"""
    with open(journal_path, "w") as f:
        f.write(journal)
        
    print(f"Running Fluent Solver (with GUI) from: {journal_path}")
    cmd = f'"{FLUENT_EXE}" 3ddp -t2 -wait -i "{journal_path}"'
    
    with open(os.path.join(WORK_DIR, "solver.log"), "w") as log:
        process = subprocess.Popen(cmd, stdout=log, stderr=log, shell=True)
        process.wait()
        
    if os.path.exists(CASE_PATH):
        print("[OK] Solver completed successfully!")
    else:
        print("[ERROR] Solver failed. See solver.log")
        sys.exit(1)

# ==============================================================================
# 5. POST-PROCESSING
# ==============================================================================
def plot_results():
    report_path = os.path.join(WORK_DIR, "report-file.out")
    if not os.path.exists(report_path):
        print("[ERROR] Results file not found.")
        return
        
    times = []
    temps = []
    with open(report_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith('"') and not line.startswith('('):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        times.append(float(parts[0]) * TIME_STEP / 3600.0) # hours
                        temps.append(float(parts[1]))
                    except:
                        pass
                        
    if not times:
        print("[ERROR] No data parsed from results.")
        return
        
    plt.figure(figsize=(10,6))
    plt.plot(times, temps, 'b-o', linewidth=2)
    plt.title('Average Dome Surface Temperature vs Time')
    plt.xlabel('Time (hours)')
    plt.ylabel('Temperature (K)')
    plt.grid(True)
    plt.axhline(y=260, color='r', linestyle='--', label='Ambient (260K)')
    plt.legend()
    
    out_plot = os.path.join(WORK_DIR, "temperature_plot.png")
    plt.savefig(out_plot, dpi=150)
    print(f"[OK] Plot saved to {out_plot}")

# ==============================================================================
# MAIN EXECUTOR
# ==============================================================================
if __name__ == "__main__":
    generate_stl(DOME_RADIUS, DOMAIN_SIZE, 60, 30, STL_PATH)
    run_meshing()
    run_solver()
    plot_results()
    print("\n--- All Done! ---")
