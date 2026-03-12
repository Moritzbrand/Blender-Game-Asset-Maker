# Purpose: material utils module.
# Example: import material_utils
import os

import bpy

from .image_utils import ImageUtils


class BakeCoordinatePreparationResult:
    def __init__(self, helper_object_names=None):
        self.helper_object_names = helper_object_names or []


class MaterialUtils:
    @staticmethod
    def _refresh_material_preview(material, context=None):
        if material is None or not material.use_nodes or material.node_tree is None:
            return

        node_tree = material.node_tree
        nodes = node_tree.nodes
        links = node_tree.links

        output_node = None
        try:
            output_node = node_tree.get_output_node("ALL")
        except Exception:
            output_node = None

        if output_node is None:
            for node in nodes:
                if node.bl_idname == "ShaderNodeOutputMaterial":
                    if getattr(node, "is_active_output", False):
                        output_node = node
                        break

        if output_node is None:
            for node in nodes:
                if node.bl_idname == "ShaderNodeOutputMaterial":
                    output_node = node
                    break

        principled_bsdf_node = None
        for node in nodes:
            if node.bl_idname == "ShaderNodeBsdfPrincipled":
                principled_bsdf_node = node
                break

        if output_node is None or principled_bsdf_node is None:
            return

        surface_input = output_node.inputs.get("Surface")
        bsdf_output = principled_bsdf_node.outputs.get("BSDF")

        if surface_input is not None and bsdf_output is not None:
            MaterialUtils._remove_links_from_socket(links, surface_input)
            links.new(bsdf_output, surface_input)

        try:
            node_tree.update()
        except Exception:
            pass

        try:
            node_tree.update_tag()
        except Exception:
            pass

        try:
            material.update_tag(refresh={'DATA'})
        except Exception:
            pass

        if context is not None:
            try:
                context.view_layer.update()
            except Exception:
                pass

    @staticmethod
    def refresh_material_preview_on_object(obj, context=None):
        if obj is None or obj.type != 'MESH':
            return 0

        refreshed_count = 0
        seen_material_pointers = set()

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material is None:
                continue

            material_pointer = material.as_pointer()
            if material_pointer in seen_material_pointers:
                continue
            seen_material_pointers.add(material_pointer)

            MaterialUtils._refresh_material_preview(material, context=context)
            refreshed_count += 1

        return refreshed_count

    @staticmethod
    def _refresh_material_output(material):
        if material is None or not material.use_nodes or material.node_tree is None:
            return

        nodes = material.node_tree.nodes
        links = material.node_tree.links

        output_node = None
        principled_bsdf_node = None

        for node in nodes:
            if output_node is None and node.bl_idname == "ShaderNodeOutputMaterial":
                if getattr(node, "is_active_output", False):
                    output_node = node

            if principled_bsdf_node is None and node.bl_idname == "ShaderNodeBsdfPrincipled":
                principled_bsdf_node = node

        if output_node is None:
            for node in nodes:
                if node.bl_idname == "ShaderNodeOutputMaterial":
                    output_node = node
                    break

        if output_node is None or principled_bsdf_node is None:
            return

        surface_input = output_node.inputs.get("Surface")
        bsdf_output = principled_bsdf_node.outputs.get("BSDF")

        if surface_input is None or bsdf_output is None:
            return

        MaterialUtils._remove_links_from_socket(links, surface_input)
        links.new(bsdf_output, surface_input)

        try:
            material.node_tree.update_tag()
        except Exception:
            pass

        try:
            material.update_tag(refresh={'DATA'})
        except Exception:
            pass
    @staticmethod
    def _node_has_any_linked_output(node):
        for socket in node.outputs:
            if socket.is_linked:
                return True
        return False

    @staticmethod
    def remove_unplugged_texture_nodes(material):
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
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def _new_placeholder_image(scene, obj_name, suffix, size, alpha=False, is_data=False, color_mode='RGBA'):
        image_name = f"{obj_name}_{suffix}"
        image = bpy.data.images.new(
            name=image_name,
            width=size,
            height=size,
            alpha=alpha,
        )

        if suffix == "BaseColor":
            image.generated_color = (1.0, 1.0, 1.0, 0.0 if alpha else 1.0)
        elif suffix == "Normal":
            image.generated_color = (0.5, 0.5, 1.0, 1.0)
        elif suffix in {"Roughness", "ORM"}:
            image.generated_color = (1.0, 1.0, 1.0, 1.0)
        else:
            image.generated_color = (0.0, 0.0, 0.0, 1.0)

        try:
            image.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
        except Exception:
            pass

        try:
            output_dir = bpy.path.abspath(scene.gameready_output_dir)
            MaterialUtils._ensure_dir(output_dir)
            image.filepath_raw = os.path.join(output_dir, f"{image_name}.png")
            image.file_format = 'PNG'
        except Exception:
            pass

        ImageUtils.configure_image_for_png_output(
            image,
            color_mode=color_mode,
            compression=int(getattr(scene, "gameready_texture_compression", 15)),
            channel_packed=is_data,
        )

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
    def _is_normal_y_display_fix_node(node):
        if node is None:
            return False
        return str(getattr(node, "name", "")).startswith("GR_NormalYDisplayFix_")

    @staticmethod
    def _is_sss_preview_node(node):
        if node is None:
            return False
        return str(getattr(node, "name", "")).startswith("GR_SSSPreview_")

    @staticmethod
    def _remove_links_from_socket(links, socket):
        if socket is None:
            return
        for link in list(socket.links):
            links.remove(link)

    @staticmethod
    def _find_normal_map_node_for_texture_node(normal_texture_node):
        if normal_texture_node is None:
            return None

        color_output = normal_texture_node.outputs.get("Color")
        if color_output is None:
            return None

        nodes_to_visit = [link.to_node for link in color_output.links]
        visited_node_pointers = set()

        while nodes_to_visit:
            current_node = nodes_to_visit.pop(0)
            current_node_pointer = current_node.as_pointer()

            if current_node_pointer in visited_node_pointers:
                continue
            visited_node_pointers.add(current_node_pointer)

            if current_node.bl_idname == "ShaderNodeNormalMap":
                return current_node

            for output_socket in current_node.outputs:
                for output_link in output_socket.links:
                    nodes_to_visit.append(output_link.to_node)

        return None

    @staticmethod
    def _remove_existing_normal_y_display_fix_nodes(nodes):
        for node in list(nodes):
            if MaterialUtils._is_normal_y_display_fix_node(node):
                nodes.remove(node)

    @staticmethod
    def _remove_existing_sss_preview_nodes(nodes):
        for node in list(nodes):
            node_name = str(getattr(node, "name", ""))
            if node_name.startswith("GR_SSSPreview_"):
                nodes.remove(node)

    @staticmethod
    def _insert_normal_y_display_fix_between_texture_and_normal_map(
        nodes,
        links,
        normal_texture_node,
        normal_map_node,
    ):
        texture_color_output = normal_texture_node.outputs.get("Color")
        normal_map_color_input = normal_map_node.inputs.get("Color")

        if texture_color_output is None or normal_map_color_input is None:
            return

        MaterialUtils._remove_links_from_socket(links, normal_map_color_input)
        MaterialUtils._remove_existing_normal_y_display_fix_nodes(nodes)

        node_y = int(getattr(normal_texture_node, "location", (0, 0))[1])

        separate_color_node = nodes.new("ShaderNodeSeparateColor")
        separate_color_node.name = "GR_NormalYDisplayFix_Separate"
        separate_color_node.label = "GR Normal Y Display Fix Separate"
        separate_color_node.location = (-650, node_y)

        invert_green_node = nodes.new("ShaderNodeMath")
        invert_green_node.name = "GR_NormalYDisplayFix_InvertGreen"
        invert_green_node.label = "GR Normal Y Display Fix Invert Green"
        invert_green_node.operation = 'SUBTRACT'
        invert_green_node.inputs[0].default_value = 1.0
        invert_green_node.location = (-450, node_y - 140)

        combine_color_node = nodes.new("ShaderNodeCombineColor")
        combine_color_node.name = "GR_NormalYDisplayFix_Combine"
        combine_color_node.label = "GR Normal Y Display Fix Combine"
        combine_color_node.location = (-250, node_y)

        try:
            separate_color_node.mode = 'RGB'
        except Exception:
            pass

        try:
            combine_color_node.mode = 'RGB'
        except Exception:
            pass

        links.new(texture_color_output, separate_color_node.inputs["Color"])
        links.new(separate_color_node.outputs["Red"], combine_color_node.inputs["Red"])
        links.new(separate_color_node.outputs["Blue"], combine_color_node.inputs["Blue"])
        links.new(separate_color_node.outputs["Green"], invert_green_node.inputs[1])
        links.new(invert_green_node.outputs["Value"], combine_color_node.inputs["Green"])
        links.new(combine_color_node.outputs["Color"], normal_map_color_input)

    @staticmethod
    def apply_normal_y_display_fix_to_material(material):
        if material is None or not material.use_nodes or material.node_tree is None:
            return False

        nodes = material.node_tree.nodes
        links = material.node_tree.links
        has_applied_fix = False

        for node in list(nodes):
            if node.bl_idname != "ShaderNodeTexImage":
                continue
            if node.name != "Normal" and node.label != "Normal":
                continue

            normal_map_node = MaterialUtils._find_normal_map_node_for_texture_node(node)
            if normal_map_node is None:
                continue

            MaterialUtils._insert_normal_y_display_fix_between_texture_and_normal_map(
                nodes=nodes,
                links=links,
                normal_texture_node=node,
                normal_map_node=normal_map_node,
            )
            has_applied_fix = True

        return has_applied_fix

    @staticmethod
    def apply_normal_y_display_fix_to_object(obj):
        if obj is None or obj.type != 'MESH':
            return 0

        fixed_material_count = 0
        seen_material_pointers = set()

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material is None:
                continue

            material_pointer = material.as_pointer()
            if material_pointer in seen_material_pointers:
                continue
            seen_material_pointers.add(material_pointer)

            if MaterialUtils.apply_normal_y_display_fix_to_material(material):
                fixed_material_count += 1

        return fixed_material_count

    @staticmethod
    def _load_image_from_path(image_filepath):
        if not image_filepath:
            return None

        try:
            absolute_path = bpy.path.abspath(image_filepath)
        except Exception:
            absolute_path = image_filepath

        if not absolute_path or not os.path.exists(absolute_path):
            return None

        try:
            image = bpy.data.images.load(absolute_path, check_existing=True)
        except Exception:
            return None

        try:
            image.colorspace_settings.name = "Non-Color"
        except Exception:
            pass

        return image

    @staticmethod
    def apply_sss_preview_to_material(material, image=None, image_filepath=""):
        if material is None or not material.use_nodes or material.node_tree is None:
            return False

        if image is None:
            image = MaterialUtils._load_image_from_path(image_filepath)
        if image is None:
            return False

        nodes = material.node_tree.nodes
        links = material.node_tree.links

        principled_bsdf_node = None
        for node in nodes:
            if node.bl_idname == "ShaderNodeBsdfPrincipled":
                principled_bsdf_node = node
                break

        if principled_bsdf_node is None:
            return False

        sss_radius_input = MaterialUtils._get_bsdf_input(principled_bsdf_node, "Subsurface Radius")
        sss_weight_input = MaterialUtils._get_bsdf_input(principled_bsdf_node, "Subsurface Weight", "Subsurface")

        if sss_radius_input is None or sss_weight_input is None:
            return False

        MaterialUtils._remove_existing_sss_preview_nodes(nodes)
        MaterialUtils._remove_links_from_socket(links, sss_radius_input)
        MaterialUtils._remove_links_from_socket(links, sss_weight_input)

        preview_frame = nodes.new("NodeFrame")
        preview_frame.name = "GR_SSSPreview_Frame"
        preview_frame.label = "GR Subsurface Preview"
        preview_frame.location = (-1300, -950)

        preview_tex = nodes.new("ShaderNodeTexImage")
        preview_tex.name = "GR_SSSPreview_Texture"
        preview_tex.label = "GR Subsurface Export Texture"
        preview_tex.image = image
        preview_tex.location = (-1200, -820)
        preview_tex.parent = preview_frame

        rgb_to_bw = nodes.new("ShaderNodeRGBToBW")
        rgb_to_bw.name = "GR_SSSPreview_RGBToBW"
        rgb_to_bw.label = "GR Subsurface Weight"
        rgb_to_bw.location = (-930, -980)
        rgb_to_bw.parent = preview_frame

        try:
            preview_tex.image.colorspace_settings.name = "Non-Color"
        except Exception:
            pass

        # RGB -> Radius
        links.new(preview_tex.outputs["Color"], sss_radius_input)

        # RGB -> grayscale -> Weight
        links.new(preview_tex.outputs["Color"], rgb_to_bw.inputs["Color"])
        links.new(rgb_to_bw.outputs["Val"], sss_weight_input)

        MaterialUtils._refresh_material_preview(material)
        return True

    @staticmethod
    def apply_sss_preview_to_object(obj, image=None, image_filepath=""):
        if obj is None or obj.type != 'MESH':
            return 0

        fixed_material_count = 0
        seen_material_pointers = set()

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material is None:
                continue

            material_pointer = material.as_pointer()
            if material_pointer in seen_material_pointers:
                continue
            seen_material_pointers.add(material_pointer)

            if MaterialUtils.apply_sss_preview_to_material(material, image=image, image_filepath=image_filepath):
                fixed_material_count += 1

        return fixed_material_count

    @staticmethod
    def setup_bake_material(obj, scene):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        size = int(scene.gameready_texture_size)

        obj.data.materials.clear()

        mat = bpy.data.materials.new(name=f"{obj.name}_MAT")
        mat.use_nodes = True
        obj.data.materials.append(mat)

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

        if scene.gameready_bake_base_color:
            final_img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "BaseColor",
                size,
                alpha=scene.gameready_bake_alpha,
                is_data=False,
                color_mode='RGBA' if scene.gameready_bake_alpha else 'RGB',
            )
            created_images["base_color"] = final_img

            final_tex = MaterialUtils._add_image_node(nodes, final_img, "Base Color", x_tex, y)
            if base_color_input is not None:
                links.new(final_tex.outputs["Color"], base_color_input)
            if scene.gameready_bake_alpha and alpha_input is not None:
                links.new(final_tex.outputs["Alpha"], alpha_input)
            y += y_step

            if scene.gameready_bake_alpha:
                rgb_tmp = MaterialUtils._new_placeholder_image(
                    scene,
                    obj.name,
                    "BaseColor_RGB_TMP",
                    size,
                    alpha=False,
                    is_data=False,
                    color_mode='RGB',
                )
                created_images["base_color_rgb_tmp"] = rgb_tmp
                MaterialUtils._add_image_node(nodes, rgb_tmp, "Base Color RGB Bake", x_tex, y)
                y += y_step

                alpha_tmp = MaterialUtils._new_placeholder_image(
                    scene,
                    obj.name,
                    "BaseColor_Alpha_TMP",
                    size,
                    alpha=False,
                    is_data=True,
                    color_mode='BW',
                )
                created_images["base_color_alpha_tmp"] = alpha_tmp
                MaterialUtils._add_image_node(nodes, alpha_tmp, "Base Color Alpha Bake", x_tex, y)
                y += y_step

        if scene.gameready_bake_emission:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "Emission",
                size,
                alpha=False,
                is_data=False,
                color_mode='RGB',
            )
            created_images["emission"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Emission", x_tex, y)
            if emission_input is not None:
                links.new(tex.outputs["Color"], emission_input)
            y += y_step

        if scene.gameready_bake_sss:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "SSS",
                size,
                alpha=False,
                is_data=True,
                color_mode='RGB',
            )
            created_images["sss"] = img
            MaterialUtils._add_image_node(nodes, img, "Subsurface Scattering Bake", x_tex, y)
            y += y_step

        if scene.gameready_bake_normal:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "Normal",
                size,
                alpha=False,
                is_data=True,
                color_mode='RGB',
            )
            created_images["normal"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Normal", x_tex, y)

            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (-250, y)

            links.new(tex.outputs["Color"], normal_map.inputs["Color"])
            if normal_input is not None:
                links.new(normal_map.outputs["Normal"], normal_input)
            y += y_step

        if scene.gameready_bake_ao:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "AO",
                size,
                alpha=False,
                is_data=True,
                color_mode='BW',
            )
            created_images["ao"] = img
            MaterialUtils._add_image_node(nodes, img, "AO", x_tex, y)
            y += y_step

        if scene.gameready_bake_roughness:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "Roughness",
                size,
                alpha=False,
                is_data=True,
                color_mode='BW',
            )
            created_images["roughness"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Roughness", x_tex, y)
            if roughness_input is not None:
                links.new(tex.outputs["Color"], roughness_input)
            y += y_step

        if scene.gameready_bake_metallic:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "Metallic",
                size,
                alpha=False,
                is_data=True,
                color_mode='BW',
            )
            created_images["metallic"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Metallic", x_tex, y)
            if metallic_input is not None:
                links.new(tex.outputs["Color"], metallic_input)
            y += y_step

        create_orm = (
            scene.gameready_pack_as_orm
            and scene.gameready_bake_ao
            and scene.gameready_bake_roughness
            and scene.gameready_bake_metallic
        )

        if create_orm:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "ORM",
                size,
                alpha=False,
                is_data=True,
                color_mode='RGB',
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


    @staticmethod
    def ensure_standard_material_on_empty_slots(obj, material_name_prefix="Gameready_Standard"):
        """Assign a temporary standard material to any empty material slots.

        Returns a list of assignment records that can be passed to
        ``remove_temporary_material_assignments``.
        """
        if obj is None or obj.type != 'MESH':
            return []

        assignment_records = []
        temporary_material = None

        for slot_index, material_slot in enumerate(obj.material_slots):
            if material_slot.material is not None:
                continue

            if temporary_material is None:
                temporary_material = bpy.data.materials.new(name=f"{material_name_prefix}_{obj.name}")
                temporary_material.use_nodes = True

            material_slot.material = temporary_material
            assignment_records.append({
                "slot_index": slot_index,
                "material_name": temporary_material.name,
            })

        if not obj.material_slots and len(assignment_records) == 0:
            if temporary_material is None:
                temporary_material = bpy.data.materials.new(name=f"{material_name_prefix}_{obj.name}")
                temporary_material.use_nodes = True
            obj.data.materials.append(temporary_material)
            assignment_records.append({
                "slot_index": 0,
                "material_name": temporary_material.name,
            })

        return assignment_records

    @staticmethod
    def remove_temporary_material_assignments(obj, assignment_records):
        if obj is None or obj.type != 'MESH' or not assignment_records:
            return 0

        removed_assignments = 0
        material_usage_delta = {}

        for record in assignment_records:
            slot_index = int(record.get("slot_index", -1))
            material_name = record.get("material_name", "")

            if slot_index < 0 or slot_index >= len(obj.material_slots):
                continue

            slot_material = obj.material_slots[slot_index].material
            if slot_material is None or slot_material.name != material_name:
                continue

            obj.material_slots[slot_index].material = None
            removed_assignments += 1
            material_usage_delta[material_name] = material_usage_delta.get(material_name, 0) + 1

        for material_name, _ in material_usage_delta.items():
            material = bpy.data.materials.get(material_name)
            if material is not None and material.users == 0:
                bpy.data.materials.remove(material, do_unlink=True)

        return removed_assignments
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
    def _is_texture_coordinate_node(node):
        return node is not None and node.bl_idname == "ShaderNodeTexCoord"

    @staticmethod
    def _iter_texcoord_links_by_output(node_tree):
        if node_tree is None:
            return
        for node in node_tree.nodes:
            if not MaterialUtils._is_texture_coordinate_node(node):
                continue

            normal_output = node.outputs.get("Normal")
            if normal_output is not None:
                for link in list(normal_output.links):
                    yield node, "Normal", link

            object_output = node.outputs.get("Object")
            if object_output is not None:
                for link in list(object_output.links):
                    yield node, "Object", link

    @staticmethod
    def _texcoord_targets_self_or_is_empty(texcoord_node, source_object):
        referenced = getattr(texcoord_node, "object", None)
        return referenced is None or referenced == source_object

    @staticmethod
    def _ensure_object_mapping_node(node_tree, texcoord_node, output_name, link, source_object):
        if node_tree is None or link is None:
            return False

        mapping_node = node_tree.nodes.new("ShaderNodeMapping")
        mapping_node.label = "GR Bake Coord Compensation"
        mapping_node.name = "GR_BakeCoordCompensation_Mapping"
        mapping_node.vector_type = 'POINT'

        texcoord_output_socket = texcoord_node.outputs.get(output_name)
        mapping_input_socket = mapping_node.inputs.get("Vector")
        mapping_output_socket = mapping_node.outputs.get("Vector")

        if texcoord_output_socket is None or mapping_input_socket is None or mapping_output_socket is None:
            node_tree.nodes.remove(mapping_node)
            return False

        mapping_node.location = (
            (texcoord_node.location.x + link.to_node.location.x) * 0.5,
            (texcoord_node.location.y + link.to_node.location.y) * 0.5,
        )

        target_socket = link.to_socket
        node_tree.links.remove(link)
        node_tree.links.new(texcoord_output_socket, mapping_input_socket)
        node_tree.links.new(mapping_output_socket, target_socket)

        inverse_rotation = source_object.matrix_world.to_euler()
        rotation_input = mapping_node.inputs.get("Rotation")
        if rotation_input is not None:
            rotation_input.default_value[0] = -inverse_rotation.x
            rotation_input.default_value[1] = -inverse_rotation.y
            rotation_input.default_value[2] = -inverse_rotation.z

        return True

    @staticmethod
    def _create_coordinate_helper_empty(context, source_object):
        helper = bpy.data.objects.new(name=f"{source_object.name}_GR_BakeCoord", object_data=None)
        collection = context.collection
        if collection is None:
            collection = context.scene.collection
        collection.objects.link(helper)
        helper.empty_display_type = 'PLAIN_AXES'
        helper.empty_display_size = 0.2
        helper.matrix_world = source_object.matrix_world.copy()
        helper.hide_render = True
        helper.hide_set(True)
        return helper

    @staticmethod
    def _material_requires_bake_coordinate_handling(material, source_object):
        if material is None or not material.use_nodes or material.node_tree is None:
            return False

        for texcoord_node, output_name, _ in MaterialUtils._iter_texcoord_links_by_output(material.node_tree):
            if output_name not in {"Normal", "Object"}:
                continue
            if not MaterialUtils._texcoord_targets_self_or_is_empty(texcoord_node, source_object):
                continue
            return True

        return False

    @staticmethod
    def make_materials_single_user_for_bake_coordinate_nodes(obj):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        copied = {}
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None:
                continue

            if not MaterialUtils._material_requires_bake_coordinate_handling(mat, obj):
                continue

            key = mat.name_full
            if key not in copied:
                copied[key] = mat.copy()
            slot.material = copied[key]

    @staticmethod
    def prepare_bake_coordinate_nodes(context, obj):
        if obj is None or obj.type != 'MESH':
            return BakeCoordinatePreparationResult()

        helper_object = None
        helper_names = []
        seen_materials = set()

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material is None or not material.use_nodes or material.node_tree is None:
                continue

            material_key = material.as_pointer()
            if material_key in seen_materials:
                continue
            seen_materials.add(material_key)

            node_tree = material.node_tree
            for texcoord_node, output_name, link in list(MaterialUtils._iter_texcoord_links_by_output(node_tree)):
                if not MaterialUtils._texcoord_targets_self_or_is_empty(texcoord_node, obj):
                    continue

                if output_name == "Normal":
                    MaterialUtils._ensure_object_mapping_node(
                        node_tree=node_tree,
                        texcoord_node=texcoord_node,
                        output_name=output_name,
                        link=link,
                        source_object=obj,
                    )
                    continue

                if output_name == "Object":
                    if helper_object is None:
                        helper_object = MaterialUtils._create_coordinate_helper_empty(context, obj)
                        helper_names.append(helper_object.name)
                    texcoord_node.object = helper_object

        return BakeCoordinatePreparationResult(helper_object_names=helper_names)
