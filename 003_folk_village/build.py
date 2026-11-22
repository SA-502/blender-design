# -*- coding: utf-8 -*-
"""
003 — قرية شعبية كاملة (للعبة).

تُبنى فوق المشهد الحالي (001 بيت + 002 برج/مجلس) وتضيف:
  • مسجداً شعبياً بقبة ومئذنة وفناء
  • سوقاً شعبياً: شارع بصفَّين من المحلات مع سقائف وأشرطة قماش
  • 12 محلاً بتجهيزات مختلفة: فخار وجرار، بقالة وبهارات، تمور، أقمشة، قهوة،
    أعشاب، أدوات، مقهى
  • بيوتاً شعبية + بوابة القرية + بئر + نخيل + فوانيس + تفاصيل
  • كاميرات جديدة (شارع/جوي/مسجد/سوق) وإضاءة عملية

التشغيل:
    ns = {"__name__": "__main__", "__file__": p}
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
    ns["main_additive"]()

السكربت آمن لإعادة التشغيل: يحذف كل ما اسمه SM3_/LGT_V3_/CAM_V3_ ثم يعيد البناء.
"""
import bpy, bmesh, importlib.util, os
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
FH_PATH = os.path.abspath(os.path.join(HERE, "..", "001_folk_house", "fh_build.py"))
_spec = importlib.util.spec_from_file_location("fh_build", FH_PATH)
fh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fh)

R = fh.R
srgb = fh.srgb
math = fh.math
random = fh.random
Vector = fh.Vector
Matrix = fh.Matrix

# ---------------------------------------------------------------------------
#  إحداثيات القرية (متر)
# ---------------------------------------------------------------------------
STREET_Y0, STREET_Y1 = -22.0, -15.0        # الشارع المعبّد
NORTH_F, NORTH_B = -15.2, -10.2            # صف المحلات الشمالي (واجهته للجنوب)
SOUTH_F, SOUTH_B = -22.2, -27.2            # صف المحلات الجنوبي (واجهته للشمال)
SHOP_H, ROOF_H = 3.2, 3.45                 # ارتفاع المحل والسقف
ARC_D = 1.70                               # عمق السقيفة أمام المحلات
MOSQUE_X0, MOSQUE_X1 = 23.5, 33.5
MOSQUE_Y0, MOSQUE_Y1 = -26.5, -13.5

C_G = C_S = C_M = C_H = C_P = C_L = C_C = None


def init_cols():
    global C_G, C_S, C_M, C_H, C_P, C_L, C_C
    C_G = fh.coll("COL_Village_Ground")
    C_S = fh.coll("COL_Village_Souq")
    C_M = fh.coll("COL_Village_Mosque")
    C_H = fh.coll("COL_Village_Houses")
    C_P = fh.coll("COL_Village_Props")
    C_L = fh.coll("COL_Village_Lights")
    C_C = fh.coll("COL_Village_Cameras")


def clear_previous():
    n = 0
    for o in list(bpy.data.objects):
        if o.name.startswith(("SM3_", "LGT_V3_", "CAM_V3_")):
            bpy.data.objects.remove(o, do_unlink=True)
            n += 1
    for c in list(bpy.data.collections):
        if c.name.startswith("COL_Village") and not c.objects and not c.children:
            bpy.data.collections.remove(c)
    return n


COLL_MAP = {}


def sort_collections():
    """يوزّع SM3_<حرف>_* على مجموعات القرية + الكاميرات والإضاءة."""
    for o in list(bpy.data.objects):
        if o.name.startswith("CAM_V3_"):
            target = C_C
        elif o.name.startswith("LGT_V3_"):
            target = C_L
        elif o.name.startswith("SM3_"):
            parts = o.name.split("_")
            target = COLL_MAP.get(parts[1] if len(parts) > 1 else "P", C_P)
        else:
            continue
        for c in list(o.users_collection):
            if c is not target:
                c.objects.unlink(o)
        if target.objects.get(o.name) is None:
            target.objects.link(o)


# ---------------------------------------------------------------------------
#  الخامات
# ---------------------------------------------------------------------------
FH_MAT_NAMES = {
    "wall": "MAT_Adobe_Wall", "wall2": "MAT_Adobe_Wall_Upper", "court": "MAT_Adobe_CourtWall",
    "floor": "MAT_Mud_Floor", "sand": "MAT_Ground_Sand",
    "palm": "MAT_Wood_Beam", "door": "MAT_Wood_Door", "lattice": "MAT_Wood_Lattice",
    "iron": "MAT_Iron_Stud", "clay": "MAT_Clay_Terracotta", "clay2": "MAT_Clay_Pale",
    "gypsum": "MAT_Gypsum_White", "stone": "MAT_Stone_Grey",
    "leaf": "MAT_Palm_Leaf", "leaf2": "MAT_Tree_Leaf", "dry": "MAT_Palm_Dry",
    "trunk": "MAT_Palm_Trunk", "dark": "MAT_Interior_Dark", "glow": "MAT_Lantern_Glow",
    "flame": "MAT_Flame", "rug": "MAT_Fabric_Rug", "cushion": "MAT_Fabric_Cushion",
}


def fetch_mats():
    M = {}
    for k, nm in FH_MAT_NAMES.items():
        m = bpy.data.materials.get(nm)
        if m is None:
            m = bpy.data.materials.new(nm)
        M[k] = m
    return M


def _get_or_make(name, factory):
    """يعيد إنشاء المادة دائماً حتى تُطبَّق القيم الجديدة عند إعادة البناء."""
    m = bpy.data.materials.get(name)
    if m is not None:
        try:
            bpy.data.materials.remove(m)
        except Exception:
            pass
    return factory()


def village_mats():
    M3 = {}
    M3["pave"] = _get_or_make("MAT_Stone_Pave", lambda: fh.mat_plain("MAT_Stone_Pave", "#a4906f", 0.93, spec=0.18, bump=0.6, bscale=13))
    M3["sack"] = _get_or_make("MAT_Sack_Burlap", lambda: fh.mat_plain("MAT_Sack_Burlap", "#b39463", 0.95, spec=0.15, bump=0.45, bscale=30))
    M3["spice_r"] = _get_or_make("MAT_Spice_Red", lambda: fh.mat_plain("MAT_Spice_Red", "#a8361f", 0.86))
    M3["spice_y"] = _get_or_make("MAT_Spice_Yellow", lambda: fh.mat_plain("MAT_Spice_Yellow", "#d2a11c", 0.86))
    M3["spice_o"] = _get_or_make("MAT_Spice_Orange", lambda: fh.mat_plain("MAT_Spice_Orange", "#c4671a", 0.86))
    M3["spice_g"] = _get_or_make("MAT_Spice_Green", lambda: fh.mat_plain("MAT_Spice_Green", "#6b7a28", 0.86))
    M3["spice_b"] = _get_or_make("MAT_Spice_Brown", lambda: fh.mat_plain("MAT_Spice_Brown", "#5e3d1c", 0.86))
    M3["awn"] = _get_or_make("MAT_Awning_Stripe", lambda: fh.mat_fabric("MAT_Awning_Stripe", [(0.0, "#8f2a20"), (0.42, "#8f2a20"), (0.50, "#dccaa3"), (0.90, "#dccaa3")], scale=1.4))
    M3["awn2"] = _get_or_make("MAT_Awning_Stripe_B", lambda: fh.mat_fabric("MAT_Awning_Stripe_B", [(0.0, "#2a5a48"), (0.42, "#2a5a48"), (0.50, "#dccaa3"), (0.90, "#dccaa3")], scale=1.4))
    M3["brass"] = _get_or_make("MAT_Brass", lambda: fh.mat_plain("MAT_Brass", "#b07d2a", 0.32, metal=1.0, spec=0.7))
    M3["tin"] = _get_or_make("MAT_Tin", lambda: fh.mat_plain("MAT_Tin", "#8f9598", 0.42, metal=1.0, spec=0.6, bump=0.2, bscale=40))
    M3["crate"] = _get_or_make("MAT_Wood_Crate", lambda: fh.mat_wood("MAT_Wood_Crate", "#8a6742", "#5f4429", "#3a2a18", rough=0.8, grain=18))
    M3["date"] = _get_or_make("MAT_Date_Fruit", lambda: fh.mat_plain("MAT_Date_Fruit", "#5e3517", 0.7, spec=0.35))
    M3["basket"] = _get_or_make("MAT_Basket", lambda: fh.mat_plain("MAT_Basket", "#b39058", 0.9, spec=0.2, bump=0.45, bscale=24))
    M3["dome"] = _get_or_make("MAT_Dome_Plaster", lambda: fh.mat_plain("MAT_Dome_Plaster", "#e6dfcd", 0.8, spec=0.3, bump=0.25, bscale=16))
    M3["cloth_b"] = _get_or_make("MAT_Cloth_Blue", lambda: fh.mat_fabric("MAT_Cloth_Blue", [(0.0, "#2c4a6b"), (0.5, "#3d6389"), (0.56, "#d9cfb6")], scale=4.0))
    M3["cloth_g"] = _get_or_make("MAT_Cloth_Green", lambda: fh.mat_fabric("MAT_Cloth_Green", [(0.0, "#2f4a2c"), (0.5, "#436b3d"), (0.56, "#cdbf9a")], scale=4.0))
    M3["cloth_m"] = _get_or_make("MAT_Cloth_Maroon", lambda: fh.mat_fabric("MAT_Cloth_Maroon", [(0.0, "#5c2028"), (0.45, "#7b2f33"), (0.52, "#d8c69e")], scale=4.0))
    return M3


