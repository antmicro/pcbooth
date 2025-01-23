# Introduction

`PCBooth` is a tool created to automate Blender scene and renderer setup and rendering of static images and videos aiding PCB-related model visualization. 

This tool works in conjunction with [gerber2blend](https://antmicro.github.io/gerber2blend/) and [picknblend](https://antmicro.github.io/picknblend/), enabling creation of Blender PCB models populated with electrical and mechanical components.
`PCBooth` can work with any model in .blend format, but it was written with using Blender outputs from the `gerber2blend` and `picknblend` pipeline in mind.
The tool is compatible with designs created using a variety of EDA (Electronic Design Automation) software.

* [Installation](install.md) describes the installation process.
* [Quick start](quickstart.md) presents a simple example of script usage based on Antmicro's open source [Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard).
* [Usage](usage.md) describes basic usage and features of the tool.
* [Configuring blendcfg.yaml](blendcfg.md) presents configuration options available for customizing the processing workflow.
