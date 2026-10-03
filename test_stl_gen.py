import math
import os

def generate_conformal_stl(R, domain_size, n_theta, n_phi, output_path):
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

    # Precompute dome vertices
    # i goes from 0 to n_theta (azimuth)
    # j goes from 0 to n_phi (elevation, 0 is equator z=0, n_phi is pole z=R)
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
                
    # 1. Dome Surface (normals pointing OUT of the dome)
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        for j in range(n_phi):
            v1 = verts[(i, j)]
            v2 = verts[(i_next, j)]
            v3 = verts[(i_next, j + 1)]
            v4 = verts[(i, j + 1)]
            
            if j == n_phi - 1:
                # Top row is triangles
                n = compute_normal(v1, v2, v3)
                all_triangles["dome_surf"].append((n, v1, v2, v3))
            else:
                # Quads split into two triangles
                n1 = compute_normal(v1, v2, v3)
                n2 = compute_normal(v1, v3, v4)
                all_triangles["dome_surf"].append((n1, v1, v2, v3))
                all_triangles["dome_surf"].append((n2, v1, v3, v4))

    # 2. Ground Inside (normals pointing UP)
    center = (0.0, 0.0, 0.0)
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        v1 = center
        v2 = verts[(i_next, 0)]
        v3 = verts[(i, 0)]
        n = compute_normal(v1, v2, v3)
        all_triangles["ground_inside"].append((n, v1, v2, v3))

    # 3. Ground Outside (normals pointing UP)
    # We will triangulate the region between the circular base and the rectangular bounding box.
    hl, hw = domain_size / 2, domain_size / 2
    corners = [
        (hl, hw, 0),    # +x, +y
        (-hl, hw, 0),   # -x, +y
        (-hl, -hw, 0),  # -x, -y
        (hl, -hw, 0)    # +x, -y
    ]
    # For each segment of the circle, we connect it to the nearest corner or edge of the bounding box.
    # A simple way to triangulate the outside ground:
    # Just project each circle point to the square perimeter.
    # The angle theta goes from 0 to 2pi.
    
    def get_square_point(theta):
        # Ray from origin at angle theta intersecting the square
        # Square is from -hl to hl, -hw to hw
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
        
        # Two triangles: (c1, sq1, c2) and (c2, sq1, sq2)
        # Normal pointing UP
        n1 = compute_normal(c1, sq1, c2)
        all_triangles["ground_outside"].append((n1, c1, sq1, c2))
        if sq1 != sq2:
            n2 = compute_normal(c2, sq1, sq2)
            all_triangles["ground_outside"].append((n2, c2, sq1, sq2))

    # 4. Domain Walls
    dh = domain_size / 2
    # Vertices of the top square
    top_sq = [ (get_square_point(2 * math.pi * i / n_theta)[0], get_square_point(2 * math.pi * i / n_theta)[1], dh) for i in range(n_theta) ]
    
    # We can just build the vertical walls matching the ground_outside perimeter points
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        sq1 = get_square_point(2 * math.pi * i / n_theta)
        sq2 = get_square_point(2 * math.pi * i_next / n_theta)
        t1 = (sq1[0], sq1[1], dh)
        t2 = (sq2[0], sq2[1], dh)
        
        if sq1 == sq2: continue
        
        # Determine which face this segment belongs to based on x or y coordinate
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

    # 5. Sky (top plane)
    center_top = (0.0, 0.0, dh)
    for i in range(n_theta):
        i_next = (i + 1) % n_theta
        t1 = top_sq[i]
        t2 = top_sq[i_next]
        if t1 == t2: continue
        n = compute_normal(t1, t2, center_top)
        all_triangles["sky"].append((n, t1, t2, center_top))

    # Write STL
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
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
            
    print(f"Generated conformal STL at {output_path}")

if __name__ == "__main__":
    generate_conformal_stl(2.0, 20.0, 60, 30, "c:/Users/Student-PC-2/Akash/Pretreatment/dome_thermal_sim/geometry/generated/test_conformal.stl")