# ---------------------------------------------------------------------------
#  أدوات محلية
# ---------------------------------------------------------------------------
def panel(name, col, mat, corners, smooth=False):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in corners]
    try:
        bm.faces.new(vs)
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return fh.bm_obj(name, bm, col, mat, smooth)


def wall_v(name, col, mat, lo, hi, holes=None):
    return fh.wall(name, col, mat, lo, hi, holes=holes, subdiv=1, disp=0.010, bev=0.022)


def sphere_lathe(name, col, mat, center, r, seg=18, n=10):
    prof = []
    for i in range(n + 1):
        t = math.pi * i / n
        prof.append((r * math.sin(t), -r * math.cos(t)))
    return fh.lathe(name, col, mat, prof, segments=seg, matrix=Matrix.Translation(center), smooth=True)


def cone_lathe(name, col, mat, base, r, h, seg=14):
    return fh.lathe(name, col, mat, [(0, 0), (r, 0), (0, h)], segments=seg,
                    matrix=Matrix.Translation(base), smooth=True)


def dome(name, col, mat, center, rr, hh, seg=32, n=14):
    prof = []
    for i in range(n + 1):
        t = (math.pi / 2) * (1.0 - i / n)
        prof.append((rr * math.sin(t), hh * math.cos(t)))
    return fh.lathe(name, col, mat, prof, segments=seg, matrix=Matrix.Translation(center), smooth=True)


def arch_ring(name, col, mat, cx, cz, r, y, n=12, rad=0.085):
    """قوس في المستوى XZ (جدار يواجه ±Y)."""
    pts = []
    for i in range(n + 1):
        t = math.pi - math.pi * i / n
        pts.append((cx + r * math.cos(t), y, cz + r * math.sin(t)))
    for i in range(n):
        fh.beam("%s_%02d" % (name, i), col, mat, pts[i], pts[i + 1], rad, rad, seg=6)


def arch_ring_x(name, col, mat, x, cy, cz, r, n=12, rad=0.085):
    """قوس في المستوى YZ (جدار يواجه ±X)."""
    pts = []
    for i in range(n + 1):
        t = math.pi - math.pi * i / n
        pts.append((x, cy + r * math.cos(t), cz + r * math.sin(t)))
    for i in range(n):
        fh.beam("%s_%02d" % (name, i), col, mat, pts[i], pts[i + 1], rad, rad, seg=6)


def shop_front_offset(F, s, d):
    """نقطة على مسافة d أمام واجهة المحل."""
    return F - s * d


# ---------------------------------------------------------------------------
#  الأرضية والشارع
# ---------------------------------------------------------------------------
def build_ground(M, M3):
    fh.bbox("SM3_G_Earth", C_G, M["sand"], (-36, -36, -0.14), (38, -9.3, -0.03))
    fh.bbox("SM3_G_Street", C_G, M3["pave"], (-24.0, STREET_Y0, -0.05), (24.0, STREET_Y1, 0.04), bevel=0.06, seg=2)
    # أرصفة جانبية أمام المحلات
    fh.bbox("SM3_G_Kerb_N", C_G, M3["pave"], (-21.0, -15.35, -0.04), (21.0, -14.85, 0.10), bevel=0.03, seg=2)
    fh.bbox("SM3_G_Kerb_S", C_G, M3["pave"], (-21.0, -22.35, -0.04), (21.0, -21.85, 0.10), bevel=0.03, seg=2)
    # ساحة المسجد + ساحة البئر
    fh.bbox("SM3_G_MosqueCourt", C_G, M["floor"], (MOSQUE_X0, MOSQUE_Y0, -0.05), (MOSQUE_X1, MOSQUE_Y1, 0.10), bevel=0.05, seg=2)
    fh.bbox("SM3_G_Plaza", C_G, M["floor"], (-6.2, -15.4, -0.05), (4.2, -10.0, 0.06), bevel=0.06, seg=2)
    # عتبة/درج صغير لدخول ساحة المسجد
    fh.bbox("SM3_G_MosqueStep", C_G, M3["pave"], (MOSQUE_X0 - 1.2, -20.6, -0.04), (MOSQUE_X0 + 0.2, -17.4, 0.12), bevel=0.04, seg=2)


# ---------------------------------------------------------------------------
#  المحلات
# ---------------------------------------------------------------------------
def shop(x0, x1, F, B, kind, idx, tag):
    s = 1.0 if B > F else -1.0          # اتجاه عمق المحل
    fx = lambda d: F + s * d
    col = C_S
    w = x1 - x0
    # جدران أمامية (عضادة يمين/يسار + عتبة علوية)
    wall_v("SM3_S_%s_%02d_JambL" % (tag, idx), col, M_G["wall2"],
           (x0, min(F, fx(0.4)), 0.0), (x0 + 0.35, max(F, fx(0.4)), SHOP_H))
    wall_v("SM3_S_%s_%02d_JambR" % (tag, idx), col, M_G["wall2"],
           (x1 - 0.35, min(F, fx(0.4)), 0.0), (x1, max(F, fx(0.4)), SHOP_H))
    wall_v("SM3_S_%s_%02d_Lintel" % (tag, idx), col, M_G["wall2"],
           (x0 + 0.35, min(F, fx(0.4)), 2.55), (x1 - 0.35, max(F, fx(0.4)), SHOP_H))
    # أرضية المحل
    fh.bbox("SM3_S_%s_%02d_Floor" % (tag, idx), col, M_G["floor"],
            (x0, min(F, B), 0.0), (x1, max(F, B), 0.14), bevel=0.02, seg=1)
    # منضدة العرض
    cy0, cy1 = min(F, fx(0.80)), max(F, fx(0.80))
    fh.bbox("SM3_S_%s_%02d_Counter" % (tag, idx), col, M_G["wall2"],
            (x0 + 0.40, cy0, 0.14), (x1 - 0.40, cy1, 0.85), bevel=0.03, seg=2)
    fh.bbox("SM3_S_%s_%02d_CounterTop" % (tag, idx), col, M_G["palm"],
            (x0 + 0.34, min(cy0, fx(0.90)), 0.85), (x1 - 0.34, max(cy0, fx(0.90)), 0.92), bevel=0.012, seg=1)
    # لافتة خشبية
    fh.bbox("SM3_S_%s_%02d_Sign" % (tag, idx), col, M_G["door"],
            (x0 + 0.55, min(F, fx(-0.06)), 2.58), (x1 - 0.55, max(F, fx(-0.06)), 2.98), bevel=0.015, seg=2)
    # قماش مظلة (ستارة قصيرة) على حافة السقيفة
    if idx % 2 == 0:
        yv = shop_front_offset(F, s, ARC_D + 0.05)
        fh.cloth_panel("SM3_S_%s_%02d_Valance" % (tag, idx),
                       C_P, M3["awn"] if (idx % 4 == 0) else M3["awn2"],
                       x0 + 0.25, x1 - 0.25, 2.42, 2.98, yv, amp=0.02, freq=4.0, droop=0.03, nx=10, nz=6)
    # تجهيزات المحل
    display(kind, x0, x1, F, s, idx, tag)


