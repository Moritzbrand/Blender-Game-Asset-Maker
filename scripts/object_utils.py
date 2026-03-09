import bpy


class ObjectUtils:
    @staticmethod
    def duplicate_active(context):
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

    @staticmethod
    def duplicate_selected(context):
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

    @staticmethod
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

    @staticmethod
    def select_objects(context, objects):
        for obj in context.selected_objects:
            obj.select_set(False)

        for obj in objects:
            obj.select_set(True)

        if objects:
            context.view_layer.objects.active = objects[0]
