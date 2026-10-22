"""Run inside Unreal Editor Python, not the scientific runtime."""

import runpy
from pathlib import Path

import unreal

unreal.EditorAssetLibrary.make_directory("/Game/Materials")
unreal.EditorAssetLibrary.make_directory("/Game/Maps")


def material_asset(name):
    path = f"/Game/Materials/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return None
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew()
    )
    material.set_editor_property("two_sided", True)
    return material


def node(material, cls, **properties):
    result = unreal.MaterialEditingLibrary.create_material_expression(material, cls)
    for key, value in properties.items():
        result.set_editor_property(key, value)
    return result


def link(source, target, pin, output=""):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(source, output, target, pin):
        raise RuntimeError(f"Material connection failed: {pin}")


def finish(material, name):
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(f"/Game/Materials/{name}")


lit = material_asset("M_XenoLit")
if lit:
    tint = node(
        lit,
        unreal.MaterialExpressionVectorParameter,
        parameter_name="Tint",
        default_value=unreal.LinearColor(0.5, 0.5, 0.5, 1),
    )
    roughness = node(
        lit, unreal.MaterialExpressionScalarParameter, parameter_name="Roughness", default_value=0.8
    )
    metallic = node(
        lit, unreal.MaterialExpressionScalarParameter, parameter_name="Metallic", default_value=0.0
    )
    glow = node(
        lit, unreal.MaterialExpressionScalarParameter, parameter_name="Glow", default_value=0.0
    )
    emission = node(lit, unreal.MaterialExpressionMultiply)
    link(tint, emission, "A")
    link(glow, emission, "B")
    for expression, prop in (
        (tint, unreal.MaterialProperty.MP_BASE_COLOR),
        (roughness, unreal.MaterialProperty.MP_ROUGHNESS),
        (metallic, unreal.MaterialProperty.MP_METALLIC),
        (emission, unreal.MaterialProperty.MP_EMISSIVE_COLOR),
    ):
        unreal.MaterialEditingLibrary.connect_material_property(expression, "", prop)
    finish(lit, "M_XenoLit")

ground = material_asset("M_XenoTerrain")
if ground:
    color = node(ground, unreal.MaterialExpressionVertexColor)
    noise = node(
        ground,
        unreal.MaterialExpressionNoise,
        scale=0.025,
        quality=1,
        levels=2,
        output_min=0.65,
        output_max=1.0,
    )
    detail = node(ground, unreal.MaterialExpressionMultiply)
    link(color, detail, "A")
    link(noise, detail, "B")
    roughness = node(ground, unreal.MaterialExpressionConstant, r=0.95)
    emission = node(ground, unreal.MaterialExpressionMultiply, const_b=0.025)
    link(detail, emission, "A")
    for expression, prop in (
        (detail, unreal.MaterialProperty.MP_BASE_COLOR),
        (roughness, unreal.MaterialProperty.MP_ROUGHNESS),
        (emission, unreal.MaterialProperty.MP_EMISSIVE_COLOR),
    ):
        unreal.MaterialEditingLibrary.connect_material_property(expression, "", prop)
    finish(ground, "M_XenoTerrain")

sky = material_asset("M_XenoSky")
if sky:
    sky.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    position = node(sky, unreal.MaterialExpressionWorldPosition)
    height = node(sky, unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False)
    scale = node(sky, unreal.MaterialExpressionDivide, const_b=18000.0)
    clamp = node(sky, unreal.MaterialExpressionSaturate)
    horizon = node(
        sky,
        unreal.MaterialExpressionConstant3Vector,
        constant=unreal.LinearColor(0.33, 0.20, 0.14, 1),
    )
    zenith = node(
        sky,
        unreal.MaterialExpressionConstant3Vector,
        constant=unreal.LinearColor(0.025, 0.055, 0.085, 1),
    )
    gradient = node(sky, unreal.MaterialExpressionLinearInterpolate)
    link(position, height, "")
    link(height, scale, "A")
    link(scale, clamp, "")
    link(horizon, gradient, "A")
    link(zenith, gradient, "B")
    link(clamp, gradient, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_property(
        gradient, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    finish(sky, "M_XenoSky")

material_path = "/Game/Materials/M_XenoSurface"
if not unreal.EditorAssetLibrary.does_asset_exist(material_path):
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_XenoSurface", "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew()
    )
    tint = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -250, 0
    )
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", unreal.LinearColor(0.1, 0.4, 0.5, 1))
    unreal.MaterialEditingLibrary.connect_material_property(
        tint, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        tint, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(material_path)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist("/Game/Maps/XenoMission"):
    if not levels.new_level("/Game/Maps/XenoMission"):
        raise RuntimeError("Could not create XenoMission map")
    levels.save_current_level()
unreal.log("XENO_ASSETS_CREATED")
runpy.run_path(str(Path(__file__).with_name("create_geology_materials.py")))
runpy.run_path(str(Path(__file__).with_name("create_canyon_assets.py")))
