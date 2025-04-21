import tkinter
from tkinter import ttk
from tkinter import filedialog as fd
from PIL import ImageTk, Image

import cv2
import torch
from moge.model.v1 import MoGeModel
from moge.utils.io import save_glb

from intrinsic.pipeline import load_models, run_pipeline
import chrislib.general as cg

import numpy as np
import utils3d


#Load MoGe Model
device = torch.device("cuda")
moge_model = MoGeModel.from_pretrained("Ruicheng/moge-vitl").to(device)

#Load decomposition model
int_model = load_models('v2')

#Set global variables
target_img = None
target_cv = []
preview_img = None
fov_x = None
fov_y = None
logo_img = None
final_img = None

#Create window
window = tkinter.Tk()
window.title("Image decomposition and compositing")

#Left column of GUI
pic_frame = ttk.Frame()
pic_frame.grid(row=0,column=0)

#Label that holds preview image
panel = ttk.Label(pic_frame,text="No image loaded",width=-50)
panel.configure(anchor="center")
panel.pack()

#Label that displays status information
info = ttk.Label(pic_frame,text="")
info.pack()

def img_resize(img):
    """
    Takes img and converts it into a preview
    to be displayed to the user
    Returned value has is resized to fixed x and
    converted to proper format
    """
    x = 300
    per = x / img.size[0]
    y = int(img.size[1]*per)
    img = img.resize((x,y))
    return ImageTk.PhotoImage(img)

def get_file():
    """
    Displays open file dialog to read image
    On success returns image
    On fail returns None
    """
    fp = fd.askopenfilename()
    try:
        img = Image.open(fp)
    except:
        panel.config(text="Error: Failed to Open Image\nMake sure file is image type")
        return None, None
    return fp, img

def load_target():
    """
    Loads an image as the target (image that the logo will be inserted into)
    On success it will display a preview of the loaded image
    On fail writes error message to bottom of screen
    """
    info.config(text="Getting Image")
    #Get file and check if it was loaded properly
    fp, t_img = get_file()
    if t_img == None:
        info.config(text="Image Could Not Be Loaded")
        return
    #Load image to global variable
    global target_img
    target_img = t_img
    global target_cv
    target_cv = cv2.cvtColor(cv2.imread(fp),cv2.COLOR_BGR2RGB)
    #Display Preview
    global preview_img
    preview_img = img_resize(t_img)
    panel.config(image=preview_img)
    info.config(text="Image Loaded")

def build_geometry():
    """Runs MoGe to convert image to 3D model"""
    if len(target_cv) == 0:
        info.config(text="Error: Load Target Image First")
        return
    #Prepare Image
    info.config(text="Preparing Image")
    input_image = target_cv
    input_image_t = torch.tensor(input_image / 255, dtype=torch.float32, device=device).permute(2, 0, 1)

    #Run Model
    info.config(text="Getting Point Map")
    output = moge_model.infer(input_image_t)

    points, depth, mask, intrinsics = output['points'].cpu().numpy(), output['depth'].cpu().numpy(), output['mask'].cpu().numpy(), output['intrinsics'].cpu().numpy()
    normals, normals_mask = utils3d.numpy.points_to_normals(points, mask=mask)

    #Get Mesh
    info.config(text="Getting Mesh")
    height, width = input_image.shape[:2]
    faces, vertices, vertex_colors, vertex_uvs = utils3d.numpy.image_mesh(
        points,
        input_image.astype(np.float32) / 255,
        utils3d.numpy.image_uv(width=width, height=height),
        mask=mask & ~(utils3d.numpy.depth_edge(depth, rtol=0.03, mask=mask) & utils3d.numpy.normals_edge(normals,tol=5,mask=normals_mask)),
        tri=True
    )
    vertices, vertex_uvs = vertices * [1, -1, -1], vertex_uvs * [1, -1] + [0, 1]

    #Save result
    info.config(text="Saving Mesh")
    save_dir = fd.askdirectory()
    save_glb(save_dir + '\\mesh.glb', vertices, faces, vertex_uvs, input_image)

    #Get FOV
    global fov_x, fov_y
    fov_x, fov_y = utils3d.numpy.intrinsics_to_fov(intrinsics)
    fov_x,fov_y = round(np.rad2deg(fov_x),3), round(np.rad2deg(fov_y),3)

    if width > height:
        fov = fov_x
    else:
        fov = fov_y

    info.config(text="Mesh Saved. FOV Is: " + str(fov))

