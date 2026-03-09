import bpy
import bmesh
import math
#test

def build_lod_ratios(lod_count):
    lod_count = max(0, int(lod_count))
    if lod_count == 0:
        return []

    step = 1.0 / (lod_count + 1)
    return [round(step * i, 6) for i in range(1, lod_count + 1)]


def apply_collapse_decimate_for_export(context, obj, ratio):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    ratio = max(0.0, min(1.0, float(ratio)))

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    for other in list(context.selected_objects):
        other.select_set(False)

    obj.select_set(True)
    context.view_layer.objects.active = obj

    mod = obj.modifiers.new(name=f"LOD_Collapse_{ratio:.3f}", type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio

    override = context.copy()
    override["active_object"] = obj
    override["object"] = obj
    override["selected_objects"] = [obj]
    override["selected_editable_objects"] = [obj]

    with context.temp_override(**override):
        bpy.ops.object.modifier_apply(modifier=mod.name)

    return obj


def export_object_and_lods_as_fbx(context, obj, output_dir, lod_count):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    exported_paths = []

    # Export original
    export_copy = duplicate_object_for_export(
        context,
        obj,
        new_name=f"{obj.name}_FBX_EXPORT",
    )
    remove_all_materials(export_copy)

    try:
        exported_paths.append(
            export_object_as_fbx(
                context=context,
                obj=export_copy,
                output_dir=output_dir,
                file_name=obj.name,
            )
        )
    finally:
        existing = bpy.data.objects.get(export_copy.name)
        if existing is not None:
            bpy.data.objects.remove(existing, do_unlink=True)

    # Export LODs
    ratios = build_lod_ratios(lod_count)

    for lod_index, ratio in enumerate(reversed(ratios), start=1):
        lod_obj = duplicate_object_for_export(
            context,
            obj,
            new_name=f"{obj.name}_LOD{lod_index}_FBX_EXPORT",
        )
        remove_all_materials(lod_obj)
        apply_collapse_decimate_for_export(context, lod_obj, ratio)

        try:
            exported_paths.append(
                export_object_as_fbx(
                    context=context,
                    obj=lod_obj,
                    output_dir=output_dir,
                    file_name=f"{obj.name}_LOD{lod_index}",
                )
            )
        finally:
            existing = bpy.data.objects.get(lod_obj.name)
            if existing is not None:
                bpy.data.objects.remove(existing, do_unlink=True)

    return exported_paths

def duplicate_object_for_export(context, obj, new_name=None):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    export_obj = obj.copy()

    if obj.data is not None:
        export_obj.data = obj.data.copy()

    context.collection.objects.link(export_obj)
    export_obj.matrix_world = obj.matrix_world.copy()

    if new_name:
        export_obj.name = new_name
        if export_obj.data is not None:
            export_obj.data.name = f"{new_name}_MESH"

    return export_obj


def remove_all_materials(obj):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    obj.data.materials.clear()
    return obj


def export_object_as_fbx(context, obj, output_dir, file_name=None):
    import os

    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    abs_output_dir = bpy.path.abspath(output_dir)
    os.makedirs(abs_output_dir, exist_ok=True)

    if not file_name:
        file_name = obj.name

    if not file_name.lower().endswith(".fbx"):
        file_name = f"{file_name}.fbx"

    export_path = os.path.join(abs_output_dir, file_name)

    previous_selected = list(context.selected_objects)
    previous_active = context.view_layer.objects.active

    try:
        for other in list(context.selected_objects):
            other.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        bpy.ops.export_scene.fbx(
            filepath=export_path,
            use_selection=True,
            axis_forward='-Y',
            axis_up='Z',
            global_scale=1.0,
            apply_unit_scale=True,
            use_space_transform=True,
            bake_space_transform=True,
            use_mesh_modifiers=True,
            use_mesh_modifiers_render=True,
        )
    finally:
        for other in list(context.selected_objects):
            other.select_set(False)

        for prev in previous_selected:
            if prev is not None and prev.name in bpy.data.objects:
                prev.select_set(True)

        if previous_active is not None and previous_active.name in bpy.data.objects:
            context.view_layer.objects.active = previous_active

    return export_path


def _iter_renderable_layer_collections(layer_collection, parent_render_enabled=True):
    """
    Recursively yield LayerCollections that are still eligible for rendering
    in the active view layer.
    """
    if layer_collection is None:
        return

    collection = layer_collection.collection

    this_render_enabled = (
        parent_render_enabled
        and not layer_collection.exclude
        and not collection.hide_render
    )

    if this_render_enabled:
        yield layer_collection

    for child in layer_collection.children:
        yield from _iter_renderable_layer_collections(child, this_render_enabled)


def get_all_rendered_objects(context, include_non_mesh=False):
    """
    Returns all objects that would still be considered render-visible
    in the active scene/view layer, based on:
      - active view layer collection exclusion
      - collection render visibility
      - object render visibility

    By default only mesh objects are returned.
    """
    view_layer = context.view_layer
    root = view_layer.layer_collection

    objects = []
    seen = set()

    for layer_coll in _iter_renderable_layer_collections(root):
        # copy to list() so we do not iterate a live collection while toggling flags later
        for obj in list(layer_coll.collection.objects):
            if obj.name in seen:
                continue
            if obj.hide_render:
                continue
            if not include_non_mesh and obj.type != 'MESH':
                continue

            seen.add(obj.name)
            objects.append(obj)

    return objects


def hide_from_render(objects):
    """
    Hides all given objects from final render.
    Returns the objects for convenience.
    """
    for obj in objects:
        if obj is not None:
            obj.hide_render = True
    return objects


def show_in_render(objects):
    """
    Shows all given objects in final render.
    Returns the objects for convenience.
    """
    for obj in objects:
        if obj is not None:
            obj.hide_render = False
    return objects

def store_render_visibility(objects):
    return {obj.name: obj.hide_render for obj in objects if obj is not None}


def restore_render_visibility(state):
    for obj_name, hide_render in state.items():
        obj = bpy.data.objects.get(obj_name)
        if obj is not None:
            obj.hide_render = hide_render

def add_unsubdivide_modifier(obj, iterations=1):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    iterations = max(1, int(iterations))

    mod = obj.modifiers.new(name="GameReady Unsubdivide", type='DECIMATE')
    mod.decimate_type = 'UNSUBDIV'
    mod.iterations = iterations

    # Place it after the last Subdivision Surface modifier, if one exists.
    last_subsurf_index = -1
    for i, existing_mod in enumerate(obj.modifiers):
        if existing_mod == mod:
            continue
        if existing_mod.type == 'SUBSURF':
            last_subsurf_index = i

    current_index = len(obj.modifiers) - 1
    target_index = last_subsurf_index + 1 if last_subsurf_index >= 0 else current_index

    if target_index != current_index:
        obj.modifiers.move(current_index, target_index)

    return mod


def add_unsubdivide_to_objects(objects, iterations=1):
    valid_objects = []

    for obj in objects:
        if obj is not None and obj.type == 'MESH':
            add_unsubdivide_modifier(obj, iterations)
            valid_objects.append(obj)

    return valid_objects

def remove_custom_normals(obj):

    bpy.ops.object.mode_set(mode='OBJECT')
    for o in bpy.context.selected_objects:
        o.select_set(False)

    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.mesh.customdata_custom_splitnormals_clear()

def duplicate_active(context) -> bpy.types.Object:
    scene = context.scene
    obj = context.active_object

    new_obj = obj.copy()

    if obj.data is not None:
        new_obj.data = obj.data.copy()

    context.collection.objects.link(new_obj)
    new_obj.matrix_world = obj.matrix_world.copy()

   
    for selected_obj in context.selected_objects:
        selected_obj.select_set(False)

    new_obj.select_set(True)
    context.view_layer.objects.active = new_obj
    return new_obj

def duplicate_selected(context) -> list[bpy.types.Object]:
    scene = context.scene
    selected_objects = context.selected_objects

    new_objects = []
    for obj in selected_objects:
        new_obj = obj.copy()
        if obj.data is not None:
            new_obj.data = obj.data.copy()
        context.collection.objects.link(new_obj)
        new_obj.matrix_world = obj.matrix_world.copy()
        new_objects.append(new_obj)

    for selected_obj in selected_objects:
        selected_obj.select_set(False)

    for new_obj in new_objects:
        new_obj.select_set(True)

    if new_objects:
        context.view_layer.objects.active = new_objects[0]

    return new_objects

def apply_transform_to_selected(context, apply_location=False, apply_rotation=True, apply_scale=True):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    if not context.selected_objects:
        return

    bpy.ops.object.transform_apply(
        location=apply_location,
        rotation=apply_rotation,
        scale=apply_scale,
    )

def join_objects(context, objects):
    if not objects:
        return None
    
    if len(objects) == 1:
        return objects[0]

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    active_obj = objects[0]

    override = context.copy()
    override["active_object"] = active_obj
    override["object"] = active_obj
    override["selected_objects"] = objects
    override["selected_editable_objects"] = objects

    with context.temp_override(**override):
        bpy.ops.object.join()

    return active_obj

def triangulate_object(obj):
    if obj is None or obj.type != 'MESH':
        raise ValueError("triangulate_object: obj must be a mesh object")

    mesh = obj.data

    bm = bmesh.new()
    bm.from_mesh(mesh)

    bmesh.ops.triangulate(
        bm,
        faces=bm.faces[:],
    )

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    return obj

def select_objects(context, objects):
    for obj in context.selected_objects:
        obj.select_set(False)

    for obj in objects:
        obj.select_set(True)

    if objects:
        context.view_layer.objects.active = objects[0]

def _is_valid_mesh_object(obj: bpy.types.Object) -> bool:
    try:
        return (
            obj is not None
            and obj.name in bpy.data.objects
            and obj.type == 'MESH'
            and obj.data is not None
        )
    except ReferenceError:
        return False

def _is_volumetric_mesh(obj: bpy.types.Object, volume_epsilon: float = 1e-6) -> bool:
    if not _is_valid_mesh_object(obj):
        return False

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()

    try:
        if len(bm.faces) == 0:
            return False

        all_edges_manifold = all(edge.is_manifold for edge in bm.edges)
        volume = abs(bm.calc_volume())

        return all_edges_manifold and volume > volume_epsilon
    finally:
        bm.free()


def _cleanup_union_result(obj: bpy.types.Object, merge_distance: float = 0.00001) -> bpy.types.Object:
    if not _is_valid_mesh_object(obj):
        return obj

    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()

    bmesh.ops.remove_doubles(
        bm,
        verts=list(bm.verts),
        dist=merge_distance,
    )

    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

    bm.to_mesh(me)
    me.update()
    bm.free()

    return obj


def _boolean_union_only(context, objects: list[bpy.types.Object]) -> bpy.types.Object | None:
    objects = [obj for obj in objects if _is_valid_mesh_object(obj)]

    if not objects:
        return None

    if len(objects) == 1:
        return objects[0]

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    base = objects[0]
    all_inputs_manifold = all(_is_volumetric_mesh(obj) for obj in objects)

    for obj in context.selected_objects:
        obj.select_set(False)

    base.select_set(True)
    context.view_layer.objects.active = base

    for other in objects[1:]:
        if not _is_valid_mesh_object(other):
            continue

        mod = base.modifiers.new(name=f"GR_Union_{other.name}", type='BOOLEAN')
        mod.operation = 'UNION'
        mod.operand_type = 'OBJECT'
        mod.object = other
        mod.solver = 'MANIFOLD' if all_inputs_manifold else 'EXACT'

        override = context.copy()
        override["active_object"] = base
        override["object"] = base
        override["selected_objects"] = [base]
        override["selected_editable_objects"] = [base]

        with context.temp_override(**override):
            bpy.ops.object.modifier_apply(modifier=mod.name)

        if _is_valid_mesh_object(other):
            bpy.data.objects.remove(other, do_unlink=True)

    return _cleanup_union_result(base)


def union(context, new_objects: list[bpy.types.Object]) -> bpy.types.Object | None:
    mesh_objects = [obj for obj in new_objects if _is_valid_mesh_object(obj)]

    if not mesh_objects:
        return None

    volumetric_objects = []
    floating_objects = []

    for obj in mesh_objects:
        if _is_volumetric_mesh(obj):
            volumetric_objects.append(obj)
        else:
            floating_objects.append(obj)

    # Step 1: union only real volumetric meshes
    union_result = _boolean_union_only(context, volumetric_objects)

    # Step 2: join floating planes back in
    if union_result and floating_objects:
        combined = [union_result] + [obj for obj in floating_objects if _is_valid_mesh_object(obj)]
        return join_objects(context, combined)

    if union_result:
        return union_result

    # Only floating/non-volumetric meshes were present
    return join_objects(context, floating_objects)

def decimate_planar(obj, angle_degrees=5.0, apply_modifier=True, dissolve_boundaries=False):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mod = obj.modifiers.new(name="Planar Decimate", type='DECIMATE')
    mod.decimate_type = 'DISSOLVE'
    mod.angle_limit = math.radians(angle_degrees)
    mod.use_dissolve_boundaries = dissolve_boundaries

    if apply_modifier:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=mod.name)

