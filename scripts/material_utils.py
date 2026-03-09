import os

import bpy


class MaterialUtils:
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
    def _new_placeholder_image(scene, obj_name, suffix, size, alpha=False, is_data=False):
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
    def _connect_normal_texture_directly_to_normal_map(links, normal_texture_node, normal_map_node):
        texture_color_output = normal_texture_node.outputs.get("Color")
        normal_map_color_input = normal_map_node.inputs.get("Color")

        if texture_color_output is None or normal_map_color_input is None:
            return

        MaterialUtils._remove_links_from_socket(links, normal_map_color_input)
        links.new(texture_color_output, normal_map_color_input)

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
            )
            created_images["emission"] = img

            tex = MaterialUtils._add_image_node(nodes, img, "Emission", x_tex, y)
            if emission_input is not None:
                links.new(tex.outputs["Color"], emission_input)
            y += y_step

        if scene.gameready_bake_normal:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "Normal",
                size,
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

        if scene.gameready_bake_ao:
            img = MaterialUtils._new_placeholder_image(
                scene,
                obj.name,
                "AO",
                size,
                alpha=False,
                is_data=True,
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