def display(kind, x0, x1, F, s, idx, tag):
    pr = lambda d: shop_front_offset(F, s, d)
    cx = (x0 + x1) * 0.5
    zc = 0.92  # سطح المنضدة
    if kind == "pottery":
        for i in range(4):
            x = x0 + 0.9 + (x1 - x0 - 1.9) * i / 3.0
            fh.lathe_pot("SM3_P_Pot_%s_%d" % (tag, i), C_P, M_G["clay"],
                         (x, pr(0.35), zc), 0.30 + 0.06 * (i % 2), seed=idx * 7 + i)
        for i in range(5):
            x = x0 + 0.55 + 0.42 * i
            fh.lathe_pot("SM3_P_PotOut_%s_%d" % (tag, i), C_P,
                         M_G["clay"] if i % 2 else M_G["clay2"],
                         (x, pr(-0.02), 0.0), 0.55 + 0.18 * (i % 3), seed=idx * 11 + i)
        # برج أزيار مقلوبة
        for i in range(3):
            fh.lathe_pot("SM3_P_PotStack_%s_%d" % (tag, i), C_P, M_G["clay"],
                         (x1 - 0.75, pr(0.15), 0.0 + i * 0.34), 0.62 - i * 0.12, seed=idx * 5 + i)
    elif kind == "spices":
        spice_mats = [M3["spice_r"], M3["spice_y"], M3["spice_o"], M3["spice_g"], M3["spice_b"]]
        for i in range(5):
            x = x0 + 0.75 + (x1 - x0 - 1.5) * i / 4.0
            sack("SM3_P_Sack_%s_%d" % (tag, i), x, pr(0.05), 0.0, 0.20, 0.52, spice_mats[i % 5])
        for i in range(3):
            x = x0 + 1.1 + 0.9 * i
            fh.lathe("SM3_P_SpiceBox_%s_%d" % (tag, i), C_P, M_G["palm"],
                     [(0, 0), (0.20, 0.0), (0.22, 0.10), (0.20, 0.12), (0, 0.12)],
                     segments=12, matrix=Matrix.Translation((x, pr(0.40), zc)))
            cone_lathe("SM3_P_SpiceMound_%s_%d" % (tag, i), C_P, spice_mats[i],
                       (x, pr(0.40), zc + 0.12), 0.19, 0.13, seg=12)
        balance_scale("SM3_P_Scale_%s" % tag, x1 - 1.0, pr(0.42), zc, M3)
        herbs_hang("SM3_P_Herb_%s" % tag, x0 + 0.7, x1 - 0.7, pr(-0.05), 2.50, M_G)
    elif kind == "dates":
        for i in range(3):
            x = x0 + 1.0 + (x1 - x0 - 2.0) * i / 2.0
            basket("SM3_P_Basket_%s_%d" % (tag, i), x, pr(0.32), zc, 0.26, M3)
        for i in range(2):
            crate("SM3_P_Crate_%s_%d" % (tag, i), x0 + 0.6 + i * 1.0, pr(0.05), 0.0, 0.42, M3, M_G)
    elif kind == "textile":
        mats = [M_G["rug"], M3["cloth_b"], M3["cloth_g"]]
        for i in range(3):
            x = x0 + 0.5 + (x1 - x0 - 1.0) * i / 2.6
            fh.cloth_panel("SM3_P_Carpet_%s_%d" % (tag, i), C_P, mats[i % 3],
                           x, x + 1.15, 0.95, 2.45, pr(-0.04), amp=0.05, freq=3.0, droop=0.06,
                           nx=14, nz=12)
        for i in range(3):
            rug_roll("SM3_P_Roll_%s_%d" % (tag, i), x0 + 2.0 + i * 0.45, pr(0.10), 0.0, 0.9, mats[i % 3], C_P)
    elif kind == "coffee":
        bench("SM3_P_CafeBench_%s" % tag, x0 + 0.5, x1 - 0.5, pr(-0.02), pr(0.55), 0.0, M_G, C_P)
        for i in range(3):
            dallah("SM3_P_Dallah_%s_%d" % (tag, i), x0 + 1.0 + 0.75 * i, pr(0.40), zc, M3, C_P)
        cups_row("SM3_P_Cups_%s" % tag, x0 + 1.4, pr(0.55), zc, 5, M3, C_P)
    elif kind == "grocery":
        sack("SM3_P_RiceSack_%s" % tag, x0 + 0.9, pr(0.05), 0.0, 0.22, 0.58, M3["spice_y"])
        sack("SM3_P_FlourSack_%s" % tag, x0 + 1.45, pr(0.05), 0.0, 0.21, 0.52, M_G["clay2"])
        for i in range(5):
            tins("SM3_P_Tin_%s_%d" % (tag, i), x0 + 2.2 + i * 0.30, pr(0.40), zc + 0.02, 0.10, M3, C_P)
        for i in range(3):
            crate("SM3_P_GCrate_%s_%d" % (tag, i), x1 - 2.0 + i * 0.55, pr(0.02), 0.0, 0.36, M3, M_G)
    elif kind == "herbs":
        herbs_hang("SM3_P_Herb2_%s" % tag, x0 + 0.5, x1 - 0.5, pr(-0.05), 2.55, M_G)
        for i in range(3):
            basket("SM3_P_HBasket_%s_%d" % (tag, i), x0 + 1.0 + 0.8 * i, pr(0.35), zc, 0.22, M3)
        jars_row("SM3_P_HJar_%s" % tag, x0 + 0.8, pr(0.05), 0.0, 4, M_G, C_P)
    elif kind == "cafe":
        bench("SM3_P_CafeB_%s_a" % tag, x0 + 0.4, cx - 0.2, pr(-0.05), pr(0.60), 0.0, M_G, C_P)
        bench("SM3_P_CafeB_%s_b" % tag, cx + 0.2, x1 - 0.4, pr(-0.05), pr(0.60), 0.0, M_G, C_P)
        dallah("SM3_P_CafeDallah_%s" % tag, cx, pr(0.40), zc, M3, C_P)
        cups_row("SM3_P_CafeCups_%s" % tag, cx - 0.5, pr(0.55), zc, 4, M3, C_P)
        tea_post("SM3_P_TeaPost_%s" % tag, x1 - 0.7, pr(1.1), M_G, M3, C_P)
    elif kind == "tools":
        for i in range(3):
            crate("SM3_P_TCrate_%s_%d" % (tag, i), x0 + 0.6 + i * 0.6, pr(0.05), 0.0, 0.34, M3, M_G)
        for i in range(5):
            beam_iron("SM3_P_Tool_%s_%d" % (tag, i), x0 + 1.6 + i * 0.20, pr(0.35), zc,
                      0.30 + 0.10 * (i % 3), M_G, C_P)
        jars_row("SM3_P_TJar_%s" % tag, x1 - 1.6, pr(0.05), 0.0, 3, M_G, C_P)


# ------------------------------ أدوات العرض --------------------------------
def sack(name, x, y, z, r, h, mound_mat):
    fh.lathe(name, C_P, M_V["sack"],
             [(0, 0), (r * 0.75, 0.02), (r, 0.16 * h / 0.5), (r * 0.95, 0.34 * h / 0.5),
              (r * 0.62, 0.46 * h / 0.5), (r * 0.50, 0.50 * h / 0.5), (r * 0.46, 0.47 * h / 0.5), (0, 0.45 * h / 0.5)],
             segments=16, matrix=Matrix.Translation((x, y, z)))
    fh.lathe("%s_Mound" % name, C_P, mound_mat,
             [(r * 0.50, h * 0.90), (r * 0.44, h * 1.00), (r * 0.20, h * 1.05), (0, h * 1.06)],
             segments=16, matrix=Matrix.Translation((x, y, z)))


