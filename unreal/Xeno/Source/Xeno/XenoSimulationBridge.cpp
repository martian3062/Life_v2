#include "XenoSimulationBridge.h"
#include "XenoSceneSpec.h"
#include "XenoPhysicsField.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/PlatformProperties.h"
#include "HAL/PlatformMisc.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "IWebSocket.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "TimerManager.h"
#include "WebSocketsModule.h"
#include "UnrealClient.h"

namespace
{
FString JsonString(const TSharedPtr<FJsonObject>& Object)
{
    FString Out;
    FJsonSerializer::Serialize(Object.ToSharedRef(), TJsonWriterFactory<>::Create(&Out));
    return Out;
}
TSharedPtr<FJsonObject> ParseJson(const FString& Text)
{
    TSharedPtr<FJsonObject> Out;
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Out);
    return Out;
}
}

void UXenoSimulationBridge::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bSmoke = FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_SMOKE")) == TEXT("1");
    bAutoRun = FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_AUTORUN")) == TEXT("1");
}

void UXenoSimulationBridge::Deinitialize()
{
    if (Socket)
    {
        Socket->OnConnected().Clear();
        Socket->OnMessage().Clear();
        Socket->OnConnectionError().Clear();
        Socket->OnClosed().Clear();
        Socket->Close();
        Socket.Reset();
    }
    if (GetWorld())
    {
        GetWorld()->GetTimerManager().ClearTimer(TimeoutHandle);
        GetWorld()->GetTimerManager().ClearTimer(FinishHandle);
        GetWorld()->GetTimerManager().ClearTimer(ActionHandle);
        GetWorld()->GetTimerManager().ClearTimer(ScreenshotHandle);
    }
    Token.Empty();
    Super::Deinitialize();
}

