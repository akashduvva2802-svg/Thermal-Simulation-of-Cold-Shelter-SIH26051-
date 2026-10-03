import os
os.environ["AWP_ROOT261"] = r"D:\ANSYS Inc\ANSYS Student\v261"
import ansys.fluent.core as pyfluent

solver = pyfluent.launch_fluent(mode="solver", precision="double", processor_count=2, ui_mode="gui", start_watchdog=False)
try:
    mesh_file = r"D:\Trial1_hemisphere_files\dp0\FFF-1\Fluent\FFF-1.msh.h5".replace("\\", "/")
    solver.tui.file.read_case(f'"{mesh_file}"')
    
    print("Setting physics models...")
    solver.setup.general.gravity = {"enable": True, "y_component": 0, "z_component": -9.81}
    solver.setup.models.energy.enabled = True
    solver.setup.models.viscous.model = "k-omega"
    solver.setup.models.viscous.k_omega_model = "sst"
    solver.setup.models.radiation.model = "s2s"
    
    print("Creating materials...")
    solver.setup.materials.fluid['air'] = {"density": {"option": "ideal-gas"}}
    solver.setup.materials.solid['dome-mat'] = {
        "density": {"option": "constant", "value": 2719},
        "specific_heat": {"option": "constant", "value": 871},
        "thermal_conductivity": {"option": "constant", "value": 202.4}
    }
    
    print("Setting boundary conditions...")
    bc = solver.setup.boundary_conditions
    bc.velocity_inlet['west'] = {"vmag": {"option": "value", "value": 2.0}, "t0": {"option": "value", "value": 260}}
    bc.velocity_inlet['south'] = {"vmag": {"option": "value", "value": 2.0}, "t0": {"option": "value", "value": 260}}
    bc.pressure_outlet['east'] = {"t0": {"option": "value", "value": 260}}
    bc.pressure_outlet['north'] = {"t0": {"option": "value", "value": 260}}
    bc.symmetry['sky'] = {}
    
    wall = bc.wall
    wall['ground'] = {"thermal_bc": "Temperature", "t": {"option": "value", "value": 260.0}}
    wall['ground.1'] = {"thermal_bc": "Temperature", "t": {"option": "value", "value": 260.0}}
    wall['inside:1'] = {"thermal_bc": "Temperature", "t": {"option": "value", "value": 260.0}}
    print("ALL OK!")
    
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    solver.exit()
