# Rendering jobs

To obtain renders of any type, `PCBooth` executes rendering jobs.
These jobs are defined in the `blendcfg.yaml` configuration file.
The following rendering jobs are queued by default:

```yaml
  STAGES:
    - STATIC:
    - FLIPTRANSITIONS:
```

Each stage in the pipeline is provided from the `jobs` package in the Blender Python environment.
For example, `STATIC` is defined in the [jobs/static.py](../../src/jobs/static.py) file:

```{eval-rst}
.. literalinclude:: ../../src/pcbooth/jobs/static.py
  :language: python
  :pyobject: Static
```

A rendering job can iterate over elements of the scene (backgrounds, cameras, rendered model) through the Studio class object that gets passed to Job class instances on initialization or alter model objects. 
A single Python file can contain multiple stage definitions.
A stage **must** inherit from the `core.job.Job` base class to be discoverable by `PCBooth`.
To call a stage from `blendcfg.yaml`, refer to the stage's class name in **uppercase** (`STATIC`, in this case) for `PCBooth` to dynamically load and run the code defined in the `iterate` method for the class.
The `execute` method for a stage is called when all previous stages are completed successfully.

## Writing rendering jobs

### Tracking progress

To properly display progress of the rendering job, the `update_status` method can be used. 
When calling it with integer as an argument, you can set the count of all renders within this job. 
You can update this total count value as many time as needed. 
Here's an example of setting total number of renders based on cameras to use:

```python
def iterate(self) -> None:
    total_renders = len(self.studio.cameras)
    self.update_status(total_renders)
    ...
```

When called without an argument, it will increment the progress count iterator and print a status update in the console:

```python
    for camera in self.studio.cameras:
      renderer.render(camera.object, file_name="render")
      renderer.clear_cache()
      self.update_status()
```

```
[15:19:30] [pcbooth.modules.renderer] (INFO) Rendering photo1T_paper_black...
[15:19:40] [pcbooth.modules.renderer] (INFO) Saved render as: //blender_renders/photo1T_paper_black.png
[15:19:40] [pcbooth.modules.renderer] (INFO) Saved render as: //blender_renders/photo1T_paper_black.jpg
[15:19:41] [pcbooth.core.job] (INFO) ### Progress: 1/6 (16%)
```

### Overriding config 

For some rendering jobs, you might want to force rendering with specific cameras or on specific backgrounds. 
You can do it by overriding `_override_studio` method within your job class and defining studio's lists there:

```python
from pcbooth.modules.background import Background
from pcbooth.modules.camera import Camera

class MyRenderingJob(pcbooth.core.job.Job):
  """ Custom example rendering job """

  def _override_studio(self):
      self.studio.backgrounds = [Background.get("transparent")]
      self.studio.positions = ["TOP", "BOTTOM"]
      self.studio.cameras = [Camera.get("PHOTO1"), Camera.get("FRONT")]
```

This method will now override values read from config for your specific job only. 
Other jobs will run with the lists parsed from blendcfg.yaml unless they have their own overrides added.

### Passing job-specific parameters in the config

You can run rendering jobs with additional parameters defined in the config file.
To enable them, override the `ParameterSchema(BaseModel)` class in your rendering job and define your parameter types and default values as follows:

```python
  from pydantic import BaseModel
  
  ...
  
  class ParameterSchema(BaseModel):
      """
      Pydantic schema class for optional job parameters.
      Overwrite this in deriving classes to add their own parameters.
      """

      PARAMETER1: bool = True
      PARAMETER2: int = 0
      PARAMETER3: List[str] = ["FOO", "BAR"]
```

Parameters are parsed and converted with use of this schema, so that only the valid ones get passed to the rendering job. Enabled parameters will be printed to console in the rendering job report:

```
[14:24:20] [pcbooth.core.job] (INFO) ### MASKS rendering job
[14:24:20] [pcbooth.core.job] (INFO) 	* enabled rendered object positions: TOP, BOTTOM
[14:24:20] [pcbooth.core.job] (INFO) 	* enabled cameras: FRONT, PHOTO1
[14:24:20] [pcbooth.core.job] (INFO) 	* enabled backgrounds: paper_black
[14:24:20] [pcbooth.core.job] (INFO) 	* enabled parameters: FULL=False, COVERED=True, HIGHLIGHTED=['A', 'J', 'PS', 'T', 'U', 'IC', 'POT']
[14:24:20] [pcbooth.core.job] (INFO) Total renders: 62
```

In the rendering job module code, you can you can access parameters using `self.params.get(<parameter name>)`.

### Using the `RendererWrapper` and `FFmpegWrapper`

`RendererWrapper` and `FFmpegWrapper` are classes handling saving render results and sequencing them into animations. 
`PCBooth` relies on image data buffers stored within them to optimize saving each output in different file formats.

In order to use them, import them from the `renderer` module and create their instances within the `iterate` method:

```python
from pcbooth.modules.renderer import FFmpegWrapper, RendererWrapper

def iterate(self) -> None
  """
  Main loop of the module to be run within execute() method.
  """

  ffmpeg = FFmpegWrapper()
  renderer = RendererWrapper()
  ...
```

#### `RendererWrapper` class

```{eval-rst}
.. autoclass:: renderer.RendererWrapper
  :members: 

```

#### `FFmpegWrapper` class

```{eval-rst}
.. autoclass:: renderer.FFmpegWrapper
  :members: 

```

### Override context managers

Some rendering jobs might require rendering settings, model position or other properties to be temporarily altered from their default state. 
To not interfere with subsequent rendering jobs in the queue, those alterations need to be reversed at the end of the job. 
To help with this, context managers from the `job_utilities` module can be used, for example:

```python
from pcbooth.modules.renderer import (
    RendererWrapper,
    setup_ultralow_cycles,
)
import pcbooth.modules.job_utilities as ju

class MyRenderingJob(pcbooth.core.job.Job):
  """ Custom example rendering job """

  def iterate(self) -> None:
    ...
    with (ju.cycles_override(setup_ultralow_cycles), ju.global_material_override()):
      for camera in self.studio.cameras:
        ...
```

This rendering job will render images using ultralow quality Cycles settings preset and apply global material override for all objects in a scene, then it will restore the settings to the previous state when it's finished.

#### `job_utilities` module

```{eval-rst}
.. automodule:: job_utilities
  :members: 
```


