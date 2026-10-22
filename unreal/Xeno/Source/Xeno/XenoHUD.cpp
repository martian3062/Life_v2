#include "XenoMissionMode.h"
#include "XenoEnvironment.h"
#include "XenoSimulationBridge.h"
#include "XenoSceneSpec.h"
#include "Dom/JsonObject.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "GameFramework/PlayerController.h"

namespace
{
const FLinearColor Ink(0.018f,0.028f,0.035f,0.9f);
const FLinearColor Text(0.85f,0.89f,0.86f);
const FLinearColor Muted(0.48f,0.61f,0.61f);
const FLinearColor Teal(0.12f,0.86f,0.68f);
const FLinearColor Amber(1.0f,0.62f,0.24f);
}

void AXenoHUD::DrawHUD()
{
    Super::DrawHUD();
    auto* Bridge=GetGameInstance()->GetSubsystem<UXenoSimulationBridge>();
    auto Obs=Bridge->LatestObservation;
    UFont* Font=GEngine->GetMediumFont();
    const float W=Canvas->SizeX, H=Canvas->SizeY;
    const float Bottom=H-177;
    DrawRect(Ink,0,0,W,88);
    DrawRect(Teal,24,25,3,38);
    DrawText(TEXT("XENO"),Text,42,20,Font,2.2f);
    DrawText(FXenoSceneSpec::Get().Title.ToUpper()+TEXT("  /  FIELD EXPEDITION"),Muted,185,27,Font,1.0f);
    DrawText(TEXT("Synthetic F0 world  /  artistic terrain at 100x scale"),Muted,185,50,Font,0.9f);
    DrawText(TEXT("RMB: orbit   Wheel: zoom   H: HUD   R: reset"),Text,W-375,30,Font,0.9f);
    DrawText(Bridge->bConnected ? TEXT("●  MISSION SYNCED") : TEXT("CONNECTING TO MISSION"),
             Bridge->bConnected ? Teal : Amber,W-375,52,Font,0.9f);

    if (Obs.IsValid())
    {
        auto Budget=Obs->GetObjectField(TEXT("remaining_budget"));
        DrawRect(Ink,W-230,108,206,126);
        DrawText(TEXT("ROVER TELEMETRY"),Muted,W-214,120,Font,0.9f);
        DrawText(FString::Printf(TEXT("%.0f J"),Budget->GetNumberField(TEXT("battery_j"))),Text,W-214,143,Font,1.5f);
        DrawText(FString::Printf(TEXT("%.1f s mission time"),Obs->GetNumberField(TEXT("simulation_time_s"))),Text,W-214,177,Font);
        DrawText(FString::Printf(TEXT("%.0f lab actions available"),Budget->GetNumberField(TEXT("lab_actions"))),Muted,W-214,204,Font,0.9f);

        int32 Index=0;
        for (const auto& Site : Obs->GetArrayField(TEXT("sites")))
        {
            ++Index;
            const auto& XY=Site->AsObject()->GetArrayField(TEXT("position_m"));
            const float X=static_cast<float>(XY[0]->AsNumber()*10000),Y=static_cast<float>(XY[1]->AsNumber()*10000);
            FVector2D Screen;
            if (GetOwningPlayerController()->ProjectWorldLocationToScreen(FVector(X,Y,AXenoEnvironment::HeightAt(X,Y)+125),Screen)
                && Screen.X>30 && Screen.X<W-30 && Screen.Y>100 && Screen.Y<Bottom-35)
            {
                DrawLine(Screen.X-5,Screen.Y,Screen.X,Screen.Y-5,Teal,1);
                DrawLine(Screen.X,Screen.Y-5,Screen.X+5,Screen.Y,Teal,1);
                DrawLine(Screen.X+5,Screen.Y,Screen.X,Screen.Y+5,Teal,1);
                DrawLine(Screen.X,Screen.Y+5,Screen.X-5,Screen.Y,Teal,1);
                DrawText(FString::Printf(TEXT("S-%02d"),Index),Text,Screen.X+12,Screen.Y-7,Font,0.9f);
            }
        }
    }

    DrawRect(Ink,24,Bottom,330,151);
    DrawRect(Bridge->bMissionComplete ? Teal : Amber,24,Bottom,330,2);
    DrawText(TEXT("INVESTIGATION"),Muted,40,Bottom+14,Font,0.9f);
    DrawText(Bridge->bMissionComplete ? TEXT("MISSION COMPLETE") : TEXT("EXPLORING THE BASIN"),Text,40,Bottom+36,Font,1.2f);
    DrawText(Bridge->bMissionComplete ? TEXT("Report: inconclusive") : *Bridge->LastAction,
        Bridge->LastError.IsEmpty() ? Teal : Amber,40,Bottom+65,Font);
    if (!Bridge->LastError.IsEmpty()) DrawText(TEXT("Connection interrupted — inspect the run log"),Amber,40,Bottom+85,Font,0.8f);
    DrawText(FString::Printf(TEXT("Observation revision %d  /  %d events"),Bridge->StateRevision,Bridge->StreamEventCount),
             Muted,40,Bottom+112,Font,0.85f);

    const float ChartW=380, ChartX=W-ChartW-24, MidX=374, MidW=ChartX-MidX-20;
    if (MidW>230)
    {
        DrawRect(Ink,MidX,Bottom,MidW,151);
        DrawText(TEXT("SAMPLE & LABORATORY"),Muted,MidX+16,Bottom+14,Font,0.9f);
        double Volume=0;
        int32 Samples=0;
        if (Obs.IsValid())
        {
            Volume=Obs->GetObjectField(TEXT("cumulative_costs"))->GetNumberField(TEXT("sample_volume_m3"))*1e6;
            Samples=Obs->GetArrayField(TEXT("samples")).Num();
        }
        DrawText(FString::Printf(TEXT("%.2f mL collected   /   %d aliquots"),Volume,Samples),Text,MidX+16,Bottom+40,Font);
        if (Bridge->LatestExperiment.IsValid())
        {
            const auto Conditions=Bridge->LatestExperiment->GetObjectField(TEXT("applied_conditions"));
            DrawText(FString::Printf(TEXT("CONTROL       %.2f K"),Conditions->GetNumberField(TEXT("control_temperature_K"))),Teal,MidX+16,Bottom+73,Font);
            DrawText(FString::Printf(TEXT("TREATMENT   %.2f K"),Conditions->GetNumberField(TEXT("treatment_temperature_K"))),Amber,MidX+16,Bottom+96,Font);
            DrawText(TEXT("Matched material  /  60 s observation"),Muted,MidX+16,Bottom+125,Font,0.85f);
        }
        else DrawText(TEXT("Waiting for paired sample allocation"),Muted,MidX+16,Bottom+84,Font);
    }

    DrawRect(Ink,ChartX,Bottom,ChartW,151);
    DrawText(TEXT("STRUCTURE RESPONSE  /  token/m3"),Muted,ChartX+16,Bottom+14,Font,0.9f);
    if (!Bridge->LatestExperiment.IsValid())
    {
        DrawText(TEXT("Live control and treatment traces appear here"),Muted,ChartX+16,Bottom+70,Font,0.85f);
        return;
    }
    const auto& Trace=Bridge->LatestExperiment->GetArrayField(TEXT("trace"));
    const float PX=ChartX+40,PY=Bottom+124,PW=ChartW-62,PH=75;
    for (int32 Tick=0;Tick<3;++Tick)
    {
        const float Y=PY-Tick*PH/2;
        DrawText(FString::FromInt(Tick*4),Muted,ChartX+17,Y-5,Font,0.75f);
        DrawLine(PX,Y,PX+PW,Y,FLinearColor(0.3f,0.4f,0.4f,0.4f),1);
    }
    for (int32 Arm=0;Arm<2;++Arm)
    {
        FVector2D Previous=FVector2D::ZeroVector;
        bool bPrevious=false;
        for (int32 I=0;I<Trace.Num();++I)
        {
            double Value=0; bool bFound=false;
            for (const auto& Entry : Trace[I]->AsObject()->GetArrayField(Arm==0 ? TEXT("control") : TEXT("treatment")))
            {
                auto M=Entry->AsObject();
                if (M->GetStringField(TEXT("channel_id"))==TEXT("structure")) bFound=M->TryGetNumberField(TEXT("value"),Value);
            }
            FVector2D Point(PX+I*PW/8,PY-Value/8*PH);
            if (bFound && bPrevious) DrawLine(Previous.X,Previous.Y,Point.X,Point.Y,Arm==0 ? Teal : Amber,2);
            Previous=Point; bPrevious=bFound;
        }
    }
    DrawText(TEXT("0 s"),Muted,PX,PY+5,Font,0.75f);
    DrawText(TEXT("30 s"),Muted,PX+PW/2-10,PY+5,Font,0.75f);
    DrawText(TEXT("60 s"),Muted,PX+PW-24,PY+5,Font,0.75f);
}
