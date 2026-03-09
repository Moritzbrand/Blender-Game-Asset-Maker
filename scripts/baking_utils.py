import bpy


class BakingUtils:
    @staticmethod
    def _iter_renderable_layer_collections(layer_collection, parent_render_enabled=True):
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
            yield from BakingUtils._iter_renderable_layer_collections(
                child,
                this_render_enabled,
            )

    @staticmethod
    def get_all_rendered_objects(context, include_non_mesh=False):
        view_layer = context.view_layer
        root = view_layer.layer_collection

        objects = []
        seen = set()

        for layer_coll in BakingUtils._iter_renderable_layer_collections(root):
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

    @staticmethod
    def hide_from_render(objects):
        for obj in objects:
            if obj is not None:
                obj.hide_render = True
        return objects

    @staticmethod
    def show_in_render(objects):
        for obj in objects:
            if obj is not None:
                obj.hide_render = False
        return objects

    @staticmethod
    def store_render_visibility(objects):
        return {obj.name: obj.hide_render for obj in objects if obj is not None}

    @staticmethod
    def restore_render_visibility(state):
        for obj_name, hide_render in state.items():
            obj = bpy.data.objects.get(obj_name)
            if obj is not None:
                obj.hide_render = hide_render

    @staticmethod
    def flip_normal_map_y(image):
        if image is None:
            raise ValueError("Image is required")

        pixels = list(image.pixels)

        if not pixels:
            return image

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
    def bake_normal_selected_to_active(context, source_obj, target_obj, target_image, extrusion, margin):
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

        normal_node = None
        for node in nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image == target_image:
                normal_node = node
                break

        if normal_node is None:
            raise ValueError("Could not find the normal image texture node")

        for node in nodes:
            node.select = False

        normal_node.select = True
        nodes.active = normal_node

        scene = context.scene
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = extrusion
        scene.render.bake.margin = margin
        scene.render.bake.target = 'IMAGE_TEXTURES'
        scene.render.bake.use_clear = True

        if hasattr(scene.render.bake, "normal_space"):
            scene.render.bake.normal_space = 'TANGENT'

        bpy.ops.object.bake(
            type='NORMAL',
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
    def bake_ao_selected_to_active(context, source_obj, target_obj, target_image, extrusion, margin):
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

        ao_node = None
        for node in nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image == target_image:
                ao_node = node
                break

        if ao_node is None:
            raise ValueError("Could not find the AO image texture node")

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
    def _clear_emit_bake_proxy_nodes(nodes):
        for node in list(nodes):
            if node.name.startswith("GR_EmitBakeProxy") or node.name.startswith("GR_EmitBakeHelper"):
                nodes.remove(node)

    @staticmethod
    def _connect_socket_to_emission(source_socket, emit_node, links):
        socket_type = getattr(source_socket, "type", None)

        if socket_type in {"VALUE", "INT", "BOOLEAN"}:
            emit_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            links.new(source_socket, emit_node.inputs["Strength"])
        else:
            links.new(source_socket, emit_node.inputs["Color"])

    @staticmethod
    def prepare_object_materials_for_emit_bake(obj, channel):
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

            output = BakingUtils._get_active_output_node(nodes)
            bsdf = BakingUtils._get_first_principled_node(nodes)

            BakingUtils._clear_emit_bake_proxy_nodes(nodes)

            surface_input = output.inputs.get("Surface")
            if surface_input is None:
                continue

            BakingUtils._remove_links_from_socket(links, surface_input)

            emit = nodes.new("ShaderNodeEmission")
            emit.name = "GR_EmitBakeProxy"
            emit.label = f"GR Emit Bake {channel.title()}"
            emit.location = (output.location.x - 260, output.location.y)
            emit.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
            emit.inputs["Strength"].default_value = 1.0

            source_input = None
            if bsdf is not None:
                if channel == "BASE_COLOR":
                    source_input = bsdf.inputs.get("Base Color")
                elif channel == "ALPHA":
                    source_input = bsdf.inputs.get("Alpha")
                elif channel == "ROUGHNESS":
                    source_input = bsdf.inputs.get("Roughness")
                elif channel == "METALLIC":
                    source_input = bsdf.inputs.get("Metallic")
                elif channel == "EMISSION":
                    source_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")

            if source_input is not None:
                if source_input.is_linked and len(source_input.links) > 0:
                    source_socket = source_input.links[0].from_socket
                    BakingUtils._connect_socket_to_emission(source_socket, emit, links)
                elif channel == "BASE_COLOR":
                    emit.inputs["Color"].default_value = BakingUtils._socket_default_to_rgba(source_input)
                elif channel in {"ALPHA", "ROUGHNESS", "METALLIC"}:
                    default_rgba = BakingUtils._socket_default_to_rgba(source_input)
                    v = float(default_rgba[0])
                    emit.inputs["Color"].default_value = (v, v, v, 1.0)

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
            out_pixels[i] = ao_pixels[i]
            out_pixels[i + 1] = roughness_pixels[i]
            out_pixels[i + 2] = metallic_pixels[i]
            out_pixels[i + 3] = 1.0

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
        values = pixels[0::4]

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
