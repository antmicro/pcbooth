# Usage

To run `PCBooth`, execute:

```bash
pcbooth
```

On first use, `PCBooth` will generate a default configuration file `blendcfg.yml` in the current directory.
This file can be adjusted to change output render results.

## Required input files

By default `PCBooth` operates on a PCB Blender model found in the `fab/` subdirectory in the directory from which the tool is executed. This file is the output of `gerber2blend` and/or `picknblend` tools.

However you can provide a path to any other Blender model file to `PCBooth` to render it using the following switch:

```bash
pcbooth -b path/to/model.blend
```

## Outputs

Resulting renders will be saved in directories specified in `blendcfg.yaml` file:

```yaml
    RENDER_DIR: blender_renders
    ANIMATION_DIR: assets/previews
```
These directories will be created in the current directory.

## Additional CLI arguments

`PCBooth` supports the following command arguments:

* `-c PRESET_NAME` - uses a selected `blendcfg` preset (see: [Custom config settings](blendcfg.md#custom-config-settings))
* `-d` - enables debug logging
* `-u` – merges additional settings from the template into the local configuration and exits. Existing user-defined settings remain unchanged. If no `blendcfg.yaml` file exists in the current directory, it is copied from the template instead.
* `-R` - resets the local configuration to match the template, overwriting any user-defined settings, then exits. If no `blendcfg.yaml` file exists in the current directory, it is copied from the template instead.
* `-l` - prints source Blender model object and collection hierarchy to console  
* `-g` - enforce rendering using GPU device, terminate script if no such device is available.

## Rendering jobs

`PCBooth` comes with rendering jobs that can be enabled to obtain various static images and animations. 

```{note}
Custom rendering jobs can be added to `PCBooth`. For more information, see: [Rendering jobs](#jobs.md) chapter.
```

````{tab} STATIC

Static image rendering job.

This module handles rendering of static images of a model on selected backgrounds using various camera angles.

Yields renders named <camera_angle><position initial>_<background name>, e.g. rightT_paper_black.png, for each combination.

```{figure} img/static.png
:align: center

````

````{tab} FLIPTRANSITION

This module handles rendering of animations showcasing the model (usually PCB) flipped from TOP to BOTTOM position. 
Flips will be rendered for all cameras specified in config file.
Always overrides background to "transparent" and positions to "TOP" and "BOTTOM".

Yields renders named <camera_angle><position initial>_<camera_angle><position initial>, e.g. rightT_leftT.webp, for each combination.

```{video} img/fliptransition.webm
:align: center

````

````{tab} CAMERATRANSITION

Camera transition animation rendering job.

This module handles rendering of animations showcasing the model transitioning from one camera angle to another. 
Transitions will be generated for all camera combinations specified in the configuration, but only within the same position (for example left to right bottom side, but never left top to right bottom).
Always overrides background to "transparent".

Yields renders named <camera_angle><position initial>_<camera_angle><position initial>, e.g. rightT_leftT.webp, for each combination.

```{video} img/cameratransition.webm
:align: center

````

````{tab} MASKS

Component binary mask rendering job.

This module handles fast rendering of static images of each component in a model component using a black and white color pallette.
These images can act as binary masks, enabling precise identification of the component's location within a full-color render. 
Masks are rendered for each camera in each model position specified in config.

Yields renders to the <RENDER_DIR>/masks/<full/covered>/<camera name><position initial>/ directory. Filename is determined based on model type:

    * for PCBs, designator of the rendered component is used as name
    * for other types of model, full rendered object name is used

This rendering job supports the following additional parameters:

    * `FULL` - boolean switch, enables mask renders as full component silhouette
    * `COVERED` - boolean switch, enables mask renders as components partially obscured by other components
    * `HIGHLIGHTED` - list of strings to restrict components rendered by specified designators (PCB type model only) 

```{figure} img/masks.png
:align: center

````

````{tab} HIGHLIGHTS

Highlighted components images rendering job.

This module handles rendering of static images of a model with simplified color pallette and its components highlighted using contrasting color.
This can be used to provide images for hardware documentation, to pinpoint specific components.

Yields renders to the <RENDER_DIR>/highlights/ directory. Filename is determined based on model type:

    * for PCBs, designator of the rendered component is used as name (adds <camera> suffix if camera is other than "TOP")
    * for other types of model, full rendered object name is used with <camera><position initial> suffix

Additional linked objects will be hidden for rendering.

```{figure} img/highlights.png
:align: center

````

````{tab} STACKUP

PCB stackup image rendering job.

This module handles rendering of static images of a PCB in exploded view.
Each layer gets rendered by hiding all the layers above it.
All objects imported on the PCB are hidden for rendering.

Yields renders named "layer<idx>", starting from 1 (e.g. layer1.png, layer2.png...).

```{note}
This rendering job is only compatible with `gerber2blend` output PCB models.
```

```{figure} img/stackup.png
:align: center

````

````{tab} ANIMATION

Animation rendering job.

This module handles rendering animation from keyframes that are predefined by user and saved within rendered .blend file.
It supports using various camera angles and selected backgrounds.

Yields renders named <camera_angle><position initial>_<background name>_animation e.g. rightT_paper_black_animation.webm, for each combination.

```{video} img/animation.webm
:align: center

````
## Model types

`PCBooth` will recognize model types based on found objects' structures or assign it based on values stored in the `blendcfg.yaml` file. 
This is implemented to properly group objects in the scene to better frame them and allow type-specific features.

If no specific model type is recognized, all objects saved within the .blend file will be framed by cameras.

### PCB type

This model type is assigned if `gerber2blend`/`picknblend` output PCB model is read. 

* by default entire model gets rotated horizontally before render (longer edge towards viewer) - can be disabled by setting ` SCENE/ADJUST_POSE: False`
* if components are imported, they are differentiated between top and bottom sides

### Single object type

This model is assigned if there's exactly one object in a scene.

* by default, the entire model gets rotated using value stored in `DISPLAY_ROT` custom property - this can be disabled by setting ` SCENE/ADJUST_POSE: False`
* before render, origin point of the model will be temporarily moved to geometric center of the model to make position changes more aesthetically appealing

### `blendcfg.yaml` override

A rendered object or group of objects can be manually specified in the `OBJECT` section in the configuration file. This will result in camera framing the object choice, while leaving rest of the scene contents in the background.

To render a selected object present in the .blend file, use the following syntax: 

```yaml
  OBJECT:
    ...
    RENDERED_OBJECT: Object/<object name>
```

Alternatively, to render the entire collection as a single rendered object, use the following syntax: 

```yaml 
  OBJECT:
    ...
    RENDERED_OBJECT: Collection/<collection name>
```

## Using a custom camera

Aside from preset cameras (see: [Configuring blendcfg.yaml: `CAMERAS`](blendcfg.md#cameras)), `PCBooth` can pick up a user-defined custom camera saved within a rendered Blender model.

For the user camera to be recognized as valid, simply name it `camera_custom`.

To enable rendering using the custom camera, enable the following setting in `blendcfg.yaml`:

```yaml
  CAMERAS:
    ...
    CUSTOM: True
```

```{note}
A custom camera gets aligned to a selected rendered object before the render, so that the object is in the center of its FOV. This might cause its position and rotation to be altered.
```


