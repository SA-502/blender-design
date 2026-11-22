# -*- coding: utf-8 -*-
"""
002 — مبنى شعبي ثانٍ: "برج حصن + مجلس (ديوانية) مفتوح".

يُبنى بجانب البيت 001 (على يمينه) داخل نفس المشهد، ويعيد استخدام دوال وخامات fh_build.py
حتى يبقى الشكل متناسقاً. الأوضاع:
    main()          -> بناء مستقل في مشهد فارغ (تصميم 002 قائم بذاته).
    main_additive() -> إضافة المبنى يمين البيت 001 في المشهد المفتوح حالياً.
"""
import bpy, importlib.util, os
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
FH_PATH = os.path.abspath(os.path.join(HERE, "..", "001_folk_house", "fh_build.py"))
_spec = importlib.util.spec_from_file_location("fh_build", FH_PATH)
fh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fh)

R, math, random, srgb = fh.R, fh.math, fh.random, fh.srgb
Vector, Matrix = fh.Vector, fh.Matrix

MAT_NAMES = {
    "wall": "MAT_Adobe_Wall", "wall2": "MAT_Adobe_Wall_Upper", "court": "MAT_Adobe_CourtWall",
    "floor": "MAT_Mud_Floor", "sand": "MAT_Ground_Sand",
    "palm": "MAT_Wood_Beam", "door": "MAT_Wood_Door", "lattice": "MAT_Wood_Lattice",
    "iron": "MAT_Iron_Stud", "clay": "MAT_Clay_Terracotta", "clay2": "MAT_Clay_Pale",
    "gypsum": "MAT_Gypsum_White", "stone": "MAT_Stone_Grey",
    "leaf": "MAT_Palm_Leaf", "leaf2": "MAT_Tree_Leaf", "dry": "MAT_Palm_Dry",
    "trunk": "MAT_Palm_Trunk", "dark": "MAT_Interior_Dark", "glow": "MAT_Lantern_Glow",
    "flame": "MAT_Flame", "rug": "MAT_Fabric_Rug", "cushion": "MAT_Fabric_Cushion",
}


def mats():
    M = {}
    for k, nm in MAT_NAMES.items():
        m = bpy.data.materials.get(nm)
        if m is None:
            m = bpy.data.materials.new(nm)
        M[k] = m
    return M


# ---------------------------------------------------------------------------
#  الأبعاد
# ---------------------------------------------------------------------------
TW, TD, TH = 4.6, 6.0, 8.6      # البرج: عرض، عمق، ارتفاع
MW = 5.8                         # المجلس: عرض
MH = 3.3                         # المجلس: ارتفاع (سقف الجريد)


def build_door(M, x0, x1, z0, z1, yf):
    """باب خشبي بسيط بعوارض حديد ومسامير وحلقة طرق."""
    fh.bbox("SM2_Tower_Threshold", fh.COL_PROPS, M["stone"],
            (x0 - 0.18, -0.22, -0.02), (x1 + 0.18, 0.62, 0.07), bevel=0.025, seg=2)
    fh.bbox("SM2_Door_Frame_L", fh.COL_PROPS, M["door"], (x0 - 0.02, yf - 0.10, z0), (x0 + 0.13, yf + 0.06, z1 + 0.14))
    fh.bbox("SM2_Door_Frame_R", fh.COL_PROPS, M["door"], (x1 - 0.13, yf - 0.10, z0), (x1 + 0.02, yf + 0.06, z1 + 0.14))
    fh.bbox("SM2_Door_Frame_T", fh.COL_PROPS, M["door"], (x0 - 0.05, yf - 0.10, z1), (x1 + 0.05, yf + 0.06, z1 + 0.22), bevel=0.015, seg=2)
    fh.bbox("SM2_Door_Lintel", fh.COL_PROPS, M["palm"], (x0 - 0.22, yf - 0.14, z1 + 0.22), (x1 + 0.22, yf + 0.04, z1 + 0.36), bevel=0.02, seg=2)
    fh.bbox("SM2_Door_Leaf", fh.COL_PROPS, M["door"], (x0 + 0.14, yf - 0.02, z0 + 0.02), (x1 - 0.14, yf + 0.07, z1 - 0.02))
    n = 4
    for k in range(n):
        px = x0 + 0.14 + (x1 - x0 - 0.28) * (k + 0.5) / n
        fh.bbox("SM2_Door_Plank_%d" % k, fh.COL_PROPS, M["door"],
                (px - 0.012, yf - 0.055, z0 + 0.10), (px + 0.012, yf - 0.02, z1 - 0.08))
    for k, zz in enumerate((0.55, 1.35)):
        fh.bbox("SM2_Door_Rail_%d" % k, fh.COL_PROPS, M["iron"],
                (x0 + 0.10, yf - 0.075, zz - 0.045), (x1 - 0.10, yf - 0.045, zz + 0.045))
        for s in range(4):
            px = x0 + 0.24 + (x1 - x0 - 0.48) * s / 3.0
            fh.lathe("SM2_Door_Stud_%d_%d" % (k, s), fh.COL_PROPS, M["iron"],
                     [(0, 0), (0.032, 0.0), (0.026, 0.025), (0.011, 0.038), (0, 0.04)],
                     segments=8, matrix=Matrix.Translation((px, yf - 0.075, zz)) @ Matrix.Rotation(R(-90), 4, "X"))
    mid = (x0 + x1) * 0.5
    fh.lathe("SM2_Knocker", fh.COL_PROPS, M["iron"],
             [(0.05, 0), (0.058, 0.012), (0.05, 0.024)], segments=20,
             matrix=Matrix.Translation((mid + 0.26, yf - 0.10, 1.05)) @ Matrix.Rotation(R(-90), 4, "X"))


