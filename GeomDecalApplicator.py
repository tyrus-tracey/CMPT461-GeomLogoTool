import bpy
import bmesh
import os.path
from mathutils import Vector
import mathutils
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from mathutils.bvhtree import BVHTree
import bpy_extras.view3d_utils
from bpy.props import StringProperty

bl_info = {
    "name": "Geometry-Aware Decal Applicator",
    "blender": (2, 8, 0),
    "category": "Object",
    "author": "Tyrus & Stefan",
    "description": "While running (F8), selects the face currently pointed to by the 3D view. The view can be moved around to select the desired region. This selection can be expanded/shrunk using the mousewheel. Once a desired region is covered, press Enter to apply the image onto the mesh.",
    "version": (1, 0, 0),
    "support": "COMMUNITY",
    "tracker_url": "",
}

class GeomAwareDecalOperator(Operator):
    bl_idname = "object.geom_aware_decal_applicator"
    bl_label = "Geometry-Aware Decal Applicator"
    bl_options = {'REGISTER', 'UNDO'}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_face_index = None
        self.obj = None
        self.obj_bmesh = None
        self.obj_bvhTree = None
        print("Start")
    
    def modal(self, context, event):         
        # Esc to cancel
        if event.type == 'ESC':
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, "Operation cancelled.")
            return {'CANCELLED'}
        # Enter to apply texture and finish
        if event.type == 'RET':
            self.applyTex(context.object, context)
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'INFO'}, "Operation finished.")
            return {'FINISHED'}
        # Mousewheel to expand/shrink region
        if event.type == 'WHEELUPMOUSE':
            bpy.ops.mesh.select_more()
            self.report({'INFO'}, "Expanding selection.")
            return {'RUNNING_MODAL'}
        if event.type == 'WHEELDOWNMOUSE':
            bpy.ops.mesh.select_less()
            self.report({'INFO'}, "Reducing selection.")
            return {'RUNNING_MODAL'}
        
        # If frame changed (i.e. mouse moved) run a raycast
        if event.type == 'MOUSEMOVE':
            # Get the context's 3D View
            rv3d = context.region_data
            
            # Update 3d cursor location to be just in front of 3D view
            #   (Makes it easy for user to see where the raycast is coming from)            
            forward = mathutils.Matrix.Translation((0,0,-1))
            cursorpos = (rv3d.view_matrix.inverted() @ forward).translation
            bpy.context.scene.cursor.location = cursorpos
            
            # Raycast down the 3D View's center of projection
            bpy.ops.object.mode_set(mode='OBJECT')
            hit, face_index = self.raycast(rv3d)
            bpy.ops.object.mode_set(mode='EDIT')
            
            if hit:
                # If a new face is hit by ray, update as the new selected face
                if face_index != self.active_face_index:
                    self.active_face_index = face_index
                    
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.mode_set(mode='OBJECT')
                    
                    self.obj.data.polygons[face_index].select = True
                    
                    bpy.ops.object.mode_set(mode='EDIT') 
                    self.report({'INFO'}, f"Selected face {face_index}.")
            else:
                self.report({'INFO'}, "No face hit.")
        
        # Pass through to allow 3D View translation/rotation events to bubble-up the event hierarchy
        #   (Otherwise 3D View is effectively locked in position while this is running) 
        return {'PASS_THROUGH'}
        
    def invoke(self, context, event):
        # Initialize some variables
        self.active_face_index = None
        self.obj = context.object
        
        if not self.obj or self.obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh.")
            return {'CANCELLED'}
        
        # Construct BVH tree of the geometry for raycast collision-detection
        self.obj_bmesh = bmesh.new()
        self.obj_bmesh.from_mesh(self.obj.data)
        self.obj_bvhTree = BVHTree.FromBMesh(self.obj_bmesh)
        
        if not self.obj_bvhTree:
            self.report({'ERROR'}, "Failed to construct BVH Tree.")
            return {'CANCELLED'}
        
        # Disable Blender from adding its own shading in the scene
        self.obj.visible_shadow = False
        
        # Open a file browser to select a .png image
        bpy.ops.object.open_png('INVOKE_DEFAULT')
        
        # Start the modal operator for face selection
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def raycast(self, rv3d):
        # Perform a raycast to find the face directly pointed to by the 3D View
        viewmat = rv3d.view_matrix
        
        viewmat_inv = rv3d.view_matrix.inverted()
        ray_origin = bpy.context.scene.cursor.location             
       
        # Define ray direction from the view's current position to the 3D cursor
        #   (Since we've set the 3D cursor to be right in front of the 3D view, 
        #    effectively this is the 3D View's forward vector translated to world space)
        cursorpos = bpy.context.scene.cursor.location
        ray_direction = cursorpos - viewmat.inverted().translation
        
        # 9999.9 for distance limit is probably sufficient
        hit, normal, face_index, dist = self.obj_bvhTree.ray_cast(ray_origin, ray_direction, 9999.9)
        
        if hit:
            return True, face_index
        else:
            return False, None
            
    def applyTex(self, obj, context):
        # Grab the logo image loaded into Blender's data struct
        img = bpy.data.images.get(context.scene.logo_filename)
        
        mat_logo = bpy.data.materials.new(name="mat")
        mat_logo.use_nodes = True
        
        mat_logo.blend_method = 'HASHED'
        
        nodes = mat_logo.node_tree.nodes
        
        for node in nodes:
            nodes.remove(node)
            
        node_logoTex = nodes.new(type='ShaderNodeTexImage')
        node_logoTex.image = img        
        node_logoTex.extension = 'CLIP'
        
        node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        node_matOut = nodes.new(type='ShaderNodeOutputMaterial')
        
        # Link image texture's RGBA values to BSDF node
        mat_logo.node_tree.links.new(node_logoTex.outputs['Color'], node_bsdf.inputs['Base Color'])
        mat_logo.node_tree.links.new(node_logoTex.outputs['Alpha'], node_bsdf.inputs['Alpha'])
        
        # Link BSDF node to output node
        mat_logo.node_tree.links.new(node_bsdf.outputs['BSDF'], node_matOut.inputs['Surface'])
        
        # Switch to object mode to apply material
        bpy.ops.object.mode_set(mode='OBJECT')
        selected_faces = [face for face in obj.data.polygons if face.select]
        
        if len(obj.data.materials) == 1:
            obj.data.materials.append(mat_logo)
        
        for face in selected_faces:
            face.material_index = 1
            
        # Switch to edit mode to apply UV unwrapping
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap(method='ANGLE_BASED', no_flip=True)
        #bpy.ops.uv.smart_project(angle_limit=1.5708, island_margin=0.02)
        
        
addon_keymaps = []

def register():
    bpy.types.Scene.logo_filename = bpy.props.StringProperty()
    
    bpy.utils.register_class(GeomAwareDecalOperator)
    bpy.utils.register_class(OpenPNGOperator)
    
    # Binds F8 to run modal
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = wm.keyconfigs.active.keymaps.get("3D View")
        kmi = km.keymap_items.new(GeomAwareDecalOperator.bl_idname, 'F8', 'PRESS', ctrl=False, shift=False)
        addon_keymaps.append((km, kmi))
    
def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    del bpy.types.Context.logo_filepath
    bpy.utils.unregister_class(GeomAwareDecalOperator)
    bpy.utils.unregister_class(OpenPNGOperator)
    
    
# Opens a file browser to select a .png image.
class OpenPNGOperator(Operator, ImportHelper):
    bl_idname = "object.open_png"
    bl_label = "Open PNG"
    
    # Exclude all other formats
    filter_glob: StringProperty(
        default='*.png',
        options={'HIDDEN'}
    )
    
    def execute(self, context):
        bpy.data.images.load(self.filepath)
        context.scene.logo_filename = os.path.basename(self.filepath)
        return {'FINISHED'}
        
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
if __name__ == "__main__":
    register()