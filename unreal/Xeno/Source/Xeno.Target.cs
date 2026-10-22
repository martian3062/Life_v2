using UnrealBuildTool;
using System.Collections.Generic;

public class XenoTarget : TargetRules
{
    public XenoTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("Xeno");
    }
}
