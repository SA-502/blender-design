# -*- coding: utf-8 -*-
"""دمج كائنات المشهد في مجسمات مجمّعة (Game-ready).

يقلل 2261 أوبجكت إلى ~20 مجسماً:
  • يطبّق الموديفايرز (تحويل إلى Mesh) ثم يدمج كل مجموعة في مجسم واحد.
  • يحافظ على خامات كل جزء (Material Slots).
  • لا يمسّ الإضاءة/الكاميرات/حجم الضباب.
يكتب النتيجة في merge_status.txt
"""
import bpy, os, re, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "merge_status.txt")


def w(m):
    with open(STATUS, "a", encoding="utf-8") as f:
        f.write("%s\n" % m)


with open(STATUS, "w", encoding="utf-8") as f:
    f.write("START %s\n" % time.strftime("%H:%M:%S"))

SKIP = ("SM_Atmosphere",)


def group_key(o):
    n = o.name
    if n.startswith("SM3_"):
        parts = n.split("_")
        cat = parts[1] if len(parts) > 1 else ""
        if cat == "P":
            m = re.search(r"_(N[12]|S[12])_", n)
            return "Village_Props_" + (m.group(1) if m else "Misc")
        if cat == "S":
            m = re.search(r"_(N[12]|S[12])_", n)
            return "Village_Souq_" + (m.group(1) if m else "Base")
        if cat == "H":
            m = re.search(r"(House[A-Za-z])", n)
            return "Village_" + (m.group(1) if m else "HouseMisc")
        if cat == "M":
            return "Village_Mosque"
        if cat == "G":
            return "Village_Ground"
        return "Village_Misc"
    for c in o.users_collection:
        return "Base_" + c.name.replace("COL_", "")
    return "Base_Misc"


def merge_group(objs, name, coll):
    objs = [o for o in objs if o.type == 'MESH']
    if not objs:
        return 0
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    active = objs[0]
    bpy.context.view_layer.objects.active = active
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=active, object=active,
                                       selected_objects=objs, selected_editable_objects=objs):
            # 1) تطبيق الموديفايرز على الكل
            try:
                bpy.ops.object.convert(target='MESH')
            except Exception as e:
                w("convert warn %s: %s" % (name, e))
            # 2) الدمج
            try:
                bpy.ops.object.join()
            except Exception as e:
                w("join fail %s: %s" % (name, e))
                return 0
    merged = bpy.context.view_layer.objects.active
    if merged is None:
        return 0
    merged.name = "MESH_" + name
    if merged.data:
        merged.data.name = "ME_" + name
    for c in list(merged.users_collection):
        c.objects.unlink(merged)
    coll.objects.link(merged)
    return 1


try:
    # مجموعة الدمج
    mcoll = bpy.data.collections.get("COL_MERGED")
    if mcoll is None:
        mcoll = bpy.data.collections.new("COL_MERGED")
        bpy.context.scene.collection.children.link(mcoll)

    groups = {}
    for o in list(bpy.data.objects):
        if o.type != 'MESH':
            continue
        if any(o.name.startswith(s) for s in SKIP):
            continue
        groups.setdefault(group_key(o), []).append(o)
    w("groups=%d  objects_before=%d" % (len(groups), len(bpy.data.objects)))

    made = 0
    for key in sorted(groups):
        objs = groups[key]
        try:
            made += merge_group(objs, key, mcoll)
            w("merged %-28s from %4d objects" % (key, len(objs)))
        except Exception:
            w("MERGE ERROR %s\n%s" % (key, traceback.format_exc()))
    w("merged_meshes=%d  objects_after=%d" % (made, len(bpy.data.objects)))
    bpy.context.view_layer.update()
    # احذف المجموعات القرية الفارغة
    for c in list(bpy.data.collections):
        if c.name.startswith("COL_") and c.name not in ("COL_MERGED",) and not c.objects and not c.children:
            try:
                bpy.data.collections.remove(c)
            except Exception:
                pass
    bpy.ops.wm.save_mainfile()
    w("SAVED objects=%d" % len(bpy.data.objects))
    w("MERGE_OK")
except Exception:
    w("MERGE_FAILED")
    w(traceback.format_exc())
finally:
    w("END %s" % time.strftime("%H:%M:%S"))
    try:
        bpy.ops.wm.quit_blender()
    except Exception:
        pass