void UXenoSimulationBridge::Request(const FString& Verb, const FString& Path,
                                    const FString& Payload, FReply Reply)
{
    if (bFinished) return;
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Http = FHttpModule::Get().CreateRequest();
    Http->SetURL(BaseUrl + Path);
    Http->SetVerb(Verb);
    Http->SetHeader(TEXT("Authorization"), TEXT("Bearer ") + Token);
    Http->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Http->SetTimeout(15.0f);
    if (!Payload.IsEmpty()) Http->SetContentAsString(Payload);
    Http->OnProcessRequestComplete().BindWeakLambda(this,
        [this, Reply = MoveTemp(Reply)](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
        {
            if (bFinished) return;
            if (!bOk || !Response.IsValid())
            {
                // No new action is issued after a timeout: the original ID remains queryable.
                Finish(false, TEXT("HTTP transport failed; retain original action ID for recovery"));
                return;
            }
            if (Response->GetResponseCode() < 200 || Response->GetResponseCode() >= 300)
            {
                Finish(false, FString::Printf(TEXT("HTTP request rejected (%d)"), Response->GetResponseCode()));
                return;
            }
            const FString Text = Response->GetContentAsString();
            TSharedPtr<FJsonObject> Object = ParseJson(Text);
            if (!Object.IsValid()) { Finish(false, TEXT("Invalid service JSON")); return; }
            Reply(Object, Text);
        });
    if (!Http->ProcessRequest()) Finish(false, TEXT("HTTP request could not start"));
}

void UXenoSimulationBridge::StartMission()
{
    if (bStarted) return;
    bStarted = true;
    StartWallTime = FPlatformTime::Seconds();
    FString SessionText;
    const FString SessionFile = FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_SESSION_FILE"));
    if (SessionFile.IsEmpty() || !FFileHelper::LoadFileToString(SessionText, *SessionFile))
    {
        Finish(false, TEXT("Launch with scripts/Run-XenoUnreal.ps1 to supply a scoped session"));
        return;
    }
    TSharedPtr<FJsonObject> Session = ParseJson(SessionText);
    if (!Session.IsValid() || !Session->TryGetStringField(TEXT("base_url"), BaseUrl)
        || !Session->TryGetStringField(TEXT("episode_id"), EpisodeId)
        || !Session->TryGetStringField(TEXT("investigator_token"), Token)
        || !Session->TryGetStringField(TEXT("result_path"), ResultPath))
    {
        Finish(false, TEXT("Invalid local runtime session")); return;
    }
    if (BaseUrl != TEXT("http://127.0.0.1:8766"))
    {
        Finish(false, TEXT("This local prototype permits only the configured loopback service")); return;
    }
    Status = TEXT("Checking XENO service");
    GetWorld()->GetTimerManager().SetTimer(TimeoutHandle,
        FTimerDelegate::CreateWeakLambda(this, [this] { Finish(false, TEXT("Mission timeout")); }),
        90.0f, false);
    Request(TEXT("GET"), TEXT("/health"), TEXT(""), [this](TSharedPtr<FJsonObject> Health, const FString&)
    {
        FString Model;
        if (!Health->TryGetStringField(TEXT("model_version"), Model) || Model != TEXT("f0-maintenance-2"))
        { Finish(false, TEXT("Model version handshake failed")); return; }
        bHealthVerified = true;
        Request(TEXT("GET"), TEXT("/v1/episodes/") + EpisodeId + TEXT("/observation"), TEXT(""),
            [this](TSharedPtr<FJsonObject> Obs, const FString&)
        {
            ApplyObservation(Obs);
            const TArray<TSharedPtr<FJsonValue>>* Sites = nullptr;
            if (!Obs->TryGetArrayField(TEXT("sites"), Sites) || Sites->Num() < 2)
            { Finish(false, TEXT("No mission sites supplied")); return; }
            SiteId = (*Sites)[1]->AsObject()->GetStringField(TEXT("site_id"));
            ConnectStream();
        });
    });
}

void UXenoSimulationBridge::ApplyObservation(TSharedPtr<FJsonObject> Object)
{
    FString Schema;
    if (!Object.IsValid() || !Object->TryGetStringField(TEXT("schema_version"), Schema) || Schema != TEXT("1.0"))
    { Finish(false, TEXT("Observation schema mismatch")); return; }
    const int32 Revision = static_cast<int32>(Object->GetNumberField(TEXT("state_revision")));
    if (Revision >= StateRevision)
    {
        LatestObservation = Object;
        StateRevision = Revision;
    }
}

void UXenoSimulationBridge::ConnectStream()
{
    FString WsBase = BaseUrl.Replace(TEXT("http://"), TEXT("ws://"));
    TMap<FString, FString> Headers;
    Headers.Add(TEXT("Authorization"), TEXT("Bearer ") + Token);
    Socket = FWebSocketsModule::Get().CreateWebSocket(
        WsBase + TEXT("/v1/episodes/") + EpisodeId + TEXT("/stream"), FString(), Headers);
    Socket->OnConnected().AddWeakLambda(this, [this]
    {
        bSocketConnected = bConnected = true;
        Status = TEXT("Connected: investigating synthetic sample");
        if (bAutoRun || bSmoke) AdvanceMission();
    });
    Socket->OnConnectionError().AddWeakLambda(this, [this](const FString&)
    { Finish(false, TEXT("WebSocket connection failed")); });
    Socket->OnClosed().AddWeakLambda(this, [this](int32, const FString&, bool)
    { if (!bFinished) Finish(false, TEXT("WebSocket closed before mission completion")); });
    Socket->OnMessage().AddWeakLambda(this, [this](const FString& Message)
    {
        TSharedPtr<FJsonObject> Envelope = ParseJson(Message);
        if (!Envelope.IsValid() || Envelope->GetStringField(TEXT("type")) != TEXT("observation")) return;
        TSharedPtr<FJsonObject> Obs = Envelope->GetObjectField(TEXT("observation"));
        const int32 Sequence = static_cast<int32>(Obs->GetNumberField(TEXT("event_sequence")));
        UE_LOG(LogTemp, Display, TEXT("XENO_STREAM sequence=%d previous=%d"), Sequence, LastStreamSequence);
        if (Sequence <= LastStreamSequence) return;
        if (Sequence != LastStreamSequence + 1)
        {
            // Request a replay from the last accepted event. Do not advance across gaps.
            Socket->Send(FString::Printf(TEXT("{\"type\":\"resync\",\"after\":%d}"), LastStreamSequence));
            return;
        }
        LastStreamSequence = Sequence;
        ++StreamEventCount;
        ApplyObservation(Obs);
    });
    Socket->Connect();
}

void UXenoSimulationBridge::SendAction(const FString& Type, TSharedPtr<FJsonObject> Parameters)
{
    LastAction = Type;
    TSharedPtr<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("schema_version"), TEXT("1.0"));
    Body->SetStringField(TEXT("episode_id"), EpisodeId);
    Body->SetStringField(TEXT("action_id"), FGuid::NewGuid().ToString(EGuidFormats::Digits));
    Body->SetNumberField(TEXT("expected_state_revision"), StateRevision);
    Body->SetStringField(TEXT("action_type"), Type);
    Body->SetObjectField(TEXT("parameters"), Parameters);
    PendingPayload = JsonString(Body);
    Request(TEXT("POST"), TEXT("/v1/episodes/") + EpisodeId + TEXT("/actions"), PendingPayload,
        [this, Type](TSharedPtr<FJsonObject> Response, const FString& Raw)
    {
        TSharedPtr<FJsonObject> Obs = Response->GetObjectField(TEXT("observation"));
        ApplyObservation(Obs);
        TSharedPtr<FJsonObject> Result = Obs->GetObjectField(TEXT("result"));
        if (Type == TEXT("run_intervention")) LatestExperiment = Result;
        if (Type == TEXT("observe_site") || Type == TEXT("run_intervention"))
            EvidenceIds.Add(Obs->GetStringField(TEXT("observation_id")));
        if (Type == TEXT("collect_sample"))
        {
            SampleId = Result->GetStringField(TEXT("sample_id"));
            OriginalCollectResult = Raw;
            // Repeat the identical payload; a second collection must not occur.
            Request(TEXT("POST"), TEXT("/v1/episodes/") + EpisodeId + TEXT("/actions"), PendingPayload,
                [this](TSharedPtr<FJsonObject>, const FString& Duplicate)
            {
                const auto First = ParseJson(OriginalCollectResult);
                const auto Second = ParseJson(Duplicate);
                if (!First.IsValid() || !Second.IsValid() || !FJsonValue::CompareEqual(
                    FJsonValueObject(First), FJsonValueObject(Second)))
                { Finish(false, TEXT("Idempotent collection returned a different result")); return; }
                bDuplicateVerified = true;
                ++Stage;
                ScheduleNext();
            });
            return;
        }
        if (Type == TEXT("split_sample"))
        {
            ControlId = Result->GetStringField(TEXT("control_id"));
            TreatmentId = Result->GetStringField(TEXT("treatment_id"));
        }
        ++Stage;
        ScheduleNext();
    });
}

