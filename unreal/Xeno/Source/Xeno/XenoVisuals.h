#pragma once

#include "CoreMinimal.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"

// Presentation helpers only. Geometry, lighting and animation do not advance scientific time.
namespace XenoVisuals
{
inline UMaterialInstanceDynamic* Material(UObject* Owner, UMaterialInterface* Base,
    FLinearColor Tint, float Roughness = 0.8f, float Metallic = 0.0f, float Glow = 0.0f)
{
    if (!Base) return nullptr;
    auto* M = UMaterialInstanceDynamic::Create(Base, Owner);
    M->SetVectorParameterValue(TEXT("Tint"), Tint);
    M->SetScalarParameterValue(TEXT("Roughness"), Roughness);
    M->SetScalarParameterValue(TEXT("Metallic"), Metallic);
    M->SetScalarParameterValue(TEXT("Glow"), Glow);
    return M;
}

inline UStaticMeshComponent* Part(AActor* Owner, UStaticMesh* Mesh, UMaterialInterface* Material,
    FVector Position, FVector Scale, FRotator Rotation = FRotator::ZeroRotator)
{
    auto* Component = NewObject<UStaticMeshComponent>(Owner);
    Owner->AddInstanceComponent(Component);
    Component->SetupAttachment(Owner->GetRootComponent());
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetStaticMesh(Mesh);
    Component->SetRelativeLocation(Position);
    Component->SetRelativeScale3D(Scale);
    Component->SetRelativeRotation(Rotation);
    Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if (Material) Component->SetMaterial(0, Material);
    Component->RegisterComponent();
    return Component;
}
}