def logo_get():
    """
    Loads an image as the logo to be inserted
    On success it will display a preview of the loaded image
    On fail writes error message to bottom of screen
    """
    # Get file and check if it was loaded properly
    info.config(text="Getting Image")
    _, t_img = get_file()
    if t_img == None:
        info.config(text="Image Could Not Be Loaded")
        return
    # Load image to global variable
    global logo_img
    logo_img = t_img
    info.config(text="Image Loaded")

def composite():
    """
    Decomposes the target image into albedo, shading, and residual
    Then alpha composites the logo with the albedo before reconstructing the image
    On success image is saved in global variable and preview is displayed
    On fail error message is displayed
    """
    #Check required images are loaded and exit if they are not
    if target_img == None:
        info.config(text="Error: Please Load Target Image First")
        return
    if logo_img == None:
        info.config(text="Error: Please Load Logo Image First")
        return
    # Check if logo image has alpha
    h1, w1, c = np.asarray(logo_img).shape
    h2, w2, _ = np.asarray(target_img).shape
    if c != 4:
        info.config(text="Error: Logo Image Should Include Transparency")
        return
    if h1 != h2 or w1 != w2:
        info.config(text="Error: Logo Image Should be Same Size As Target Image")
        return

    #Perform Intrinsic Decomposition
    info.config(text="Decomposing Image")
    i_img = np.array(target_img).astype(np.single)
    i_img = i_img / float((2 ** 8) - 1)
    decomp_results = run_pipeline(int_model,i_img,device='cuda',resize_conf=None)
    alb = decomp_results['hr_alb']
    dif = 1 - cg.invert(decomp_results['dif_shd'])
    res = decomp_results['residual']

    #Alpha composite logo onto albedo
    #Convert albedo to PIL format, add alpha to logo and then composite
    info.config(text="Compositing Logo")
    alb = Image.fromarray((alb*255).astype(np.uint8))
    #alb.save("test1.png")
    alb.putalpha(255)
    l_img = logo_img.resize(alb.size)
    alb = Image.alpha_composite(alb,l_img)
    #alb.save("test.png")
    #Convert albedo back to array
    alb = np.asarray(alb)
    alb = alb[:,:,0:3]

    #Composite Remaining Layers
    info.config(text="Reconstructing Image")
    alb = alb.astype(np.float32) / 255
    #recon = np.add(res, np.multiply(alb,dif))
    recon = cg.view(alb*dif)
    #Convert to image format
    recon = Image.fromarray((recon * 255).astype(np.uint8))
    global final_img
    final_img = recon

    #Display preview of result
    global preview_img
    preview_img = img_resize(recon)
    panel.config(image=preview_img)
    info.config(text="Compositing Complete")

def save_img():
    """
    Prompts user to save the final image
    """
    #Check that final image is constructed
    if final_img == None:
        info.config(text="Error: Composite Image First")
        return
    #Get save path from user and then save
    info.config(text="Saving Image")
    save_path = fd.asksaveasfilename(initialfile='Untitled.png',defaultextension='png',filetypes=[("png","*.png"),("jpg","*.jpg")])
    final_img.save(save_path)
    info.config(text="Image Saved")

#Define right column of GUI
button_frame = ttk.Frame()
button_frame.grid(row=0,column=1)

#Define all buttons
button_img = ttk.Button(button_frame,text="Load Target\nImage",command=load_target)
button_img.grid(row=0,column=0,padx=5)

button_geo = ttk.Button(button_frame,text="Build\nGeometry",command=build_geometry)
button_geo.grid(row=1,column=0,padx=5)

button_logo = ttk.Button(button_frame,text="Load Logo",command=logo_get)
button_logo.grid(row=2,column=0,padx=5)

button_composite = ttk.Button(button_frame,text="Composite\nImage",command=composite)
button_composite.grid(row=3,column=0,padx=5)

button_save = ttk.Button(button_frame,text="Save Image",command=save_img)
button_save.grid(row=4,column=0,padx=5)

window.mainloop()