void UXenoSimulationBridge::ScheduleNext()
{
    if (bSmoke) AdvanceMission();
    else GetWorld()->GetTimerManager().SetTimer(ActionHandle, this,
        &UXenoSimulationBridge::AdvanceMission, 1.2f, false);
}

void UXenoSimulationBridge::AdvanceMission()
{
    if (bFinished) return;
    TSharedPtr<FJsonObject> P = MakeShared<FJsonObject>();
    switch (Stage)
    {
    case 0:
        P->SetStringField(TEXT("site_id"), SiteId); SendAction(TEXT("move"), P); break;
    case 1:
        P->SetStringField(TEXT("site_id"), SiteId); SendAction(TEXT("observe_site"), P); break;
    case 2:
        P->SetStringField(TEXT("site_id"), SiteId); P->SetNumberField(TEXT("volume_m3"), 2e-7);
        SendAction(TEXT("collect_sample"), P); break;
    case 3:
        P->SetStringField(TEXT("sample_id"), SampleId); SendAction(TEXT("split_sample"), P); break;
    case 4:
        P->SetStringField(TEXT("control_id"), ControlId);
        P->SetStringField(TEXT("treatment_id"), TreatmentId);
        P->SetStringField(TEXT("intervention"), TEXT("temperature_shift"));
        P->SetNumberField(TEXT("duration_s"), 60); SendAction(TEXT("run_intervention"), P); break;
    case 5:
    {
        P->SetStringField(TEXT("outcome"), TEXT("inconclusive"));
        P->SetNumberField(TEXT("target_score"), 0.5);
        TArray<TSharedPtr<FJsonValue>> Ids;
        for (const FString& Id : EvidenceIds) Ids.Add(MakeShared<FJsonValueString>(Id));
        P->SetArrayField(TEXT("evidence_ids"), Ids);
        P->SetStringField(TEXT("interpretation"), TEXT("Unreal runtime completed a controlled experiment. Transport smoke test only."));
        P->SetArrayField(TEXT("alternatives"), {MakeShared<FJsonValueString>(TEXT("Unknown mechanism"))});
        P->SetArrayField(TEXT("limitations"), {MakeShared<FJsonValueString>(TEXT("Synthetic F0 model; no calibrated inference in this client."))});
        P->SetStringField(TEXT("next_experiment"), TEXT("Run the headless investigator for a policy comparison."));
        SendAction(TEXT("submit_conclusion"), P);
        break;
    }
    default:
        GetWorld()->GetTimerManager().SetTimer(FinishHandle, this,
            &UXenoSimulationBridge::PollFinish, 0.1f, true);
        break;
    }
}