def crate(name, x, y, z, w, M3, M):
    fh.bbox(name, C_P, M3["crate"], (x - w / 2, y - w / 2, z), (x + w / 2, y + w / 2, z + w * 0.75), bevel=0.012, seg=1)
    fh.bbox(name + "_Rim", C_P, M3["crate"], (x - w / 2 - 0.015, y - w / 2 - 0.015, z + w * 0.62),
            (x + w / 2 + 0.015, y + w / 2 + 0.015, z + w * 0.75), bevel=0.008, seg=1)


def basket(name, x, y, z, r, M3):
    fh.lathe(name, C_P, M3["basket"],
             [(0, 0), (r * 0.85, 0.01), (r, 0.10), (r * 1.05, 0.16), (r * 0.92, 0.18), (r * 0.8, 0.15), (0, 0.10)],
             segments=16, matrix=Matrix.Translation((x, y, z)))
    fh.lathe(name + "_Fill", C_P, M3["date"],
             [(0, 0), (r * 0.78, 0.01), (r * 0.55, 0.06), (0, 0.09)],
             segments=14, matrix=Matrix.Translation((x, y, z + 0.13)))


def dallah(name, x, y, z, M3, col):
    base = Matrix.Translation((x, y, z))
    fh.lathe(name, col, M3["brass"],
             [(0, 0), (0.09, 0.01), (0.11, 0.05), (0.085, 0.13), (0.055, 0.19), (0.07, 0.23), (0.05, 0.26), (0, 0.27)],
             segments=14, matrix=base)
    fh.lathe(name + "_Lid", col, M3["brass"],
             [(0, 0), (0.05, 0.0), (0.03, 0.05), (0, 0.06)], segments=12,
             matrix=base @ Matrix.Translation((0, 0, 0.27)))
    fh.beam(name + "_Spout", col, M3["brass"], (x + 0.05, y, z + 0.16), (x + 0.17, y, z + 0.24), 0.018, 0.011, seg=6)
    fh.beam(name + "_Handle", col, M3["brass"], (x - 0.07, y, z + 0.10), (x - 0.12, y, z + 0.20), 0.012, 0.012, seg=5)


def cups_row(name, x, y, z, n, M3, col):
    for i in range(n):
        fh.lathe("%s_%d" % (name, i), col, M3["brass"],
                 [(0, 0), (0.035, 0.005), (0.042, 0.05), (0.038, 0.06), (0, 0.05)],
                 segments=10, matrix=Matrix.Translation((x + i * 0.13, y, z)))


def balance_scale(name, x, y, z, M3):
    fh.beam(name + "_Post", C_P, M_G["palm"], (x, y, z), (x, y, z + 0.55), 0.028, 0.022, seg=6)
    fh.beam(name + "_Arm", C_P, M_G["palm"], (x - 0.34, y, z + 0.55), (x + 0.34, y, z + 0.55), 0.018, 0.018, seg=5)
    for side in (-1, 1):
        fh.beam(name + "_Str%d" % side, C_P, M_G["dry"], (x + side * 0.30, y, z + 0.54), (x + side * 0.30, y, z + 0.36), 0.006, 0.006, seg=4)
        fh.lathe(name + "_Pan%d" % side, C_P, M3["brass"],
                 [(0, 0), (0.09, 0.005), (0.11, 0.03), (0.10, 0.04), (0, 0.03)],
                 segments=12, matrix=Matrix.Translation((x + side * 0.30, y, z + 0.33)))


def herbs_hang(name, x0, x1, y, z_top, M_G):
    for i in range(7):
        x = x0 + (x1 - x0) * i / 6.0
        for k in range(3):
            fh.beam("%s_%d_%d" % (name, i, k), C_P, M_G["dry"],
                    (x + k * 0.03, y, z_top), (x + k * 0.02, y, z_top - 0.28 - 0.06 * k), 0.012, 0.004, seg=4)


def rug_roll(name, x, y, z, length, mat, col):
    fh.lathe(name, col, mat, [(0, 0), (0.085, 0.0), (0.085, length), (0, length)], segments=12,
             matrix=Matrix.Translation((x, y, z + 0.09)) @ Matrix.Rotation(R(90), 4, "Y"))


def bench(name, x0, x1, y0, y1, z, M_G, col):
    fh.bbox(name, col, M_G["wall2"], (x0, min(y0, y1), z), (x1, max(y0, y1), z + 0.40), bevel=0.03, seg=2)
    fh.bbox(name + "_Top", col, M_G["palm"], (x0 - 0.04, min(y0, y1) - 0.04, z + 0.40),
            (x1 + 0.04, max(y0, y1) + 0.04, z + 0.46), bevel=0.015, seg=1)


def tins(name, x, y, z, r, M3, col):
    fh.lathe(name, col, M3["tin"], [(0, 0), (r, 0.0), (r, 0.16), (r * 0.95, 0.17), (0, 0.17)],
             segments=10, matrix=Matrix.Translation((x, y, z)))


def jars_row(name, x, y, z, n, M_G, col):
    for i in range(n):
        fh.lathe_pot("%s_%d" % (name, i), col, M_G["clay"] if i % 2 else M_G["clay2"],
                     (x + i * 0.42, y, z), 0.42 + 0.06 * i, seed=i * 3)


def beam_iron(name, x, y, z, length, M_G, col):
    fh.beam(name, col, M_G["iron"], (x - length / 2, y, z), (x + length / 2, y, z), 0.022, 0.016, seg=6)


def tea_post(name, x, y, M_G, M3, col):
    fh.beam(name + "_Post", col, M_G["palm"], (x, y, 0), (x, y, 2.0), 0.05, 0.04, seg=7)
    fh.beam(name + "_Arm", col, M_G["palm"], (x, y, 1.94), (x + 0.40, y, 1.94), 0.03, 0.025, seg=6)
    fh.lathe(name + "_Pot", col, M3["brass"], [(0, 0), (0.10, 0.01), (0.12, 0.08), (0.08, 0.15), (0, 0.16)],
             segments=12, matrix=Matrix.Translation((x + 0.40, y, 1.72)))
    fh.lathe(name + "_Flame", col, M_G["flame"], [(0, 0), (0.05, 0.02), (0.03, 0.09), (0, 0.12)],
             segments=8, matrix=Matrix.Translation((x + 0.40, y, 1.56)))


def shop_row(kinds, x_start, x_end, F, B, tag):
    col = C_S
    s = 1.0 if B > F else -1.0
    # جدار خلفي + سقف مستمر
    wall_v("SM3_S_%s_BackWall" % tag, col, M_G["wall"], (x_start - 0.2, min(B, B + s * 0.4), 0.0),
           (x_end + 0.2, max(B, B + s * 0.4), ROOF_H))
    fh.bbox("SM3_S_%s_Roof" % tag, col, M_G["wall"], (x_start - 0.25, min(F, B), ROOF_H - 0.22),
            (x_end + 0.25, max(F, B), ROOF_H), bevel=0.03, seg=2)
    # حافة سور السطح (تمنع مظهر البلاطة العارية)
    PAR_H = 0.42
    for nm, yy in (("RoofParF", min(F, B)), ("RoofParB", max(F, B))):
        fh.bbox("SM3_S_%s_%s" % (tag, nm), col, M_G["wall"],
                (x_start - 0.27, yy - 0.15, ROOF_H), (x_end + 0.27, yy + 0.15, ROOF_H + PAR_H),
                bevel=0.022, seg=2)
    for nm, xx in (("RoofParL", x_start - 0.27), ("RoofParR", x_end + 0.12)):
        fh.bbox("SM3_S_%s_%s" % (tag, nm), col, M_G["wall"],
                (xx, min(F, B) - 0.15, ROOF_H), (xx + 0.30, max(F, B) + 0.15, ROOF_H + PAR_H),
                bevel=0.022, seg=2)
    # فواصل بين المحلات
    n = len(kinds)
    width = (x_end - x_start) / n
    for i in range(n + 1):
        x = x_start + i * width
        wall_v("SM3_S_%s_Div%d" % (tag, i), col, M_G["wall2"], (x - 0.15, min(F, B), 0.0),
               (x + 0.15, max(F, B), SHOP_H))
    # السقيفة + الأعمدة + العارضة
    ypost = shop_front_offset(F, s, ARC_D)
    k = 0
    x = x_start + 0.35
    while x < x_end - 0.2:
        fh.beam("SM3_S_%s_Post%02d" % (tag, k), col, M_G["palm"], (x, ypost, 0.10), (x, ypost, 2.92), 0.10, 0.09, seg=9)
        k += 1
        x += 2.55
    fh.beam("SM3_S_%s_ArcBeam" % tag, col, M_G["palm"], (x_start - 0.1, ypost, 2.92), (x_end + 0.1, ypost, 2.92), 0.09, 0.08, seg=8)
    fh.bbox("SM3_S_%s_ArcRoof" % tag, col, M_G["dry"], (x_start - 0.2, min(F, ypost) - 0.25, 2.92),
            (x_end + 0.2, max(F, ypost) + 0.05, 3.06), bevel=0.01, seg=1)
    for j in range(int((x_end - x_start) / 2.2)):
        xx = x_start + 0.6 + j * 2.2
        fh.beam("SM3_S_%s_Rafter%02d" % (tag, j), col, M_G["palm"],
                (xx, ypost - 0.15 * s, 3.04), (xx, F, 3.06), 0.03, 0.028, seg=5)
    # المحلات
    for i, kind in enumerate(kinds):
        shop(x_start + i * width, x_start + (i + 1) * width, F, B, kind, i, tag)


