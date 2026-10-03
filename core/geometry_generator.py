"""
geometry_generator.py
=====================
Parametric hemispherical dome geometry generator.
Creates IGES/STL geometry for the dome shelter with configurable:
  - Inner radius
  - Shell thickness
  - Door opening angle and width
  - Bounding box (external air domain)

Uses SpaceClaim scripting or fallback analytical STL generation.
"""

import math
import os
import struct
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class DomeGeometryParams:
    """Parameters defining the hemispherical dome shelter geometry."""
    inner_radius: float = 2.0       # Inner radius of dome (m)
    thickness: float = 0.01         # Shell thickness (m)
    door_width: float = 0.8         # Door opening width (m)
    door_height: float = 1.8        # Door opening height (m)
    ground_extension: float = 10.0  # Ground plane extension beyond dome (m)
    domain_height: float = 10.0     # Air domain height (m)
    domain_length: float = 20.0     # Air domain length in flow direction (m)
    domain_width: float = 20.0      # Air domain width (m)

    @property
    def outer_radius(self) -> float:
        return self.inner_radius + self.thickness

    @property
    def dome_surface_area(self) -> float:
        """External hemispherical surface area (m^2)."""
        return 2 * math.pi * self.outer_radius ** 2

    @property
    def dome_volume_internal(self) -> float:
        """Internal volume of the hemisphere (m^3)."""
        return (2 / 3) * math.pi * self.inner_radius ** 3

    @property
    def shell_volume(self) -> float:
        """Volume of the shell material (m^3)."""
        return (2 / 3) * math.pi * (self.outer_radius ** 3 - self.inner_radius ** 3)

    @property
    def projected_area(self) -> float:
        """Projected area on ground plane (circle) (m^2)."""
        return math.pi * self.outer_radius ** 2

    def to_dict(self) -> dict:
        return {
            "inner_radius": self.inner_radius,
            "thickness": self.thickness,
            "door_width": self.door_width,
            "door_height": self.door_height,
            "ground_extension": self.ground_extension,
            "domain_height": self.domain_height,
            "domain_length": self.domain_length,
            "domain_width": self.domain_width,
            "outer_radius": self.outer_radius,
            "dome_surface_area": self.dome_surface_area,
            "dome_volume_internal": self.dome_volume_internal,
            "shell_volume": self.shell_volume,
            "projected_area": self.projected_area,
        }


