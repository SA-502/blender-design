# -*- coding: utf-8 -*-
"""Render helper for the folk house scene."""
import bpy, os

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
OUT_DIR = os.path.join(HERE, "renders")
os.makedirs(OUT_DIR, exist_ok=True)
SC = bpy.context.scene


def shot(cam_name, filename, res=(1600, 900), samples=64, exposure=None, filepath=None):
    SC.camera = bpy.data.objects[cam_name]
    SC.render.resolution_x, SC.render.resolution_y = res
    SC.render.resolution_percentage = 100
    try:
        SC.eevee.taa_render_samples = samples
    except Exception:
        pass
    if exposure is not None:
        SC.view_settings.exposure = exposure
    path = filepath or os.path.join(OUT_DIR, filename)
    SC.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def render_all(prefix="prev", res=(1280, 720), samples=32, only=None):
    out = []
    shots = [
        ("CAM_Hero_01", "hero"),
        ("CAM_Courtyard_02", "courtyard"),
        ("CAM_Door_03", "door"),
        ("CAM_Wide_04", "wide"),
    ]
    for cam, tag in shots:
        if only and tag not in only:
            continue
        out.append(shot(cam, "%s_%s.png" % (prefix, tag), res=res, samples=samples))
    return out
