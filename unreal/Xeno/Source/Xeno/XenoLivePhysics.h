#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "XenoLivePhysics.generated.h"
class AXenoRover;
class UProceduralMeshComponent;
class UTextRenderComponent;
UCLASS()
class XENO_API AXenoLivePhysics : public AActor
{
    GENERATED_BODY()
public:
    AXenoLivePhysics();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    void SetTarget(FVector2D ScientificPosition);
    UPROPERTY() TObjectPtr<AXenoRover> Rover;
    static bool bLive;
    static int32 LiveFrame;
private:
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Surface;
    UPROPERTY() TObjectPtr<UTextRenderComponent> Label;
    FString Directory;
    float Poll=0;
    uint32 TerrainCrc=MAX_uint32;
    int32 Frame=-1;
    int32 RenderFrames=0;
    float RenderSeconds=0,LastPoseTime=0;
    FVector2D Target=FVector2D::ZeroVector;
    TArray<FVector> Vertices, Normals;
    TArray<FVector2D> UV;
    void ExportTerrain();
};