def build_tower(M, dx):
    x0, x1 = dx, dx + TW
    # الجدران
    fh.wall("SM2_Tower_Front", fh.COL_HOUSE, M["wall"], (x0, 0.0, 0.0), (x1, 0.55, TH),
            holes=[((x0 + 2.05, -1.0, 0.0), (x0 + 3.35, 1.2, 2.2)),
                   ((x0 + 1.55, -1.0, 4.6), (x0 + 1.85, 1.2, 5.6)),
                   ((x0 + 3.75, -1.0, 6.5), (x0 + 4.05, 1.2, 7.5))])
    fh.wall("SM2_Tower_Back", fh.COL_HOUSE, M["wall"], (x0, TD - 0.55, 0.0), (x1, TD, TH))
    fh.wall("SM2_Tower_Left", fh.COL_HOUSE, M["wall"], (x0, 0.0, 0.0), (x0 + 0.55, TD, TH))
    fh.wall("SM2_Tower_Right", fh.COL_HOUSE, M["wall"], (x1 - 0.55, 0.0, 0.0), (x1, TD, TH),
            holes=[((x1 - 1.0, 2.0, 4.2), (x1 + 1.0, 2.3, 5.2))])
    # السقف والسور
    fh.bbox("SM2_Tower_Roof", fh.COL_HOUSE, M["wall"], (x0 - 0.10, -0.10, TH - 0.22), (x1 + 0.10, TD + 0.10, TH), bevel=0.03, seg=2)
    PAR = 0.9
    for nm, lo, hi in (
        ("SM2_Tower_Par_S", (x0 - 0.10, -0.10, TH), (x1 + 0.10, 0.22, TH + PAR)),
        ("SM2_Tower_Par_E", (x1 - 0.18, -0.10, TH), (x1 + 0.10, TD + 0.10, TH + PAR)),
        ("SM2_Tower_Par_N", (x0 - 0.10, TD - 0.12, TH), (x1 + 0.10, TD + 0.10, TH + PAR)),
        ("SM2_Tower_Par_W", (x0 - 0.10, -0.10, TH), (x0 + 0.05, TD + 0.10, TH + PAR)),
    ):
        fh.bbox(nm, fh.COL_HOUSE, M["wall"], lo, hi, bevel=0.028, seg=2)
    # شرافات مثلثة على سور البرج
    step, i = 0.55, 0
    xx = x0 + 0.3
    while xx < x1 - 0.3:
        fh.bbox("SM2_Merl_%02d" % i, fh.COL_HOUSE, M["wall"],
                (xx - 0.14, -0.02, TH + PAR), (xx + 0.14, 0.16, TH + PAR + 0.18), bevel=0.02, seg=1)
        fh.tri_prism("SM2_Merl_T%02d" % i, fh.COL_HOUSE, M["wall"],
                     cx=xx, base_z=TH + PAR + 0.18, y=-0.02, w=0.26, h=0.18, depth=0.18)
        i += 1
        xx += step
    # عوارض الأثل
    for zz in (3.3, 5.6, 7.9):
        i = 0
        bxx = x0 + 0.25
        while bxx < x1 - 0.1:
            fh.beam("SM2_Beam_F_%s_%02d" % (int(zz * 10), i), fh.COL_HOUSE, M["palm"],
                    (bxx, 0.52, zz), (bxx, -0.42, zz), 0.08, 0.07, seg=8)
            i += 1
            bxx += 0.62
    y = 0.6
    i = 0
    while y < TD - 0.3:
        fh.beam("SM2_Beam_R_%02d" % i, fh.COL_HOUSE, M["palm"],
                (x1 - 0.52, y, 5.6), (x1 + 0.38, y, 5.6), 0.072, 0.065, seg=8)
        i += 1
        y += 0.66
    # فتحات المشكاة (داخل مظلم)
    for (a, b, za, zb) in ((x0 + 1.55, x0 + 1.85, 4.6, 5.6), (x0 + 3.75, x0 + 4.05, 6.5, 7.5)):
        fh.bbox("SM2_Slit_%d" % int(za), fh.COL_PROPS, M["dark"], (a, 0.28, za), (b, 0.40, zb))
    fh.bbox("SM2_Slit_R", fh.COL_PROPS, M["dark"], (x1 - 0.35, 2.0, 4.2), (x1 - 0.28, 2.3, 5.2))
    # الباب
    build_door(M, x0 + 2.05, x0 + 3.35, 0.0, 2.2, 0.10)
    # إفريز مثلثات
    for k in range(7):
        fh.tri_prism("SM2_Tri_%d" % k, fh.COL_HOUSE, M["gypsum"],
                     cx=x0 + 2.05 + 0.06 + k * 0.16, base_z=2.35, y=-0.005, w=0.13, h=0.19, depth=0.02)
    for k in range(9):
        fh.tri_prism("SM2_TriTop_%d" % k, fh.COL_HOUSE, M["gypsum"],
                     cx=x0 + 0.5 + k * 0.42, base_z=8.02, y=-0.005, w=0.14, h=0.20, depth=0.02)
    return x1


