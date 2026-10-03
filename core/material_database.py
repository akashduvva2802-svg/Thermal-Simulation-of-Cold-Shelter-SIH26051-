"""
material_database.py
====================
Material property database for dome shelter thermal simulation.
Contains thermal properties for common shelter construction materials
and air properties for internal/external fluid domains.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os


@dataclass
class MaterialProperties:
    """Thermal and physical properties of a material."""
    name: str
    density: float              # kg/m^3
    specific_heat: float        # J/(kg·K)
    thermal_conductivity: float # W/(m·K)
    absorptivity: float = 0.5  # Solar absorptivity (0-1)
    emissivity: float = 0.9    # Thermal emissivity (0-1)
    transmissivity: float = 0.0  # Solar transmissivity (for translucent materials)
    category: str = "solid"     # solid, fluid, composite
    description: str = ""

    @property
    def thermal_diffusivity(self) -> float:
        """Thermal diffusivity in m^2/s."""
        return self.thermal_conductivity / (self.density * self.specific_heat)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "density": self.density,
            "specific_heat": self.specific_heat,
            "thermal_conductivity": self.thermal_conductivity,
            "absorptivity": self.absorptivity,
            "emissivity": self.emissivity,
            "transmissivity": self.transmissivity,
            "category": self.category,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialProperties":
        return cls(**data)


# ──────────────────────────────────────────────────────────────────────
#  BUILT-IN MATERIAL DATABASE
# ──────────────────────────────────────────────────────────────────────

MATERIALS_DB: Dict[str, MaterialProperties] = {
    # ── Metals ──
    "mild_steel": MaterialProperties(
        name="Mild Steel",
        density=7850,
        specific_heat=500,
        thermal_conductivity=54,
        absorptivity=0.6,
        emissivity=0.28,
        category="solid",
        description="Low carbon steel, common structural material",
    ),
    "stainless_steel_304": MaterialProperties(
        name="Stainless Steel 304",
        density=8000,
        specific_heat=500,
        thermal_conductivity=16.2,
        absorptivity=0.55,
        emissivity=0.59,
        category="solid",
        description="Austenitic stainless steel, corrosion-resistant",
    ),
    "aluminum_6061": MaterialProperties(
        name="Aluminum 6061-T6",
        density=2700,
        specific_heat=896,
        thermal_conductivity=167,
        absorptivity=0.3,
        emissivity=0.09,
        category="solid",
        description="Common structural aluminum alloy",
    ),
    "copper": MaterialProperties(
        name="Copper",
        density=8960,
        specific_heat=385,
        thermal_conductivity=401,
        absorptivity=0.65,
        emissivity=0.03,
        category="solid",
        description="Pure copper, excellent thermal conductor",
    ),
    "galvanized_steel": MaterialProperties(
        name="Galvanized Steel",
        density=7800,
        specific_heat=510,
        thermal_conductivity=52,
        absorptivity=0.65,
        emissivity=0.28,
        category="solid",
        description="Zinc-coated steel for outdoor structures",
    ),

    # ── Polymers / Composites ──
    "fiberglass": MaterialProperties(
        name="Fiberglass (GRP)",
        density=1800,
        specific_heat=800,
        thermal_conductivity=0.3,
        absorptivity=0.5,
        emissivity=0.9,
        category="solid",
        description="Glass-fiber reinforced polymer",
    ),
    "polycarbonate": MaterialProperties(
        name="Polycarbonate",
        density=1200,
        specific_heat=1250,
        thermal_conductivity=0.2,
        absorptivity=0.15,
        emissivity=0.9,
        transmissivity=0.75,
        category="solid",
        description="Transparent thermoplastic, allows solar transmission",
    ),
    "pvc": MaterialProperties(
        name="PVC (Rigid)",
        density=1400,
        specific_heat=900,
        thermal_conductivity=0.16,
        absorptivity=0.45,
        emissivity=0.91,
        category="solid",
        description="Rigid polyvinyl chloride",
    ),
    "hdpe": MaterialProperties(
        name="HDPE",
        density=960,
        specific_heat=1900,
        thermal_conductivity=0.5,
        absorptivity=0.4,
        emissivity=0.9,
        category="solid",
        description="High-density polyethylene",
    ),

    # ── Concrete / Masonry ──
    "concrete": MaterialProperties(
        name="Concrete",
        density=2300,
        specific_heat=880,
        thermal_conductivity=1.4,
        absorptivity=0.6,
        emissivity=0.94,
        category="solid",
        description="Standard Portland cement concrete",
    ),
    "brick": MaterialProperties(
        name="Clay Brick",
        density=1920,
        specific_heat=790,
        thermal_conductivity=0.72,
        absorptivity=0.7,
        emissivity=0.93,
        category="solid",
        description="Standard fired clay brick",
    ),

    # ── Insulation ──
    "eps_foam": MaterialProperties(
        name="EPS Foam (Expanded Polystyrene)",
        density=25,
        specific_heat=1340,
        thermal_conductivity=0.035,
        absorptivity=0.4,
        emissivity=0.6,
        category="solid",
        description="Expanded polystyrene insulation",
    ),
    "rockwool": MaterialProperties(
        name="Rock Wool Insulation",
        density=120,
        specific_heat=840,
        thermal_conductivity=0.04,
        absorptivity=0.5,
        emissivity=0.9,
        category="solid",
        description="Mineral wool thermal insulation",
    ),
    "polyurethane_foam": MaterialProperties(
        name="Polyurethane Foam",
        density=35,
        specific_heat=1400,
        thermal_conductivity=0.025,
        absorptivity=0.45,
        emissivity=0.9,
        category="solid",
        description="Closed-cell PU foam insulation",
    ),

    # ── Wood ──
    "plywood": MaterialProperties(
        name="Plywood",
        density=540,
        specific_heat=1700,
        thermal_conductivity=0.12,
        absorptivity=0.6,
        emissivity=0.9,
        category="solid",
        description="Standard structural plywood",
    ),
    "bamboo": MaterialProperties(
        name="Bamboo",
        density=700,
        specific_heat=1600,
        thermal_conductivity=0.17,
        absorptivity=0.55,
        emissivity=0.9,
        category="solid",
        description="Natural bamboo material",
    ),

    # ── Special / Coated ──
    "white_painted_steel": MaterialProperties(
        name="White-Painted Steel",
        density=7850,
        specific_heat=500,
        thermal_conductivity=54,
        absorptivity=0.2,
        emissivity=0.9,
        category="solid",
        description="Steel with reflective white paint coating",
    ),
    "reflective_aluminum": MaterialProperties(
        name="Reflective Aluminum Sheet",
        density=2700,
        specific_heat=896,
        thermal_conductivity=167,
        absorptivity=0.1,
        emissivity=0.05,
        category="solid",
        description="Polished/reflective aluminum for solar shielding",
    ),

    # ── Fluids ──
    "air": MaterialProperties(
        name="Air",
        density=1.225,
        specific_heat=1006.43,
        thermal_conductivity=0.0242,
        category="fluid",
        description="Ambient air at STP (ideal gas assumption for buoyancy)",
    ),
}


class MaterialManager:
    """Manages materials including custom additions and persistence."""

    def __init__(self, custom_db_path: Optional[str] = None):
        self._materials = dict(MATERIALS_DB)
        self._custom_path = custom_db_path or os.path.join(
            os.path.dirname(__file__), "..", "results", "custom_materials.json"
        )
        self._load_custom()

    def _load_custom(self):
        """Load user-defined custom materials from JSON."""
        if os.path.exists(self._custom_path):
            try:
                with open(self._custom_path, "r") as f:
                    custom = json.load(f)
                for key, data in custom.items():
                    self._materials[key] = MaterialProperties.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass

    def save_custom(self, key: str, mat: MaterialProperties):
        """Save a custom material to persistent storage."""
        self._materials[key] = mat
        custom = {}
        if os.path.exists(self._custom_path):
            try:
                with open(self._custom_path, "r") as f:
                    custom = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass
        custom[key] = mat.to_dict()
        os.makedirs(os.path.dirname(self._custom_path), exist_ok=True)
        with open(self._custom_path, "w") as f:
            json.dump(custom, f, indent=2)

    def get(self, key: str) -> Optional[MaterialProperties]:
        return self._materials.get(key)

    def list_all(self) -> Dict[str, MaterialProperties]:
        return dict(self._materials)

    def list_by_category(self, category: str) -> Dict[str, MaterialProperties]:
        return {k: v for k, v in self._materials.items() if v.category == category}

    def get_solid_names(self) -> List[str]:
        return [v.name for k, v in self._materials.items() if v.category == "solid"]

    def get_solid_keys(self) -> List[str]:
        return [k for k, v in self._materials.items() if v.category == "solid"]
