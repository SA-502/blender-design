# قالب تصميم جديد

مجلد جاهز ومُختبَر. انسخه باسم `NNN_اسم_التصميم` ثم عدّل دالة `build()` فقط:

```powershell
Copy-Item -Recurse designs\_template designs\002_my_design
```

```python
# داخل Blender
p = r"...\designs\002_my_design\build.py"
ns = {"__name__": "__main__", "__file__": p}
exec(compile(open(p, encoding="utf-8").read(), p, "exec"), ns)
ns["main"]()          # يبني المشهد + يحفظ 002_my_design.blend بجانبه

ns["render"]("final_hero.png", res=(1920, 1080), samples=96)
```

## ما يوفره القالب

| الدالة | الوظيفة |
|---|---|
| `reset_scene()` | تفريغ المشهد بالكامل (قاعدة: السكربت يعيد البناء من الصفر) |
| `coll(name)` | إنشاء/جلب مجموعة بأسماء `COL_*` |
| `box(name, col, mat, lo, hi, bevel, seg)` | صندوق من زاوية إلى زاوية |
| `lathe(name, col, mat, profile, segments, matrix)` | جسم دوراني (أزيار، أعمدة، قباب) |
| `srgb("#rrggbb")` | تحويل لون من hex إلى خطّي |
| `material(name, color, rough, metal, bump, noise_scale)` | مادة Principled + نويز/بامب |
| `setup_world_and_lights()` | عالم + شمس |
| `add_camera(loc, target, lens)` | كاميرا موجّهة تلقائياً |
| `setup_render(res, samples)` | EEVEE + AgX + عيّنات |
| `render(file, res, samples)` | رندر PNG داخل `renders/` |

## قواعد

- عدّل `build()` فقط؛ لا تحذف `main()`.
- المقاسات بالمتر و Z للأعلى.
- الأسماء: `SM_` للمجسمات، `MAT_` للمواد، `LGT_` للإضاءة، `CAM_` للكاميرات.
- لا تضع الصور إلا في `renders/`.
