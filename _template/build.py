# -*- coding: utf-8 -*-
"""
قالب تصميم Blender — انسخ هذا المجلد وسمّه NNN_اسم_التصميم ثم عدّل BUILD().

التشغيل داخل Blender (أو عبر MCP):
    p = r"...\\designs\\002_my_design\\build.py"
    ns = {"__name__": "__main__", "__file__": p}
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
    ns["main"]()

المبدأ: السكربت يعيد بناء المشهد من الصفر (reset) ثم يحفظ .blend بجانبه.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix

R = math.radians
SCENE = bpy.context.scene
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
BLEND_PATH = os.path.join(HERE, os.path.basename(HERE) + ".blend")
RENDER_DIR = os.path.join(HERE, "renders")
os.makedirs(RENDER_DIR, exist_ok=True)
random.seed(3)


# ---------------------------------------------------------------- scene setup
def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for pool in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.worlds):
        for d in list(pool):
            try:
                pool.remove(d)
            except Exception:
                pass


def coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        SCENE.collection.children.link(c)
    return c


# ---------------------------------------------------------------- primitives
def _obj(name, bm, col, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll(col).objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def box(name, col, mat, lo, hi, bevel=0.0, seg=2):
    """صندوق من زاوية lo إلى hi (إحداثيات عالمية مخبوزة في الميش)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]
    cx, cy, cz = [(lo[i] + hi[i]) * 0.5 for i in range(3)]
    for v in bm.verts:
        v.co.x = v.co.x * sx + cx
        v.co.y = v.co.y * sy + cy
        v.co.z = v.co.z * sz + cz
    ob = _obj(name, bm, col, mat)
    if bevel > 0:
        m = ob.modifiers.new("Bevel", "BEVEL")
        m.width, m.segments, m.limit_method = bevel, seg, "ANGLE"
        m.angle_limit = R(35)
    return ob


def lathe(name, col, mat, profile, segments=24, matrix=None, smooth=True):
    """جسم دوراني: profile = [(radius, z), ...] من الأسفل للأعلى. radius=0 = قطب."""
    verts, faces, poles, rows = [], [], {}, []
    for j, (r, z) in enumerate(profile):
        if abs(r) < 1e-6:
            poles[j] = len(verts)
            verts.append((0.0, 0.0, z))
            rows.append(None)
        else:
            rows.append([])
    for i in range(segments):
        a = 2 * math.pi * i / segments
        ca, sa = math.cos(a), math.sin(a)
        for j, (r, z) in enumerate(profile):
            if abs(r) > 1e-6:
                rows[j].append(len(verts))
                verts.append((r * ca, r * sa, z))

    def g(i, j):
        return poles[j] if abs(profile[j][0]) < 1e-6 else rows[j][i % segments]

    for i in range(segments):
        for j in range(len(profile) - 1):
            quad = []
            for p in (g(i, j), g(i + 1, j), g(i + 1, j + 1), g(i, j + 1)):
                if p not in quad:
                    quad.append(p)
            if len(quad) >= 3:
                faces.append(tuple(quad))
    if profile[0][0] > 1e-6:
        faces.append(tuple(rows[0][i] for i in range(segments - 1, -1, -1)))
    if profile[-1][0] > 1e-6:
        faces.append(tuple(rows[-1][i] for i in range(segments)))
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if matrix is not None:
        bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    return _obj(name, bm, col, mat, smooth)


# ---------------------------------------------------------------- materials
def srgb(hexstr):
    h = hexstr.lstrip("#")
    def f(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(int(h[0:2], 16)), f(int(h[2:4], 16)), f(int(h[4:6], 16)), 1.0)


def material(name, color, rough=0.8, metal=0.0, bump=0.0, noise_scale=20.0):
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = srgb(color) if isinstance(color, str) else color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if bump > 0:
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = noise_scale
        nz.inputs["Detail"].default_value = 8.0
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        bp.inputs["Distance"].default_value = 0.02
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m


# ---------------------------------------------------------------- stage
def setup_world_and_lights():
    w = bpy.data.worlds.new("WORLD")
    SCENE.world = w
    if hasattr(w, "use_nodes"):
        w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.45, 0.55, 0.72, 1.0)
        bg.inputs["Strength"].default_value = 1.0

    sun_d = bpy.data.lights.new("LGT_Sun_Key", type="SUN")
    sun_d.energy = 4.0
    sun_d.color = (1.0, 0.86, 0.72)
    sun_d.angle = R(2.0)
    sun = bpy.data.objects.new("LGT_Sun_Key", sun_d)
    coll("COL_Lights").objects.link(sun)
    d = Vector((-0.6, 0.6, -0.5)).normalized()
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return sun


def add_camera(loc, target, lens=40.0, name="CAM_Hero_01", shift_y=0.0):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_width, cd.shift_y = lens, 36.0, shift_y
    ob = bpy.data.objects.new(name, cd)
    coll("COL_Cameras").objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).normalized().to_track_quat("-Z", "Y").to_euler()
    SCENE.camera = ob
    return ob


def setup_render(res=(1920, 1080), samples=96):
    SCENE.render.engine = "BLENDER_EEVEE"
    SCENE.render.resolution_x, SCENE.render.resolution_y = res
    SCENE.render.resolution_percentage = 100
    SCENE.render.image_settings.file_format = "PNG"
    try:
        SCENE.eevee.taa_render_samples = samples
        SCENE.eevee.use_raytracing = True
    except Exception:
        pass
    for vt in ("AgX", "Filmic", "Standard"):
        try:
            SCENE.view_settings.view_transform = vt
            break
        except Exception:
            continue
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            SCENE.view_settings.look = look
            break
        except Exception:
            continue
    SCENE.view_settings.exposure = 0.15


def render(filename="final_hero.png", res=(1920, 1080), samples=96):
    SCENE.render.resolution_x, SCENE.render.resolution_y = res
    try:
        SCENE.eevee.taa_render_samples = samples
    except Exception:
        pass
    path = os.path.join(RENDER_DIR, filename)
    SCENE.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


# ---------------------------------------------------------------- Build me
def build():
    """← غيّر هذا: كل الهندسة والخامات هنا."""
    M = {
        "ground": material("MAT_Ground", "#c2a97f", 0.95, bump=0.4, noise_scale=12),
        "hero": material("MAT_Hero", "#a86742", 0.6, bump=0.3),
    }
    box("SM_Ground", "COL_Environment", M["ground"], (-20, -20, -0.1), (20, 20, 0.0))
    box("SM_Hero", "COL_Props", M["hero"], (-1, -1, 0.0), (1, 1, 2.0), bevel=0.05, seg=3)
    lathe("SM_Vase", "COL_Props", M["hero"],
          [(0, 0), (0.2, 0.02), (0.3, 0.3), (0.22, 0.6), (0.24, 0.66), (0.2, 0.66),
           (0.19, 0.55), (0.16, 0.05), (0, 0.03)], segments=24,
          matrix=Matrix.Translation((1.6, 0.6, 0.0)))

    setup_world_and_lights()
    add_camera((5.5, -8.0, 3.2), (0.0, 0.0, 1.2), lens=45.0)
    setup_render()


def main():
    reset_scene()
    build()
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return {"blend": BLEND_PATH, "objects": len(bpy.data.objects),
            "materials": len(bpy.data.materials)}


if __name__ == "__main__":
    print(main())
