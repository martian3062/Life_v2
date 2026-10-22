using UnrealBuildTool;
using System.Collections.Generic;

public class XenoEditorTarget : TargetRules
{
    public XenoEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("Xeno");
        ExtraModuleNames.Add("XenoAuthoring");
    }
}
