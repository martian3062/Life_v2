#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "XenoRover.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class FJsonValue;

UCLASS()
class XENO_API AXenoRover : public AActor
{
    GENERATED_BODY()
public:
    AXenoRover();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    void SetObservedPosition(FVector2D Position);
    void SetPhysicsPose(FVector Position,FQuat Rotation,const TArray<TSharedPtr<FJsonValue>>& Travel);
    void DisablePhysicsPose() { bPhysicsPose=false; }
private:
    UPROPERTY() TObjectPtr<UStaticMesh> Cube;
    UPROPERTY() TObjectPtr<UStaticMesh> Cylinder;
    UPROPERTY() TObjectPtr<UStaticMesh> Sphere;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Wheels;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> Beacon;
    FVector Destination = FVector::ZeroVector;
    bool bPhysicsPose=false;
    FVector PhysicsPosition=FVector::ZeroVector;
    FQuat PhysicsRotation=FQuat::Identity;
};