# ---------------------------------------------------------------------------
#  المسجد
# ---------------------------------------------------------------------------
def build_mosque(M, M3):
    C = C_M
    fx = MOSQUE_X0
    # سور الفناء (منخفض) مع فتحة دخول غربية
    H = 1.0
    wall_v("SM3_M_CourtW1", C, M["court"], (MOSQUE_X0, MOSQUE_Y0, 0.0), (MOSQUE_X0 + 0.4, -20.8, H))
    wall_v("SM3_M_CourtW2", C, M["court"], (MOSQUE_X0, -17.2, 0.0), (MOSQUE_X0 + 0.4, MOSQUE_Y1, H))
    wall_v("SM3_M_CourtN", C, M["court"], (MOSQUE_X0, MOSQUE_Y1 - 0.4, 0.0), (MOSQUE_X1, MOSQUE_Y1, H))
    wall_v("SM3_M_CourtS", C, M["court"], (MOSQUE_X0, MOSQUE_Y0, 0.0), (MOSQUE_X1, MOSQUE_Y0 + 0.4, H))
    wall_v("SM3_M_CourtE", C, M["court"], (MOSQUE_X1 - 0.4, MOSQUE_Y0, 0.0), (MOSQUE_X1, MOSQUE_Y1, H))
    # عمودان يحدّان فتحة الدخول (بين Y=-20.8 و Y=-17.2) + عتبة
    for i, (yy0, yy1) in enumerate(((-20.9, -20.6), (-17.5, -17.2))):
        wall_v("SM3_M_CourtPier_%d" % i, C, M["court"], (MOSQUE_X0 - 0.15, yy0, 0.0),
               (MOSQUE_X0 + 0.55, yy1, H + 0.35))
    fh.bbox("SM3_M_CourtLintel", C, M["court"], (MOSQUE_X0 - 0.20, -20.9, H + 0.30),
            (MOSQUE_X0 + 0.60, -17.2, H + 0.85), bevel=0.03, seg=2)

    # قاعة الصلاة
    HX0, HX1 = 26.0, 33.0
    HY0, HY1 = -25.5, -16.0
    HH = 3.8
    wall_v("SM3_M_Hall_W", C, M["wall"], (HX0, HY0, 0.0), (HX0 + 0.5, HY1, HH),
           holes=[((HX0 - 1.0, -21.7, 0.0), (HX0 + 1.0, -19.3, 2.65)),
                  ((HX0 - 1.0, -24.6, 1.55), (HX0 + 1.0, -23.4, 2.65))])
    wall_v("SM3_M_Hall_E", C, M["wall"], (HX1 - 0.5, HY0, 0.0), (HX1, HY1, HH))
    wall_v("SM3_M_Hall_S", C, M["wall"], (HX0, HY0, 0.0), (HX1, HY0 + 0.5, HH),
           holes=[((HX0 + 1.6, HY0 - 1.0, 1.55), (HX0 + 2.8, HY0 + 1.0, 2.65)),
                  ((HX0 + 4.4, HY0 - 1.0, 1.55), (HX0 + 5.6, HY0 + 1.0, 2.65))])
    wall_v("SM3_M_Hall_N", C, M["wall"], (HX0, HY1 - 0.5, 0.0), (HX1, HY1, HH),
           holes=[((HX0 + 2.2, HY1 - 1.0, 1.55), (HX0 + 3.4, HY1 + 1.0, 2.65)),
                  ((HX0 + 5.0, HY1 - 1.0, 1.55), (HX0 + 6.2, HY1 + 1.0, 2.65))])
    fh.bbox("SM3_M_HallRoof", C, M["wall"], (HX0 - 0.15, HY0 - 0.15, HH - 0.24), (HX1 + 0.15, HY1 + 0.15, HH), bevel=0.03, seg=2)
    # سور السطح
    PAR = 0.70
    for nm, lo, hi in (
        ("SM3_M_ParW", (HX0 - 0.15, HY0 - 0.15, HH), (HX0 + 0.1, HY1 + 0.15, HH + PAR)),
        ("SM3_M_ParE", (HX1 - 0.1, HY0 - 0.15, HH), (HX1 + 0.15, HY1 + 0.15, HH + PAR)),
        ("SM3_M_ParS", (HX0 - 0.15, HY0 - 0.15, HH), (HX1 + 0.15, HY0 + 0.1, HH + PAR)),
        ("SM3_M_ParN", (HX0 - 0.15, HY1 - 0.1, HH), (HX1 + 0.15, HY1 + 0.15, HH + PAR)),
    ):
        fh.bbox(nm, C, M["wall"], lo, hi, bevel=0.025, seg=2)
    # القبة
    dcx, dcy = (HX0 + HX1) * 0.5 + 0.3, (HY0 + HY1) * 0.5 - 0.3
    fh.lathe("SM3_M_Drum", C, M3["dome"],
             [(3.05, 0.0), (3.12, 0.35), (3.02, 0.55), (2.95, 0.60)],
             segments=40, matrix=Matrix.Translation((dcx, dcy, HH)))
    dome("SM3_M_Dome", C, M3["dome"], (dcx, dcy, HH + 0.55), 3.0, 2.45, seg=40, n=16)
    fh.beam("SM3_M_FinialPost", C, M3["brass"], (dcx, dcy, HH + 2.95), (dcx, dcy, HH + 3.35), 0.05, 0.04, seg=8)
    sphere_lathe("SM3_M_Finial", C, M3["brass"], (dcx, dcy, HH + 3.42), 0.12, seg=12)
    cone_lathe("SM3_M_FinialTip", C, M3["brass"], (dcx, dcy, HH + 3.52), 0.045, 0.22, seg=8)

    # المدخل: عقد + باب خشبي + عتبة
    arch_ring_x("SM3_M_DoorArch", C, M["gypsum"], HX0 - 0.08, -20.5, 2.50, 1.15, n=14, rad=0.09)
    fh.bbox("SM3_M_DoorThreshold", C, M["stone"], (HX0 - 0.30, -21.9, -0.02), (HX0 + 0.55, -19.1, 0.10), bevel=0.02, seg=2)
    fh.bbox("SM3_M_DoorLeaf", C, M["door"], (HX0 + 0.10, -21.55, 0.10), (HX0 + 0.22, -19.45, 2.60), bevel=0.01, seg=1)
    for i in range(4):
        xx = -21.40 + i * 0.62
        fh.bbox("SM3_M_DoorPlank_%d" % i, C, M["door"], (HX0 + 0.06, xx, 0.16), (HX0 + 0.10, xx + 0.06, 2.54), bevel=0.008, seg=1)
    for i in range(3):
        fh.bbox("SM3_M_DoorStud_%d" % i, C, M["iron"], (HX0 + 0.04, -21.2 + i * 0.55, 1.30),
                (HX0 + 0.14, -21.08 + i * 0.55, 1.42), bevel=0.02, seg=1)
    # مشربيات النوافذ (شبك خشبي بسيط)
    for i, (wy0, wy1) in enumerate(((-24.6, -23.4),)):
        for k in range(6):
            yy = wy0 + 0.10 + (wy1 - wy0 - 0.2) * k / 5.0
            fh.bbox("SM3_M_WinBar_%d_%d" % (i, k), C, M["lattice"], (HX0 + 0.20, yy - 0.018, 1.55),
                    (HX0 + 0.26, yy + 0.018, 2.65), bevel=0.004, seg=1)
    # زخرفة مثلثات على الواجهة الجنوبية للقاعة
    for k in range(9):
        fh.tri_prism("SM3_M_Tri_%d" % k, C, M["gypsum"], cx=HX0 + 0.6 + k * 0.72, base_z=3.14,
                     y=HY0 - 0.005, w=0.16, h=0.24, depth=0.02)
    # المئذنة (الركن الشمالي الغربي)
    MX0, MY0 = 26.0, -17.6
    MS = 1.55
    fh.bbox("SM3_M_MinBase", C, M["wall"], (MX0, MY0, 0.0), (MX0 + MS, MY0 + MS, 7.20), bevel=0.03, seg=2)
    fh.bbox("SM3_M_MinBalc", C, M["wall"], (MX0 - 0.28, MY0 - 0.28, 7.20), (MX0 + MS + 0.28, MY0 + MS + 0.28, 7.52),
            bevel=0.03, seg=2)
    for nm, lo, hi in (
        ("SM3_M_MinRailN", (MX0 - 0.28, MY0 + MS + 0.06, 7.52), (MX0 + MS + 0.28, MY0 + MS + 0.28, 8.30)),
        ("SM3_M_MinRailS", (MX0 - 0.28, MY0 - 0.28, 7.52), (MX0 + MS + 0.28, MY0 + 0.06, 8.30)),
        ("SM3_M_MinRailW", (MX0 - 0.28, MY0 - 0.28, 7.52), (MX0 + 0.06, MY0 + MS + 0.28, 8.30)),
        ("SM3_M_MinRailE", (MX0 + MS - 0.06, MY0 - 0.28, 7.52), (MX0 + MS + 0.28, MY0 + MS + 0.28, 8.30)),
    ):
        fh.bbox(nm, C, M["wall"], lo, hi, bevel=0.018, seg=2)
    fh.bbox("SM3_M_MinShaft", C, M["wall"], (MX0 + 0.16, MY0 + 0.16, 7.52), (MX0 + MS - 0.16, MY0 + MS - 0.16, 9.80),
            bevel=0.025, seg=2)
    dome("SM3_M_MinDome", C, M3["dome"], (MX0 + MS * 0.5, MY0 + MS * 0.5, 9.80), 0.72, 0.72, seg=22, n=10)
    cone_lathe("SM3_M_MinTip", C, M3["brass"], (MX0 + MS * 0.5, MY0 + MS * 0.5, 10.50), 0.05, 0.30, seg=8)
    # فتحات المئذنة
    for zz in (2.4, 4.6, 6.4):
        fh.bbox("SM3_M_MinSlit_%d" % int(zz * 10), C, M["dark"],
                (MX0 - 0.02, MY0 + 0.55, zz), (MX0 + 0.02, MY0 + 0.85, zz + 0.7))
    # عوارض الأثل + إفريز
    for zz in (3.3, 6.6):
        i = 0
        xx = HX0 + 0.3
        while xx < HX1 - 0.2:
            fh.beam("SM3_M_BeamE_%d_%02d" % (int(zz * 10), i), C, M["palm"],
                    (HX1 - 0.52, -20.7, zz), (HX1 + 0.40, -20.75, zz), 0.075, 0.068, seg=8)
            i += 1
            xx += 0.66
    # سقيفة أمام المدخل
    for i in range(3):
        fh.beam("SM3_M_PorchPost_%d" % i, C, M["palm"], (HX0 - 1.6 + i * 1.6, -20.5, 0.10),
                (HX0 - 1.6 + i * 1.6, -20.5, 2.90), 0.09, 0.08, seg=8)
    fh.bbox("SM3_M_PorchRoof", C, M["dry"], (HX0 - 1.9, -22.0, 2.90), (HX0 + 0.2, -19.0, 3.04), bevel=0.01, seg=1)
    # مصباح المدخل
    fh.beam("SM3_M_LampArm", C, M["iron"], (HX0 - 0.05, -19.2, 2.85), (HX0 - 0.75, -19.2, 2.85), 0.02, 0.02, seg=5)
    fh.lathe("SM3_M_LampGlass", C, M["glow"], [(0, 0), (0.075, 0.01), (0.10, 0.09), (0.07, 0.18), (0, 0.19)],
             segments=10, matrix=Matrix.Translation((HX0 - 0.75, -19.2, 2.42)))
    fh.lathe("SM3_M_LampCap", C, M["iron"], [(0, 0), (0.02, 0), (0.11, 0.04), (0.09, 0.07), (0, 0.07)],
             segments=10, matrix=Matrix.Translation((HX0 - 0.75, -19.2, 2.61)))
    # بئر صغير للوضوء + نخيل
    fh.lathe("SM3_M_Basin", C, M["stone"], [(0.75, 0.0), (0.80, 0.22), (0.70, 0.30), (0.66, 0.06)],
             segments=20, matrix=Matrix.Translation((MOSQUE_X0 + 1.9, MOSQUE_Y0 + 2.0, 0.10)))
    fh.bbox("SM3_M_BasinWater", C, M["lattice"], (MOSQUE_X0 + 1.25, MOSQUE_Y0 + 1.35, 0.16),
            (MOSQUE_X0 + 2.55, MOSQUE_Y0 + 2.65, 0.18))


