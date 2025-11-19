# Quick start

This scenario will use a generated Blender model of the [Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard) as an example.
This guide uses following tool pipeline to prepare the base PCB model:
* [`gerber2blend`](https://github.com/antmicro/gerber2blend)
* [`picknblend`](https://github.com/antmicro/picknblend)

## Clone the board

```bash
git clone https://github.com/antmicro/jetson-orin-baseboard.git
```

## Generate PCB Blender model

Use the [`gerber2blend`](https://github.com/antmicro/gerber2blend) tool to generate a Blender model of the PCB.
Refer to `gerber2blend`'s [Quick start](https://antmicro.github.io/gerber2blend/quickstart.html) guide for detailed instructions.

Then use the [`picknblend`](https://github.com/antmicro/picknblend) tool to populate the PCB model with components.
Refer to `picknblend`'s [Quick start](https://antmicro.github.io/picknblend/quickstart.html) guide for detailed instructions.

## Prepare renders of the PCB

In order to prepare renders of the PCB, run `pcbooth` with `demo` preset:

```bash
pcbooth -c demo
```

This preset yields static image renders on black background using `TOP` and `PHOTO1` camera views and transition animation between the two.  

## Prepare any renders 

`PCBooth` can render any model in .blend format if called with path to the model:

```bash
pcbooth -b path/to/model.blend -c demo
```
