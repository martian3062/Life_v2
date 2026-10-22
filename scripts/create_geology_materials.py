"""Editor-only procedural PBR material generation. No external texture dependencies."""

import unreal

edit = unreal.MaterialEditingLibrary


def material(name):
    path = f"/Game/Materials/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        existing = unreal.EditorAssetLibrary.load_asset(path)
        edit.delete_all_material_expressions(existing)
        return existing
    result = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew()
    )
    result.set_editor_property("two_sided", True)
    return result


def node(mat, cls, **props):
    result = edit.create_material_expression(mat, cls)
    for key, value in props.items():
        result.set_editor_property(key, value)
    return result


def connect(source, target, pin, output=""):
    if not edit.connect_material_expressions(source, output, target, pin):
        raise RuntimeError(f"Invalid material connection: {pin}")


def custom(mat, code, inputs):
    custom_inputs = []
    for name in inputs:
        entry = unreal.CustomInput()
        entry.set_editor_property("input_name", name)
        custom_inputs.append(entry)
    return node(
        mat,
        unreal.MaterialExpressionCustom,
        code=code,
        output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3,
        inputs=custom_inputs,
    )


def scalar(mat, name, value):
    return node(
        mat, unreal.MaterialExpressionScalarParameter, parameter_name=name, default_value=value
    )


def vector(mat, name, color):
    return node(
        mat,
        unreal.MaterialExpressionVectorParameter,
        parameter_name=name,
        default_value=unreal.LinearColor(*color, 1),
    )


def finish(mat, name):
    edit.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(f"/Game/Materials/{name}")


