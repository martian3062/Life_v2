#pragma once
#include "CoreMinimal.h"
#include "ToolsetRegistry/ToolsetDefinition.h"
#include "XenoAuthoringToolset.generated.h"
/** XENO scene authoring. Operates only on the approved local scene file and XENO-owned actors. */
UCLASS()
class UXenoAuthoringToolset : public UToolsetDefinition
{
    GENERATED_BODY()
public:
    /** Read the approved XENO scene CRC and title. No file paths or commands are accepted. */
    UFUNCTION(meta=(AICallable),Category="XenoAuthoring")
    static FString GetApprovedScene();
    /** Build the approved scene in the current editor world. ExpectedCrc must match the validated plan. */
    UFUNCTION(meta=(AICallable),Category="XenoAuthoring")
    static FString BuildApprovedScene(const FString& ExpectedCrc);
};
