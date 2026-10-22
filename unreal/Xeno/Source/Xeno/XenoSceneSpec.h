#pragma once

#include "CoreMinimal.h"

// Presentation contract only: none of these fields enter the scientific protocol.
struct XENO_API FXenoSceneSpec
{
    FString Biome = TEXT("hydrothermal_canyon"), Title = TEXT("Saffron Veil");
    FString Direction, FilePath;
    int32 Seed = 72391;
    float Relief = 1.1f, RockDensity = 0.8f, MicroDetail = 0.9f, PoolScale = 1.1f;
    float FogDensity = 0.26f, SunElevation = 24, SunAzimuth = -35;
    float CameraYaw = -65, CameraPitch = 16, CameraDistance = 2900;
    bool bShowStation = true;
    uint32 SpecCrc = 0;
    static FXenoSceneSpec& Get();
    static bool LoadIfChanged();
    void RecordBuilt() const;
    bool IsIce() const { return Biome == TEXT("brine_glacier"); }
    bool IsVolcanic() const { return Biome == TEXT("basalt_caldera"); }
};