thermal = material("M_XenoThermal")
thermal_color = node(thermal, unreal.MaterialExpressionVertexColor)
thermal_rough = node(thermal, unreal.MaterialExpressionConstant, r=0.22)
edit.connect_material_property(thermal_color, "", unreal.MaterialProperty.MP_BASE_COLOR)
edit.connect_material_property(thermal_rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
finish(thermal, "M_XenoThermal")


geology = material("M_XenoGeology")
if geology:
    pos = node(geology, unreal.MaterialExpressionWorldPosition)
    vertex = node(geology, unreal.MaterialExpressionVertexColor)
    tint = vector(geology, "Tint", (1, 1, 1))
    biome = scalar(geology, "Biome", 0)
    detail = scalar(geology, "Detail", 0.9)
    base = custom(
        geology,
        """
struct FGrain {
 float hash(float3 p) { return frac(sin(dot(p,float3(127.1,311.7,74.7)))*43758.5453); }
 float noise(float3 p) {
  float3 i=floor(p),f=frac(p); f=f*f*(3-2*f);
  return lerp(lerp(lerp(hash(i),hash(i+float3(1,0,0)),f.x),
   lerp(hash(i+float3(0,1,0)),hash(i+float3(1,1,0)),f.x),f.y),
   lerp(lerp(hash(i+float3(0,0,1)),hash(i+float3(1,0,1)),f.x),
   lerp(hash(i+float3(0,1,1)),hash(i+float3(1,1,1)),f.x),f.y),f.z);
 }
}; FGrain g;
float coarse=g.noise(P*.012), medium=g.noise(P*.11), fine=g.noise(P*.9);
float stratum=(g.noise(float3(P.x*.002,P.y*.002,P.z*.025))-.5)*.16;
float fracture=pow(saturate(1-abs(sin(P.x*.017+coarse*2))),48);
float pits=pow(saturate(fine),6);
float mineral=.76+coarse*.24+(medium-.5)*.2*Detail+(fine-.5)*.14*Detail;
mineral+=stratum*Detail;
if(Biome>.5 && Biome<1.5) mineral=1.0+medium*.12-fracture*.32*Detail;
if(Biome>1.5) mineral=.8+medium*.3+pits*.4-fracture*.1;
return float3(mineral,mineral,mineral);
""",
        ["P", "Biome", "Detail"],
    )
    connect(pos, base, "P")
    connect(biome, base, "Biome")
    connect(detail, base, "Detail")
    color = node(geology, unreal.MaterialExpressionMultiply)
    connect(vertex, color, "A")
    connect(tint, color, "B")
    final = node(geology, unreal.MaterialExpressionMultiply)
    connect(color, final, "A")
    connect(base, final, "B")
    bump = custom(
        geology,
        """
struct FGrain {
 float hash(float3 p) { return frac(sin(dot(p,float3(127.1,311.7,74.7)))*43758.5453); }
 float noise(float3 p) {
  float3 i=floor(p),f=frac(p); f=f*f*(3-2*f);
  return lerp(lerp(lerp(hash(i),hash(i+float3(1,0,0)),f.x),
   lerp(hash(i+float3(0,1,0)),hash(i+float3(1,1,0)),f.x),f.y),
   lerp(lerp(hash(i+float3(0,0,1)),hash(i+float3(1,0,1)),f.x),
   lerp(hash(i+float3(0,1,1)),hash(i+float3(1,1,1)),f.x),f.y),f.z);
 }
}; FGrain g;
float3 p=P*.21; float n=g.noise(p);
float dx=n-g.noise(p+float3(.7,0,0)),dy=n-g.noise(p+float3(0,.7,0));
float strength=Biome>.5 && Biome<1.5 ? .22 : .55;
return normalize(float3(dx*strength*Detail,dy*strength*Detail,1));

""",
        ["P", "Biome", "Detail"],
    )
    connect(pos, bump, "P")
    connect(biome, bump, "Biome")
    connect(detail, bump, "Detail")
    rough = scalar(geology, "Roughness", 0.9)
    emission = node(geology, unreal.MaterialExpressionMultiply, const_b=0.018)
    connect(final, emission, "A")
    for expression, prop in (
        (final, unreal.MaterialProperty.MP_BASE_COLOR),
        (bump, unreal.MaterialProperty.MP_NORMAL),
        (rough, unreal.MaterialProperty.MP_ROUGHNESS),
        (emission, unreal.MaterialProperty.MP_EMISSIVE_COLOR),
    ):
        edit.connect_material_property(expression, "", prop)
    finish(geology, "M_XenoGeology")

fluid = material("M_XenoFluid")
if fluid:
    pos = node(fluid, unreal.MaterialExpressionWorldPosition)
    time = node(fluid, unreal.MaterialExpressionTime)
    tint = vector(fluid, "Tint", (0.08, 0.45, 0.4))
    ripple = custom(
        fluid,
        """
float a=sin(P.x*.055+P.y*.018+T*.7)*.05;
float b=cos(P.y*.07-P.x*.015+T*.5)*.045;
return normalize(float3(a,b,1));
""",
        ["P", "T"],
    )
    connect(pos, ripple, "P")
    connect(time, ripple, "T")
    glow = scalar(fluid, "Glow", 0.02)
    emission = node(fluid, unreal.MaterialExpressionMultiply)
    connect(tint, emission, "A")
    connect(glow, emission, "B")
    for expression, prop in (
        (tint, unreal.MaterialProperty.MP_BASE_COLOR),
        (ripple, unreal.MaterialProperty.MP_NORMAL),
        (scalar(fluid, "Roughness", 0.14), unreal.MaterialProperty.MP_ROUGHNESS),
        (scalar(fluid, "Metallic", 0.25), unreal.MaterialProperty.MP_METALLIC),
        (emission, unreal.MaterialProperty.MP_EMISSIVE_COLOR),
    ):
        edit.connect_material_property(expression, "", prop)
    finish(fluid, "M_XenoFluid")

sky = material("M_XenoSkyV2")
if sky:
    sky.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    sky.set_editor_property("is_sky", True)
    pos = node(sky, unreal.MaterialExpressionWorldPosition)
    horizon = vector(sky, "Horizon", (0.42, 0.33, 0.23))
    zenith = vector(sky, "Zenith", (0.03, 0.07, 0.12))
    gradient = custom(sky, "return lerp(H,Z,saturate(P.z/16000));", ["P", "H", "Z"])
    connect(pos, gradient, "P")
    connect(horizon, gradient, "H")
    connect(zenith, gradient, "Z")
    edit.connect_material_property(gradient, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(sky, "M_XenoSkyV2")

unreal.log("XENO_GEOLOGY_MATERIALS_CREATED")

reference = material("M_XenoReference")
if reference:
    reference.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    vertex = node(reference, unreal.MaterialExpressionVertexColor)
    edit.connect_material_property(vertex, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(reference, "M_XenoReference")
