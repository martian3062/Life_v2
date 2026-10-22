#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "XenoPhysicsField.generated.h"

class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class XENO_API AXenoPhysicsField : public AActor
{
    GENERATED_BODY()
public:
    AXenoPhysicsField();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    static bool bReferenceLoaded;
    static FString ReferenceDataset;
private:
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Surface;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Arrows;
    UPROPERTY() TObjectPtr<UTextRenderComponent> Label;
    TArray<TArray<float>> Density, Velocity;
    TArray<float> Times;
    TArray<FVector> Vertices, Normals;
    TArray<FVector2D> UV;
    int32 NX=0, NY=0, Frame=-1;
    float Elapsed=0, Poll=0;
    void UpdateField(int32 Index);
};
