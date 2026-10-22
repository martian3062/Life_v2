"""Register only the project-scoped editor authoring toolset at editor startup."""

import unreal

if unreal.ToolsetRegistry.is_available():
    unreal.ToolsetRegistry.register_toolset_class(unreal.XenoAuthoringToolset)
    unreal.log("XENO_APPROVED_AUTHORING_REGISTERED")
