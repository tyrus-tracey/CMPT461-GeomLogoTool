# Geometry-Aware Logo Application Blender Add-on
Apply desired logo images onto your Blender mesh such that it properly conforms to the geometry. This does NOT use projection!

## Installation Instructions
After cloning the repo, open Blender and navigate to Edit > Preferences. Go to Add-ons and click on the downward arrow on the top-right to access the drop-down menu for "Install from disk...". Locate the python scripts and install.

## How to Use
### Applying the Logo
Once your scene geometry from MoGE is loaded into Blender, simply press F8 to execute the add-on. 
First load your PNG logo image. Once loaded, the 3D cursor is brought up to indicate where on the geometry you would like to apply the logo. You are free to move the 3D Viewport around to direct the target region. You can then use the mousewheel to expand or shrink the selection region.
Once the desired target region is selected, press Enter to apply the logo image as a texture. 
### Tuning Logo Placement
To fine-tune the UV parameters, bring up the Render Panel by navigating to the side toolbar (next to the Navigation Gizmo). This may be collapsed by default (in which case it is a leftward arrow); click on it to expand. The click on Render Applied Logo to bring up the panel. Logo translation, rotation, scale can be adjusted here. 
### Rendering
To render the image (which will only contain the logo), first input the FOV (from MoGE) and the image's resolution. Then hit Render Image to produce the render, saved in the same directory as the current Blender project.
