import os
import sys

os.environ["AWP_ROOT242"] = r"D:\ANSYS Inc\ANSYS Student\v261"
os.environ["AWP_ROOT241"] = os.environ["AWP_ROOT242"]

import ansys.fluent.core as pyfluent
from ansys.fluent.core.utils.fluent_version import FluentVersion

_orig = FluentVersion._missing_
@classmethod
def _patched_missing(cls, value):
    if "26.1" in str(value) or "261" in str(value):
        return FluentVersion.v242
    return _orig(value)
FluentVersion._missing_ = _patched_missing

def test_cube():
    print("Launching fluent...")
    solver = pyfluent.launch_fluent(mode="meshing", precision="double", processor_count=2, start_watchdog=False)
    print("Fluent launched.")
    
    workflow = solver.workflow
    workflow.InitializeWorkflow(WorkflowType="Watertight Geometry")
    
    box_stl = "box.stl"
    
    workflow.TaskObject["Import Geometry"].Arguments.set_state({
        "FileName": box_stl,
        "LengthUnit": "m",
    })
    workflow.TaskObject["Import Geometry"].Execute()
    print("Geometry imported.")
    
    workflow.TaskObject["Add Local Sizing"].AddChildAndUpdate(DeferUpdate=False, RetainValues=True)
    print("Local sizing skipped/added.")
    
    workflow.TaskObject["Generate the Surface Mesh"].Arguments.set_state({
        "CFDSurfaceMeshControls": {"MinSize": 0.5, "MaxSize": 2.0},
    })
    workflow.TaskObject["Generate the Surface Mesh"].Execute()
    print("Surface mesh generated.")
    
    solver.exit()
    print("Done.")

if __name__ == "__main__":
    test_cube()