def generate_hemisphere_stl(
    params: DomeGeometryParams,
    output_dir: str,
    n_theta: int = 60,
    n_phi: int = 30,
) -> dict:
    """
    Generate conformal STL files for the dome shelter geometry.
    Creates a single assembly with:
      - dome_surf (outer shell, we use shell conduction for thickness)
      - ground_inside, ground_outside (ground plane)
      - domain boundaries (west, east, north, south, sky)
    Returns dict of {zone_name: file_path}.
    """
    os.makedirs(output_dir, exist_ok=True)
    combined_path = os.path.join(output_dir, "dome_assembly.stl")
    files = {"assembly": combined_path}

    R = params.inner_radius  # Use inner radius as the base, thickness is added via shell conduction
    domain_size = params.domain_length  # assume square domain
    
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
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx, vy, vz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length > 0:
            return (nx/length, ny/length, nz/length)
        return (0, 0, 1)

    verts = {}
    for i in range(n_theta):
        theta = 2 * math.pi * i / n_theta
        for j in range(n_phi + 1):
            phi = (math.pi / 2) * j / n_phi
            x = R * math.cos(phi) * math.cos(theta)
            y = R * math.cos(phi) * math.sin(theta)
            z = R * math.sin(phi)
            if j == n_phi:
                verts[(i, j)] = (0.0, 0.0, float(R)) # Exact pole
            else:
                verts[(i, j)] = (x, y, z)
                
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        for j in range(n_phi):
            v1 = verts[(i, j)]
            v2 = verts[(i_next, j)]
            v3 = verts[(i_next, j + 1)]
            v4 = verts[(i, j + 1)]
            if j == n_phi - 1:
                n = compute_normal(v1, v2, v3)
                all_triangles["dome_surf"].append((n, v1, v2, v3))
            else:
                n1 = compute_normal(v1, v2, v3)
                n2 = compute_normal(v1, v3, v4)
                all_triangles["dome_surf"].append((n1, v1, v2, v3))
                all_triangles["dome_surf"].append((n2, v1, v3, v4))

    center = (0.0, 0.0, 0.0)
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        v1 = center
        v2 = verts[(i_next, 0)]
        v3 = verts[(i, 0)]
        n = compute_normal(v1, v2, v3)
        all_triangles["ground_inside"].append((n, v1, v2, v3))

    hl, hw = domain_size / 2, params.domain_width / 2
    dh = params.domain_height
    
    def get_square_point(theta):
        t_x = hl / math.cos(theta) if math.cos(theta) != 0 else float('inf')
        t_x = t_x if t_x > 0 else -hl / math.cos(theta)
        t_y = hw / math.sin(theta) if math.sin(theta) != 0 else float('inf')
        t_y = t_y if t_y > 0 else -hw / math.sin(theta)
        t = min(t_x, t_y)
        return (t * math.cos(theta), t * math.sin(theta), 0.0)

    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        theta1 = 2 * math.pi * i / n_theta
        theta2 = 2 * math.pi * i_next / n_theta
        
        c1 = verts[(i, 0)]
        c2 = verts[(i_next, 0)]
        sq1 = get_square_point(theta1)
        sq2 = get_square_point(theta2)
        
        n1 = compute_normal(c1, sq1, c2)
        all_triangles["ground_outside"].append((n1, c1, sq1, c2))
        if sq1 != sq2:
            n2 = compute_normal(c2, sq1, sq2)
            all_triangles["ground_outside"].append((n2, c2, sq1, sq2))

    top_sq = [ (get_square_point(2 * math.pi * i / n_theta)[0], get_square_point(2 * math.pi * i / n_theta)[1], dh) for i in range(n_theta) ]
    
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        sq1 = get_square_point(2 * math.pi * i / n_theta)
        sq2 = get_square_point(2 * math.pi * i_next / n_theta)
        t1 = (sq1[0], sq1[1], dh)
        t2 = (sq2[0], sq2[1], dh)
        
        if sq1 == sq2: continue
        
        if abs(sq1[0] - hl) < 1e-6 and abs(sq2[0] - hl) < 1e-6:
            face = "east"
            n1 = compute_normal(sq1, sq2, t1)
            n2 = compute_normal(sq2, t2, t1)
            all_triangles[face].append((n1, sq1, sq2, t1))
            all_triangles[face].append((n2, sq2, t2, t1))
        elif abs(sq1[0] + hl) < 1e-6 and abs(sq2[0] + hl) < 1e-6:
            face = "west"
            n1 = compute_normal(sq1, t1, sq2)
            n2 = compute_normal(sq2, t1, t2)
            all_triangles[face].append((n1, sq1, t1, sq2))
            all_triangles[face].append((n2, sq2, t1, t2))
        elif abs(sq1[1] - hw) < 1e-6 and abs(sq2[1] - hw) < 1e-6:
            face = "north"
            n1 = compute_normal(sq1, t1, sq2)
            n2 = compute_normal(sq2, t1, t2)
            all_triangles[face].append((n1, sq1, t1, sq2))
            all_triangles[face].append((n2, sq2, t1, t2))
        elif abs(sq1[1] + hw) < 1e-6 and abs(sq2[1] + hw) < 1e-6:
            face = "south"
            n1 = compute_normal(sq1, sq2, t1)
            n2 = compute_normal(sq2, t2, t1)
            all_triangles[face].append((n1, sq1, sq2, t1))
            all_triangles[face].append((n2, sq2, t2, t1))

    center_top = (0.0, 0.0, dh)
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        t1 = top_sq[i]
        t2 = top_sq[i_next]
        if t1 == t2: continue
        n = compute_normal(t1, t2, center_top)
        all_triangles["sky"].append((n, t1, t2, center_top))

    with open(combined_path, "w") as f:
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

    return files


