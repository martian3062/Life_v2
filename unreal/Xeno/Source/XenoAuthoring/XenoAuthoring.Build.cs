using UnrealBuildTool;
public class XenoAuthoring : ModuleRules
{
    public XenoAuthoring(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "ToolsetRegistry" });
        PrivateDependencyModuleNames.AddRange(new string[] { "UnrealEd", "Xeno", "Json", "JsonUtilities" });
    }
}
