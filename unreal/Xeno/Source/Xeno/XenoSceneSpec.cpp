#include "XenoSceneSpec.h"
#include "Dom/JsonObject.h"
#include "Misc/Crc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

FXenoSceneSpec& FXenoSceneSpec::Get()
{
    static FXenoSceneSpec Spec;
    return Spec;
}

bool FXenoSceneSpec::LoadIfChanged()
{
    const FString Path = FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_SCENE_FILE"));
    if (Path.IsEmpty()) return false;
    TArray<uint8> Bytes;
    if (!FFileHelper::LoadFileToArray(Bytes, *Path) || Bytes.Num() > 65536) return false;
    const uint32 Crc = FCrc::MemCrc32(Bytes.GetData(), Bytes.Num());
    if (Crc == Get().SpecCrc) return false;
    FString Json;
    FFileHelper::BufferToString(Json, Bytes.GetData(), Bytes.Num());
    TSharedPtr<FJsonObject> Object;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Object) || !Object.IsValid()) return false;
    FXenoSceneSpec Next;
    double Version = 0, Value = 0;
    if (!Object->TryGetNumberField(TEXT("version"), Version) || Version != 1 ||
        !Object->TryGetStringField(TEXT("biome"), Next.Biome) ||
        !(Next.Biome == TEXT("hydrothermal_canyon") || Next.IsIce() || Next.IsVolcanic()) ||
        !Object->TryGetStringField(TEXT("title"), Next.Title) || Next.Title.Len() > 48 ||
        !Object->TryGetStringField(TEXT("direction"), Next.Direction) ||
        !Object->TryGetBoolField(TEXT("show_station"), Next.bShowStation)) return false;
    auto Read = [&](const TCHAR* Key, float& Target, double Min, double Max)
    {
        if (!Object->TryGetNumberField(Key, Value) || !FMath::IsFinite(Value) || Value < Min || Value > Max) return false;
        Target = static_cast<float>(Value); return true;
    };
    if (!Object->TryGetNumberField(TEXT("seed"), Value) || !FMath::IsFinite(Value) ||
        Value < 0 || Value > 2147483647.0 || FMath::FloorToDouble(Value) != Value) return false;
    Next.Seed = static_cast<int32>(Value);
    if (!Read(TEXT("relief"),Next.Relief,0.3,1.8) || !Read(TEXT("rock_density"),Next.RockDensity,0.2,1) ||
        !Read(TEXT("micro_detail"),Next.MicroDetail,0.2,1) || !Read(TEXT("pool_scale"),Next.PoolScale,0.5,1.6) ||
        !Read(TEXT("fog_density"),Next.FogDensity,0,1) || !Read(TEXT("sun_elevation"),Next.SunElevation,10,65) ||
        !Read(TEXT("sun_azimuth"),Next.SunAzimuth,-180,180) || !Read(TEXT("camera_yaw"),Next.CameraYaw,-180,180) ||
        !Read(TEXT("camera_pitch"),Next.CameraPitch,10,55) || !Read(TEXT("camera_distance"),Next.CameraDistance,900,5000)) return false;
    Next.SpecCrc = Crc; Next.FilePath = Path;
    Get() = Next;
    UE_LOG(LogTemp,Display,TEXT("XENO_SCENE_LOADED biome=%s title=%s crc=%u"),*Next.Biome,*Next.Title,Crc);
    return true;
}

void FXenoSceneSpec::RecordBuilt() const
{
    if (FilePath.IsEmpty()) return;
    TSharedPtr<FJsonObject> Object = MakeShared<FJsonObject>();
    Object->SetStringField(TEXT("biome"),Biome);
    Object->SetStringField(TEXT("title"),Title);
    Object->SetNumberField(TEXT("seed"),Seed);
    Object->SetNumberField(TEXT("spec_crc"),SpecCrc);
    Object->SetStringField(TEXT("state"),TEXT("built"));
    FString Json;
    FJsonSerializer::Serialize(Object.ToSharedRef(),TJsonWriterFactory<>::Create(&Json));
    FFileHelper::SaveStringToFile(Json,*FPaths::Combine(FPaths::GetPath(FilePath),TEXT("scene-status.json")),
        FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    UE_LOG(LogTemp,Display,TEXT("XENO_SCENE_BUILT biome=%s crc=%u"),*Biome,SpecCrc);
}
