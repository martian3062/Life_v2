using UnrealBuildTool;

public class Xeno : ModuleRules
{
    public Xeno(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicIncludePaths.Add(ModuleDirectory);
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "InputCore", "HTTP", "Json", "JsonUtilities", "WebSockets", "ProceduralMeshComponent"
        });
    }
}
