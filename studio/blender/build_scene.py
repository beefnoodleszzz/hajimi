"""CLI helper for rendering a deterministic preview through Blender.

Usage inside a shot directory:

    blender -b --python studio/blender/build_scene.py -- --output /path/out

The scene is intentionally simple: three labelled slabs expose the causal
layer mismatch without asking an image/video model to infer physics.
"""

from __future__ import annotations

import argparse
import sys


def build_scene(output: str | None = None) -> None:  # pragma: no cover - Blender runtime only
    import bpy
    from mathutils import Vector

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 540
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.frame_start = 1
    scene.frame_end = 180
    scene.world.color = (0.01, 0.02, 0.04)

    def material(name: str, color: tuple[float, float, float, float]):
        value = bpy.data.materials.new(name)
        value.diffuse_color = color
        return value

    land = material("LAND", (0.45, 0.27, 0.12, 1))
    air = material("AIR", (0.20, 0.62, 0.72, 1))
    ocean = material("OCEAN", (0.03, 0.24, 0.55, 1))

    def slab(name: str, location: tuple[float, float, float], size: tuple[float, float, float], mat, offset: float = 0.0):
        bpy.ops.mesh.primitive_cube_add(location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = Vector(size)
        obj.data.materials.append(mat)
        obj.keyframe_insert(data_path="location", frame=1, index=0)
        obj.location.x += offset
        obj.keyframe_insert(data_path="location", frame=90, index=0)
        return obj

    slab("LAND", (0, 0, -2.4), (5.5, 1.2, 0.5), land, 0)
    slab("AIR", (1.2, 0, 0), (5.5, 1.2, 0.45), air, 1.2)
    slab("OCEAN", (1.8, 0, 2.3), (5.5, 1.2, 0.5), ocean, 1.8)

    bpy.ops.object.camera_add(location=(0, -18, 0), rotation=(1.5708, 0, 0))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 14
    scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=(0, -6, 8))
    bpy.context.object.data.energy = 900
    bpy.context.object.data.shape = "RECTANGLE"
    bpy.context.object.data.size = 10

    if output:
        scene.render.filepath = output
    bpy.ops.wm.save_as_mainfile(filepath=output.replace(".png", ".blend") if output else "/tmp/hajimi_s007.blend")
    if output:
        bpy.ops.render.render(write_still=True)


def main() -> int:  # pragma: no cover - Blender runtime only
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    args, _ = parser.parse_known_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    build_scene(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