def build_majlis(M, dx):
    x0, x1 = dx, dx + MW
    # أرضية مرتفعة
    fh.bbox("SM2_Majlis_Floor", fh.COL_HOUSE, M["wall2"], (x0, 0.0, 0.0), (x1, TD, 0.28), bevel=0.03, seg=2)
    # جدار خلفي + جانبي (اليسار يشترك مع جدار البرج)
    fh.wall("SM2_Majlis_Back", fh.COL_HOUSE, M["wall2"], (x0, TD - 0.40, 0.0), (x1, TD, MH))
    fh.wall("SM2_Majlis_Right", fh.COL_HOUSE, M["wall2"], (x1 - 0.40, 0.0, 0.0), (x1, TD, MH))
    # أعمدة الرواق الأمامي
    posts_x = [x0 + 0.58, x0 + 2.0, x0 + 3.42, x0 + 4.6, x0 + 5.2]
    for i, px in enumerate(posts_x):
        fh.beam("SM2_Majlis_Post_%d" % i, fh.COL_HOUSE, M["palm"],
                (px, 1.05, 0.28), (px, 1.05, 3.05), 0.11, 0.10, seg=10)
    # عارضة أمامية + عوارض السقف + حصير الجريد
    fh.beam("SM2_Majlis_Beam_Front", fh.COL_HOUSE, M["palm"],
            (x0 - 0.10, 1.05, 3.05), (x1 + 0.10, 1.05, 3.05), 0.09, 0.08, seg=8)
    for i, yy in enumerate((1.1, 2.5, 3.9, 5.3)):
        fh.beam("SM2_Majlis_BeamY_%d" % i, fh.COL_HOUSE, M["palm"],
                (x0 - 0.05, yy, 3.18), (x1 + 0.05, yy, 3.18), 0.06, 0.05, seg=7)
    fh.bbox("SM2_Majlis_Roof", fh.COL_HOUSE, M["dry"], (x0 - 0.20, -0.15, 3.22), (x1 + 0.20, TD + 0.15, 3.34), bevel=0.01, seg=1)
    # أرضية الجريد الداخلية
    fh.bbox("SM2_Majlis_Mat", fh.COL_HOUSE, M["dry"], (x0 + 0.06, 0.10, 0.30), (x1 - 0.06, TD - 0.10, 0.34), bevel=0.01, seg=1)


