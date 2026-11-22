# -*- coding: utf-8 -*-
"""خط الإنتاج الكامل للقرية (headless):
   1) بناء/إعادة بناء القرية على المصدر غير المدمج
   2) دمج المشهد في مجسمات مجمّعة (game-ready)
   3) رندر اللقطات
   4) حفظ folk_house.blend

    blender-launcher.exe -b folk_house_source.blend -P pipeline.py
"""
import bpy, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "pipeline_status.txt")
OUT = os.path.join(HERE, "renders")
BUILD = os.path.join(HERE, "build.py")
MERGE = os.path.join(HERE, "merge_scene.py")
os.makedirs(OUT, exist_ok=True)


def w(m):
    with open(STATUS, "a", encoding="utf-8") as f:
        f.write("%s\n" % m)


with open(STATUS, "w", encoding="utf-8") as f:
    f.write("START %s\n" % time.strftime("%H:%M:%S"))

try:
    w("loaded=%s objects_in=%d" % (os.path.basename(bpy.data.filepath), len(bpy.data.objects)))
    # ---------------- 1) BUILD ----------------
    ns = {"__name__": "__main__", "__file__": BUILD}
    with open(BUILD, encoding="utf-8") as f:
        exec(compile(f.read(), BUILD, "exec"), ns)
    res = ns["main_additive"]()
    w("BUILD %r" % (res,))

    # ---------------- 2) MERGE ----------------
    ns2 = {"__name__": "merge_scene", "__file__": MERGE}
    with open(MERGE, encoding="utf-8") as f:
        exec(compile(f.read(), MERGE, "exec"), ns2)
    w("merged objects_now=%d" % len(bpy.data.objects))

    # ---------------- 3) RENDER ----------------
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = 96
    except Exception:
        pass
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    shots = [("CAM_V3_Street", "final_street"), ("CAM_V3_Aerial", "final_aerial"),
             ("CAM_V3_Souq", "final_souq"), ("CAM_V3_Mosque", "final_mosque"),
             ("CAM_V3_Over", "final_over"), ("CAM_Hero_01", "final_house")]
    for cn, fn in shots:
        cam = bpy.data.objects.get(cn)
        if not cam:
            w("MISSING camera %s" % cn)
            continue
        sc.camera = cam
        sc.render.filepath = os.path.join(OUT, fn + ".png")
        bpy.ops.render.render(write_still=True)
        w("rendered %s" % fn)

    # ---------------- 4) SAVE ----------------
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    try:
                        space.shading.type = 'MATERIAL'
                    except Exception:
                        pass
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(HERE), "001_folk_house", "folk_house.blend"))
    w("SAVED objects=%d" % len(bpy.data.objects))
    w("PIPELINE_OK")
except Exception:
    w("PIPELINE_FAILED")
    w(traceback.format_exc())
finally:
    w("END %s" % time.strftime("%H:%M:%S"))
    try:
        bpy.ops.wm.quit_blender()
    except Exception:
        pass
