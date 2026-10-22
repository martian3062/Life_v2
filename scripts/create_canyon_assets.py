"""Unreal Editor-only import, Nanite build and scanned PBR material setup."""

import hashlib
import json
from pathlib import Path

import unreal

root = Path(__file__).resolve().parents[1] / "runs/assets"
tools = unreal.AssetToolsHelpers.get_asset_tools()
edit = unreal.MaterialEditingLibrary
unreal.EditorAssetLibrary.make_directory("/Game/Canyon")


def imported(path, name):
    asset_path = f"/Game/Canyon/{name}"
    digest = hashlib.sha256((root / path).read_bytes()).hexdigest()
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        existing = unreal.EditorAssetLibrary.load_asset(asset_path)
        if (
            not path.endswith((".obj", ".fbx"))
            or unreal.EditorAssetLibrary.get_metadata_tag(existing, "XenoSourceHash") == digest
        ):
            return existing
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(root / path))
    task.set_editor_property("destination_path", "/Game/Canyon")
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    if path.endswith((".obj", ".fbx")):
        options = unreal.FbxImportUI()
        options.set_editor_property("import_materials", False)
        options.set_editor_property("import_textures", False)
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
        options.static_mesh_import_data.set_editor_property("convert_scene", path.endswith(".fbx"))
        options.static_mesh_import_data.set_editor_property("combine_meshes", True)
        task.set_editor_property("options", options)
        task.set_editor_property("factory", unreal.FbxFactory())
    tools.import_asset_tasks([task])
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        raise RuntimeError(f"Import failed: {asset_path}")
    unreal.EditorAssetLibrary.set_metadata_tag(asset, "XenoSourceHash", digest)
    return asset


def pbr(name, prefix, tint, ground=False):
    path = f"/Game/Canyon/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mat = unreal.EditorAssetLibrary.load_asset(path)
        edit.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(name, "/Game/Canyon", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("two_sided", prefix.startswith("Scan"))
    samples = {}
    coordinates = None
    if ground:
        position = edit.create_material_expression(mat, unreal.MaterialExpressionWorldPosition)
        mask = edit.create_material_expression(mat, unreal.MaterialExpressionComponentMask)
        mask.set_editor_property("r", True)
        mask.set_editor_property("g", True)
        mask.set_editor_property("b", False)
        coordinates = edit.create_material_expression(mat, unreal.MaterialExpressionMultiply)
        coordinates.set_editor_property("const_b", 0.002)
        edit.connect_material_expressions(position, "", mask, "")
        edit.connect_material_expressions(mask, "", coordinates, "A")
    filenames = {
        "Cliff": [
            "Rock030_2K-JPG_Color.jpg",
            "Rock030_2K-JPG_NormalDX.jpg",
            "Rock030_2K-JPG_Roughness.jpg",
        ],
        "Rock": [
            "rock_boulder_dry_diff_2k.jpg",
            "rock_boulder_dry_nor_dx_2k.jpg",
            "rock_boulder_dry_rough_2k.jpg",
        ],
    }
    for index in range(2):
        base = f"namaqualand_cliff_0{index + 1}"
        filenames[f"Scan{index}"] = [
            f"{base}_diff_2k.jpg",
            f"{base}_nor_dx_2k.jpg",
            f"{base}_rough_2k.jpg",
        ]
    for kind, file in zip(["Color", "Normal", "Roughness"], filenames[prefix], strict=True):
        texture = imported(file, f"T_Canyon{prefix}{kind}")
        if kind != "Color":
            texture.set_editor_property("srgb", False)
        if kind == "Normal":
            texture.set_editor_property(
                "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP
            )
        unreal.EditorAssetLibrary.save_loaded_asset(texture)
        sample = edit.create_material_expression(mat, unreal.MaterialExpressionTextureSample)
        sample.set_editor_property("texture", texture)
        sample.set_editor_property(
            "sampler_type",
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
            if kind == "Normal"
            else (
                unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
                if kind == "Color"
                else unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
            ),
        )
        samples[kind] = sample
        if coordinates:
            edit.connect_material_expressions(coordinates, "", sample, "UVs")
    color = edit.create_material_expression(mat, unreal.MaterialExpressionVectorParameter)
    color.set_editor_property("parameter_name", "Tint")
    color.set_editor_property("default_value", unreal.LinearColor(*tint, 1))
    multiply = edit.create_material_expression(mat, unreal.MaterialExpressionMultiply)
    edit.connect_material_expressions(samples["Color"], "RGB", multiply, "A")
    edit.connect_material_expressions(color, "", multiply, "B")
    if ground:
        vertex = edit.create_material_expression(mat, unreal.MaterialExpressionVertexColor)
        blend = edit.create_material_expression(mat, unreal.MaterialExpressionMultiply)
        edit.connect_material_expressions(multiply, "", blend, "A")
        edit.connect_material_expressions(vertex, "", blend, "B")
        edit.connect_material_property(blend, "", unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        edit.connect_material_property(multiply, "", unreal.MaterialProperty.MP_BASE_COLOR)
    edit.connect_material_property(samples["Normal"], "RGB", unreal.MaterialProperty.MP_NORMAL)
    edit.connect_material_property(samples["Roughness"], "R", unreal.MaterialProperty.MP_ROUGHNESS)
    edit.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


cliff_mat = pbr("M_CanyonCliff", "Cliff", (0.95, 0.66, 0.4))
rock_mat = pbr("M_CanyonRock", "Rock", (0.63, 0.47, 0.32))
pbr("M_CanyonGround", "Rock", (1, 1, 1), ground=True)
report = []
for kind, mat in [("Cliff", cliff_mat), ("Rock", rock_mat)]:
    for i in range(4):
        name = f"SM_Canyon{kind}{i}"
        asset = imported(f"{name}.obj", name)
        asset.set_material(0, mat)
        settings = asset.get_editor_property("nanite_settings")
        settings.set_editor_property("enabled", True)
        asset.set_editor_property("nanite_settings", settings)
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
        bounds = asset.get_bounds()
        report.append(
            {
                "asset": asset.get_path_name(),
                "nanite": settings.enabled,
                "extent_cm": [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z],
            }
        )
for index in range(2):
    mat = pbr(f"M_CanyonScan{index}", f"Scan{index}", (1, 0.9, 0.8))
    name = f"SM_CanyonScan{index}"
    asset = imported(f"namaqualand_cliff_0{index + 1}_2k.fbx", name)
    asset.set_material(0, mat)
    settings = asset.get_editor_property("nanite_settings")
    settings.set_editor_property("enabled", True)
    asset.set_editor_property("nanite_settings", settings)
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    bounds = asset.get_bounds()
    report.append(
        {
            "asset": asset.get_path_name(),
            "nanite": True,
            "extent_cm": [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z],
            "origin_cm": [bounds.origin.x, bounds.origin.y, bounds.origin.z],
        }
    )
(root / "unreal-import-report.json").write_text(json.dumps(report, indent=2))
unreal.log("XENO_CANYON_ASSETS_READY 2 CC0 cliff scans + 8 generated variants / Nanite / 2K PBR")