# ---------------------------------------------------------------------------
#  بيوت شعبية صغيرة
# ---------------------------------------------------------------------------
def small_house(M, M3, x0, y0, w, d, h, upper, name, col=None):
    col = col or C_H
    x1, y1 = x0 + w, y0 + d
    T = 0.45
    wall_v(name + "_F", col, M["wall"], (x0, y0, 0), (x1, y0 + T, h),
           holes=[((x0 + w * 0.42, y0 - 1, 0), (x0 + w * 0.42 + 1.1, y0 + 2, 2.15)),
                  ((x0 + 0.55, y0 - 1, 1.15), (x0 + 0.55 + 0.85, y0 + 2, 2.05))])
    wall_v(name + "_B", col, M["wall"], (x0, y1 - T, 0), (x1, y1, h))
    wall_v(name + "_W", col, M["wall"], (x0, y0, 0), (x0 + T, y1, h))
    wall_v(name + "_E", col, M["wall"], (x1 - T, y0, 0), (x1, y1, h))
    fh.bbox(name + "_Roof", col, M["wall"], (x0 - 0.1, y0 - 0.1, h - 0.2), (x1 + 0.1, y1 + 0.1, h), bevel=0.03, seg=2)
    # سور السطح + شرافات
    PAR = 0.75
    for nm, lo, hi in ((name + "_ParF", (x0 - 0.1, y0 - 0.1, h), (x1 + 0.1, y0 + 0.15, h + PAR)),
                       (name + "_ParB", (x0 - 0.1, y1 - 0.15, h), (x1 + 0.1, y1 + 0.1, h + PAR)),
                       (name + "_ParW", (x0 - 0.1, y0 - 0.1, h), (x0 + 0.15, y1 + 0.1, h + PAR)),
                       (name + "_ParE", (x1 - 0.15, y0 - 0.1, h), (x1 + 0.1, y1 + 0.1, h + PAR))):
        fh.bbox(nm, col, M["wall"], lo, hi, bevel=0.025, seg=2)
    i = 0
    xx = x0 + 0.4
    while xx < x1 - 0.3:
        fh.bbox("%s_Merl%02d" % (name, i), col, M["wall"],
                (xx - 0.13, y0 - 0.02, h + PAR), (xx + 0.13, y0 + 0.14, h + PAR + 0.17), bevel=0.015, seg=1)
        i += 1
        xx += 0.55
    # عوارض
    i = 0
    xx = x0 + 0.3
    while xx < x1 - 0.2:
        fh.beam("%s_Beam%02d" % (name, i), col, M["palm"], (xx, y0 + 0.42, h - 0.3), (xx, y0 - 0.35, h - 0.3), 0.07, 0.062, seg=8)
        i += 1
        xx += 0.62
    # باب خشبي
    dx = x0 + w * 0.42
    fh.bbox(name + "_Door", col, M["door"], (dx + 0.14, y0 - 0.06, 0.02), (dx + 1.0, y0 + 0.06, 2.10), bevel=0.01, seg=1)
    fh.bbox(name + "_DoorStud", col, M["iron"], (dx + 0.20, y0 - 0.12, 1.15), (dx + 0.95, y0 - 0.04, 1.30), bevel=0.01, seg=1)
    # مشربية النافذة
    for k in range(5):
        px = x0 + 0.62 + k * 0.16
        fh.bbox("%s_WinBar%d" % (name, k), col, M["lattice"],
                (px, y0 + 0.12, 1.18), (px + 0.03, y0 + 0.20, 2.02), bevel=0.004, seg=1)
    # إفريز مثلثات
    for k in range(6):
        fh.tri_prism("%s_Tri%d" % (name, k), col, M["gypsum"], cx=x0 + 0.6 + k * 0.45, base_z=2.30,
                     y=y0 - 0.005, w=0.13, h=0.19, depth=0.02)
    if upper:
        ux0, ux1 = x0 + 0.4, x1 - 0.9
        uy0, uy1 = y0 + 0.8, y1 - 0.2
        uh = h + 2.1
        wall_v(name + "_U_F", col, M["wall2"], (ux0, uy0, h), (ux1, uy0 + 0.4, uh),
               holes=[((ux0 + 0.7, uy0 - 1, h + 0.8), (ux0 + 1.5, uy0 + 2, h + 1.9))])
        wall_v(name + "_U_B", col, M["wall2"], (ux0, uy1 - 0.4, h), (ux1, uy1, uh))
        wall_v(name + "_U_W", col, M["wall2"], (ux0, uy0, h), (ux0 + 0.4, uy1, uh))
        wall_v(name + "_U_E", col, M["wall2"], (ux1 - 0.4, uy0, h), (ux1, uy1, uh))
        fh.bbox(name + "_U_Roof", col, M["wall2"], (ux0 - 0.1, uy0 - 0.1, uh - 0.2), (ux1 + 0.1, uy1 + 0.1, uh), bevel=0.03, seg=2)
        for nm, lo, hi in ((name + "_U_ParF", (ux0 - 0.1, uy0 - 0.1, uh), (ux1 + 0.1, uy0 + 0.12, uh + 0.6)),
                           (name + "_U_ParE", (ux1 - 0.12, uy0 - 0.1, uh), (ux1 + 0.1, uy1 + 0.1, uh + 0.6)),
                           (name + "_U_ParB", (ux0 - 0.1, uy1 - 0.12, uh), (ux1 + 0.1, uy1 + 0.1, uh + 0.6)),
                           (name + "_U_ParW", (ux0 - 0.1, uy0 - 0.1, uh), (ux0 + 0.12, uy1 + 0.1, uh + 0.6))):
            fh.bbox(nm, col, M["wall2"], lo, hi, bevel=0.022, seg=2)


