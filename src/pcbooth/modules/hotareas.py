import bpy
import pcbooth.modules.config as config
import re
from os import path, listdir, remove
import cv2
import json
import numpy as np

from pcbooth.modules.renderer import (
    setup_ultralow_cycles,
    revert_cycles,
    stdout_redirected,
    set_pads_compositing,
    set_compositing,
    set_hotarea_compositing,
)
import logging
import pcbooth.modules.studio as studio

logger = logging.getLogger(__name__)


def check_if_interactive(component, cfg):
    if config.isAssembly or config.isComponent:
        return True
    pattern = r"^([A-Za-z]+)\d*:"
    match = re.match(pattern, component.name)
    designator = match.group(1) if match else ""

    isInteractive = False
    if "All" in cfg:
        isInteractive = True
        return isInteractive
    elif "Default" in cfg or cfg == "":
        default = ["A", "J", "PS", "T", "U", "IC", "POT"]
        interactive = default
    else:
        interactive = cfg
    if any([inter == designator for inter in interactive]):
        isInteractive = True
    return isInteractive


def parse_interactive():
    interactive = config.blendcfg["SETTINGS"]["INTERACTIVE"]
    interactive = interactive.replace(" ", "")
    interactive = interactive.split(",")
    return interactive


def setup_hotarea_config():
    """
    Override ['RENDERS'] setting with all possible views if 'All' is set in ['TRANSITIONS'] in blendcfg.
    Use ['RENDERS'] setting if 'Renders' is picked.
    """

    config_backup = config.blendcfg["RENDERS"].copy()
    if config.blendcfg["OUTPUT"]["TRANSITIONS"][1] == "All":
        config.blendcfg["RENDERS"]["TOP"] = True
        config.blendcfg["RENDERS"]["BOTTOM"] = True
        config.blendcfg["RENDERS"]["ORTHO"] = True
        config.blendcfg["RENDERS"]["PHOTO"] = False
        config.blendcfg["RENDERS"]["LEFT"] = True
        config.blendcfg["RENDERS"]["RIGHT"] = True
        config.blendcfg["RENDERS"]["ISO"] = False
        config.blendcfg["RENDERS"]["PERSP"] = False
        config.blendcfg["RENDERS"]["FRONT"] = False

    return config_backup


def get_contours(img):
    _, thresh = cv2.threshold(img.copy(), 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_L1)
    if contours:
        return contours
    else:
        return []


def shape2contour(img, simplify=None, filter_level=0.01):
    morph = False
    img = cv2.GaussianBlur(img, (3, 3), 0)
    contours = get_contours(img)
    if len(contours) == 0:
        return []
    for c in contours:
        if len(c) < 1:
            return []
        if len(c) > 25 and len(c) < 50:
            c1 = cv2.convexHull(c)
            if len(c1) > 20:
                morph = True
                break
            else:
                c1 = c
        if len(c) > 50:
            morph = True
            break
    if morph:
        kernel = np.ones((3, 3))
        kernel2 = np.ones((3, 3))
        img2 = cv2.erode(img.copy(), kernel, iterations=3)
        img2 = cv2.dilate(img2, kernel2, iterations=1)
        contours = get_contours(img2)
        eps = simplify
        for c in contours:
            peri = cv2.arcLength(c, True)
            c = cv2.approxPolyDP(c, eps * peri, True)
    # remove small contour areas
    max_area = max([cv2.contourArea(c) for c in contours])
    if max_area == 0:
        return []
    filtered_contours = []
    for c in contours:
        if cv2.contourArea(c) / max_area > filter_level:
            # biggest contour first in list
            if cv2.contourArea(c) == max_area and len(filtered_contours):
                filtered_contours.insert(0, c)
            else:
                filtered_contours.append(c)
    return filtered_contours


def process_hotarea(hotarea_path: str) -> None:
    logger.info(f"Processing {hotarea_path}")
    reference = path.basename(hotarea_path).split(".")[0]
    dir = path.dirname(hotarea_path)
    # print(dir)
    try:
        img = cv2.imread(hotarea_path, cv2.IMREAD_GRAYSCALE)
    except:
        logger.error("Cannot read image")
        return
    contours = shape2contour(img, simplify=0.01)
    if contours is None:
        logger.info("Contours not found on image")
        return
    clist = []
    height, width = img.shape
    for c in contours:
        c_tojson = c.astype(float)
        for coord in c_tojson:
            coord[0][1] = float(coord[0][1]) / width
            coord[0][0] = float(coord[0][0]) / height
        clist.append([list(float(c_tojson) for c_tojson in v[0]) for v in c_tojson])
    imo = np.clip(img, 170, 255)
    try:
        cv2.drawContours(imo, contours, -1, 10, 2)
        cjson = {"reference": reference, "proportionalOutlinePath": clist[0]}
        if len(clist) > 1:
            cjson["additionalOutlinePaths"] = clist[1:]
        with open(path.join(dir, reference + ".json"), "w") as file:
            json.dump(cjson, file)
    except:
        logger.error(f"{hotarea_path} can't be processed! Skipping.")