void UXenoSimulationBridge::PollFinish()
{
    if (LastStreamSequence < StateRevision) return;
    const bool bOk = bHealthVerified && bSocketConnected && bDuplicateVerified
        && LatestObservation.IsValid()
        && LatestObservation->GetStringField(TEXT("status")) == TEXT("concluded");
    Finish(bOk, bOk ? FString() : TEXT("Mission verification failed"));
}

void UXenoSimulationBridge::Finish(bool bSuccess, const FString& Error)
{
    if (bFinished) return;
    bFinished = true;
    bMissionComplete = bSuccess;
    LastError = Error;
    Status = bSuccess ? TEXT("MISSION VERIFIED - inconclusive scientific outcome") : TEXT("Connection check failed: ") + Error;
    if (GetWorld())
    {
        GetWorld()->GetTimerManager().ClearTimer(TimeoutHandle);
        GetWorld()->GetTimerManager().ClearTimer(FinishHandle);
    }
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetBoolField(TEXT("success"), bSuccess);
    Result->SetStringField(TEXT("error"), Error);
    Result->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
    Result->SetBoolField(TEXT("requires_cooked_data"), FPlatformProperties::RequiresCookedData());
    Result->SetStringField(TEXT("episode_id"), EpisodeId);
    Result->SetBoolField(TEXT("health_verified"), bHealthVerified);
    Result->SetBoolField(TEXT("websocket_connected"), bSocketConnected);
    Result->SetBoolField(TEXT("duplicate_collection_verified"), bDuplicateVerified);
    Result->SetNumberField(TEXT("stream_events"), StreamEventCount);
    Result->SetNumberField(TEXT("final_revision"), StateRevision);
    Result->SetStringField(TEXT("scene_biome"), FXenoSceneSpec::Get().Biome);
    Result->SetBoolField(TEXT("well_reference_loaded"),AXenoPhysicsField::bReferenceLoaded);
    Result->SetStringField(TEXT("well_dataset"),AXenoPhysicsField::ReferenceDataset);
    Result->SetNumberField(TEXT("scene_spec_crc"), FXenoSceneSpec::Get().SpecCrc);
    Result->SetNumberField(TEXT("wall_clock_s"), FPlatformTime::Seconds() - StartWallTime);
    if (!ResultPath.IsEmpty()) FFileHelper::SaveStringToFile(JsonString(Result), *ResultPath);
    UE_LOG(LogTemp, Display, TEXT("XENO_RUNTIME_CHECK success=%d revision=%d events=%d"), bSuccess, StateRevision, StreamEventCount);
    if (bSuccess && !bSmoke)
    {
        GetWorld()->GetTimerManager().SetTimer(ScreenshotHandle,
            FTimerDelegate::CreateWeakLambda(this, [this]
        {
            FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::GetPath(ResultPath), TEXT("preview.png")), false, false);
        }), 20.0f, false);
    }
    if (bSmoke) FPlatformMisc::RequestExitWithStatus(false, bSuccess ? 0 : 1);
}
