import os
os.environ["AWP_ROOT261"] = r"D:\ANSYS Inc\ANSYS Student\v261"
os.environ["AWP_ROOT262"] = r"D:\ANSYS Inc\ANSYS Student\v261"
import ansys.fluent.core as pyfluent
print("Launching solver...")
solver = pyfluent.launch_fluent(mode="solver", precision="double", processor_count=2, ui_mode="gui", start_watchdog=False)
print("Connected!")
solver.exit()
print("Exited!")
