# Purpose: result dialog module.
# Example: import result_dialog
import bpy


class GAMEREADY_OT_result_dialog(bpy.types.Operator):
    bl_idname = "gameready.result_dialog"
    bl_label = "Game Asset Ready"
    bl_options = {'INTERNAL'}

    message: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(
            self,
            width=480,
            title="Game Asset Ready",
            confirm_text="Done",
        )

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        column.label(text="The process finished successfully.", icon='CHECKMARK')
        column.label(text="You can now continue working with the created asset.")
        column.separator()

        for message_line in self.message.split("\n"):
            if message_line:
                column.label(text=message_line)

    def execute(self, context):
        return {'FINISHED'}