def build_houses(M, M3):
    small_house(M, M3, -33.0, -28.0, 7.0, 6.5, 3.6, True, "SM3_H_HouseA")
    small_house(M, M3, -33.5, -18.5, 6.2, 6.8, 3.5, False, "SM3_H_HouseB")
    small_house(M, M3, -12.5, -34.5, 7.2, 6.0, 3.7, True, "SM3_H_HouseC")
    small_house(M, M3, 8.0, -35.0, 6.4, 6.2, 3.5, False, "SM3_H_HouseD")
    small_house(M, M3, 16.5, -35.5, 6.8, 6.4, 3.6, True, "SM3_H_HouseE")
    # أسوار صغيرة بين البيوت
    wall_v("SM3_H_Wall1", C_H, M["court"], (-25.5, -28.6, 0), (-12.5, -28.2, 2.1))
    wall_v("SM3_H_Wall2", C_H, M["court"], (8.0, -28.6, 0), (23.3, -28.2, 2.1))


# ---------------------------------------------------------------------------
#  بوابة القرية + البئر + النخيل + الفوانيس
# ---------------------------------------------------------------------------
def build_gate(M):
    gx0, gx1 = -26.4, -24.6
    gy0, gy1 = -23.4, -13.6
    H = 4.4
    arch_ring_x("SM3_S_GateArch", C_S, M["court"], gx1 - 0.02, -18.5, H - 1.6, 1.5, n=14, rad=0.15)
    wall_v("SM3_S_GateL", C_S, M["court"], (gx0, gy0, 0), (gx1, gy0 + 3.4, H))
    wall_v("SM3_S_GateR", C_S, M["court"], (gx0, gy1 - 3.4, 0), (gx1, gy1, H))
    fh.bbox("SM3_S_GateTop", C_S, M["court"], (gx0, gy0, H - 0.6), (gx1, gy1, H + 0.5), bevel=0.03, seg=2)
    for k in range(3):
        fh.tri_prism("SM3_S_GateTri_%d" % k, C_S, M["gypsum"], cx=gx0 + 0.42 + k * 0.52,
                     base_z=H + 0.15, y=gy0 - 0.005, w=0.14, h=0.20, depth=0.02)
    # أبواب خشبية
    for side, (a, b) in enumerate(((gy0 + 3.6, -18.6), (-18.2, gy1 - 3.6))):
        fh.bbox("SM3_S_GateLeaf_%d" % side, C_S, M["door"], (gx0 + 0.06, a, 0.02), (gx0 + 0.16, b, 3.60), bevel=0.01, seg=1)
        for i in range(3):
            fh.bbox("SM3_S_GateRail_%d_%d" % (side, i), C_S, M["iron"],
                    (gx0 + 0.02, a + 0.1, 0.55 + i * 1.05), (gx0 + 0.08, b - 0.1, 0.66 + i * 1.05), bevel=0.008, seg=1)


def build_well(M, M3):
    wx, wy = -1.0, -12.7
    for k in range(16):
        a = 2 * math.pi * k / 16
        fh.rock("SM3_P_WellStone_%d" % k, C_P, M["stone"],
                (wx + 0.95 * math.cos(a), wy + 0.95 * math.sin(a), 0.22), (0.30, 0.26, 0.36),
                seed=900 + k, rough=0.09)
    fh.lathe("SM3_P_WellRim", C_P, M["stone"],
             [(0.92, 0.06), (0.98, 0.46), (0.86, 0.48), (0.84, 0.08)], segments=24,
             matrix=Matrix.Translation((wx, wy, 0.0)))
    fh.bbox("SM3_P_WellDark", C_P, M["dark"], (wx - 0.9, wy - 0.9, 0.30), (wx + 0.9, wy + 0.9, 0.32))
    for side in (-1, 1):
        fh.beam("SM3_P_WellPost_%d" % side, C_P, M["palm"], (wx + side * 1.05, wy, 0.0),
                (wx + side * 1.05, wy, 2.20), 0.07, 0.06, seg=8)
    fh.beam("SM3_P_WellCross", C_P, M["palm"], (wx - 1.22, wy, 2.12), (wx + 1.22, wy, 2.12), 0.06, 0.06, seg=8)
    fh.beam("SM3_P_WellRope", C_P, M["dry"], (wx, wy, 1.55), (wx, wy, 2.12), 0.016, 0.016, seg=5)
    fh.lathe("SM3_P_WellBucket", C_P, M["clay"],
             [(0, 0), (0.13, 0.02), (0.16, 0.30), (0.14, 0.32), (0.12, 0.28), (0, 0.26)], segments=14,
             matrix=Matrix.Translation((wx, wy, 1.18)))