def decimate_collapse(obj, ratio=0.5, apply_modifier=True):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mod = obj.modifiers.new(name="Collapse Decimate", type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio

    if apply_modifier:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=mod.name)

def merge_by_distance(context, obj, distance=0.0001):
    if obj is None or obj.type != 'MESH':
        raise ValueError("Object must be a mesh")

    # Make object active and selected
    for o in context.selected_objects:
        o.select_set(False)

    obj.select_set(True)
    context.view_layer.objects.active = obj

    # Switch to edit mode
    if context.mode != 'EDIT_MESH':
        bpy.ops.object.mode_set(mode='EDIT')

    # Select everything and merge by distance
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=distance)

    # Back to object mode
    bpy.ops.object.mode_set(mode='OBJECT')

def apply_modifiers_to_selected(context):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    selected_mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

    for obj in selected_mesh_objects:
        # Make this object the only active selected one
        for other in context.selected_objects:
            other.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Copy names first because applying/removing modifiers changes the collection
        modifier_names = [mod.name for mod in obj.modifiers]

        for mod_name in modifier_names:
            if mod_name not in obj.modifiers:
                continue

            override = context.copy()
            override["active_object"] = obj
            override["object"] = obj
            override["selected_objects"] = [obj]
            override["selected_editable_objects"] = [obj]

            with context.temp_override(**override):
                bpy.ops.object.modifier_apply(modifier=mod_name)


