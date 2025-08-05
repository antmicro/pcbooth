# Configuring blendcfg.yaml

You can customize `PCBooth`'s behavior and outputs by editing the `blendcfg.yaml` file which defines many scene parameters like background, camera, light, compositor effects options and render jobs to execute.
The file needs to be placed in the main directory of the hardware project.
A default `blendcfg.yaml` is generated in the project directory when one does not exist.
Alternatively it can be copied manually from this repo, from the [`templates/blendcfg.yaml`](../../src/pcbooth/templates/blendcfg.yaml) file.

A single, joint `blendcfg.yaml` file can be shared between [`gerber2blend`](https://github.com/antmicro/gerber2blend), [`picknblend`](https://github.com/antmicro/picknblend) and `PCBooth` tools.

This file can contain the following configuration sections:

## Config section descriptions

### `SETTINGS`

Specifies paths to input files and naming conventions used by `PCBooth`:
* `PRJ_EXTENSION` - string containing EDA software main project file extension, used to read the PCB project name. Can be set to `""` if the extension is undefined. If no files with this extension are found, `unknownpcb` will be used as the name.
* `FAB_DIR` - string specifying the **name** of the intermediate work directory that the board model and PnP data are located in. This is relative to the working directory/hardware project that `pcbooth` is executed from.
* `RENDER_DIR` - string specifying the **name** of the intermediate work directory that the output render image files will be saved to
* `ANIMATION_DIR`- string specifying the **name** of the intermediate work directory that the output video files will be saved to
* `IMAGE_FORMAT` - list of output image formats; each must be supported by Blender (currently _BMP, IRIS, PNG, JPEG, JPEG2000, TARGA, TARGA_RAW, CINEON, DPX, OPEN_EXR_MULTILAYER, OPEN_EXR, HDR, TIFF, WEBP_)
* `VIDEO_FORMAT` - list of output video formats; the currently supported formats are: _AVI, MP4, MPEG, WEBM, GIF_
* `THUMBNAILS` - boolean switch enabling saving scaled copies of renders as thumbnails 
* `KEEP_FRAMES` - boolean switch enabling preserving rendered intermediate files like cache and animation frames
* `SAVE_SCENE` - boolean switch enabling saving a copy of the input Blender model with scene objects added

### `RENDERER`

Renderer-related settings:
* `SAMPLES` - `Cycles` render engine samples as integer, lower values speed up rendering times but results are noisy, higher values yield higher quality image but rendering times are longer 
* `FPS` - frames per second as integer - value used for interpolating animations and FFMPEG sequencing
* `IMAGE_WIDTH`, `IMAGE_HEIGHT` - rendered image output resolution as integer, applies to initial render, saved stills and frames
* `VIDEO_WIDTH`, `VIDEO_HEIGHT` - sequenced video output resolution as integer, applies to saved video files
* `THUMBNAIL_WIDTH`, `THUMBNAIL_HEIGHT` - output thumbnail resolution as integer, applies to both output images and videos

### `SCENE`
Scene configuration:
* `LIGHTS_COLOR` - area lights color in form of hex value (_AABBCC_)
* `LIGHTS_INTENSITY` - area lights intensity in form of float value multiplier. Default is _1.0_, set to _0.0_ to disable area lights.
* `HDRI_INTENSITY` - HDRI intensity in form of float value multiplier. Default is _0.5_, set to _0.0_ to disable HDRI.
* `DEPTH_OF_FIELD` - boolean switch enabling depth of field for all cameras in the Blender scene.
* `FOCAL_RATIO` - sets the camera's aperture as a ratio of focal length for depth of field effect (accepts fractions like f/4, 1/4 or floats, type "auto" for calculated value).
* `FOCAL_LENGTH` - defines the focal length of the perspective camera in millimeters. Defaults to 105 mm.
* `LED_ON` - boolean switch enabling emissive shader nodes in the entire model. Setting this switch to _False_ will cause all LED-like elements of the model to not emit any light on render.
* `ADJUST_POS` - boolean switch enabling automatic rotations to be applied to rendered object before renders to improve position in frame
* `ADJUST_CAM` - boolean switch enabling custom camera adjustments applied to camera_custom before renders, based on the rendered object's bounding box and distance
* `ORTHO_CAM` - boolean switch enabling increased focal length setting applied to all cameras in Blender scene resulting in orthographic-like renders.
* `RENDERED_OBJECT` - optional string defining exact Blender object or collection to be used as rendered object. Syntax is `Object/<name of object>` or `Collection/<name of collection>`.

### `BACKGROUNDS`
List of enabled backgrounds:
* `LIST` - list of strings specifying backgrounds to use in renders. Accepts names from models stored in the `../../pcbooth/templates/backgrounds/` directory and "_transparent_" to render without background

#### Examples of available backgrounds:

````{tab} paper_black

```{figure} img/paper_black.png
:align: center

````

````{tab} paper_white

```{figure} img/paper_white.png
:align: center

````

````{tab} transparent

```{figure} img/transparent.png
:align: center

````

### `CAMERAS`
Camera configuration to use for renders:

* `TOP`, `ISO`, `FRONT`, `LEFT`, `RIGHT`, `PHOTO1`, `PHOTO2` - boolean switches enabling camera angle presets. 
* `CUSTOM` - boolean switch enabling use of a custom camera predefined by user in the input Blender model. The camera must be named "_camera\_custom_" to be recognized by PCBooth.

#### Examples of camera angle presets:

````{tab} TOP

```{figure} img/topT.png
:align: center

````

````{tab} ISO

```{figure} img/isoT.png
:align: center

````

````{tab} FRONT

```{figure} img/frontT.png
:align: center

````

````{tab} LEFT

```{figure} img/leftT.png
:align: center

````

````{tab} RIGHT

```{figure} img/rightT.png
:align: center

````

````{tab} PHOTO1

```{figure} img/photo1T.png
:align: center

````

````{tab} PHOTO2

```{figure} img/photo2T.png
:align: center

````

### `POSITIONS`
Configuration of rendered object:
* `TOP`, `BOTTOM`, `REAR` - boolean switches enabling different rendered model positions facing the camera

#### Example of rendered model positions:

````{tab} TOP

```{figure} img/photo1T.png
:align: center

````
````{tab} BOTTOM

```{figure} img/photo1B.png
:align: center

````
````{tab} REAR

```{figure} img/photo1R.png
:align: center

````

### `OUTPUTS`
List of render jobs to be executed with `PCBooth`. The module names are followed by a _:_, for example:

```yaml
OUTPUTS:
    - STATIC:
    - FLIP_TRANSITIONS:
```

Some rendering jobs support additional job-specific parameters. 
They can be passed in the config using the following syntax:

```yaml
OUTPUTS:
    - MASKS:
        FULL: True
        COVERED: False
        HIGHLIGHTED: ["U", "A", "J"]
    - STATIC:
    ...
```

```{note}
To learn how to create your own rendering jobs, see the [Rendering jobs](#jobs.md) chapter.
```

## Custom config settings

You can run `PCBooth` with a specified configuration preset by typing `PCBooth -c custom_preset` as mentioned in [usage chapter](usage.md#additional-cli-arguments). The current template file contains a single, default preset. You can add a new preset and save it in the `blendcfg.yaml` template file as follows:

```yaml
default:
  SETTINGS:
    PRJ_EXTENSION: .kicad_pro         
    FAB_DIR: fab                      
    RENDER_DIR: blender_renders       
    ANIMATION_DIR: assets/previews    
        ...

custom_preset:
  SETTINGS:
    PRJ_EXTENSION: .pro         
```

In `blendcfg.yaml` presets, only the fields that are modified need to be included in a new preset. The remaining values are inherited from the default preset through mapping merges. 