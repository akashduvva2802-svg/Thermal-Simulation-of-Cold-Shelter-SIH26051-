import os
os.environ["AWP_ROOT261"] = r"D:\ANSYS Inc\ANSYS Student\v261"
import ansys.fluent.core as pyfluent

solver = pyfluent.launch_fluent(mode="solver", precision="double", processor_count=2, ui_mode="gui", start_watchdog=False)
try:
    print("General attrs:", dir(solver.setup.general))
    solver.setup.general.gravity = {"enable": True, "y_component": 0, "z_component": -9.81}
    print("Gravity set!")
except Exception as e:
    print("Error:", e)
finally:
    solver.exit()