def build_props(M, dx):
    # فناء مدكوك أمام المبنى
    fh.bbox("SM2_Yard", fh.COL_GROUND, M["floor"], (dx - 0.6, -4.2, -0.03), (dx + TW + MW + 0.6, 0.05, 0.02), bevel=0.05, seg=2)
    # أزيار
    fh.lathe_pot("SM2_Jar_A", fh.COL_PROPS, M["clay"], (dx + 0.1, -1.6, 0.0), 1.0, seed=11)
    fh.lathe_pot("SM2_Jar_B", fh.COL_PROPS, M["clay2"], (dx + TW + MW - 0.6, -2.0, 0.0), 0.7, seed=12)
    # دكّة صغيرة + مصباح
    fh.bbox("SM2_Bench", fh.COL_PROPS, M["wall2"], (dx + 3.6, -1.4, 0.0), (dx + 5.0, -0.5, 0.42), bevel=0.035, seg=2)
    fh.bbox("SM2_Bench_Cushion", fh.COL_PROPS, M["cushion"], (dx + 3.7, -1.32, 0.42), (dx + 4.9, -0.55, 0.62), bevel=0.05, seg=2)
    # فانوس على عمود
    sx = dx + TW + MW - 1.4
    fh.beam("SM2_Pole", fh.COL_PROPS, M["palm"], (sx, -3.4, 0.0), (sx, -3.4, 2.5), 0.06, 0.05, seg=8)
    fh.beam("SM2_Pole_Arm", fh.COL_PROPS, M["palm"], (sx, -3.4, 2.44), (sx - 0.42, -3.4, 2.44), 0.034, 0.03, seg=6)
    lx = sx - 0.42
    fh.lathe("SM2_Lantern_Glass", fh.COL_PROPS, M["glow"],
             [(0, 0), (0.085, 0.005), (0.105, 0.09), (0.075, 0.18), (0, 0.19)], segments=12,
             matrix=Matrix.Translation((lx, -3.4, 2.06)))
    fh.lathe("SM2_Lantern_Cap", fh.COL_PROPS, M["iron"],
             [(0, 0), (0.02, 0.0), (0.115, 0.045), (0.10, 0.075), (0, 0.075)], segments=12,
             matrix=Matrix.Translation((lx, -3.4, 2.06 + 0.19)))
    fh.lathe("SM2_Lantern_Flame", fh.COL_PROPS, M["flame"],
             [(0, 0), (0.022, 0.006), (0.015, 0.05), (0, 0.075)], segments=8,
             matrix=Matrix.Translation((lx, -3.4, 2.10)))
    # أشجار
    fh.build_palm(dx + TW + MW + 2.2, -1.6, 6.6, M, "SM2_Palm_A")
    fh.build_tree(dx + 0.6, TD + 3.0, 3.2, M, "SM2_Sidr_A")
    fh.build_tree(dx + TW + 1.0, TD + 2.4, 2.6, M, "SM2_Sidr_B")


def build(M, dx):
    x1 = build_tower(M, dx)
    build_majlis(M, x1)
    build_props(M, dx)


# ---------------------------------------------------------------------------
#  إضافة يمين البيت 001 (الوضع الأساسي)
# ---------------------------------------------------------------------------
DX_RIGHT = 13.0


def main_additive(dx=DX_RIGHT):
    fh.init_collections()
    M = mats()
    build(M, dx)
    fh.add_light("LGT_Tower_Lantern", "POINT", (dx + 2.7, -0.35, 2.3), 32.0, (1.0, 0.58, 0.26), 0.08)
    fh.add_camera("CAM_Village_05", (11.0, -33.0, 11.0), (11.0, 2.0, 4.5), 30.0, shift_y=-0.02)
    fh.add_camera("CAM_Tower_06", (12.8, -16.0, 5.0), (15.9, 2.4, 5.6), 42.0)
    bpy.context.scene.camera = bpy.data.objects["CAM_Village_05"]
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(FH_PATH), "folk_house.blend"))
    return {"objects": len(bpy.data.objects), "saved": bpy.data.filepath}


# ---------------------------------------------------------------------------
#  بناء مستقل (تصميم 002 قائم بذاته)
# ---------------------------------------------------------------------------
def main():
    fh.reset_scene()
    fh.init_collections()
    M = fh.build_materials()
    fh.bbox("SM2_Ground", fh.COL_GROUND, M["sand"], (-30, -30, -0.1), (30, 30, 0.0))
    build(M, 0.0)
    fh.setup_world()
    fh.setup_lights()
    fh.add_camera("CAM_002_Hero", (-9.0, -14.0, 6.0), (4.0, 2.0, 4.0), 36.0)
    fh.setup_render(res=(1600, 900), samples=96)
    bpy.context.scene.camera = bpy.data.objects["CAM_002_Hero"]
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "002_folk_building.blend"))
    return {"objects": len(bpy.data.objects), "saved": bpy.data.filepath}
