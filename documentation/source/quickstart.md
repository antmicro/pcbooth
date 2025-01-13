# Quick start

This scenario will use a generated Blender model of the [Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard) as an example.
This guide uses following tool pipeline to prepare the base PCB model:
* [`gerber2blend`](https://github.com/antmicro/gerber2blend)
* [`picknblend`](https://github.com/antmicro/picknblend)

## Clone the board

```bash
git clone https://github.com/antmicro/jetson-orin-baseboard.git
```

## Clone the 3D model library

```bash
git clone https://github.com/antmicro/hardware-components.git
```

In order for the library to be visible by `picknblend`, specify it in the environment variable `MODEL_LIBRARY_PATHS`:

```bash
export MODEL_LIBRARY_PATHS=path/to/library/directory/hardware-components/
```

Alternatively, you can provide this path in the `blendcfg.yaml` file:

```bash
MODEL_LIBRARY_PATHS:
      - path/to/library/directory/hardware-components/
```

## Generate PCB Blender model

Use the [`gerber2blend`](https://github.com/antmicro/gerber2blend) tool to generate a Blender model of the PCB:

```bash
cd jetson-orin-baseboard
gerber2blend
```

Refer to `gerber2blend`'s [Quick start](https://antmicro.github.io/gerber2blend/quickstart.html) guide for detailed instructions.

## Populate generated model with components from 3D model library

Use the [`picknblend`](https://github.com/antmicro/antmicro-picknblend) tool to populate the PCB model with components:

```bash
picknblend
```

Refer to `picknblend`'s [Quick start](https://antmicro.github.io/picknblend/quickstart.html) guide for detailed instructions.

## Prepare renders of the PCB

In order to prepare renders of the PCB, run:

```bash
pcbooth
```

To preview the generated `.blend` file with populated components, open it with an instance of Blender in version >=4.1.

## Prepare any renders 

`PCBooth` can render any model in .blend format if called with path to the model:

```bash
pcbooth -b path/to/model.blend
```