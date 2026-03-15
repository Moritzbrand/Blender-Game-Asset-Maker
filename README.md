# Blender Game Asset Maker

Blender Game Asset Maker is a Blender add-on for turning selected objects into game-ready assets. It helps with mesh cleanup, optional UV generation, texture baking, material preview, LOD export, and final file export.

## Features
- Build a final game asset from selected source objects
- Optional UV unwrap and auto smooth shading
- Bake textures such as base color, normals, AO, roughness, metallic, emission, and SSS
- Optional mesh optimization steps like merge by distance, planar cleanup, collapse decimation, and triangulation
- Export the finished asset and optional LODs

## Requirements
- Blender 5.0 or newer

## Installation
1. Download this repository as a ZIP
2. In Blender, open **Edit → Preferences → Add-ons**
3. Click **Install from Disk** and select the ZIP file
4. Enable **Game Asset Maker**

## Usage
1. Select one or more source objects in the 3D View
2. Open **View3D → Sidebar → Game Asset Maker**
3. Adjust the settings you need
4. Click **Create Game Asset**
5. Preview the result in Blender and export it if needed

## Project Structure
- `__init__.py` - add-on registration and Blender metadata
- `panel.py` - UI panels in the Blender sidebar
- `properties.py` and `addon_properties/` - scene properties and settings
- `addon_operators/` - main workflow operators and services
- `scripts/` - helper modules for meshes, materials, UVs, baking, exporting, and progress handling

## Notes
- The add-on duplicates and prepares source objects before creating the final game asset
- Baking and Selected to Active workflows can use different internal paths
- Some options are meant for speed, others for higher quality
