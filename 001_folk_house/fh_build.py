# -*- coding: utf-8 -*-
"""
بيت شعبي نجدي - Traditional Arabian folk house, fully procedural in Blender.

Scale : meters, Z up.  House facade sits on the Y=0 plane, courtyard in -Y.
Usage : exec(open(path).read(), ns); ns['build_all']()

Everything is generated from code: geometry, procedural shaders, lighting, cameras.
"""
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix

R = math.radians
SC = bpy.context.scene
random.seed(11)

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
OUT_DIR = os.path.join(HERE, "renders")
os.makedirs(OUT_DIR, exist_ok=True)

# =============================================================================
#  helpers
# =============================================================================
def srgb(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    def f(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b), 1.0)


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for pool in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.curves, bpy.data.node_groups,
                 bpy.data.textures, bpy.data.worlds):
        for d in list(pool):
            try:
                pool.remove(d)
            except Exception:
                pass


def coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        SC.collection.children.link(c)
    return c


COL_HOUSE = COL_COURT = COL_PROPS = COL_GROUND = COL_LIGHT = COL_CAM = COL_TMP = COL_FX = None


def init_collections():
    global COL_HOUSE, COL_COURT, COL_PROPS, COL_GROUND, COL_LIGHT, COL_CAM, COL_TMP, COL_FX
    COL_GROUND = coll("COL_Ground")
    COL_HOUSE = coll("COL_House")
    COL_COURT = coll("COL_Courtyard")
    COL_PROPS = coll("COL_Props")
    COL_LIGHT = coll("COL_Lights")
    COL_CAM = coll("COL_Cameras")
    COL_FX = coll("COL_Atmosphere")
    COL_TMP = coll("_TMP")


