#include "XenoMissionMode.h"
#include "XenoEnvironment.h"
#include "XenoRover.h"
#include "XenoSimulationBridge.h"
#include "XenoSceneSpec.h"
#include "XenoPhysicsField.h"
#include "XenoLivePhysics.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpectatorPawn.h"
#include "InputCoreTypes.h"
#include "TimerManager.h"

AXenoMissionMode::AXenoMissionMode()
{
    PrimaryActorTick.bCanEverTick = true;
    HUDClass = AXenoHUD::StaticClass();
    DefaultPawnClass = ASpectatorPawn::StaticClass();
}

void AXenoMissionMode::BeginPlay()
{
    Super::BeginPlay();
    FXenoSceneSpec::LoadIfChanged();
    Environment = GetWorld()->SpawnActor<AXenoEnvironment>();
    Rover = GetWorld()->SpawnActor<AXenoRover>();
    auto* Live=GetWorld()->SpawnActor<AXenoLivePhysics>();Live->Rover=Rover;
    LivePhysics=Live;
    PhysicsField = GetWorld()->SpawnActor<AXenoPhysicsField>();
    Camera = GetWorld()->SpawnActor<ACameraActor>();
    Camera->GetCameraComponent()->SetFieldOfView(65.0f);
    Camera->GetCameraComponent()->bConstrainAspectRatio = false;
    if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
    {
        PC->SetViewTarget(Camera);
        PC->bShowMouseCursor = true;
        if (PC->GetHUD()) PC->GetHUD()->bShowHUD = FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_CLEAN_VIEW")) != TEXT("1");
        FInputModeGameAndUI InputMode;
        InputMode.SetHideCursorDuringCapture(false);
        PC->SetInputMode(InputMode);
    }
    ApplySceneCamera();
    FXenoSceneSpec::Get().RecordBuilt();
    UpdateCamera(0);
    FTimerHandle StartHandle;
    GetWorld()->GetTimerManager().SetTimer(StartHandle,
        FTimerDelegate::CreateWeakLambda(this, [this]
    {
        GetGameInstance()->GetSubsystem<UXenoSimulationBridge>()->StartMission();
    }), 1.0f, false);
}

void AXenoMissionMode::ApplySceneCamera()
{
    const auto& Spec = FXenoSceneSpec::Get();
    CameraFocus = FVector(350,400,110);
    CameraDistance = Spec.CameraDistance; CameraPitch = Spec.CameraPitch; CameraYaw = Spec.CameraYaw;
    if (FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_CAMERA_VIEW")) == TEXT("Rover"))
    {
        CameraFocus = FVector(600, 100, 70);
        CameraDistance = 1150; CameraPitch = 14; CameraYaw = -55;
    }
}

void AXenoMissionMode::UpdateCamera(float DeltaSeconds)
{
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    if (!PC || !Camera) return;
    if (PC->IsInputKeyDown(EKeys::RightMouseButton))
    {
        float X=0, Y=0; PC->GetInputMouseDelta(X,Y);
        CameraYaw -= X * 0.3f;
        CameraPitch = FMath::Clamp(CameraPitch + Y * 0.2f, 8.0f, 65.0f);
    }
    if (PC->WasInputKeyJustPressed(EKeys::MouseScrollUp)) CameraDistance *= 0.9f;
    if (PC->WasInputKeyJustPressed(EKeys::MouseScrollDown)) CameraDistance *= 1.1f;
    if (PC->IsInputKeyDown(EKeys::A)) CameraYaw -= 30 * DeltaSeconds;
    if (PC->IsInputKeyDown(EKeys::D)) CameraYaw += 30 * DeltaSeconds;
    if (PC->WasInputKeyJustPressed(EKeys::R))
    {
        ApplySceneCamera();
    }
    if (PC->WasInputKeyJustPressed(EKeys::H) && PC->GetHUD()) PC->GetHUD()->bShowHUD = !PC->GetHUD()->bShowHUD;
    if (PC->WasInputKeyJustPressed(EKeys::P) && PhysicsField) PhysicsField->SetActorHiddenInGame(!PhysicsField->IsHidden());
    CameraDistance = FMath::Clamp(CameraDistance, 700.0f, 6000.0f);
    const float Pitch=FMath::DegreesToRadians(CameraPitch), Yaw=FMath::DegreesToRadians(CameraYaw);
    FVector Position=CameraFocus+FVector(FMath::Cos(Yaw)*FMath::Cos(Pitch),
        FMath::Sin(Yaw)*FMath::Cos(Pitch),FMath::Sin(Pitch))*CameraDistance;
    Position.Z=FMath::Max(Position.Z,AXenoEnvironment::HeightAt(Position.X,Position.Y)+100);
    Camera->SetActorLocation(Position);
    Camera->SetActorRotation((CameraFocus-Position).Rotation());
}

void AXenoMissionMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    ScenePoll += DeltaSeconds;
    if (ScenePoll > 1.0f)
    {
        ScenePoll = 0;
        if (FXenoSceneSpec::LoadIfChanged())
        {
            if (Environment) Environment->Destroy();
            Environment = GetWorld()->SpawnActor<AXenoEnvironment>();
            bSitesSpawned = false;
            ApplySceneCamera();
            FXenoSceneSpec::Get().RecordBuilt();
        }
    }
    UpdateCamera(DeltaSeconds);
    UXenoSimulationBridge* Bridge = GetGameInstance()->GetSubsystem<UXenoSimulationBridge>();
    if (!Bridge->LatestObservation.IsValid()) return;
    const auto& Position = Bridge->LatestObservation->GetArrayField(TEXT("position_m"));
    Rover->SetObservedPosition(FVector2D(Position[0]->AsNumber(),Position[1]->AsNumber()));
    if(LivePhysics)LivePhysics->SetTarget(FVector2D(Position[0]->AsNumber(),Position[1]->AsNumber()));
    if (!bSitesSpawned)
    {
        for (const auto& Site : Bridge->LatestObservation->GetArrayField(TEXT("sites")))
        {
            const auto Object=Site->AsObject();
            const auto& XY=Object->GetArrayField(TEXT("position_m"));
            const double Hue=Object->GetObjectField(TEXT("appearance"))->GetNumberField(TEXT("hue"));
            Environment->AddSampleSite(FVector2D(XY[0]->AsNumber()*10000,XY[1]->AsNumber()*10000),Hue);
        }
        bSitesSpawned=true;
    }
}