class MaterialUtils:

    @staticmethod
    def flip_normal_map_y(image):
        if image is None:
            raise ValueError("Image is required")

        pixels = list(image.pixels)

        if not pixels:
            return image

        # RGBA float pixels, so green is index 1 in every 4-float pixel
        for i in range(0, len(pixels), 4):
            pixels[i + 1] = 1.0 - pixels[i + 1]

        image.pixels[:] = pixels
        image.update()

        try:
            if image.filepath_raw:
                image.save()
        except Exception:
            pass

        return image

    @staticmethod
    def _node_has_any_linked_output(node):
        for socket in node.outputs:
            if socket.is_linked:
                return True
        return False

    @staticmethod
    def remove_unplugged_texture_nodes(material):
        """
        Remove all image texture nodes from a material whose outputs are unused.
        Returns the images that may have become orphaned.
        """
        if material is None or not material.use_nodes or material.node_tree is None:
            return []

        nodes = material.node_tree.nodes
        candidate_images = []

        for node in list(nodes):
            if node.bl_idname != "ShaderNodeTexImage":
                continue

            if MaterialUtils._node_has_any_linked_output(node):
                continue

            if node.image is not None:
                candidate_images.append(node.image)

            nodes.remove(node)

        return candidate_images

    @staticmethod
    def cleanup_unplugged_textures_on_object(obj):
        """
        Remove every unplugged image texture node on the object's materials,
        then delete any images that became unused because of that.
        """
        if obj is None or obj.type != 'MESH':
            return {"removed_nodes": 0, "removed_images": 0}

        removed_nodes = 0
        candidate_images = []
        seen_materials = set()

        for slot in obj.material_slots:
            mat = slot.material
            if mat is None:
                continue

            mat_key = mat.as_pointer()
            if mat_key in seen_materials:
                continue
            seen_materials.add(mat_key)

            before = len(mat.node_tree.nodes) if (mat.use_nodes and mat.node_tree) else 0
            imgs = MaterialUtils.remove_unplugged_texture_nodes(mat)
            after = len(mat.node_tree.nodes) if (mat.use_nodes and mat.node_tree) else 0

            removed_nodes += max(0, before - after)
            candidate_images.extend(imgs)

        removed_images = 0
        for img in set(candidate_images):
            try:
                if img is not None and img.users == 0:
                    bpy.data.images.remove(img, do_unlink=True)
                    removed_images += 1
            except ReferenceError:
                pass

        return {
            "removed_nodes": removed_nodes,
            "removed_images": removed_images,
        }

    @staticmethod
    def purge_unused_images():
        removed = 0
        for img in list(bpy.data.images):
            if img.users == 0:
                bpy.data.images.remove(img, do_unlink=True)
                removed += 1
        return removed

    @staticmethod
    def purge_unused_materials():
        removed = 0
        for mat in list(bpy.data.materials):
            if mat.users == 0:
                bpy.data.materials.remove(mat, do_unlink=True)
                removed += 1
        return removed

    @staticmethod
    def cleanup_unused_textures_and_materials(obj=None):
        """
        1) Remove unplugged texture nodes on obj's materials
        2) Remove now-unused images
        3) Remove now-unused materials
        4) Purge any remaining orphan data-blocks recursively
        """
        stats = {
            "removed_nodes": 0,
            "removed_images": 0,
            "removed_materials": 0,
        }

        if obj is not None and obj.type == 'MESH':
            result = MaterialUtils.cleanup_unplugged_textures_on_object(obj)
            stats["removed_nodes"] += result["removed_nodes"]
            stats["removed_images"] += result["removed_images"]

        stats["removed_images"] += MaterialUtils.purge_unused_images()
        stats["removed_materials"] += MaterialUtils.purge_unused_materials()

        try:
            bpy.data.orphans_purge(do_recursive=True)
        except TypeError:
            bpy.data.orphans_purge()

        return stats

    @staticmethod
    def _ensure_dir(path):
        import os
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def _new_placeholder_image(scene, obj_name, suffix, size, alpha=False, is_data=False):
        import os

        image_name = f"{obj_name}_{suffix}"
        image = bpy.data.images.new(
            name=image_name,
            width=size,
            height=size,
            alpha=alpha,
        )

        # Nice default preview colors for placeholders
        if suffix == "BaseColor":
            image.generated_color = (1.0, 1.0, 1.0, 0.0 if alpha else 1.0)
        elif suffix == "Normal":
            image.generated_color = (0.5, 0.5, 1.0, 1.0)
        elif suffix in {"Roughness", "ORM"}:
            image.generated_color = (1.0, 1.0, 1.0, 1.0)
        else:
            image.generated_color = (0.0, 0.0, 0.0, 1.0)

        # Color management
        try:
            image.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
        except Exception:
            pass

        # Optional file path for later saving/baking
        try:
            output_dir = bpy.path.abspath(scene.gameready_output_dir)
            MaterialUtils._ensure_dir(output_dir)
            image.filepath_raw = os.path.join(output_dir, f"{image_name}.png")
            image.file_format = 'PNG'
        except Exception:
            pass

        return image

    @staticmethod
    def _get_bsdf_input(bsdf, *names):
        for name in names:
            sock = bsdf.inputs.get(name)
            if sock is not None:
                return sock
        return None

    @staticmethod
    def _add_image_node(nodes, image, label, x, y):
        node = nodes.new("ShaderNodeTexImage")
        node.label = label
        node.name = label
        node.image = image
        node.location = (x, y)
        return node

    @staticmethod
    def _clear_emit_bake_proxy_nodes(nodes):
        for node in list(nodes):
            if node.name.startswith("GR_EmitBakeProxy") or node.name.startswith("GR_EmitBakeHelper"):
                nodes.remove(node)


    @staticmethod
    def _connect_socket_to_emission(source_socket, emit_node, links):
        socket_type = getattr(source_socket, "type", None)

        # Scalar-like sockets are better routed to Emission Strength with white color
        if socket_type in {"VALUE", "INT", "BOOLEAN"}:
            emit_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            links.new(source_socket, emit_node.inputs["Strength"])
        else:
            links.new(source_socket, emit_node.inputs["Color"])


    @staticmethod
    def setup_bake_material(obj, scene):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        size = int(scene.gameready_texture_size)

        # Remove all material slots from the object
        obj.data.materials.clear()

        # Create fresh material
        mat = bpy.data.materials.new(name=f"{obj.name}_MAT")
        mat.use_nodes = True
        obj.data.materials.append(mat)

        # If alpha should be used, make the material transparent-capable
        if scene.gameready_bake_alpha:
            try:
                mat.blend_method = 'BLEND'
            except Exception:
                pass

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (900, 0)

        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (500, 0)

        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

        base_color_input = MaterialUtils._get_bsdf_input(bsdf, "Base Color")
        alpha_input = MaterialUtils._get_bsdf_input(bsdf, "Alpha")
        roughness_input = MaterialUtils._get_bsdf_input(bsdf, "Roughness")
        metallic_input = MaterialUtils._get_bsdf_input(bsdf, "Metallic")
        normal_input = MaterialUtils._get_bsdf_input(bsdf, "Normal")
        emission_input = MaterialUtils._get_bsdf_input(bsdf, "Emission Color", "Emission")

        created_images = {}

        x_tex = -900
        y = 500
        y_step = -260

        # Base Color (+ optional Alpha)
        if scene.gameready_bake_base_color:
            final_img = MaterialUtils._new_placeholder_image(
                scene, obj.name, "BaseColor", size,
                alpha=scene.gameready_bake_alpha,
                is_data=False,
            )
            created_images["base_color"] = final_img

            final_tex = MaterialUtils._add_image_node(nodes, final_img, "Base Color", x_tex, y)
            if base_color_input is not None:
                links.new(final_tex.outputs["Color"], base_color_input)
            if scene.gameready_bake_alpha and alpha_input is not None:
                links.new(final_tex.outputs["Alpha"], alpha_input)
            y += y_step

            # When alpha is enabled, bake RGB and Alpha into separate temporary images first,
            # then combine them into the final RGBA base_color image.
            if scene.gameready_bake_alpha:
                rgb_tmp = MaterialUtils._new_placeholder_image(
                    scene, obj.name, "BaseColor_RGB_TMP", size,
                    alpha=False,
                    is_data=False,
                )
                created_images["base_color_rgb_tmp"] = rgb_tmp
                MaterialUtils._add_image_node(nodes, rgb_tmp, "Base Color RGB Bake", x_tex, y)
                y += y_step

                alpha_tmp = MaterialUtils._new_placeholder_image(
                    scene, obj.name, "BaseColor_Alpha_TMP", size,
                    alpha=False,
                    is_data=True,
                )
                created_images["base_color_alpha_tmp"] = alpha_tmp
                MaterialUtils._add_image_node(nodes, alpha_tmp, "Base Color Alpha Bake", x_tex, y)
                y += y_step

        # Emission
        if scene.gameready_bake_emission:
            img = MaterialUtils._new_placeholder_image(
                scene, obj.name, "Emission", size,
                alpha=False,
                is_data=False,
            )
            created_images["emission"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Emission", x_tex, y)
            if emission_input is not None:
                links.new(tex.outputs["Color"], emission_input)
            y += y_step

        # Normal
        if scene.gameready_bake_normal:
            img = MaterialUtils._new_placeholder_image(
                scene, obj.name, "Normal", size,
                alpha=False,
                is_data=True,
            )
            created_images["normal"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Normal", x_tex, y)

            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (-250, y)

            links.new(tex.outputs["Color"], normal_map.inputs["Color"])
            if normal_input is not None:
                links.new(normal_map.outputs["Normal"], normal_input)
            y += y_step

        # Always create selected individual maps
        if scene.gameready_bake_ao:
            img = MaterialUtils._new_placeholder_image(
                scene, obj.name, "AO", size,
                alpha=False,
                is_data=True,
            )
            created_images["ao"] = img
            MaterialUtils._add_image_node(nodes, img, "AO", x_tex, y)
            y += y_step

        if scene.gameready_bake_roughness:
            img = MaterialUtils._new_placeholder_image(
                scene, obj.name, "Roughness", size,
                alpha=False,
                is_data=True,
            )
            created_images["roughness"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Roughness", x_tex, y)
            if roughness_input is not None:
                links.new(tex.outputs["Color"], roughness_input)
            y += y_step

        if scene.gameready_bake_metallic:
            img = MaterialUtils._new_placeholder_image(
                scene, obj.name, "Metallic", size,
                alpha=False,
                is_data=True,
            )
            created_images["metallic"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Metallic", x_tex, y)
            if metallic_input is not None:
                links.new(tex.outputs["Color"], metallic_input)
            y += y_step

        # Create packed ORM only if all three channels are enabled
        create_orm = (
            scene.gameready_pack_as_orm
            and scene.gameready_bake_ao
            and scene.gameready_bake_roughness
            and scene.gameready_bake_metallic
        )

        if create_orm:
            img = MaterialUtils._new_placeholder_image(
                scene, obj.name, "ORM", size,
                alpha=False,
                is_data=True,
            )
            created_images["orm"] = img

            orm_tex = MaterialUtils._add_image_node(nodes, img, "ORM", x_tex, y)

            separate = nodes.new("ShaderNodeSeparateColor")
            separate.location = (-250, y)

            links.new(orm_tex.outputs["Color"], separate.inputs["Color"])

            if roughness_input is not None:
                links.new(separate.outputs["Green"], roughness_input)

            if metallic_input is not None:
                links.new(separate.outputs["Blue"], metallic_input)

            y += y_step

        return mat, created_images
    

    def bake_normal_selected_to_active(context, source_obj, target_obj, target_image, extrusion, margin):
        if source_obj is None or target_obj is None:
            raise ValueError("Source and target objects are required")

        if source_obj.type != 'MESH' or target_obj.type != 'MESH':
            raise ValueError("Source and target must be mesh objects")

        if target_image is None:
            raise ValueError("Target image is required")

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect everything first
        for obj in context.selected_objects:
            obj.select_set(False)

        # Select high-poly source first
        source_obj.select_set(True)

        # Select low-poly target and make it active
        target_obj.select_set(True)
        context.view_layer.objects.active = target_obj

        mat = target_obj.active_material
        if mat is None or not mat.use_nodes:
            raise ValueError("Target object needs an active node material")

        nodes = mat.node_tree.nodes

        # Find the image texture node that uses the normal image
        normal_node = None
        for node in nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image == target_image:
                normal_node = node
                break

        if normal_node is None:
            raise ValueError("Could not find the normal image texture node")

        # Make this the active bake target node
        for node in nodes:
            node.select = False

        normal_node.select = True
        nodes.active = normal_node

        scene = context.scene

        # Mirror the UI bake settings
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = extrusion
        scene.render.bake.margin = margin
        scene.render.bake.target = 'IMAGE_TEXTURES'
        scene.render.bake.use_clear = True

        # Optional but typical for game normal maps
        if hasattr(scene.render.bake, "normal_space"):
            scene.render.bake.normal_space = 'TANGENT'

        bpy.ops.object.bake(
            type='NORMAL',
            use_selected_to_active=True,
            cage_extrusion=extrusion,
            margin=margin,
        )

        # Save if the image has a path
        try:
            if target_image.filepath_raw:
                target_image.save()
        except Exception:
            pass

    @staticmethod
    def bake_ao_selected_to_active(context, source_obj, target_obj, target_image, extrusion, margin):
        if source_obj is None or target_obj is None:
            raise ValueError("Source and target objects are required")

        if source_obj.type != 'MESH' or target_obj.type != 'MESH':
            raise ValueError("Source and target must be mesh objects")

        if target_image is None:
            raise ValueError("Target image is required")

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect everything first
        for obj in context.selected_objects:
            obj.select_set(False)

        # Select high-poly source first
        source_obj.select_set(True)

        # Select low-poly target and make it active
        target_obj.select_set(True)
        context.view_layer.objects.active = target_obj

        mat = target_obj.active_material
        if mat is None or not mat.use_nodes:
            raise ValueError("Target object needs an active node material")

        nodes = mat.node_tree.nodes

        # Find the AO image texture node
        ao_node = None
        for node in nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image == target_image:
                ao_node = node
                break

        if ao_node is None:
            raise ValueError("Could not find the AO image texture node")

        # Make this the active bake target node
        for node in nodes:
            node.select = False

        ao_node.select = True
        nodes.active = ao_node

        scene = context.scene

        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = extrusion
        scene.render.bake.margin = margin
        scene.render.bake.target = 'IMAGE_TEXTURES'
        scene.render.bake.use_clear = True

        bpy.ops.object.bake(
            type='AO',
            use_selected_to_active=True,
            cage_extrusion=extrusion,
            margin=margin,
        )

        try:
            if target_image.filepath_raw:
                target_image.save()
        except Exception:
            pass

    @staticmethod
    def make_materials_single_user(obj):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        copied = {}

        for slot in obj.material_slots:
            mat = slot.material
            if mat is None:
                continue

            key = mat.name_full
            if key not in copied:
                copied[key] = mat.copy()

            slot.material = copied[key]


    @staticmethod
    def _get_active_output_node(nodes):
        for node in nodes:
            if node.bl_idname == "ShaderNodeOutputMaterial" and getattr(node, "is_active_output", False):
                return node

        for node in nodes:
            if node.bl_idname == "ShaderNodeOutputMaterial":
                return node

        node = nodes.new("ShaderNodeOutputMaterial")
        node.location = (600, 0)
        return node


    @staticmethod
    def _get_first_principled_node(nodes):
        for node in nodes:
            if node.bl_idname == "ShaderNodeBsdfPrincipled":
                return node
        return None


    @staticmethod
    def _remove_links_from_socket(node_tree_links, socket):
        for link in list(socket.links):
            node_tree_links.remove(link)


    @staticmethod
    def _socket_default_to_rgba(socket):
        value = getattr(socket, "default_value", 0.0)

        if isinstance(value, (int, float)):
            v = float(value)
            return (v, v, v, 1.0)

        try:
            values = list(value)
            if len(values) >= 4:
                return (
                    float(values[0]),
                    float(values[1]),
                    float(values[2]),
                    float(values[3]),
                )
            if len(values) == 3:
                return (
                    float(values[0]),
                    float(values[1]),
                    float(values[2]),
                    1.0,
                )
            if len(values) == 1:
                v = float(values[0])
                return (v, v, v, 1.0)
        except TypeError:
            pass

        return (0.0, 0.0, 0.0, 1.0)

    @staticmethod
    def prepare_object_materials_for_emit_bake(obj, channel):
        """
        Rewires each material on obj so the requested Principled input is emitted
        through Material Output -> Surface.

        channel:
            'BASE_COLOR'
            'ALPHA'
            'ROUGHNESS'
            'METALLIC'
            'EMISSION'

        Behavior:
        - BASE_COLOR:
            if linked -> forward the linked input
            if not linked -> use Principled Base Color default value
        - ALPHA / ROUGHNESS / METALLIC:
            if linked -> forward the linked input
            if not linked -> use the Principled socket default value as grayscale
        - EMISSION:
            if linked -> forward the linked input
            if not linked -> keep black
        """
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        channel = channel.upper()
        if channel not in {"BASE_COLOR", "ALPHA", "ROUGHNESS", "METALLIC", "EMISSION"}:
            raise ValueError(f"Unsupported channel: {channel}")

        for slot in obj.material_slots:
            mat = slot.material
            if mat is None:
                continue

            if not mat.use_nodes:
                mat.use_nodes = True

            node_tree = mat.node_tree
            nodes = node_tree.nodes
            links = node_tree.links

            output = MaterialUtils._get_active_output_node(nodes)
            bsdf = MaterialUtils._get_first_principled_node(nodes)

            MaterialUtils._clear_emit_bake_proxy_nodes(nodes)

            surface_input = output.inputs.get("Surface")
            if surface_input is None:
                continue

            MaterialUtils._remove_links_from_socket(links, surface_input)

            emit = nodes.new("ShaderNodeEmission")
            emit.name = "GR_EmitBakeProxy"
            emit.label = f"GR Emit Bake {channel.title()}"
            emit.location = (output.location.x - 260, output.location.y)
            emit.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
            emit.inputs["Strength"].default_value = 1.0

            source_input = None
            if bsdf is not None:
                if channel == "BASE_COLOR":
                    source_input = MaterialUtils._get_bsdf_input(bsdf, "Base Color")
                elif channel == "ALPHA":
                    source_input = MaterialUtils._get_bsdf_input(bsdf, "Alpha")
                elif channel == "ROUGHNESS":
                    source_input = MaterialUtils._get_bsdf_input(bsdf, "Roughness")
                elif channel == "METALLIC":
                    source_input = MaterialUtils._get_bsdf_input(bsdf, "Metallic")
                elif channel == "EMISSION":
                    source_input = MaterialUtils._get_bsdf_input(bsdf, "Emission Color", "Emission")

            if source_input is not None:
                if source_input.is_linked and len(source_input.links) > 0:
                    source_socket = source_input.links[0].from_socket
                    MaterialUtils._connect_socket_to_emission(source_socket, emit, links)

                elif channel == "BASE_COLOR":
                    emit.inputs["Color"].default_value = MaterialUtils._socket_default_to_rgba(source_input)

                elif channel in {"ALPHA", "ROUGHNESS", "METALLIC"}:
                    default_rgba = MaterialUtils._socket_default_to_rgba(source_input)
                    v = float(default_rgba[0])
                    emit.inputs["Color"].default_value = (v, v, v, 1.0)

                # EMISSION stays black when unlinked

            links.new(emit.outputs["Emission"], surface_input)

    @staticmethod
    def combine_orm_images(ao_image, roughness_image, metallic_image, target_image):
        if ao_image is None or roughness_image is None or metallic_image is None or target_image is None:
            raise ValueError("AO, roughness, metallic, and target images are required")

        ao_size = tuple(ao_image.size)
        roughness_size = tuple(roughness_image.size)
        metallic_size = tuple(metallic_image.size)
        target_size = tuple(target_image.size)

        if not (ao_size == roughness_size == metallic_size == target_size):
            raise ValueError("All ORM images must have the same size")

        ao_pixels = list(ao_image.pixels)
        roughness_pixels = list(roughness_image.pixels)
        metallic_pixels = list(metallic_image.pixels)

        out_pixels = [0.0] * len(ao_pixels)

        for i in range(0, len(out_pixels), 4):
            # All three baked maps are grayscale, so sampling red is enough
            out_pixels[i]     = ao_pixels[i]         # R = AO
            out_pixels[i + 1] = roughness_pixels[i]  # G = Roughness
            out_pixels[i + 2] = metallic_pixels[i]   # B = Metallic
            out_pixels[i + 3] = 1.0                  # A = fully opaque

        try:
            target_image.alpha_mode = 'STRAIGHT'
        except Exception:
            pass

        try:
            target_image.file_format = 'PNG'
        except Exception:
            pass

        target_image.pixels[:] = out_pixels
        target_image.update()

        try:
            if target_image.filepath_raw:
                target_image.save()
        except Exception:
            pass

    @staticmethod
    def debug_grayscale_range(image, label="Image"):
        if image is None:
            print(f"{label}: image is None")
            return

        pixels = list(image.pixels)
        values = pixels[0::4]  # red channel; fine for grayscale bake

        if not values:
            print(f"{label}: no pixels found")
            return

        print(f"{label}: value min={min(values):.6f}, max={max(values):.6f}")

    @staticmethod
    def combine_rgb_and_alpha_images(rgb_image, alpha_image, target_image):
        if rgb_image is None or alpha_image is None or target_image is None:
            raise ValueError("RGB, alpha, and target images are required")

        rgb_size = tuple(rgb_image.size)
        alpha_size = tuple(alpha_image.size)
        target_size = tuple(target_image.size)

        if rgb_size != alpha_size or rgb_size != target_size:
            raise ValueError("All images must have the same size")

        rgb_pixels = list(rgb_image.pixels)
        alpha_pixels = list(alpha_image.pixels)

        out_pixels = [0.0] * len(rgb_pixels)

        for i in range(0, len(rgb_pixels), 4):
            out_pixels[i] = rgb_pixels[i]
            out_pixels[i + 1] = rgb_pixels[i + 1]
            out_pixels[i + 2] = rgb_pixels[i + 2]

            # alpha bake is stored as grayscale in RGB, so use red
            out_pixels[i + 3] = alpha_pixels[i]

        try:
            target_image.alpha_mode = 'STRAIGHT'
        except Exception:
            pass

        try:
            target_image.file_format = 'PNG'
        except Exception:
            pass

        target_image.pixels[:] = out_pixels
        target_image.update()

        # DO NOT reload here

        try:
            if target_image.filepath_raw:
                target_image.save()
        except Exception:
            pass

    @staticmethod
    def bake_emit_selected_to_active(context, source_obj, target_obj, target_image, extrusion, margin):
        if source_obj is None or target_obj is None:
            raise ValueError("Source and target objects are required")

        if source_obj.type != 'MESH' or target_obj.type != 'MESH':
            raise ValueError("Source and target must be mesh objects")

        if target_image is None:
            raise ValueError("Target image is required")

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for obj in context.selected_objects:
            obj.select_set(False)

        source_obj.select_set(True)
        target_obj.select_set(True)
        context.view_layer.objects.active = target_obj

        mat = target_obj.active_material
        if mat is None or not mat.use_nodes:
            raise ValueError("Target object needs an active node material")

        nodes = mat.node_tree.nodes

        target_node = None
        for node in nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image == target_image:
                target_node = node
                break

        if target_node is None:
            raise ValueError("Could not find the target image texture node")

        for node in nodes:
            node.select = False

        target_node.select = True
        nodes.active = target_node

        scene = context.scene
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = extrusion
        scene.render.bake.margin = margin
        scene.render.bake.target = 'IMAGE_TEXTURES'
        scene.render.bake.use_clear = True

        bpy.ops.object.bake(
            type='EMIT',
            use_selected_to_active=True,
            cage_extrusion=extrusion,
            margin=margin,
        )

        try:
            if target_image.filepath_raw:
                target_image.save()
        except Exception:
            pass


class CyclesUtils:
    @staticmethod
    def _refresh_cycles_devices(cprefs):
        try:
            cprefs.refresh_devices()
            return
        except Exception:
            pass

        try:
            cprefs.get_devices()
        except Exception:
            pass

    @staticmethod
    def _iter_cycles_devices(cprefs):
        devices = getattr(cprefs, "devices", [])
        for entry in devices:
            if hasattr(entry, "use") and hasattr(entry, "type"):
                yield entry
            else:
                try:
                    for sub in entry:
                        if hasattr(sub, "use") and hasattr(sub, "type"):
                            yield sub
                except TypeError:
                    pass

    @staticmethod
    def configure_cycles(scene, samples=512):
        scene.render.engine = 'CYCLES'

        backend_used = None
        denoiser_used = 'OPENIMAGEDENOISE'

        prefs = bpy.context.preferences
        cycles_addon = prefs.addons.get("cycles")

        if cycles_addon is not None:
            cprefs = cycles_addon.preferences

            for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
                try:
                    cprefs.compute_device_type = backend
                    CyclesUtils._refresh_cycles_devices(cprefs)

                    gpu_found = False
                    for device in CyclesUtils._iter_cycles_devices(cprefs):
                        # enable GPU devices, disable CPU
                        use_device = (getattr(device, "type", None) != 'CPU')
                        device.use = use_device
                        if use_device:
                            gpu_found = True

                    if gpu_found:
                        scene.cycles.device = 'GPU'
                        backend_used = backend
                        break
                except Exception:
                    continue

        if backend_used is None:
            scene.cycles.device = 'CPU'

        print("Backend:", backend_used)
        for device in CyclesUtils._iter_cycles_devices(cprefs):
            print(device.name, device.type, device.use)

        scene.cycles.samples = samples
        scene.cycles.preview_samples = min(samples, 64)

        if hasattr(scene.cycles, "use_adaptive_sampling"):
            scene.cycles.use_adaptive_sampling = False

        if hasattr(scene.cycles, "use_denoising"):
            scene.cycles.use_denoising = True

        # Automatic prefers GPU-accelerated denoising when supported.
        # OptiX is NVIDIA-only; OIDN is the usual default.
        if backend_used == "OPTIX":
            denoiser_used = 'OPTIX'
        else:
            denoiser_used = 'OPENIMAGEDENOISE'

        if hasattr(scene.cycles, "denoiser"):
            try:
                scene.cycles.denoiser = denoiser_used
            except Exception:
                pass

        if hasattr(scene.cycles, "use_preview_denoising"):
            scene.cycles.use_preview_denoising = True

        if hasattr(scene.cycles, "preview_denoiser"):
            try:
                scene.cycles.preview_denoiser = denoiser_used
            except Exception:
                pass

        # This is the checkbox you are looking for in Render > Denoise > Use GPU
        if hasattr(scene.cycles, "denoising_use_gpu"):
            try:
                scene.cycles.denoising_use_gpu = (backend_used is not None)
            except Exception:
                pass

        # Optional: viewport denoise GPU too, if present
        if hasattr(scene.cycles, "preview_denoising_use_gpu"):
            try:
                scene.cycles.preview_denoising_use_gpu = (backend_used is not None)
            except Exception:
                pass

        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        return {
            "engine": scene.render.engine,
            "device": scene.cycles.device,
            "backend": backend_used if backend_used else "CPU",
            "samples": scene.cycles.samples,
            "denoiser": denoiser_used,
            "denoising_use_gpu": getattr(scene.cycles, "denoising_use_gpu", None),
        }
    
    
        