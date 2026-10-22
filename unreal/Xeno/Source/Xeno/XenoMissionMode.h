#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "XenoMissionMode.generated.h"
class AXenoLivePhysics;

class AXenoEnvironment;
class AXenoRover;
class ACameraActor;
class AXenoPhysicsField;

UCLASS()
class XENO_API AXenoHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};

UCLASS()
class XENO_API AXenoMissionMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AXenoMissionMode();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
private:
    UPROPERTY() TObjectPtr<AXenoLivePhysics> LivePhysics;
    UPROPERTY() TObjectPtr<AXenoEnvironment> Environment;
    UPROPERTY() TObjectPtr<AXenoRover> Rover;
    UPROPERTY() TObjectPtr<ACameraActor> Camera;
    UPROPERTY() TObjectPtr<AXenoPhysicsField> PhysicsField;
    bool bSitesSpawned = false;
    float CameraYaw = -65.0f, CameraPitch = 12.0f, CameraDistance = 2450.0f;
    FVector CameraFocus = FVector(350, 400, 90);
    float ScenePoll = 0;
    void UpdateCamera(float DeltaSeconds);
    void ApplySceneCamera();
};