def bm_obj(name, bm, col, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def bbox(name, col, mat, lo, hi, bevel=0.0, seg=2, smooth=False):
    """Axis aligned box from corner lo to corner hi (mesh baked, object at origin)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]
    cx, cy, cz = (lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5, (lo[2] + hi[2]) * 0.5
    for v in bm.verts:
        v.co.x = v.co.x * sx + cx
        v.co.y = v.co.y * sy + cy
        v.co.z = v.co.z * sz + cz
    ob = bm_obj(name, bm, col, mat, smooth)
    if bevel > 0:
        add_bevel(ob, bevel, seg)
    return ob


def add_bevel(ob, width, seg=2, angle=35.0):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = seg
    m.limit_method = "ANGLE"
    m.angle_limit = R(angle)
    m.miter_outer = "MITER_ARC"
    return m


def adobe_surface(ob, strength=0.012, subdiv=2):
    """Simple subdivision + procedural displacement -> irregular hand-made mud walls."""
    tex = bpy.data.textures.get("TEX_AdobeNoise")
    if tex is None:
        tex = bpy.data.textures.new("TEX_AdobeNoise", type="CLOUDS")
        tex.noise_scale = 0.55
        tex.noise_depth = 2
    sd = ob.modifiers.new("Subdiv", "SUBSURF")
    sd.subdivision_type = "SIMPLE"
    sd.levels = subdiv
    sd.render_levels = subdiv
    dp = ob.modifiers.new("Displace", "DISPLACE")
    dp.texture = tex
    dp.texture_coords = "GLOBAL"
    dp.strength = strength
    dp.mid_level = 0.5
    return ob


def bm_apply_boolean(ob, cutters):
    """Bake the current modifier stack, then cut the openings (booleans must be first)."""
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    for md in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=md.name)
        except Exception as e:
            print("pre-bake failed", ob.name, md.name, e)
    for c in cutters:
        md = ob.modifiers.new("BOOL", "BOOLEAN")
        md.object = c
        md.operation = "DIFFERENCE"
        try:
            md.solver = "EXACT"
        except Exception:
            pass
    for md in [m for m in ob.modifiers if m.type == "BOOLEAN"]:
        bpy.ops.object.modifier_apply(modifier=md.name)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)


def cutter(lo, hi):
    return bbox("CUT", COL_TMP, None, lo, hi)


def lathe(name, col, mat, profile, segments=24, matrix=None, smooth=True):
    """profile = [(radius, z), ...] bottom->top. radius 0 = pole (auto cap)."""
    verts, faces, poles = [], [], {}
    rows = []
    for j, (r, z) in enumerate(profile):
        if abs(r) < 1e-6:
            poles[j] = len(verts)
            verts.append((0.0, 0.0, z))
            rows.append(None)
        else:
            rows.append([])
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        ca, sa = math.cos(a), math.sin(a)
        for j, (r, z) in enumerate(profile):
            if abs(r) < 1e-6:
                continue
            rows[j].append(len(verts))
            verts.append((r * ca, r * sa, z))

    def g(i, j):
        if abs(profile[j][0]) < 1e-6:
            return poles[j]
        return rows[j][i % segments]

    n = len(profile)
    for i in range(segments):
        for j in range(n - 1):
            quad = []
            for p in (g(i, j), g(i + 1, j), g(i + 1, j + 1), g(i, j + 1)):
                if p not in quad:
                    quad.append(p)
            if len(quad) >= 3:
                faces.append(tuple(quad))
    # flat caps if the profile ends with an open ring
    if abs(profile[0][0]) > 1e-6:
        faces.append(tuple(rows[0][i] for i in range(segments - 1, -1, -1)))
    if abs(profile[-1][0]) > 1e-6:
        faces.append(tuple(rows[-1][i] for i in range(segments)))
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    bm.verts.ensure_lookup_table()
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if matrix is not None:
        bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    return bm_obj(name, bm, col, mat, smooth)


def beam(name, col, mat, p0, p1, r0, r1=None, seg=10, smooth=True):
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    r1 = r0 if r1 is None else r1
    prof = [(0, 0), (r0, 0), (r1, L), (0, L)]
    q = (p1 - p0).to_track_quat("Z", "Y")
    M = Matrix.Translation(p0) @ q.to_matrix().to_4x4()
    return lathe(name, col, mat, prof, segments=seg, matrix=M, smooth=smooth)


def rock(name, col, mat, center, size, seed=0, cuts=1, smooth=True, rough=0.13):
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        v.co += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * rough
    for v in bm.verts:
        v.co.x = v.co.x * size[0] + center[0]
        v.co.y = v.co.y * size[1] + center[1]
        v.co.z = v.co.z * size[2] + center[2]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_obj(name, bm, col, mat, smooth)


def tri_prism(name, col, mat, cx, base_z, y, w=0.2, h=0.3, depth=0.045):
    """Relief triangle (Najdi gypsum motif). Faces toward -Y."""
    v = [(cx - w / 2, y, base_z), (cx + w / 2, y, base_z), (cx, y, base_z + h),
         (cx - w / 2, y + depth, base_z), (cx + w / 2, y + depth, base_z),
         (cx, y + depth, base_z + h)]
    f = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in v]
    for face in f:
        try:
            bm.faces.new([vs[i] for i in face])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_obj(name, bm, col, mat)


# =============================================================================
#  procedural materials
# =============================================================================
def base_mat(name):
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (620, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf


def seti(node, name, val):
    if name in node.inputs:
        try:
            node.inputs[name].default_value = val
        except Exception:
            pass


def mat_adobe(name, c_top, c_mid, c_low, rough=0.93, bump=0.45, mscale=16.0):
    m, nt, bsdf = base_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1100, 250)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-900, 300)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    n1 = nt.nodes.new("ShaderNodeTexNoise"); n1.location = (-900, 40)
    seti(n1, "Scale", 7.0); seti(n1, "Detail", 6.0); seti(n1, "Roughness", 0.6)
    mt = nt.nodes.new("ShaderNodeMath"); mt.location = (-700, 180)
    mt.operation = "ADD"
    nt.links.new(sep.outputs["Z"], mt.inputs[0])
    nt.links.new(n1.outputs["Fac"], mt.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-480, 220)
    cr = ramp.color_ramp
    cr.elements[0].position = 0.02; cr.elements[0].color = srgb(c_low)
    cr.elements[1].position = 0.42; cr.elements[1].color = srgb(c_mid)
    e = cr.elements.new(0.78); e.color = srgb(c_top)
    e2 = cr.elements.new(1.35); e2.color = srgb(c_top)
    nt.links.new(mt.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    # micro relief
    n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.location = (-900, -220)
    seti(n2, "Scale", 6.5); seti(n2, "Detail", 8.0); seti(n2, "Roughness", 0.62)
    bp = nt.nodes.new("ShaderNodeBump"); bp.location = (-380, -180)
    seti(bp, "Strength", bump); seti(bp, "Distance", 0.05)
    nt.links.new(n2.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    n3 = nt.nodes.new("ShaderNodeTexNoise"); n3.location = (-900, -460)
    seti(n3, "Scale", 3.0); seti(n3, "Detail", 4.0)
    rr = nt.nodes.new("ShaderNodeMapRange"); rr.location = (-620, -380)
    seti(rr, "From Min", 0.3); seti(rr, "From Max", 0.7)
    seti(rr, "To Min", rough - 0.07); seti(rr, "To Max", min(1.0, rough + 0.04))
    nt.links.new(n3.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
    seti(bsdf, "Specular IOR Level", 0.3)
    return m


def mat_wood(name, c1, c2, c3, rough=0.7, grain=14.0, bump=0.3):
    m, nt, bsdf = base_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1100, 0)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-920, 0)
    seti(mp, "Scale", (1.6, 1.6, grain))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.location = (-720, 120)
    wv.wave_type = "BANDS"; wv.bands_direction = "X"; wv.wave_profile = "SAW"
    seti(wv, "Scale", 2.4); seti(wv, "Distortion", 6.0); seti(wv, "Detail", 3.0)
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.location = (-720, -160)
    seti(nz, "Scale", 6.0); seti(nz, "Detail", 7.0)
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMath"); mix.location = (-520, 20)
    mix.operation = "MULTIPLY"
    nt.links.new(wv.outputs["Fac"], mix.inputs[0])
    nt.links.new(nz.outputs["Fac"], mix.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-320, 120)
    cr = ramp.color_ramp
    cr.elements[0].position = 0.05; cr.elements[0].color = srgb(c1)
    cr.elements[1].position = 0.5; cr.elements[1].color = srgb(c2)
    e = cr.elements.new(0.95); e.color = srgb(c3)
    nt.links.new(mix.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.location = (-320, -200)
    seti(bp, "Strength", bump); seti(bp, "Distance", 0.02)
    nt.links.new(mix.outputs[0], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    seti(bsdf, "Roughness", rough)
    seti(bsdf, "Specular IOR Level", 0.35)
    return m


def mat_plain(name, col, rough=0.8, metal=0.0, spec=0.4, bump=0.0, bscale=40.0):
    m, nt, bsdf = base_mat(name)
    seti(bsdf, "Base Color", srgb(col) if isinstance(col, str) else col)
    seti(bsdf, "Roughness", rough)
    seti(bsdf, "Metallic", metal)
    seti(bsdf, "Specular IOR Level", spec)
    if bump > 0:
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.location = (-700, -200)
        seti(nz, "Scale", bscale); seti(nz, "Detail", 8.0)
        bp = nt.nodes.new("ShaderNodeBump"); bp.location = (-400, -200)
        seti(bp, "Strength", bump); seti(bp, "Distance", 0.02)
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def mat_fabric(name, stripes, rough=0.88, scale=9.0):
    """stripes = [(pos, hexcolor), ...]"""
    m, nt, bsdf = base_mat(name)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1100, 0)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-920, 0)
    seti(mp, "Scale", (scale, 1.0, 1.0))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.location = (-720, 80)
    wv.wave_type = "BANDS"; wv.bands_direction = "X"
    seti(wv, "Scale", 3.0); seti(wv, "Distortion", 0.15); seti(wv, "Detail", 1.0)
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-500, 120)
    cr = ramp.color_ramp
    cr.elements[0].position = stripes[0][0]; cr.elements[0].color = srgb(stripes[0][1])
    cr.elements[1].position = stripes[1][0]; cr.elements[1].color = srgb(stripes[1][1])
    for pos, hexc in stripes[2:]:
        cr.elements.new(pos).color = srgb(hexc)
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.location = (-720, -260)
    seti(nz, "Scale", 120.0); seti(nz, "Detail", 6.0)
    bp = nt.nodes.new("ShaderNodeBump"); bp.location = (-400, -220)
    seti(bp, "Strength", 0.5); seti(bp, "Distance", 0.01)
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    seti(bsdf, "Roughness", rough)
    seti(bsdf, "Sheen Weight", 0.35)
    seti(bsdf, "Specular IOR Level", 0.3)
    return m


def mat_emit(name, col, strength=5.0):
    m, nt, bsdf = base_mat(name)
    seti(bsdf, "Base Color", srgb(col))
    seti(bsdf, "Emission Color", srgb(col))
    seti(bsdf, "Emission Strength", strength)
    seti(bsdf, "Roughness", 0.35)
    return m


def build_materials():
    M = {}
    M["wall"] = mat_adobe("MAT_Adobe_Wall", "#c9ab7d", "#a88252", "#6b5133")
    M["wall2"] = mat_adobe("MAT_Adobe_Wall_Upper", "#c4a67a", "#a28050", "#705636", rough=0.95)
    M["court"] = mat_adobe("MAT_Adobe_CourtWall", "#bc9a6c", "#997a4e", "#664e30", rough=0.95)
    M["floor"] = mat_adobe("MAT_Mud_Floor", "#b3946a", "#9a7d55", "#745c3d", rough=0.97, bump=0.7, mscale=20)
    M["sand"] = mat_plain("MAT_Ground_Sand", "#b08a52", rough=0.97, spec=0.12, bump=0.5, bscale=9)
    M["palm"] = mat_wood("MAT_Wood_Beam", "#54432e", "#3a2c1c", "#1e160d", rough=0.80, grain=10)
    M["door"] = mat_wood("MAT_Wood_Door", "#63402a", "#412918", "#24150d", rough=0.60, grain=26)
    M["lattice"] = mat_wood("MAT_Wood_Lattice", "#6f4a2c", "#4d311c", "#2b1a0c", rough=0.68, grain=26)
    M["iron"] = mat_plain("MAT_Iron_Stud", "#26241f", rough=0.50, metal=1.0, spec=0.6, bump=0.25, bscale=60)
    M["clay"] = mat_plain("MAT_Clay_Terracotta", "#96593a", rough=0.94, spec=0.18, bump=0.4, bscale=22)
    M["clay2"] = mat_plain("MAT_Clay_Pale", "#a57850", rough=0.94, spec=0.16, bump=0.35, bscale=20)
    M["gypsum"] = mat_plain("MAT_Gypsum_White", "#cfc1a6", rough=0.82, spec=0.3, bump=0.35, bscale=30)
    M["stone"] = mat_plain("MAT_Stone_Grey", "#7f7567", rough=0.9, spec=0.22, bump=0.45, bscale=18)
    M["rug"] = mat_fabric("MAT_Fabric_Rug", [(0.0, "#7b2a1c"), (0.26, "#7b2a1c"),
                                             (0.33, "#c8b189"), (0.47, "#c8b189"),
                                             (0.54, "#26211c"), (0.66, "#7b2a1c")], scale=2.1)
    M["cushion"] = mat_fabric("MAT_Fabric_Cushion", [(0.0, "#6a2418"), (0.30, "#8a2c1c"),
                                                     (0.46, "#b39a6f"), (0.56, "#6a2418"),
                                                     (0.72, "#2a241e"), (0.86, "#8a2c1c")], scale=9.0)
    M["leaf"] = mat_plain("MAT_Palm_Leaf", "#49571f", rough=0.70, spec=0.32, bump=0.0)
    M["leaf2"] = mat_plain("MAT_Tree_Leaf", "#525a2a", rough=0.80, spec=0.25)
    M["dry"] = mat_plain("MAT_Palm_Dry", "#a98d57", rough=0.9, spec=0.2, bump=0.3, bscale=30)
    M["trunk"] = mat_wood("MAT_Palm_Trunk", "#64543a", "#473a25", "#2c2416", rough=0.85, grain=22)
    M["dark"] = mat_plain("MAT_Interior_Dark", "#0d0b09", rough=1.0, spec=0.0)
    M["glow"] = mat_emit("MAT_Lantern_Glow", "#ffb257", 2.4)
    M["flame"] = mat_emit("MAT_Flame", "#ff8a2a", 8.0)
    return M


# =============================================================================
#  ground
# =============================================================================
def build_ground(M):
    bbox("SM_Desert_Floor", COL_GROUND, M["sand"], (-260, -300, -0.14), (260, 220, -0.02))
    bbox("SM_Courtyard_Floor", COL_GROUND, M["floor"], (-7.0, -9.0, -0.04), (7.0, 0.05, 0.02),
         bevel=0.05, seg=2)
    # pebbles + stones
    for i in range(46):
        x = random.uniform(-11, 11)
        y = random.uniform(-13, 2)
        if -6.7 < x < 6.7 and -8.7 < y < 0.0:
            continue
        s = random.uniform(0.06, 0.26)
        rock("SM_Pebble_%02d" % i, COL_GROUND, M["stone"],
             (x, y, -0.02 + s * 0.25), (s, s * random.uniform(0.7, 1.2), s * 0.45), seed=i)
    # a few bigger rocks out in the sand
    for i in range(9):
        x = random.uniform(-22, 22); y = random.uniform(-24, -10)
        s = random.uniform(0.35, 1.0)
        rock("SM_Rock_%02d" % i, COL_GROUND, M["stone"], (x, y, -0.05),
             (s, s * 0.8, s * 0.55), seed=100 + i, smooth=True)
    # distant dunes on the horizon for depth (they sit behind the house, +Y)
    bbox("SM_Desert_Far", COL_GROUND, M["sand"], (-1400, -1400, -1.4), (1400, 1400, -0.6))
    dunes = [(-150, 330, 300, 200, 26), (90, 470, 380, 240, 38), (350, 320, 260, 180, 22),
             (-430, 410, 320, 210, 30), (560, 520, 340, 220, 34), (-720, 300, 300, 190, 20),
             (170, 680, 460, 280, 46), (-280, 600, 380, 240, 36)]
    for i, (x, y, sx, sy, h) in enumerate(dunes):
        rock("SM_Dune_%02d" % i, COL_GROUND, M["sand"], (x, y, -6.0),
             (sx, sy, h), seed=500 + i, cuts=3, smooth=True, rough=0.20)
    # far scrub bushes (only outside the courtyard)
    for i in range(18):
        x = random.uniform(-90, 90)
        y = random.choice([random.uniform(35, 140), random.uniform(-95, -30)])
        s = random.uniform(0.7, 1.6)
        for b in range(3):
            rock("SM_Bush_%02d_%d" % (i, b), COL_GROUND, M["leaf2"],
                 (x + random.uniform(-0.6, 0.6), y + random.uniform(-0.6, 0.6), 0.05),
                 (s * 0.7, s * 0.6, s * 0.45), seed=700 + i * 3 + b, cuts=1, smooth=True, rough=0.2)
    # sandy track leading away from the gate
    bbox("SM_Track", COL_GROUND, M["floor"], (-1.9, -34.0, 0.0), (1.9, -8.55, 0.012),
         bevel=0.4, seg=4)
    # dry tufts
    for i in range(26):
        x = random.uniform(-7.5, 7.5); y = random.uniform(-9.5, -0.2)
        for b in range(4):
            h = random.uniform(0.15, 0.34)
            beam("SM_Tuft_%02d_%d" % (i, b), COL_GROUND, M["dry"],
                 (x, y, 0.0), (x + random.uniform(-0.12, 0.12), y + random.uniform(-0.12, 0.12), h),
                 0.012, 0.002, seg=4)


# =============================================================================
#  house shell
# =============================================================================
HW = 4.6          # half width   (X)
YD = 7.0          # depth        (Y)
WT = 0.55         # wall thickness
H1 = 3.70         # first floor height
H2 = 6.60         # second floor height
PAR = 0.90        # parapet height
# second floor block
UX0, UX1 = -4.6, 0.60
UY0 = 0.90

# openings
DOOR = (-3.18, -1.62, 0.00, 2.46)      # x0,x1,z0,z1
WIN = (0.95, 2.05, 1.15, 2.28)         # x0,x1,z0,z1
UWIN = (-3.30, -2.15, 4.95, 6.10)      # upper facade window (x0,x1,z0,z1) on Y=0.90


def wall(name, col, mat, lo, hi, holes=None, subdiv=2, disp=0.012, bev=0.028):
    """Adobe wall: irregular subdivided surface first, then clean boolean openings,
    then a soft bevel. (Subdividing *after* a cut corrupts n-gons with holes.)"""
    o = bbox(name, col, mat, lo, hi)
    if subdiv:
        adobe_surface(o, disp, subdiv)
    if holes:
        bm_apply_boolean(o, [cutter(*h) for h in holes])
    add_bevel(o, bev, 2)
    return o


def build_house(M):
    # ---- first floor: front wall with door + window openings
    wall("SM_Wall_Front", COL_HOUSE, M["wall"], (-HW - 0.02, 0.0, 0.0), (HW + 0.02, WT, H1),
         holes=[((DOOR[0], -1.0, DOOR[2]), (DOOR[1], 1.2, DOOR[3])),
                ((WIN[0], -1.0, WIN[2]), (WIN[1], 1.2, WIN[3]))])

    # ---- back wall
    wall("SM_Wall_Back", COL_HOUSE, M["wall"], (-HW - 0.02, YD - WT, 0.0), (HW + 0.02, YD, H1))

    # ---- west wall with two small windows
    wall("SM_Wall_West", COL_HOUSE, M["wall"], (-HW, 0.0, 0.0), (-HW + WT, YD, H1),
         holes=[((-HW - 1.0, 1.35, 1.30), (-HW + 1.0, 2.35, 2.35)),
                ((-HW - 1.0, 4.55, 1.30), (-HW + 1.0, 5.55, 2.35))])
    for k, yy in enumerate((1.35, 4.55)):
        bbox("SM_WWin_Recess_%d" % k, COL_PROPS, M["dark"], (-HW + 0.26, yy, 1.30),
             (-HW + 0.32, yy + 1.0, 2.35))
        lattice_panel("SM_WWin_Mash_%d" % k, COL_PROPS, M, (-HW + 0.10, yy + 0.03, 1.32),
                      (-HW + 0.18, yy + 0.97, 2.33), axis="X")
        bbox("SM_WWin_Sill_%d" % k, COL_PROPS, M["stone"], (-HW - 0.10, yy - 0.14, 1.21),
             (-HW + 0.26, yy + 1.14, 1.31), bevel=0.02, seg=2)

    # ---- east wall (inner, mostly hidden by the staircase)
    wall("SM_Wall_East", COL_HOUSE, M["wall"], (HW - WT, 0.0, 0.0), (HW, YD, H1))

    # ---- first floor roof slab (terrace floor)
    slab = bbox("SM_Roof_L1", COL_HOUSE, M["wall"], (-HW - 0.10, -0.10, H1 - 0.22),
                (HW + 0.10, YD + 0.10, H1), bevel=0.03, seg=2)
    adobe_surface(slab, 0.008, 1)

    # ---- second floor block
    wall("SM_Wall_L2_Front", COL_HOUSE, M["wall2"], (UX0 - 0.02, UY0, H1), (UX1 + 0.02, UY0 + 0.50, H2),
         holes=[((UWIN[0], UY0 - 1.0, UWIN[2]), (UWIN[1], UY0 + 1.2, UWIN[3]))])
    wall("SM_Wall_L2_East", COL_HOUSE, M["wall2"], (UX1 - 0.50, UY0, H1), (UX1, YD, H2),
         holes=[((UX1 - 1.0, 1.70, 4.62), (UX1 + 1.0, 3.30, 5.95))])
    wall("SM_Wall_L2_West", COL_HOUSE, M["wall2"], (UX0, UY0, H1), (UX0 + 0.50, YD, H2))
    wall("SM_Wall_L2_Back", COL_HOUSE, M["wall2"], (UX0, YD - 0.50, H1), (UX1, YD, H2))

    slab2 = bbox("SM_Roof_L2", COL_HOUSE, M["wall2"], (UX0 - 0.10, UY0 - 0.10, H2 - 0.22),
                 (UX1 + 0.10, YD + 0.10, H2), bevel=0.03, seg=2)
    adobe_surface(slab2, 0.008, 1)

    # ---- parapets
    def par(name, lo, hi):
        o = bbox(name, COL_HOUSE, M["wall"], lo, hi, bevel=0.028, seg=2)
        adobe_surface(o, 0.008, 1)
        return o

    # L1 terrace parapet (south / east / north / short west)
    par("SM_Par_L1_S", (-HW - 0.10, -0.10, H1), (HW + 0.10, 0.22, H1 + PAR))
    par("SM_Par_L1_E", (HW - 0.18, -0.10, H1), (HW + 0.10, YD + 0.10, H1 + PAR))
    par("SM_Par_L1_N", (UX1, YD - 0.12, H1), (HW + 0.10, YD + 0.10, H1 + PAR))
    par("SM_Par_L1_W", (UX0 - 0.10, -0.10, H1), (UX0 + 0.05, 0.22, H1 + PAR))
    # L2 roof parapet
    par("SM_Par_L2_S", (UX0 - 0.10, UY0 - 0.12, H2), (UX1 + 0.10, UY0 + 0.20, H2 + PAR * 0.85))
    par("SM_Par_L2_E", (UX1 - 0.20, UY0 - 0.12, H2), (UX1 + 0.10, YD + 0.10, H2 + PAR * 0.85))
    par("SM_Par_L2_W", (UX0 - 0.10, UY0 - 0.12, H2), (UX0 + 0.18, YD + 0.10, H2 + PAR * 0.85))
    par("SM_Par_L2_N", (UX0 - 0.10, YD - 0.18, H2), (UX1 + 0.10, YD + 0.10, H2 + PAR * 0.85))

    # ---- protruding palm beams (أخشاب الأثل) under the roof lines
    z = H1 - 0.30
    i = 0
    x = -HW + 0.25
    while x < HW - 0.1:
        beam("SM_Beam_L1_%02d" % i, COL_HOUSE, M["palm"], (x, 0.52, z), (x, -0.42, z),
             0.085, 0.075, seg=8)
        i += 1
        x += 0.62
    z = H2 - 0.28
    i = 0
    x = UX0 + 0.25
    while x < UX1 - 0.05:
        beam("SM_Beam_L2_%02d" % i, COL_HOUSE, M["palm"], (x, UY0 + 0.45, z), (x, UY0 - 0.40, z),
             0.08, 0.07, seg=8)
        i += 1
        x += 0.62
    # side beams on the east facade
    y = 0.5
    i = 0
    while y < YD - 0.3:
        beam("SM_Beam_E_%02d" % i, COL_HOUSE, M["palm"], (HW - 0.52, y, z), (HW + 0.36, y, z),
             0.075, 0.068, seg=8)
        i += 1
        y += 0.62
    # beams on the west facade of the upper block
    y = UY0 + 0.45
    i = 0
    while y < YD - 0.3:
        beam("SM_Beam_W2_%02d" % i, COL_HOUSE, M["palm"], (UX0 + 0.48, y, z), (UX0 - 0.36, y, z),
             0.072, 0.065, seg=8)
        i += 1
        y += 0.66
    # west facade of the ground floor: beams + a vent
    zw = H1 - 0.30
    y = 0.9
    i = 0
    while y < YD - 0.3:
        beam("SM_Beam_W_%02d" % i, COL_HOUSE, M["palm"], (-HW + 0.50, y, zw), (-HW - 0.36, y, zw),
             0.078, 0.070, seg=8)
        i += 1
        y += 0.66

    # ---- white gypsum triangle friezes (زخرفة مثلثات جصية)
    for k in range(10):
        tri_prism("SM_Tri_Door_%d" % k, COL_HOUSE, M["gypsum"],
                  cx=DOOR[0] + 0.06 + k * 0.175, base_z=2.74, y=-0.005,
                  w=0.135, h=0.20, depth=0.020)
    for k in range(7):
        tri_prism("SM_Tri_Win_%d" % k, COL_HOUSE, M["gypsum"],
                  cx=WIN[0] + 0.04 + k * 0.175, base_z=2.56, y=-0.005,
                  w=0.13, h=0.19, depth=0.020)
    for k in range(8):
        tri_prism("SM_Tri_L2_%d" % k, COL_HOUSE, M["gypsum"],
                  cx=-4.10 + k * 0.20, base_z=6.26, y=UY0 - 0.005,
                  w=0.14, h=0.20, depth=0.020)

    # ---- triangular merlons (شرافات) along the parapet tops
    def merlons(prefix, a0, a1, fixed, axis, zbase, h=0.34, w=0.34, step=0.62):
        n = max(2, int((a1 - a0) / step))
        for k in range(n):
            c = a0 + (a1 - a0) * (k + 0.5) / n
            if axis == "X":
                bbox("%s_%02d" % (prefix, k), COL_HOUSE, M["wall"],
                     (c - w * 0.5, fixed - 0.09, zbase), (c + w * 0.5, fixed + 0.09, zbase + h * 0.55),
                     bevel=0.02, seg=1)
                tri_prism("%s_T%02d" % (prefix, k), COL_HOUSE, M["wall"],
                          cx=c, base_z=zbase + h * 0.55, y=fixed - 0.09,
                          w=w, h=h * 0.5, depth=0.18)
            else:
                bbox("%s_%02d" % (prefix, k), COL_HOUSE, M["wall"],
                     (fixed - 0.09, c - w * 0.5, zbase), (fixed + 0.09, c + w * 0.5, zbase + h * 0.55),
                     bevel=0.02, seg=1)

    merlons("SM_Merl_S", -HW + 0.3, HW - 0.3, 0.06, "X", H1 + PAR)
    merlons("SM_Merl_E", 0.3, YD - 0.3, HW + 0.0, "Y", H1 + PAR)
    merlons("SM_Merl_L2", UX0 + 0.3, UX1 - 0.3, UY0 + 0.04, "X", H2 + PAR * 0.85)


# =============================================================================
#  door, windows, lattice
# =============================================================================
def build_door(M):
    x0, x1, z0, z1 = DOOR
    yf = 0.10
    # stone threshold
    bbox("SM_Threshold", COL_PROPS, M["stone"], (x0 - 0.18, -0.22, -0.02),
         (x1 + 0.18, 0.60, 0.07), bevel=0.025, seg=2)
    # frame
    bbox("SM_Door_Frame_L", COL_PROPS, M["door"], (x0 - 0.02, yf - 0.10, z0), (x0 + 0.13, yf + 0.06, z1 + 0.14))
    bbox("SM_Door_Frame_R", COL_PROPS, M["door"], (x1 - 0.13, yf - 0.10, z0), (x1 + 0.02, yf + 0.06, z1 + 0.14))
    bbox("SM_Door_Frame_T", COL_PROPS, M["door"], (x0 - 0.05, yf - 0.10, z1), (x1 + 0.05, yf + 0.06, z1 + 0.22),
         bevel=0.015, seg=2)
    bbox("SM_Door_Lintel", COL_PROPS, M["palm"], (x0 - 0.22, yf - 0.14, z1 + 0.22),
         (x1 + 0.22, yf + 0.04, z1 + 0.36), bevel=0.02, seg=2)
    # two leaves with vertical planks
    mid = (x0 + x1) * 0.5
    leaves = [(x0 + 0.14, mid - 0.015), (mid + 0.015, x1 - 0.14)]
    for li, (a, b) in enumerate(leaves):
        bbox("SM_Door_Leaf_%d" % li, COL_PROPS, M["door"], (a, yf - 0.02, z0 + 0.02),
             (b, yf + 0.07, z1 - 0.02))
        n = 4
        for k in range(n):
            px = a + (b - a) * (k + 0.5) / n
            bbox("SM_Door_Plank_%d_%d" % (li, k), COL_PROPS, M["door"],
                 (px - 0.012, yf - 0.055, z0 + 0.10), (px + 0.012, yf - 0.02, z1 - 0.08))
        # iron rails + studs
        for k, zz in enumerate((0.55, 1.35, 2.15)):
            bbox("SM_Door_Rail_%d_%d" % (li, k), COL_PROPS, M["iron"],
                 (a + 0.03, yf - 0.075, zz - 0.045), (b - 0.03, yf - 0.045, zz + 0.045))
            m = 5
            for s in range(m):
                px = a + 0.10 + (b - a - 0.20) * s / (m - 1)
                lathe("SM_Door_Stud_%d_%d_%d" % (li, k, s), COL_PROPS, M["iron"],
                      [(0, 0), (0.035, 0.0), (0.028, 0.028), (0.012, 0.042), (0, 0.045)],
                      segments=10, matrix=Matrix.Translation((px, yf - 0.075, zz)) @
                      Matrix.Rotation(R(-90), 4, "X"))
    # ring knocker
    lathe("SM_Knocker", COL_PROPS, M["iron"],
          [(0.055, 0.0), (0.062, 0.012), (0.055, 0.024)] + [(0.05, 0.03)],
          segments=24,
          matrix=Matrix.Translation((mid + 0.30, yf - 0.10, 1.10)) @ Matrix.Rotation(R(-90), 4, "X"))
    # wooden handle plates
    for side in (-1, 1):
        px = mid + side * 0.12
        bbox("SM_Door_Plate_%d" % side, COL_PROPS, M["iron"], (px - 0.05, yf - 0.085, 0.95),
             (px + 0.05, yf - 0.06, 1.45), bevel=0.012, seg=2)


def lattice_panel(name, col, M, lo, hi, axis="Y", vstep=0.085, hstep=0.62):
    """Wooden mashrabiya grid filling a rect. axis = normal axis of the panel."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    # outer frame
    bbox(name + "_F0", col, M["lattice"], (x0, y0, z0), (x1, y1, z0 + 0.07))
    bbox(name + "_F1", col, M["lattice"], (x0, y0, z1 - 0.07), (x1, y1, z1))
    if axis == "Y":
        midy = (y0 + y1) * 0.5
        bbox(name + "_F2", col, M["lattice"], (x0, y0, z0), (x0 + 0.07, y1, z1))
        bbox(name + "_F3", col, M["lattice"], (x1 - 0.07, y0, z0), (x1, y1, z1))
        span = x1 - x0 - 0.14
        n = max(3, int(span / vstep))
        for k in range(n):
            px = x0 + 0.07 + span * (k + 0.5) / n
            bbox("%s_V%02d" % (name, k), col, M["lattice"],
                 (px - 0.014, midy - 0.030, z0 + 0.07), (px + 0.014, midy + 0.030, z1 - 0.07))
        m = max(2, int((z1 - z0 - 0.14) / hstep))
        for k in range(1, m):
            pz = z0 + 0.07 + (z1 - z0 - 0.14) * k / m
            bbox("%s_H%02d" % (name, k), col, M["lattice"],
                 (x0 + 0.07, midy - 0.024, pz - 0.016), (x1 - 0.07, midy + 0.024, pz + 0.016))
    else:
        midx = (x0 + x1) * 0.5
        bbox(name + "_F2", col, M["lattice"], (x0, y0, z0), (x1, y0 + 0.07, z1))
        bbox(name + "_F3", col, M["lattice"], (x0, y1 - 0.07, z0), (x1, y1, z1))
        span = y1 - y0 - 0.14
        n = max(3, int(span / vstep))
        for k in range(n):
            py = y0 + 0.07 + span * (k + 0.5) / n
            bbox("%s_V%02d" % (name, k), col, M["lattice"],
                 (midx - 0.030, py - 0.014, z0 + 0.07), (midx + 0.030, py + 0.014, z1 - 0.07))
        m = max(2, int((z1 - z0 - 0.14) / hstep))
        for k in range(1, m):
            pz = z0 + 0.07 + (z1 - z0 - 0.14) * k / m
            bbox("%s_H%02d" % (name, k), col, M["lattice"],
                 (midx - 0.024, y0 + 0.07, pz - 0.016), (midx + 0.024, y1 - 0.07, pz + 0.016))


def cloth_panel(name, col, mat, x0, x1, z0, z1, y, amp=0.045, freq=3.0, droop=0.06,
                nx=18, nz=14, thick=0.0):
    """Hanging woven rug / textile with soft ripples."""
    verts, faces = [], []
    for j in range(nz + 1):
        tz = j / nz
        z = z0 + (z1 - z0) * tz
        for i in range(nx + 1):
            tx = i / nx
            x = x0 + (x1 - x0) * tx
            yy = y + amp * math.sin(freq * math.pi * tx) * (0.30 + 0.70 * math.sin(math.pi * tz))
            yy += amp * 0.5 * math.sin(freq * 2.3 * math.pi * tz)
            zz = z - droop * math.sin(math.pi * tx) * (1.0 - tz) ** 1.5
            verts.append((x, yy, zz))
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_obj(name, bm, col, mat, True)


def build_windows(M):
    # ---- lower window
    x0, x1, z0, z1 = WIN
    bbox("SM_Win_Recess", COL_PROPS, M["dark"], (x0, 0.28, z0), (x1, 0.34, z1))
    lattice_panel("SM_Win_Mash", COL_PROPS, M, (x0 + 0.03, 0.13, z0 + 0.02),
                  (x1 - 0.03, 0.21, z1 - 0.02))
    bbox("SM_Win_Sill", COL_PROPS, M["stone"], (x0 - 0.14, -0.10, z0 - 0.09),
         (x1 + 0.14, 0.30, z0 + 0.01), bevel=0.02, seg=2)
    bbox("SM_Win_Head", COL_PROPS, M["palm"], (x0 - 0.18, -0.12, z1 + 0.04),
         (x1 + 0.18, 0.30, z1 + 0.17), bevel=0.02, seg=2)
    # shutters folded back against the wall
    for side, xx in ((-1, x0 - 0.02), (1, x1 + 0.02)):
        bbox("SM_Win_Shutter_%d" % side, COL_PROPS, M["door"],
             (xx - 0.30 if side < 0 else xx, -0.06, z0 + 0.04),
             (xx if side < 0 else xx + 0.30, 0.03, z1 - 0.04))

    # ---- upper facade window
    ux0, ux1, uz0, uz1 = UWIN
    yy = UY0
    bbox("SM_UWin_Recess", COL_PROPS, M["dark"], (ux0, yy + 0.22, uz0), (ux1, yy + 0.28, uz1))
    lattice_panel("SM_UWin_Mash", COL_PROPS, M, (ux0 + 0.03, yy + 0.06, uz0 + 0.02),
                  (ux1 - 0.03, yy + 0.14, uz1 - 0.02))
    bbox("SM_UWin_Sill", COL_PROPS, M["stone"], (ux0 - 0.16, yy - 0.12, uz0 - 0.10),
         (ux1 + 0.16, yy + 0.26, uz0 + 0.01), bevel=0.02, seg=2)
    bbox("SM_UWin_Head", COL_PROPS, M["palm"], (ux0 - 0.20, yy - 0.14, uz1 + 0.04),
         (ux1 + 0.20, yy + 0.26, uz1 + 0.18), bevel=0.02, seg=2)


def build_balcony(M):
    """Wooden lattice balcony (شناشيل) on the L2 east facade, over the terrace."""
    bx0, bx1 = UX1, UX1 + 1.05
    by0, by1 = 1.45, 4.35
    fz, rz = 4.62, 5.92
    bbox("SM_Balc_Floor", COL_HOUSE, M["palm"], (bx0 - 0.05, by0, fz - 0.14), (bx1, by1, fz),
         bevel=0.02, seg=2)
    bbox("SM_Balc_Roof", COL_HOUSE, M["palm"], (bx0 - 0.05, by0 - 0.10, rz), (bx1 + 0.10, by1 + 0.10, rz + 0.14),
         bevel=0.02, seg=2)
    # corner posts
    for (px, py) in ((bx1 - 0.09, by0 + 0.06), (bx1 - 0.09, by1 - 0.09),
                     (bx0 + 0.10, by0 + 0.06), (bx0 + 0.10, by1 - 0.09)):
        bbox("SM_Balc_Post_%.2f_%.2f" % (px, py), COL_HOUSE, M["palm"],
             (px - 0.055, py - 0.055, fz), (px + 0.055, py + 0.055, rz))
    # lattice sides: front (east face) + two returns
    lattice_panel("SM_Balc_Lat_E", COL_PROPS, M, (bx1 - 0.10, by0 + 0.05, fz + 0.05),
                  (bx1 - 0.01, by1 - 0.05, rz - 0.02), axis="X", vstep=0.10)
    lattice_panel("SM_Balc_Lat_S", COL_PROPS, M, (bx0 + 0.05, by0 + 0.05, fz + 0.05),
                  (bx1 - 0.02, by0 + 0.14, rz - 0.02), axis="Y", vstep=0.10)
    lattice_panel("SM_Balc_Lat_N", COL_PROPS, M, (bx0 + 0.05, by1 - 0.14, fz + 0.05),
                  (bx1 - 0.02, by1 - 0.05, rz - 0.02), axis="Y", vstep=0.10)
    # inner dark
    bbox("SM_Balc_Dark", COL_PROPS, M["dark"], (bx0 - 0.02, by0 + 0.05, fz + 0.05),
         (bx0 + 0.02, by1 - 0.05, rz - 0.05))


# =============================================================================
#  external staircase
# =============================================================================
def build_stairs(M):
    x0, x1 = HW + 0.10, 6.15       # outer edge
    y0 = -4.55
    steps = 14
    rise = H1 / steps
    run = 4.55 / steps
    for i in range(steps):
        a = y0 + i * run
        b = y0 + (i + 1) * run
        top = (i + 1) * rise
        o = bbox("SM_Step_%02d" % i, COL_HOUSE, M["wall2"], (x0, a, 0.0), (x1, b, top),
                 bevel=0.025, seg=2)
        add_bevel(o, 0.01, 1)
        # outer stepped railing wall
        r = bbox("SM_StairWall_%02d" % i, COL_HOUSE, M["wall2"], (x1, a, 0.0),
                 (x1 + 0.24, b, top + 0.78), bevel=0.025, seg=2)
        add_bevel(r, 0.01, 1)
    # landing at the top, connecting to the terrace
    bbox("SM_Stair_Landing", COL_HOUSE, M["wall2"], (x0, 0.0, 0.0), (x1, 1.25, H1),
         bevel=0.03, seg=2)
    bbox("SM_Stair_LandingWall", COL_HOUSE, M["wall2"], (x1, 0.0, 0.0), (x1 + 0.24, 1.25, H1 + 0.78),
         bevel=0.03, seg=2)
    # opening in L1 parapet where the stair arrives (short parapet posts)
    bbox("SM_Par_Post_A", COL_HOUSE, M["wall"], (HW - 0.18, 1.18, H1), (HW + 0.10, 1.42, H1 + PAR),
         bevel=0.02, seg=2)


# =============================================================================
#  roof terrace: arish shade, pots
# =============================================================================
def build_terrace(M):
    # عريش : palm frond shade
    ax0, ax1 = 2.05, 4.35
    ay0, ay1 = 1.20, 4.30
    pz = H1 + 2.05
    for (px, py) in ((ax0 + 0.10, ay0 + 0.10), (ax1 - 0.10, ay0 + 0.10),
                     (ax0 + 0.10, ay1 - 0.10), (ax1 - 0.10, ay1 - 0.10)):
        beam("SM_Arish_Post_%.1f_%.1f" % (px, py), COL_HOUSE, M["palm"], (px, py, H1),
             (px, py, pz + 0.1), 0.075, 0.068, seg=8)
    # main beams
    for k in range(5):
        yy = ay0 + (ay1 - ay0) * k / 4.0
        beam("SM_Arish_BeamY_%d" % k, COL_HOUSE, M["palm"], (ax0 - 0.15, yy, pz),
             (ax1 + 0.15, yy, pz), 0.055, 0.05, seg=7)
    for k in range(6):
        xx = ax0 + (ax1 - ax0) * k / 5.0
        beam("SM_Arish_BeamX_%d" % k, COL_HOUSE, M["palm"], (xx, ay0 - 0.20, pz + 0.11),
             (xx, ay1 + 0.20, pz + 0.11), 0.045, 0.042, seg=6)
    # frond mats
    for k in range(5):
        yy = ay0 + (ay1 - ay0) * (k + 0.5) / 5.0
        bbox("SM_Arish_Mat_%d" % k, COL_HOUSE, M["dry"], (ax0 - 0.20, yy - 0.22, pz + 0.13),
             (ax1 + 0.20, yy + 0.22, pz + 0.17), bevel=0.008, seg=1)
    # roof clutter
    lathe_pot("SM_Terrace_Pot_A", COL_PROPS, M["clay"], (3.05, 5.60, H1), 0.55)
    lathe_pot("SM_Terrace_Pot_B", COL_PROPS, M["clay2"], (2.55, 5.95, H1), 0.40)
    bbox("SM_Terrace_Mat_Roll", COL_PROPS, M["dry"], (3.55, 5.30, H1),
         (3.85, 6.15, H1 + 0.30), bevel=0.05, seg=2)
    # low parapet lamp
    beam("SM_Terrace_Pole", COL_PROPS, M["palm"], (1.15, 6.55, H1), (1.15, 6.55, H1 + 1.5), 0.05, 0.04, seg=8)


# =============================================================================
#  courtyard walls, gate
# =============================================================================
def build_courtyard(M):
    H = 2.30
    # west / east / south walls
    for name, lo, hi in (
        ("SM_CourtWall_W", (-7.0, -9.0, 0.0), (-6.55, 0.0, H)),
        ("SM_CourtWall_E", (6.55, -9.0, 0.0), (7.0, 0.0, H)),
    ):
        o = bbox(name, COL_COURT, M["court"], lo, hi, bevel=0.03, seg=2)
        adobe_surface(o, 0.012, 2)
    # south wall with gate opening
    wall("SM_CourtWall_S", COL_COURT, M["court"], (-7.0, -9.0, 0.0), (7.0, -8.55, H),
         holes=[((-1.35, -10.0, -0.5), (1.35, -8.0, 2.38))])
    # gate posts + lintel
    bbox("SM_Gate_Post_L", COL_COURT, M["court"], (-1.55, -9.10, 0.0), (-1.30, -8.45, 2.85),
         bevel=0.02, seg=2)
    bbox("SM_Gate_Post_R", COL_COURT, M["court"], (1.30, -9.10, 0.0), (1.55, -8.45, 2.85),
         bevel=0.02, seg=2)
    bbox("SM_Gate_Lintel", COL_PROPS, M["palm"], (-1.62, -9.05, 2.38), (1.62, -8.50, 2.62),
         bevel=0.02, seg=2)
    # gate doors (two leaves)
    for side, (a, b) in enumerate(((-1.32, -0.02), (0.02, 1.32))):
        bbox("SM_Gate_Leaf_%d" % side, COL_PROPS, M["lattice"], (a, -8.90, 0.03), (b, -8.80, 2.34))
        for k in range(3):
            zz = 0.45 + k * 0.70
            bbox("SM_Gate_Rail_%d_%d" % (side, k), COL_PROPS, M["iron"],
                 (a + 0.03, -8.945, zz - 0.04), (b - 0.03, -8.90, zz + 0.04))
            for s in range(4):
                px = a + 0.12 + (b - a - 0.24) * s / 3.0
                lathe("SM_Gate_Stud_%d_%d_%d" % (side, k, s), COL_PROPS, M["iron"],
                      [(0, 0), (0.03, 0.0), (0.024, 0.024), (0.011, 0.036), (0, 0.038)],
                      segments=8, matrix=Matrix.Translation((px, -8.945, zz)) @
                      Matrix.Rotation(R(90), 4, "X"))
    # coping on courtyard walls
    bbox("SM_Court_Coping_W", COL_COURT, M["court"], (-7.06, -9.0, H), (-6.49, 0.02, H + 0.10),
         bevel=0.03, seg=2)
    bbox("SM_Court_Coping_E", COL_COURT, M["court"], (6.49, -9.0, H), (7.06, 0.02, H + 0.10),
         bevel=0.03, seg=2)
    bbox("SM_Court_Coping_S", COL_COURT, M["court"], (-7.06, -9.06, H), (7.06, -8.49, H + 0.10),
         bevel=0.03, seg=2)
    # decoration on the outer face of the south wall: frieze + niches
    for k in range(21):
        cx = -4.55 + k * 0.455
        if abs(cx) < 1.55:
            continue
        tri_prism("SM_Court_Tri_%d" % k, COL_COURT, M["gypsum"],
                  cx=cx, base_z=1.94, y=-9.062, w=0.105, h=0.15, depth=0.018)
    for side in (-1, 1):
        bbox("SM_Court_Niche_%d" % side, COL_COURT, M["dark"],
             (side * 3.6 - 0.24, -9.062, 0.78), (side * 3.6 + 0.24, -9.050, 1.30))
        bbox("SM_Court_Niche_Frame_%d" % side, COL_PROPS, M["palm"],
             (side * 3.6 - 0.34, -9.075, 0.68), (side * 3.6 + 0.34, -9.050, 0.79))


# =============================================================================
#  props
# =============================================================================
def lathe_pot(name, col, mat, base, s=1.0, seed=0):
    prof = [(0, 0.0), (0.16, 0.02), (0.27, 0.16), (0.31, 0.38), (0.25, 0.56),
            (0.185, 0.65), (0.185, 0.70), (0.155, 0.70), (0.155, 0.57),
            (0.20, 0.38), (0.22, 0.16), (0.135, 0.08), (0, 0.06)]
    prof = [(r * s, z * s) for (r, z) in prof]
    M = Matrix.Translation(base) @ Matrix.Rotation(R(random.uniform(0, 360)), 4, "Z")
    return lathe(name, col, mat, prof, segments=28, matrix=M)


def build_props(M):
    # ---- دكّة : mud bench along the facade
    bbox("SM_Bench_Base", COL_PROPS, M["wall2"], (-1.25, -1.42, 0.0), (0.95, -0.52, 0.46),
         bevel=0.035, seg=2)
    bbox("SM_Bench_Top", COL_PROPS, M["wall2"], (-1.32, -1.49, 0.46), (1.02, -0.47, 0.54),
         bevel=0.03, seg=2)
    # cushions + bolsters
    bbox("SM_Cushion_A", COL_PROPS, M["cushion"], (-1.15, -1.32, 0.54), (-0.15, -0.58, 0.86),
         bevel=0.06, seg=3)
    bbox("SM_Cushion_B", COL_PROPS, M["cushion"], (-0.02, -1.32, 0.54), (0.88, -0.58, 0.86),
         bevel=0.06, seg=3)
    for k, px in enumerate((-1.05, -0.05, 0.72)):
        beam("SM_Bolster_%d" % k, COL_PROPS, M["cushion"], (px - 0.17, -0.95, 0.86),
             (px + 0.17, -0.95, 0.86), 0.15, 0.15, seg=14)
    # rug thrown over the bench
    bbox("SM_Rug_Bench_Top", COL_PROPS, M["rug"], (-1.34, -1.50, 0.885), (1.02, -0.98, 0.915),
         bevel=0.012, seg=1)
    cloth_panel("SM_Rug_Bench_Drape", COL_PROPS, M["rug"], -1.32, 1.00, 0.58, 0.90, -1.50,
                amp=0.028, freq=2.4, droop=0.05, nx=16, nz=8)

    # ---- clay water jars (زير)
    lathe_pot("SM_Jar_A", COL_PROPS, M["clay"], (-5.05, -1.55, 0.0), 1.15, seed=1)
    lathe_pot("SM_Jar_B", COL_PROPS, M["clay2"], (-5.75, -2.35, 0.0), 0.78, seed=2)
    lathe_pot("SM_Jar_C", COL_PROPS, M["clay"], (2.45, -0.85, 0.0), 0.55, seed=3)
    lathe_pot("SM_Jar_D", COL_PROPS, M["clay2"], (3.10, -1.35, 0.0), 0.72, seed=4)
    # jar lids / a bowl
    lathe("SM_Bowl", COL_PROPS, M["clay"],
          [(0, 0), (0.14, 0.01), (0.20, 0.10), (0.19, 0.11), (0.135, 0.03), (0, 0.02)],
          segments=22, matrix=Matrix.Translation((-5.05, -1.55, 0.80)))

    # ---- hanging rug on the facade (woven textile)
    cloth_panel("SM_Rug_Wall", COL_PROPS, M["rug"], 2.55, 4.25, 0.95, 2.25, -0.03,
                amp=0.055, freq=3.5, droop=0.07, nx=22, nz=18)
    bbox("SM_Rug_Rod", COL_PROPS, M["palm"], (2.45, -0.09, 2.25), (4.35, -0.02, 2.32))

    # ---- wooden ladder leaning on the facade
    lx = 3.55
    beam("SM_Ladder_R0", COL_PROPS, M["palm"], (lx - 0.22, -1.35, 0.0), (lx - 0.22, -0.02, 2.75), 0.035, 0.032, seg=6)
    beam("SM_Ladder_R1", COL_PROPS, M["palm"], (lx + 0.22, -1.35, 0.0), (lx + 0.22, -0.02, 2.75), 0.035, 0.032, seg=6)
    for k in range(7):
        t = (k + 0.6) / 7.4
        p = Vector((lx, -1.35 + 1.33 * t, 2.75 * t))
        beam("SM_Ladder_Rung_%d" % k, COL_PROPS, M["palm"], (p.x - 0.22, p.y, p.z),
             (p.x + 0.22, p.y, p.z), 0.024, 0.024, seg=6)

    # ---- palm rib bundle (حزمة جريد) leaning on the east court wall
    for k in range(9):
        a = random.uniform(-0.10, 0.10)
        beam("SM_Ribs_%d" % k, COL_PROPS, M["dry"],
             (6.30 + a, -2.6 + a, 0.0), (6.05 + a * 2, -1.9 + a * 2, 2.15 + random.uniform(-0.1, 0.1)),
             0.028, 0.022, seg=5)

    # ---- firewood stack
    for k in range(11):
        zz = 0.09 + (k // 4) * 0.17
        xx = -4.42 + (k % 4) * 0.22 + random.uniform(-0.02, 0.02)
        beam("SM_Wood_%d" % k, COL_PROPS, M["palm"], (xx, -1.10 - (k // 4) * 0.10, zz),
             (xx, -0.62, zz), 0.075, 0.06, seg=7)

    # ---- door mat (palm mat)
    bbox("SM_Door_Mat", COL_PROPS, M["dry"], (-3.05, -0.95, 0.02), (-1.72, -0.12, 0.05),
         bevel=0.008, seg=1)

    # ---- well (بئر) with wooden crossbeam
    wx, wy = 1.95, -5.70
    for k in range(18):
        a = 2 * math.pi * k / 18
        rock("SM_Well_Stone_%d" % k, COL_PROPS, M["stone"],
             (wx + 1.02 * math.cos(a), wy + 1.02 * math.sin(a), 0.20),
             (0.30, 0.26, 0.34), seed=200 + k, rough=0.09)
    lathe("SM_Well_Rim", COL_PROPS, M["stone"],
          [(0.98, 0.05), (1.02, 0.44), (0.90, 0.46), (0.88, 0.06)], segments=26,
          matrix=Matrix.Translation((wx, wy, 0.0)))
    bbox("SM_Well_Dark", COL_PROPS, M["dark"], (wx - 0.95, wy - 0.95, 0.30), (wx + 0.95, wy + 0.95, 0.32))
    for side in (-1, 1):
        beam("SM_Well_Post_%d" % side, COL_PROPS, M["palm"], (wx + side * 1.12, wy, 0.0),
             (wx + side * 1.12, wy, 2.25), 0.07, 0.06, seg=8)
    beam("SM_Well_Cross", COL_PROPS, M["palm"], (wx - 1.30, wy, 2.18), (wx + 1.30, wy, 2.18), 0.06, 0.06, seg=8)
    beam("SM_Well_Rope", COL_PROPS, M["dry"], (wx, wy, 1.55), (wx, wy, 2.18), 0.018, 0.018, seg=5)
    lathe("SM_Well_Bucket", COL_PROPS, M["clay"],
          [(0, 0), (0.13, 0.02), (0.16, 0.30), (0.14, 0.32), (0.12, 0.28), (0, 0.26)],
          segments=16, matrix=Matrix.Translation((wx, wy, 1.20)))

    # ---- clay bread oven (تنور) + extra water jars along the west wall
    tx, ty = -5.45, -4.55
    lathe("SM_Tannour", COL_PROPS, M["clay"],
          [(0, 0), (0.40, 0.02), (0.46, 0.22), (0.44, 0.42), (0.34, 0.60),
           (0.20, 0.72), (0.15, 0.73), (0.145, 0.66), (0, 0.60)],
          segments=24, matrix=Matrix.Translation((tx, ty, 0.0)))
    bbox("SM_Tannour_Hole", COL_PROPS, M["dark"], (tx - 0.16, ty - 0.47, 0.10),
         (tx + 0.16, ty - 0.36, 0.40))
    lathe_pot("SM_Jar_E", COL_PROPS, M["clay2"], (-6.10, -2.55, 0.0), 0.92, seed=5)
    lathe_pot("SM_Jar_F", COL_PROPS, M["clay"], (-6.05, -6.05, 0.0), 0.68, seed=6)

    # ---- oil lamps on the bench
    for k, px in enumerate((-0.75, 0.10, 0.75)):
        lathe("SM_OilLamp_%d" % k, COL_PROPS, M["clay"],
              [(0, 0), (0.10, 0.01), (0.13, 0.10), (0.09, 0.16), (0.05, 0.17), (0, 0.06)],
              segments=18, matrix=Matrix.Translation((px, -0.98, 0.54)))

    # ---- tree: palm
    build_palm(-7.95, -11.30, 7.4, M, "SM_Palm_A")
    build_palm(5.75, -7.85, 5.9, M, "SM_Palm_B")
    build_tree(5.35, -3.05, 3.3, M, "SM_Sidr")
    build_tree(-6.75, -11.60, 2.9, M, "SM_Sidr_B")


def build_palm(px, py, height, M, name):
    n = 22
    prof = []
    for i in range(n + 1):
        t = i / n
        r = 0.24 * (1 - 0.36 * t) + (0.012 if i % 2 == 0 else 0.0)
        prof.append((r, t * height))
    lathe(name + "_Trunk", COL_PROPS, M["trunk"], prof, segments=14,
          matrix=Matrix.Translation((px, py, 0.0)), smooth=False)
    crown = Vector((px, py, height))
    rnd = random.Random(int(px * 100) + 7)
    nf = 26
    for i in range(nf):
        ang = 2 * math.pi * i / nf + rnd.uniform(-0.09, 0.09)
        tilt = rnd.uniform(0.55, 1.15)
        L = rnd.uniform(1.9, 2.8)
        frond(name + "_Frond_%02d" % i, COL_PROPS, M["leaf"], crown, ang, tilt, L,
              rnd.uniform(0.26, 0.38))
    # inner upright crown fronds
    for i in range(7):
        ang = 2 * math.pi * i / 7 + 0.4
        frond(name + "_FrondUp_%02d" % i, COL_PROPS, M["leaf"], crown + Vector((0, 0, 0.05)),
              ang, rnd.uniform(1.25, 1.6), rnd.uniform(1.1, 1.5), rnd.uniform(0.16, 0.24))
    # dates
    for i in range(7):
        a = 2 * math.pi * i / 7
        rock(name + "_Date_%d" % i, COL_PROPS, M["clay2"],
             (px + 0.30 * math.cos(a), py + 0.30 * math.sin(a), height - 0.42),
             (0.09, 0.09, 0.13), seed=300 + i, rough=0.05, smooth=True)


def frond(name, col, mat, base, ang, tilt, length, width):
    steps = 18
    verts, faces = [], []
    side = Vector((-math.sin(ang), math.cos(ang), 0))
    horiz = Vector((math.cos(ang), math.sin(ang), 0))
    for i in range(steps + 1):
        t = i / steps
        d = length * t
        z = (tilt * length * t) - (1.75 * length * t * t * t)
        p = base + horiz * d + Vector((0, 0, z))
        env = math.sin(math.pi * min(1.0, 0.10 + 0.90 * t)) ** 0.5
        w = width * env * (1 - 0.45 * t)
        zig = 0.030 if i % 2 == 0 else -0.008
        verts.append(p + side * (w * 0.5 + zig) + Vector((0, 0, 0.02)))
        verts.append(p - side * (w * 0.5 - zig) + Vector((0, 0, -0.02)))
    for i in range(steps):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_obj(name, bm, col, mat, True)


def build_tree(px, py, height, M, name):
    beam(name + "_Trunk", COL_PROPS, M["trunk"], (px, py, 0.0), (px + 0.10, py - 0.05, height * 0.50),
         0.16, 0.10, seg=10)
    rnd = random.Random(int(px * 37) + 11)
    for i in range(4):
        a = 2 * math.pi * i / 4 + rnd.uniform(-0.4, 0.4)
        tip = Vector((px + 0.10 + math.cos(a) * height * 0.24,
                      py - 0.05 + math.sin(a) * height * 0.24,
                      height * 0.50 + height * 0.14))
        beam(name + "_Branch_%d" % i, COL_PROPS, M["trunk"],
             (px + 0.10, py - 0.05, height * 0.46), tip, 0.08, 0.04, seg=8)
    for i in range(6):
        a = 2 * math.pi * i / 6
        rock(name + "_Canopy_%d" % i, COL_PROPS, M["leaf2"],
             (px + 0.10 + math.cos(a) * height * 0.20,
              py - 0.05 + math.sin(a) * height * 0.20,
              height * 0.70 + rnd.uniform(-0.10, 0.12)),
             (height * 0.27, height * 0.25, height * 0.13), seed=400 + i, cuts=2, rough=0.18)


# =============================================================================
#  lanterns
# =============================================================================
def build_lanterns(M):
    """Hanging iron+glass oil lanterns."""
    def lantern(name, x, y, z, s=1.0):
        # top cap
        lathe(name + "_Cap", COL_PROPS, M["iron"],
              [(0, 0), (0.02 * s, 0.0), (0.115 * s, 0.045 * s), (0.10 * s, 0.075 * s), (0, 0.075 * s)],
              segments=12, matrix=Matrix.Translation((x, y, z + 0.19 * s)))
        # glass body
        lathe(name + "_Glass", COL_PROPS, M["glow"],
              [(0, 0), (0.085 * s, 0.005 * s), (0.105 * s, 0.09 * s), (0.075 * s, 0.18 * s), (0, 0.19 * s)],
              segments=12, matrix=Matrix.Translation((x, y, z)))
        # bottom cap
        lathe(name + "_Base", COL_PROPS, M["iron"],
              [(0, 0), (0.09 * s, 0.005 * s), (0.07 * s, 0.035 * s), (0, 0.04 * s)],
              segments=12, matrix=Matrix.Translation((x, y, z - 0.035 * s)))
        # corner bars
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            beam("%s_Bar_%d" % (name, k), COL_PROPS, M["iron"],
                 (x + 0.075 * s * math.cos(a), y + 0.075 * s * math.sin(a), z - 0.01),
                 (x + 0.095 * s * math.cos(a), y + 0.095 * s * math.sin(a), z + 0.185 * s),
                 0.010 * s, 0.010 * s, seg=5)
        # hanger ring
        lathe(name + "_Ring", COL_PROPS, M["iron"],
              [(0.030 * s, 0), (0.038 * s, 0.008), (0.030 * s, 0.016)], segments=10,
              matrix=Matrix.Translation((x, y, z + 0.265 * s)) @ Matrix.Rotation(R(90), 4, "X"))
        # flame
        lathe(name + "_Flame", COL_PROPS, M["flame"],
              [(0, 0), (0.022 * s, 0.006), (0.015 * s, 0.05 * s), (0, 0.075 * s)],
              segments=8, matrix=Matrix.Translation((x, y, z + 0.04 * s)))
        return (x, y, z)

    # ---- by the door: iron bracket driven into the wall
    bbox("SM_Lantern_Bracket", COL_PROPS, M["iron"], (-1.50, -0.32, 2.70), (-1.40, -0.02, 2.79))
    beam("SM_Lantern_Arm", COL_PROPS, M["iron"], (-1.45, -0.02, 2.74), (-1.45, -0.36, 2.74),
         0.017, 0.017, seg=6)
    beam("SM_Lantern_Arm2", COL_PROPS, M["iron"], (-1.45, -0.30, 2.74), (-1.45, -0.30, 2.60), 0.014, 0.014, seg=5)
    lantern("SM_Lantern_A", -1.45, -0.30, 2.28, 1.0)

    # ---- standing courtyard lantern on a wooden post
    sx, sy = 3.55, -4.35
    beam("SM_Court_Pole", COL_PROPS, M["palm"], (sx, sy, 0.0), (sx, sy, 2.62), 0.065, 0.052, seg=8)
    beam("SM_Court_Arm", COL_PROPS, M["palm"], (sx, sy, 2.56), (sx - 0.46, sy, 2.56), 0.038, 0.030, seg=6)
    beam("SM_Court_Brace", COL_PROPS, M["palm"], (sx, sy, 2.10), (sx - 0.44, sy, 2.54), 0.022, 0.020, seg=5)
    beam("SM_Court_Hook", COL_PROPS, M["iron"], (sx - 0.44, sy, 2.56), (sx - 0.44, sy, 2.46), 0.010, 0.010, seg=5)
    lantern("SM_Lantern_B", sx - 0.44, sy, 2.14, 1.05)


# =============================================================================
#  world + lights + cameras + render
# =============================================================================
def setup_world():
    w = bpy.data.worlds.new("WORLD_GoldenHour")
    SC.world = w
    if hasattr(w, "use_nodes"):
        w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (500, 0)
    bg = nt.nodes.new("ShaderNodeBackground"); bg.location = (300, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-700, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-500, 0)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (-320, 0)
    seti(mr, "From Min", -0.02); seti(mr, "From Max", 0.105)
    seti(mr, "To Min", 0.0); seti(mr, "To Max", 1.0)
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-120, 0)
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0;  cr.elements[0].color = srgb("#f6b06a")
    cr.elements[1].position = 0.22; cr.elements[1].color = srgb("#efc79a")
    e = cr.elements.new(0.48); e.color = srgb("#c2c6c4")
    e = cr.elements.new(0.70); e.color = srgb("#8aa8c6")
    e = cr.elements.new(1.0);  e.color = srgb("#4a6f96")
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    seti(bg, "Strength", 1.35)
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


def add_light(name, kind, loc, energy, color, size=0.1, rot=None):
    ld = bpy.data.lights.new(name, type=kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    elif kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld)
    COL_LIGHT.objects.link(ob)
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    return ob


def setup_lights():
    # key: low golden-hour sun from the south-east
    sun_d = bpy.data.lights.new("LGT_Sun_Key", type="SUN")
    sun_d.energy = 4.6
    sun_d.color = (1.0, 0.66, 0.38)
    sun_d.angle = R(1.3)
    sun = bpy.data.objects.new("LGT_Sun_Key", sun_d)
    COL_LIGHT.objects.link(sun)
    d = Vector((-0.70, 0.62, -0.34)).normalized()
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    # sky fill (cool bounce from the opposite side)
    fill = add_light("LGT_Fill_Sky", "AREA", (11.0, -14.0, 12.0), 1500.0, (0.68, 0.80, 1.0), size=24.0)
    d = (Vector((-1.0, 1.2, 2.6)) - Vector(fill.location)).normalized()
    fill.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    # warm bounce on the facade
    bounce = add_light("LGT_Bounce_Sand", "AREA", (-4.0, -9.0, 1.0), 220.0, (1.0, 0.70, 0.42), size=11.0)
    d = (Vector((-1.0, 0.0, 2.0)) - Vector(bounce.location)).normalized()
    bounce.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    # practicals
    add_light("LGT_Lantern_Door", "POINT", (-1.45, -0.30, 2.34), 30.0, (1.0, 0.58, 0.26), 0.08)
    add_light("LGT_Lantern_Court", "POINT", (3.11, -4.35, 2.20), 40.0, (1.0, 0.56, 0.24), 0.08)
    add_light("LGT_OilLamps_Bench", "POINT", (-0.10, -1.02, 0.85), 12.0, (1.0, 0.50, 0.18), 0.05)
    add_light("LGT_Window_Glow", "POINT", (1.50, 0.85, 1.75), 16.0, (1.0, 0.54, 0.24), 0.10)
    add_light("LGT_Well_Lamp", "POINT", (1.95, -4.60, 1.30), 10.0, (1.0, 0.55, 0.22), 0.06)


def add_camera(name, loc, target, lens=40.0, shift_y=0.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.shift_y = shift_y
    ob = bpy.data.objects.new(name, cd)
    COL_CAM.objects.link(ob)
    ob.location = loc
    d = (Vector(target) - Vector(loc)).normalized()
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def setup_cameras():
    hero = add_camera("CAM_Hero_01", (-8.4, -20.4, 6.8), (0.30, 1.20, 3.05), 37.0, shift_y=-0.02)
    add_camera("CAM_Courtyard_02", (-5.60, -7.60, 1.68), (-1.40, 0.50, 2.05), 25.0)
    add_camera("CAM_Door_03", (-0.95, -3.20, 1.55), (-2.65, 0.05, 1.85), 34.0)
    add_camera("CAM_Wide_04", (-14.2, -14.8, 1.85), (-0.40, 2.20, 4.10), 32.0)
    SC.camera = hero
    return hero


def setup_render(res=(1600, 900), samples=96):
    SC.render.engine = "BLENDER_EEVEE"
    SC.render.resolution_x, SC.render.resolution_y = res
    SC.render.resolution_percentage = 100
    SC.render.film_transparent = False
    SC.render.image_settings.file_format = "PNG"
    SC.render.image_settings.color_mode = "RGB"
    SC.render.use_file_extension = True
    try:
        SC.eevee.taa_render_samples = samples
        SC.eevee.taa_samples = 16
        SC.eevee.use_raytracing = True
        SC.eevee.ray_tracing_method = "SCREEN"
        SC.eevee.use_shadows = True
        SC.eevee.shadow_ray_count = 2
        SC.eevee.shadow_step_count = 8
        SC.eevee.use_volumetric_shadows = True
        SC.eevee.volumetric_tile_size = "8"
        SC.eevee.volumetric_samples = 64
        SC.eevee.volumetric_end = 90.0
        SC.eevee.use_fast_gi = True
        SC.eevee.fast_gi_distance = 3.0
    except Exception as e:
        print("eevee settings:", e)
    for vt in ("AgX", "Filmic", "Standard"):
        try:
            SC.view_settings.view_transform = vt
            break
        except Exception:
            continue
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Punchy"):
        try:
            SC.view_settings.look = look
            break
        except Exception:
            continue
    SC.view_settings.exposure = 0.05
    SC.view_settings.gamma = 1.0


def build_atmosphere():
    m, nt, bsdf = base_mat("MAT_Atmosphere_Haze")
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    vol = nt.nodes.new("ShaderNodeVolumePrincipled"); vol.location = (300, 0)
    seti(vol, "Color", srgb("#cfc0a8"))
    seti(vol, "Density", 0.0014)
    seti(vol, "Anisotropy", 0.45)
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    ob = bbox("SM_Atmosphere_Domain", COL_FX, m, (-130, -130, -1.0), (130, 920, 46.0))
    ob.visible_shadow = False
    return ob


def finalize():
    bpy.context.view_layer.update()
    SC.render.filepath = os.path.join(OUT_DIR, "hero")
    n_obj = len(bpy.data.objects)
    n_tri = 0
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data:
            n_tri += len(o.data.polygons)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "folk_house.blend"))
    return {"objects": n_obj, "faces": n_tri,
            "materials": len(bpy.data.materials), "blend": bpy.data.filepath}


def build_all():
    reset_scene()
    init_collections()
    M = build_materials()
    build_ground(M)
    build_house(M)
    build_door(M)
    build_windows(M)
    build_balcony(M)
    build_stairs(M)
    build_terrace(M)
    build_courtyard(M)
    build_props(M)
    build_lanterns(M)
    setup_world()
    setup_lights()
    build_atmosphere()
    setup_cameras()
    setup_render()
    for o in list(bpy.data.collections["_TMP"].objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(bpy.data.collections["_TMP"])
    return finalize()
