import os
os.environ["AWP_ROOT261"] = r"D:\ANSYS Inc\ANSYS Student\v261"
import ansys.fluent.core as pyfluent
print("Launching PyFluent...")
try:
    solver = pyfluent.launch_fluent(mode="solver", precision="double", processor_count=2, ui_mode="gui", start_watchdog=False)
    print("PyFluent connected successfully!")
    print("Reading mesh...")
    solver.tui.file.read_case(r"D:\Trial1_hemisphere_files\dp0\FFF-1\Fluent\FFF-1.msh.h5")
    print("Mesh loaded! Testing Settings API...")
    solver.setup.models.energy.enabled = True
    print("Energy enabled!")
    solver.exit()
except Exception as e:
    print(f"Error: {e}")

