#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Interfaces/IHttpRequest.h"
#include "XenoSimulationBridge.generated.h"

class IWebSocket;
class FJsonObject;

UCLASS()
class XENO_API UXenoSimulationBridge : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    void StartMission();
    FString Status = TEXT("Waiting for external service");
    FString LastAction;
    FString LastError;
    TSharedPtr<FJsonObject> LatestObservation;
    TSharedPtr<FJsonObject> LatestExperiment;
    int32 StreamEventCount = 0;
    int32 StateRevision = 0;
    bool bMissionComplete = false;
    bool bConnected = false;
private:
    FString BaseUrl, EpisodeId, Token, ResultPath;
    FString SiteId, SampleId, ControlId, TreatmentId;
    FString PendingPayload, OriginalCollectResult;
    TArray<FString> EvidenceIds;
    TSharedPtr<IWebSocket> Socket;
    FTimerHandle TimeoutHandle, FinishHandle, ActionHandle, ScreenshotHandle;
    double StartWallTime = 0;
    int32 Stage = 0;
    int32 LastStreamSequence = -1;
    bool bStarted = false, bAutoRun = false, bSmoke = false;
    bool bHealthVerified = false, bDuplicateVerified = false, bFinished = false;
    bool bSocketConnected = false;

    using FReply = TFunction<void(TSharedPtr<FJsonObject>, const FString&)>;
    void Request(const FString& Verb, const FString& Path, const FString& Payload, FReply Reply);
    void ConnectStream();
    void ApplyObservation(TSharedPtr<FJsonObject> Object);
    void AdvanceMission();
    void ScheduleNext();
    void SendAction(const FString& Type, TSharedPtr<FJsonObject> Parameters);
    void PollFinish();
    void Finish(bool bSuccess, const FString& Error = FString());
};
