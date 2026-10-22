#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "XenoEnvironment.generated.h"

class UStaticMesh;
class UMaterialInterface;
class UProceduralMeshComponent;

UCLASS()
class XENO_API AXenoEnvironment : public AActor
{
    GENERATED_BODY()
public:
    AXenoEnvironment();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Destroyed() override;
    static float HeightAt(float X, float Y);
    void AddSampleSite(FVector2D Position, float AppearanceHue);
    void BuildPreview();
private:
    UPROPERTY() TObjectPtr<UStaticMesh> Cube;
    UPROPERTY() TObjectPtr<UStaticMesh> Sphere;
    UPROPERTY() TObjectPtr<UStaticMesh> Cylinder;
    UPROPERTY() TObjectPtr<UStaticMesh> Cone;
    UPROPERTY() TObjectPtr<UMaterialInterface> Lit;
    UPROPERTY() TObjectPtr<UMaterialInterface> TerrainMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> SkyMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> FluidMaterial;
    UPROPERTY() TArray<TObjectPtr<AActor>> LightingActors;
    void BuildTerrain();
    void BuildLighting();
    void BuildStation();
    void BuildGeology();
    void BuildWall();
    void ScatterPebbles();
    void Pool(FVector2D Center, float RadiusX, float RadiusY, float Level);
    void Column(FVector Position, float Radius, float Height, int32 Seed);
    void Rock(FVector Position, FVector Scale, int32 Seed, FLinearColor Tint);
    void Ring(FVector2D Position, float Radius, FLinearColor Color);
};