def build_trees(M):
    fh.build_palm(-2.6, -13.4, 7.2, M, "SM3_P_Palm_W1")
    fh.build_palm(2.0, -13.0, 6.4, M, "SM3_P_Palm_W2")
    fh.build_palm(-22.8, -20.0, 6.0, M, "SM3_P_Palm_S1")
    fh.build_palm(21.6, -20.6, 6.8, M, "SM3_P_Palm_S2")
    fh.build_palm(34.6, -19.0, 7.0, M, "SM3_P_Palm_M1")
    fh.build_palm(-30.6, -24.0, 6.2, M, "SM3_P_Palm_H1")
    fh.build_palm(25.0, -30.0, 6.6, M, "SM3_P_Palm_H2")
    fh.build_tree(-20.0, -30.5, 3.0, M, "SM3_P_Sidr_1")
    fh.build_tree(12.0, -30.0, 3.2, M, "SM3_P_Sidr_2")
    fh.build_tree(30.0, -30.5, 3.4, M, "SM3_P_Sidr_3")


def lantern(name, x, y, z, M, col):
    fh.lathe(name + "_Glass", col, M["glow"],
             [(0, 0), (0.075, 0.01), (0.10, 0.09), (0.07, 0.18), (0, 0.19)], segments=10,
             matrix=Matrix.Translation((x, y, z)))
    fh.lathe(name + "_Cap", col, M["iron"],
             [(0, 0), (0.02, 0), (0.11, 0.04), (0.09, 0.07), (0, 0.07)], segments=10,
             matrix=Matrix.Translation((x, y, z + 0.19)))
    fh.lathe(name + "_Flame", col, M["flame"],
             [(0, 0), (0.022, 0.006), (0.015, 0.05), (0, 0.075)], segments=8,
             matrix=Matrix.Translation((x, y, z + 0.04)))


def build_lanterns(M):
    # فوانيس معلّقة على السقائف
    for i, x in enumerate((-18.0, -11.0, 6.0, 13.0, 19.0)):
        lantern("SM3_P_LantN%d" % i, x, NORTH_F + 1.7, 2.30, M, C_P)
    for i, x in enumerate((-16.0, -4.0, 9.0, 17.0)):
        lantern("SM3_P_LantS%d" % i, x, SOUTH_F - 1.7, 2.30, M, C_P)
    # أعمدة فوانيس في الساحة والشارع
    for i, (x, y) in enumerate(((-5.0, -14.4), (3.4, -14.4), (-23.0, -15.6), (22.0, -21.4))):
        fh.beam("SM3_P_LampPost%d" % i, C_P, M["palm"], (x, y, 0), (x, y, 2.55), 0.06, 0.05, seg=8)
        fh.beam("SM3_P_LampArm%d" % i, C_P, M["palm"], (x, y, 2.48), (x, y - 0.42, 2.48), 0.032, 0.028, seg=6)
        lantern("SM3_P_LampH%d" % i, x, y - 0.42, 2.10, M, C_P)


# ---------------------------------------------------------------------------
#  الإضاءة والكاميرات
# ---------------------------------------------------------------------------
def build_lights(M):
    def pt(name, loc, energy, color, rad=0.08):
        fh.add_light(name, "POINT", loc, energy, color, rad)
    pt("LGT_V3_Souq_N1", (-14.0, -16.9, 2.55), 75.0, (1.0, 0.62, 0.30), 0.16)
    pt("LGT_V3_Souq_N2", (-2.0, -15.6, 2.55), 85.0, (1.0, 0.60, 0.28), 0.16)
    pt("LGT_V3_Souq_N3", (11.0, -16.9, 2.55), 75.0, (1.0, 0.62, 0.30), 0.16)
    pt("LGT_V3_Souq_S1", (-7.0, -20.5, 2.55), 75.0, (1.0, 0.60, 0.28), 0.16)
    pt("LGT_V3_Souq_S2", (15.0, -20.5, 2.55), 75.0, (1.0, 0.60, 0.28), 0.16)
    pt("LGT_V3_Mosque", (26.6, -19.6, 2.60), 90.0, (1.0, 0.66, 0.34), 0.14)
    pt("LGT_V3_Well", (-1.0, -12.7, 1.60), 40.0, (1.0, 0.58, 0.26), 0.10)
    pt("LGT_V3_Coffee", (11.0, -21.9, 2.20), 45.0, (1.0, 0.55, 0.24), 0.10)
    # إضاءة دافئة عريضة فوق السوق (تمنع الصبغة الزرقاء في الظل)
    fh.add_light("LGT_V3_WarmFill", "AREA", (0.0, -18.5, 15.0), 2600.0, (1.0, 0.85, 0.64), size=42.0)


def tune_lighting():
    """ضبط إضاءة المشهد المشترك ليقرأ الشارع (كانت الشمس منخفضة فتحجبها السقائف)."""
    import mathutils
    sc = bpy.context.scene
    sun = bpy.data.objects.get("LGT_Sun_Key")
    if sun:
        # ارتفاع ~34° من الجنوب-الشرق: ينير واجهات المحلات وأرضية الشارع
        d = mathutils.Vector((-0.19, 0.80, -0.56)).normalized()
        sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        sun.data.energy = 4.0
        sun.data.color = (1.0, 0.78, 0.55)
        sun.data.angle = R(2.4)
    fill = bpy.data.objects.get("LGT_Fill_Sky")
    if fill:
        fill.data.energy = 500.0
        fill.data.color = (1.0, 0.95, 0.86)
    bounce = bpy.data.objects.get("LGT_Bounce_Sand")
    if bounce:
        bounce.data.energy = 420.0
        bounce.data.color = (1.0, 0.72, 0.44)
    world = sc.world
    if world and world.node_tree:
        bg = world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs["Strength"].default_value = 1.45
    sc.view_settings.exposure = 0.35


def build_cameras():
    fh.add_camera("CAM_V3_Street", (-22.6, -18.6, 1.95), (21.0, -18.4, 2.30), 22.0)
    fh.add_camera("CAM_V3_Aerial", (-6.0, -62.0, 40.0), (2.0, -18.0, 1.0), 32.0)
    fh.add_camera("CAM_V3_Mosque", (12.5, -40.0, 7.0), (28.4, -19.8, 3.10), 34.0)
    fh.add_camera("CAM_V3_Souq", (-17.0, -19.2, 1.75), (-12.6, -14.6, 1.90), 26.0)
    fh.add_camera("CAM_V3_Over", (-14.0, -30.0, 12.0), (6.0, -18.0, 3.0), 34.0)


# ---------------------------------------------------------------------------
#  البناء
# ---------------------------------------------------------------------------
M_G = {}
M_V = {}
M3 = {}          # alias لـ M_V (تستخدمه دوال عرض المحلات)


def main_additive():
    global M_G, M_V, M3, COLL_MAP
    fh.init_collections()
    removed = clear_previous()      # قبل إنشاء المجموعات (كان يحذفها وهي فارغة)
    init_cols()
    COLL_MAP = {"G": C_G, "S": C_S, "M": C_M, "H": C_H, "P": C_P}
    M_G = fetch_mats()
    M_V = village_mats()
    M3 = M_V

    build_ground(M_G, M_V)
    # الصف الشمالي: فتحة ساحة في المنتصف
    shop_row(["pottery", "spices", "dates"], -20.5, -6.1, NORTH_F, NORTH_B, "N1")
    shop_row(["textile", "coffee", "grocery"], 4.1, 20.5, NORTH_F, NORTH_B, "N2")
    # الصف الجنوبي
    shop_row(["grocery", "pottery", "cafe"], -20.5, -1.9, SOUTH_F, SOUTH_B, "S1")
    shop_row(["textile", "spices", "herbs"], 1.9, 20.5, SOUTH_F, SOUTH_B, "S2")
    build_mosque(M_G, M_V)
    build_houses(M_G, M_V)
    build_gate(M_G)
    build_well(M_G, M_V)
    build_trees(M_G)
    build_lanterns(M_G)
    build_lights(M_G)
    tune_lighting()
    build_cameras()
    sort_collections()
    bpy.context.scene.camera = bpy.data.objects["CAM_V3_Over"]
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(FH_PATH), "folk_house.blend"))
    return {"removed": removed, "objects": len(bpy.data.objects),
            "village_objects": sum(1 for o in bpy.data.objects if o.name.startswith("SM3_")),
            "saved": bpy.data.filepath}


if __name__ == "__main__":
    print(main_additive())