def generate_fluent_meshing_journal(
    params: DomeGeometryParams,
    geometry_files: dict,
    output_path: str,
) -> str:
    """
    Generate a Fluent Meshing Python journal script for the dome geometry.
    This script can be executed by PyFluent meshing mode.
    """
    # Build file import list
    file_list = []
    for zone, path in geometry_files.items():
        file_list.append(f'r"{path}"')

    journal = f'''# Auto-generated Fluent Meshing Journal
# Dome Geometry: R_inner={params.inner_radius}m, thickness={params.thickness}m

import ansys.fluent.core as pyfluent

# --- This journal is designed to be executed within PyFluent meshing session ---

def setup_meshing(meshing):
    """Configure and execute watertight meshing workflow."""
    workflow = meshing.workflow

    # Initialize watertight workflow
    workflow.InitializeWorkflow(WorkflowType="Watertight Geometry")

    # Import geometry
    workflow.TaskObject["Import Geometry"].Arguments.set_state({{
        "FileName": r"{list(geometry_files.values())[0] if geometry_files else ''}",
        "LengthUnit": "m",
    }})
    workflow.TaskObject["Import Geometry"].Execute()

    # Add local sizing for dome surfaces
    workflow.TaskObject["Add Local Sizing"].Arguments.set_state({{
        "AddChild": "yes",
        "BOICellsPerGap": 1,
        "BOICurvatureNormalAngle": 18,
        "BOIExecution": "Face Size",
        "BOIFaceLabelList": ["inside_surf", "outside_surf"],
        "BOIGrowthRate": 1.35,
        "BOISize": 0.05,
        "BOIZoneorLabel": "label",
        "DrawSizeControl": True,
    }})
    workflow.TaskObject["Add Local Sizing"].AddChildAndUpdate(
        DeferUpdate=False, RetainValues=True
    )

    # Generate surface mesh
    workflow.TaskObject["Generate the Surface Mesh"].Arguments.set_state({{
        "CFDSurfaceMeshControls": {{
            "MinSize": 0.01,
        }},
        "SurfaceMeshPreferences": {{
            "ShowSurfaceMeshPreferences": True,
        }},
    }})
    workflow.TaskObject["Generate the Surface Mesh"].Execute()

    # Describe geometry
    workflow.TaskObject["Describe Geometry"].Arguments.set_state({{
        "SetupType": "The geometry consists of both fluid and solid regions and/or voids",
        "CappingRequired": "No",
        "InvokeShareTopology": "No",
        "WallToInternal": "No",
    }})
    workflow.TaskObject["Describe Geometry"].Execute()

    # Update boundaries
    workflow.TaskObject["Update Boundaries"].Arguments.set_state({{
        "BoundaryLabelList": [
            "west", "south", "east", "ground", "north", "sky", "inside_surf"
        ],
        "BoundaryLabelTypeList": [
            "velocity-inlet", "velocity-inlet", "pressure-outlet",
            "wall", "pressure-outlet", "pressure-outlet", "wall"
        ],
    }})
    workflow.TaskObject["Update Boundaries"].Execute()

    # Create regions
    workflow.TaskObject["Create Regions"].Arguments.set_state({{
        "NumberOfFlowVolumes": 2,
    }})
    workflow.TaskObject["Create Regions"].Execute()

    # Update regions
    workflow.TaskObject["Update Regions"].Execute()

    # Add boundary layers
    workflow.TaskObject["Add Boundary Layers"].Arguments.set_state({{
        "LocalPrismPreferences": {{"Continuous": "Continuous"}},
        "NumberOfLayers": 5,
    }})
    workflow.TaskObject["Add Boundary Layers"].AddChildAndUpdate(
        DeferUpdate=False, RetainValues=True
    )

    # Generate volume mesh
    workflow.TaskObject["Generate the Volume Mesh"].Arguments.set_state({{
        "VolumeFill": "poly-hexcore",
    }})
    workflow.TaskObject["Generate the Volume Mesh"].Execute()

    print("Meshing complete!")
    return meshing
'''
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(journal)

    return output_path


# ──────────────────────────────────────────────────────────────────────
#  DISCRETE SIZE OPTIONS (for UI sliders)
# ──────────────────────────────────────────────────────────────────────

# Inner radius options (meters)
INNER_RADIUS_OPTIONS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]

# Shell thickness options (meters)
THICKNESS_OPTIONS = [0.002, 0.005, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05]

# Door width options (meters)
DOOR_WIDTH_OPTIONS = [0.6, 0.8, 1.0, 1.2, 1.5]

# Door height options (meters)
DOOR_HEIGHT_OPTIONS = [1.4, 1.6, 1.8, 2.0, 2.2]

# Domain size multipliers (relative to dome radius)
DOMAIN_SIZE_OPTIONS = [
    {"label": "Small (5x)", "multiplier": 5},
    {"label": "Medium (10x)", "multiplier": 10},
    {"label": "Large (15x)", "multiplier": 15},
    {"label": "Extra Large (20x)", "multiplier": 20},
]
