import os
os.environ["AWP_ROOT242"] = r"D:\ANSYS Inc\ANSYS Student\v261"
import ansys.fluent.core as pyfluent
print("Launching solver...")
solver = pyfluent.launch_fluent(product_version="24.2.0", mode="solver", precision="double", processor_count=2, ui_mode="gui", start_watchdog=False)
print("Connected!")
print("Reading mesh via TUI...")
solver.tui.file.read_case(r"D:\Trial1_hemisphere_files\dp0\FFF-1\Fluent\FFF-1.msh.h5")
print("Mesh loaded via TUI!")
solver.setup.models.energy.enabled = True
print("Energy enabled via Settings API!")
solver.exit()