def run_hotareas_script(hotareas_path):
    logger.info("** [CONTOUR DETECTION] **")
    logger.debug(f"Searching dir: {hotareas_path}")
    if not path.exists(hotareas_path):
        logger.info(f"{hotareas_path} directory not found. Skipping.")
        return
    for dir in listdir(hotareas_path):
        logger.debug("dir = " + dir)
        png_files = [
            f for f in listdir(hotareas_path + "/" + dir) if f.endswith(".png")
        ]
        logger.debug("found pngs: " + str(png_files))
        for png in png_files:
            logger.debug(f"Generate JSON from png: {png}")
            designator = png[:-4]
            process_hotarea(hotareas_path + dir + "/" + png)
            if path.exists(path.join(hotareas_path, dir, designator + ".json")):
                logger.debug(f"JSON for {png} was saved.")
            else:
                logger.debug(f"JSON for {png} was not saved.")
            if not config.blendcfg["SETTINGS"]["KEEP_PNGS"]:
                remove(path.join(hotareas_path, dir, png))


def hotarea_renders(pcb_parent, add_info=""):
    logger.info("** [HOTAREA] **")
    direction = ["TOP", "BOTTOM", "REAR"]

    interactive = parse_interactive()
    components_bottom = [
        obj
        for obj in config.bottom_components
        if check_if_interactive(obj, interactive)
    ]
    components_top = [
        obj for obj in config.top_components if check_if_interactive(obj, interactive)
    ]
    setup_ultralow_cycles()
    config_backup = setup_hotarea_config()
    hotarea_path = config.hotareas_path

    for dir in direction:  # {direction} True backgrounds
        if config.blendcfg["RENDERS"][dir]:  # direction {True} backgrounds
            for cam_type in config.cam_types:  # {cam_type} True
                if config.blendcfg["RENDERS"][cam_type]:  # cam_type {True}
                    logger.info(f"{add_info} {dir} {cam_type}")
                    file_path = hotarea_path + cam_type.lower() + dir[0]
                    cam_obj = bpy.data.objects.get("camera_" + cam_type.lower())
                    if cam_obj is None:
                        logger.warning(
                            f"{cam_type} view enabled in config but no 'camera_{cam_type.lower()}' object found in file. Skipping hotarea."
                        )
                    else:
                        studio.obj_set_rotation(pcb_parent, dir[0])
                        studio.studio_prepare(pcb_parent, "Transparent", cam_obj)
                        view = cam_type.lower() + dir[0]
                        component_hotareas(
                            view,
                            (
                                components_top
                                if dir[0] in ["T", "R"]
                                else components_bottom
                            ),
                            file_path,
                            cam_obj,
                        )
                        studio.obj_set_rotation(pcb_parent, "T")
    revert_cycles()
    run_hotareas_script(hotarea_path)

    # revert config
    config.blendcfg["RENDERS"] = config_backup


def hide_from_renders(collection_name: str, is_hidden: bool) -> None:
    collection = bpy.data.collections.get(collection_name)
    for obj in collection.objects:
        obj.hide_render = is_hidden
    collection.hide_render = is_hidden


def component_hotareas(side, component_list, file_path, camera):
    logger.debug(file_path)
    logger.debug(side)
    logger.debug(component_list)
    scene = bpy.context.scene
    scene.camera = camera

    # set hotarea compositing
    # take alpha of generated image and color it black and gray
    set_hotarea_compositing()

    if config.isComponent:
        config.rendered_obj.hide_render = True

    # create and assign simple override material
    override_material = bpy.data.materials.new("override_material")
    view_layer = bpy.context.view_layer
    view_layer.material_override = override_material
    # render objects as holdouts, creating a hole in the image with zero alpha
    for obj in bpy.data.objects:
        obj.is_holdout = True

    for comp in component_list:
        if config.isPCB or config.isComponent:
            scene.render.filepath = file_path + "/" + comp.name.split(":")[0]
        else:
            scene.render.filepath = file_path + "/" + comp.name.rsplit(".")[0]

        logger.debug(f"Rendering: {str(comp.name)} Side: {str(side)}")
        comp.is_holdout = False  # enable single object
        with stdout_redirected():
            bpy.ops.render.render(write_still=True)
        comp.is_holdout = True  # disable single object

    # restore objects' render without holdouts
    for obj in bpy.data.objects:
        obj.is_holdout = False

    # restore overriden materials, remove override material
    view_layer.material_override = None
    bpy.data.materials.remove(override_material)

    # revert compositing
    if config.isComponent:
        set_pads_compositing()
        config.rendered_obj.hide_render = False
    else:
        set_compositing()
