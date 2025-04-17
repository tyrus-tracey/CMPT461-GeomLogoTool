import bpy
import bmesh
import os
import time
from bpy.types import Operator, Panel
from math import radians
from math import degrees
from mathutils import Vector, Matrix

bl_info = {
    "name": "Render Panel",
    "blender": (2, 8, 0),
    "author": "Tyrus & Stefan",
    "description": "Render the applied logo. Also contains settings to adjust the UV mapping.",
    "version": (1, 0, 0),
    "support": "COMMUNITY",
    "tracker_url": "",
}

# Define an operator that will manipulate the UVs of selected faces
class UVTransformOperator(Operator):
    bl_idname = "object.uv_transform_operator"
    bl_label = "Adjust UV"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object

        if obj.type != 'MESH':
            self.report({'ERROR'}, "Object is not a mesh")
            return {'CANCELLED'}
            
        scene = context.scene
        bpy.ops.object.mode_set(mode='EDIT')
        # Start editing the mesh in BMesh mode
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        for face in bm.faces:
            if face.select:
                for loop in face.loops:
                    loop_uv = loop[uv_layer]
                    
                    # Apply translation
                    loop_uv.uv += Vector(scene.uv_translation)

                    # Apply rotation
                    if scene.uv_rotation != 0.0:
                        matRot = Matrix.Rotation(radians(scene.uv_rotation), 2, 'Z')
                        loop_uv.uv = matRot @ loop_uv.uv

                    # Apply scaling
                    loop_uv.uv *= scene.uv_scale

        # Update the mesh to reflect the changes
        bmesh.update_edit_mesh(obj.data)

        bpy.ops.object.mode_set(mode='OBJECT')
        
        self.report({'INFO'}, "UV transform applied.")
        return {'FINISHED'}
        
# Resets UV adjustment sliders to default values
class UVControlResetOperator(Operator):
    bl_idname = "object.uv_reset_operator"
    bl_label = "Reset UV Parameters"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = bpy.context.scene
        scene.uv_translation = Vector((0,0))
        scene.uv_rotation = 0.0
        scene.uv_scale = 1.0
        return {'FINISHED'}
    
# Creates a camera to render the applied logo from the scene
class RenderImageOperator(Operator):
    bl_idname = "object.render_image"
    bl_label = "Render Image"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.object
        
        if obj.type != 'MESH':
            self.report({'ERROR'}, "Object is not a mesh.")
            return {'CANCELLED'}
            
        scene = bpy.context.scene
        camObj = scene.camera
        
        if camObj is None:
            # Create camera struct
            cam = bpy.data.cameras.new("Render")
            
            # Create camera object from struct
            camObj = bpy.data.objects.new("Render", cam)
            
            # Position camera
            camObj.location = Vector((0,0,0))
            camObj.rotation_euler = Vector((radians(90),0,0)) 
            
            # Add camera object to scene
            scene.collection.objects.link(camObj)
            scene.camera = camObj
        
        # Set non-logo texturing as invisible
        mat_base = obj.active_material
        mat_base_nodes = mat_base.node_tree.nodes
        node_bsdf = mat_base_nodes.get("Principled BSDF")
        node_bsdf.inputs['Alpha'].default_value = 0
        
        # Render settings
        scene.render.film_transparent = True
        scene.view_layers["ViewLayer"].use_pass_diffuse_color = True
        scene.eevee.use_shadows = False
        scene.render.resolution_x = scene.render_resolution[0]
        scene.render.resolution_y = scene.render_resolution[1]
        camObj.data.lens_unit = 'FOV'
        camObj.data.angle = radians(scene.camera_fov)
        
        # File output settings
        scene.render.image_settings.file_format = 'PNG'
        timestamp = time.strftime("%Y-%m-%d__%H-%M-%S")
        directory = os.path.dirname(bpy.data.filepath)
        filename = "logo-albedo-render__" + timestamp + ".png"
        scene.render.filepath = os.path.join(directory, filename)
        
        # Render and save only the albedo (Diffuse Color) pass
        scene.use_nodes = True
        render_tree = scene.node_tree
        render_tree.links.clear()
        render_nodes = render_tree.nodes
        node_viewlayer = render_nodes.get("Render Layers")
        node_composite = render_nodes.get("Composite")
        render_tree.links.new(node_viewlayer.outputs["DiffCol"], node_composite.inputs["Image"])
        bpy.ops.render.render(write_still=True)
        
        # Revert invisibility
        node_bsdf.inputs['Alpha'].default_value = 1
        
        self.report({'INFO'}, "Render saved.")
        return {'FINISHED'}

# Define a panel for the UI
class RenderPanel(Panel):
    bl_label = "Render Applied Logo"
    bl_idname = "VIEW3D_PT_render_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Render Applied Logo'

    def draw(self, context):
        layout = self.layout
        obj = context.object

        if obj and obj.type == 'MESH':
            layout.label(text="UV Controls")
            
            # Reset parameters button
            row = layout.row()
            row.operator(UVControlResetOperator.bl_idname, text="Reset UV controls")
            
            # Translation sliders (X, Y)
            row = layout.row()
            row.prop(context.scene, "uv_translation", text="Translate")

            # Rotation slider
            row = layout.row()
            row.prop(context.scene, "uv_rotation", text="Rotation")

            # Scale slider
            row = layout.row()
            row.prop(context.scene, "uv_scale", text="Scale")
            
            # Apply button
            row = layout.row()
            row.operator(UVTransformOperator.bl_idname, text="Apply UV Transform")
            
            
            layout.label(text="Render Parameters")
            
            # Resolution
            row = layout.row()
            row.prop(context.scene, "camera_fov", text="FOV (degrees)")
            
            # FOV
            row = layout.row()
            row.prop(context.scene, "render_resolution", text="Resolution")
            
            # Render button
            row = layout.row()
            row.operator(RenderImageOperator.bl_idname, text="Render Image")


def register():
    bpy.types.Scene.uv_translation = bpy.props.FloatVectorProperty(
        name="Translation (X, Y)",
        size=2,
        default=(0.0, 0.0),
        soft_min=-1.0,
        soft_max=1.0
    )
    
    bpy.types.Scene.uv_rotation = bpy.props.FloatProperty(
        name="Rotation",
        default=0.0,
        soft_min=-360,  
        soft_max=360
    )

    bpy.types.Scene.uv_scale = bpy.props.FloatProperty(
        name="Scale",
        default=1.0,
        soft_min=0.01,
        soft_max=10.0
    )
    
    bpy.types.Scene.camera_fov = bpy.props.FloatProperty(
        name="Fov (X, Y)",
        default=90,
        soft_min=0,
        soft_max=360
    )
    
    bpy.types.Scene.render_resolution = bpy.props.IntVectorProperty(
        name="Resolution (Width, Height)",
        size=2,
        default=(1920,1080),
        soft_min=0
    )

    bpy.utils.register_class(UVTransformOperator)
    bpy.utils.register_class(RenderImageOperator)
    bpy.utils.register_class(UVControlResetOperator)
    bpy.utils.register_class(RenderPanel)


def unregister():
    bpy.utils.unregister_class(UVTransformOperator)
    bpy.utils.unregister_class(RenderImageOperator)
    bpy.utils.unregister_class(UVControlResetOperator)
    bpy.utils.unregister_class(RenderPanel)

    del bpy.types.Scene.uv_translation
    del bpy.types.Scene.uv_rotation
    del bpy.types.Scene.uv_scale
    del bpy.types.Scene.render_fov
    del bpy.types.Scene.render_resolution


if __name__ == "__main__":
    register()
