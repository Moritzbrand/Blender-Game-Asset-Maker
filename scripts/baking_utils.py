# Example:
# BakingUtils.bake_normal_selected_to_active(
#     bpy.context,
#     high_poly_object,
#     low_poly_object,
#     normal_image,
#     extrusion=0.02,
#     margin=16,
# )

import bpy

from .image_utils import ImageUtils


class BakingUtils:
    #-----------------------------
    #---| Member Variables |------
    #-----------------------------
    IMAGE_TEXTURE_NODE_TYPE = "ShaderNodeTexImage"
    MATERIAL_OUTPUT_NODE_TYPE = "ShaderNodeOutputMaterial"
    PRINCIPLED_BSDF_NODE_TYPE = "ShaderNodeBsdfPrincipled"
    EMISSION_NODE_TYPE = "ShaderNodeEmission"

    SUPPORTED_EMIT_CHANNEL_NAMES = {
        "BASE_COLOR",
        "ALPHA",
        "ROUGHNESS",
        "METALLIC",
        "EMISSION",
    }

    SCALAR_EMIT_CHANNEL_NAMES = {
        "ALPHA",
        "ROUGHNESS",
        "METALLIC",
    }

    EMIT_CHANNEL_TO_PRINCIPLED_INPUT_NAMES = {
        "BASE_COLOR": ("Base Color",),
        "ALPHA": ("Alpha",),
        "ROUGHNESS": ("Roughness",),
        "METALLIC": ("Metallic",),
        "EMISSION": ("Emission Color", "Emission"),
    }

    #------------------------------------
    #---| Render Visibility Helpers |----
    #------------------------------------
    @classmethod
    def _iterate_renderable_layer_collections(
        cls,
        layer_collection,
        parent_collection_can_render=True,
    ):
        if layer_collection is None:
            return

        current_collection = layer_collection.collection
        current_collection_can_render = (
            parent_collection_can_render
            and not layer_collection.exclude
            and not current_collection.hide_render
        )

        if current_collection_can_render:
            yield layer_collection

        for child_layer_collection in layer_collection.children:
            yield from cls._iterate_renderable_layer_collections(
                child_layer_collection,
                current_collection_can_render,
            )

    @classmethod
    def get_all_rendered_objects(cls, context, include_non_mesh=False):
        root_layer_collection = context.view_layer.layer_collection
        rendered_objects = []
        already_added_object_names = set()

        for renderable_layer_collection in cls._iterate_renderable_layer_collections(root_layer_collection):
            for collection_object in list(renderable_layer_collection.collection.objects):
                if collection_object.name in already_added_object_names:
                    continue
                if collection_object.hide_render:
                    continue
                if not include_non_mesh and collection_object.type != 'MESH':
                    continue

                already_added_object_names.add(collection_object.name)
                rendered_objects.append(collection_object)

        return rendered_objects

    @classmethod
    def _set_objects_render_hidden_state(cls, objects, hide_from_render):
        for scene_object in objects:
            if scene_object is not None:
                scene_object.hide_render = hide_from_render
        return objects

    @classmethod
    def hide_from_render(cls, objects):
        return cls._set_objects_render_hidden_state(objects, True)

    @classmethod
    def show_in_render(cls, objects):
        return cls._set_objects_render_hidden_state(objects, False)

    @classmethod
    def store_render_visibility(cls, objects):
        return {
            scene_object.name: scene_object.hide_render
            for scene_object in objects
            if scene_object is not None
        }

    @classmethod
    def restore_render_visibility(cls, stored_render_visibility_by_object_name):
        for object_name, hide_from_render in stored_render_visibility_by_object_name.items():
            scene_object = bpy.data.objects.get(object_name)
            if scene_object is not None:
                scene_object.hide_render = hide_from_render

    #-----------------------------
    #---| Public Bake API |-------
    #-----------------------------
    @classmethod
    def bake_normal_selected_to_active(
        cls,
        context,
        source_obj,
        target_obj,
        target_image,
        extrusion,
        margin,
    ):
        cls._bake_selected_to_active_image(
            context=context,
            source_object=source_obj,
            target_object=target_obj,
            target_image=target_image,
            bake_type='NORMAL',
            extrusion=extrusion,
            margin=margin,
            use_tangent_normal_space=True,
        )

    @classmethod
    def bake_ao_selected_to_active(
        cls,
        context,
        source_obj,
        target_obj,
        target_image,
        extrusion,
        margin,
    ):
        cls._bake_selected_to_active_image(
            context=context,
            source_object=source_obj,
            target_object=target_obj,
            target_image=target_image,
            bake_type='AO',
            extrusion=extrusion,
            margin=margin,
            use_tangent_normal_space=False,
        )

    @classmethod
    def bake_emit_selected_to_active(
        cls,
        context,
        source_obj,
        target_obj,
        target_image,
        extrusion,
        margin,
    ):
        cls._bake_selected_to_active_image(
            context=context,
            source_object=source_obj,
            target_object=target_obj,
            target_image=target_image,
            bake_type='EMIT',
            extrusion=extrusion,
            margin=margin,
            use_tangent_normal_space=False,
        )

    #--------------------------------
    #---| Bake Execution Flow |------
    #--------------------------------
    @classmethod
    def _bake_selected_to_active_image(
        cls,
        context,
        source_object,
        target_object,
        target_image,
        bake_type,
        extrusion,
        margin,
        use_tangent_normal_space,
    ):
        cls._require_mesh_object(source_object, "source_object")
        cls._require_mesh_object(target_object, "target_object")
        ImageUtils.require_image(target_image, "target_image")

        cls._ensure_object_mode(context)
        cls._prepare_selected_to_active_bake_selection(
            context=context,
            source_object=source_object,
            target_object=target_object,
        )

        target_material = cls._require_active_node_material(target_object)
        target_nodes = target_material.node_tree.nodes

        target_image_texture_node = cls._require_image_texture_node_for_image(
            nodes=target_nodes,
            target_image=target_image,
        )

        cls._make_node_the_only_active_bake_target(
            nodes=target_nodes,
            active_node=target_image_texture_node,
        )

        cls._configure_scene_for_selected_to_active_bake(
            scene=context.scene,
            extrusion=extrusion,
            margin=margin,
            use_tangent_normal_space=use_tangent_normal_space,
        )

        bpy.ops.object.bake(
            type=bake_type,
            use_selected_to_active=True,
            cage_extrusion=extrusion,
            margin=margin,
        )

        ImageUtils.save_image_if_possible(target_image)

    @classmethod
    def _ensure_object_mode(cls, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

    @classmethod
    def _prepare_selected_to_active_bake_selection(
        cls,
        context,
        source_object,
        target_object,
    ):
        for selected_object in list(context.selected_objects):
            selected_object.select_set(False)

        source_object.select_set(True)
        target_object.select_set(True)
        context.view_layer.objects.active = target_object

    @classmethod
    def _configure_scene_for_selected_to_active_bake(
        cls,
        scene,
        extrusion,
        margin,
        use_tangent_normal_space,
    ):
        bake_settings = scene.render.bake
        bake_settings.use_selected_to_active = True
        bake_settings.cage_extrusion = extrusion
        bake_settings.margin = margin
        bake_settings.target = 'IMAGE_TEXTURES'
        bake_settings.use_clear = True

        if use_tangent_normal_space and hasattr(bake_settings, "normal_space"):
            bake_settings.normal_space = 'TANGENT'

    @classmethod
    def _make_node_the_only_active_bake_target(cls, nodes, active_node):
        for node in nodes:
            node.select = False

        active_node.select = True
        nodes.active = active_node

    #----------------------------------
    #---| Validation and Lookups |-----
    #----------------------------------
    @classmethod
    def _require_mesh_object(cls, scene_object, argument_name):
        if scene_object is None:
            raise ValueError(f"{argument_name} is required")
        if scene_object.type != 'MESH':
            raise ValueError(f"{argument_name} must be a mesh object")

    @classmethod
    def _require_active_node_material(cls, mesh_object):
        active_material = mesh_object.active_material
        if active_material is None or not active_material.use_nodes or active_material.node_tree is None:
            raise ValueError("Target object needs an active node material")
        return active_material

    @classmethod
    def _require_image_texture_node_for_image(cls, nodes, target_image):
        for node in nodes:
            if node.bl_idname == cls.IMAGE_TEXTURE_NODE_TYPE and node.image == target_image:
                return node
        raise ValueError("Could not find the target image texture node")

    @classmethod
    def _get_active_material_output_node(cls, nodes):
        for node in nodes:
            if node.bl_idname == cls.MATERIAL_OUTPUT_NODE_TYPE and getattr(node, "is_active_output", False):
                return node

        for node in nodes:
            if node.bl_idname == cls.MATERIAL_OUTPUT_NODE_TYPE:
                return node

        new_output_node = nodes.new(cls.MATERIAL_OUTPUT_NODE_TYPE)
        new_output_node.location = (600, 0)
        return new_output_node

    @classmethod
    def _get_first_principled_bsdf_node(cls, nodes):
        for node in nodes:
            if node.bl_idname == cls.PRINCIPLED_BSDF_NODE_TYPE:
                return node
        return None

    @classmethod
    def _get_principled_input_socket_for_emit_channel(cls, principled_bsdf_node, channel_name):
        if principled_bsdf_node is None:
            return None

        input_socket_names = cls.EMIT_CHANNEL_TO_PRINCIPLED_INPUT_NAMES[channel_name]
        for input_socket_name in input_socket_names:
            input_socket = principled_bsdf_node.inputs.get(input_socket_name)
            if input_socket is not None:
                return input_socket

        return None

    #-------------------------------------
    #---| Emit Bake Material Setup |------
    #-------------------------------------
    @classmethod
    def prepare_object_materials_for_emit_bake(cls, obj, channel):
        cls._require_mesh_object(obj, "obj")

        normalized_channel_name = channel.upper()
        if normalized_channel_name not in cls.SUPPORTED_EMIT_CHANNEL_NAMES:
            raise ValueError(f"Unsupported channel: {normalized_channel_name}")

        for material_slot in obj.material_slots:
            material = material_slot.material
            if material is None:
                continue

            if not material.use_nodes:
                material.use_nodes = True

            node_tree = material.node_tree
            if node_tree is None:
                continue

            nodes = node_tree.nodes
            links = node_tree.links

            output_node = cls._get_active_material_output_node(nodes)
            principled_bsdf_node = cls._get_first_principled_bsdf_node(nodes)

            cls._remove_existing_emit_bake_proxy_nodes(nodes)

            material_surface_input_socket = output_node.inputs.get("Surface")
            if material_surface_input_socket is None:
                continue

            cls._remove_all_links_from_socket(links, material_surface_input_socket)

            emission_proxy_node = cls._create_emit_bake_proxy_node(
                nodes=nodes,
                output_node=output_node,
                channel_name=normalized_channel_name,
            )

            source_input_socket = cls._get_principled_input_socket_for_emit_channel(
                principled_bsdf_node=principled_bsdf_node,
                channel_name=normalized_channel_name,
            )

            if source_input_socket is not None:
                if source_input_socket.is_linked and len(source_input_socket.links) > 0:
                    source_output_socket = source_input_socket.links[0].from_socket
                    cls._connect_source_socket_to_emission_proxy(
                        source_socket=source_output_socket,
                        emission_proxy_node=emission_proxy_node,
                        links=links,
                    )
                else:
                    cls._apply_unlinked_socket_default_to_emission_proxy(
                        source_input_socket=source_input_socket,
                        channel_name=normalized_channel_name,
                        emission_proxy_node=emission_proxy_node,
                    )

            links.new(emission_proxy_node.outputs["Emission"], material_surface_input_socket)

    @classmethod
    def _remove_existing_emit_bake_proxy_nodes(cls, nodes):
        for node in list(nodes):
            if node.name.startswith("GR_EmitBakeProxy") or node.name.startswith("GR_EmitBakeHelper"):
                nodes.remove(node)

    @classmethod
    def _create_emit_bake_proxy_node(cls, nodes, output_node, channel_name):
        emission_proxy_node = nodes.new(cls.EMISSION_NODE_TYPE)
        emission_proxy_node.name = "GR_EmitBakeProxy"
        emission_proxy_node.label = f"GR Emit Bake {channel_name.title()}"
        emission_proxy_node.location = (output_node.location.x - 260, output_node.location.y)
        emission_proxy_node.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        emission_proxy_node.inputs["Strength"].default_value = 1.0
        return emission_proxy_node

    @classmethod
    def _remove_all_links_from_socket(cls, links, socket):
        for existing_link in list(socket.links):
            links.remove(existing_link)

    @classmethod
    def _connect_source_socket_to_emission_proxy(
        cls,
        source_socket,
        emission_proxy_node,
        links,
    ):
        source_socket_type = getattr(source_socket, "type", None)

        if source_socket_type in {"VALUE", "INT", "BOOLEAN"}:
            emission_proxy_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            links.new(source_socket, emission_proxy_node.inputs["Strength"])
            return

        links.new(source_socket, emission_proxy_node.inputs["Color"])

    @classmethod
    def _apply_unlinked_socket_default_to_emission_proxy(
        cls,
        source_input_socket,
        channel_name,
        emission_proxy_node,
    ):
        if channel_name == "BASE_COLOR":
            emission_proxy_node.inputs["Color"].default_value = cls._convert_socket_default_value_to_rgba(source_input_socket)
            return

        if channel_name in cls.SCALAR_EMIT_CHANNEL_NAMES:
            default_rgba = cls._convert_socket_default_value_to_rgba(source_input_socket)
            grayscale_value = float(default_rgba[0])
            emission_proxy_node.inputs["Color"].default_value = (
                grayscale_value,
                grayscale_value,
                grayscale_value,
                1.0,
            )

    @classmethod
    def _convert_socket_default_value_to_rgba(cls, socket):
        default_value = getattr(socket, "default_value", 0.0)

        if isinstance(default_value, (int, float)):
            grayscale_value = float(default_value)
            return (grayscale_value, grayscale_value, grayscale_value, 1.0)

        try:
            default_value_items = list(default_value)

            if len(default_value_items) >= 4:
                return (
                    float(default_value_items[0]),
                    float(default_value_items[1]),
                    float(default_value_items[2]),
                    float(default_value_items[3]),
                )

            if len(default_value_items) == 3:
                return (
                    float(default_value_items[0]),
                    float(default_value_items[1]),
                    float(default_value_items[2]),
                    1.0,
                )

            if len(default_value_items) == 1:
                grayscale_value = float(default_value_items[0])
                return (grayscale_value, grayscale_value, grayscale_value, 1.0)
        except TypeError:
            pass

        return (0.0, 0.0, 0.0, 1.0)
