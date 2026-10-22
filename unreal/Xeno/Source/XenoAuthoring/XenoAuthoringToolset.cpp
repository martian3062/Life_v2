#include "XenoAuthoringToolset.h"
#include "XenoEnvironment.h"
#include "XenoSceneSpec.h"
#include "Editor.h"
#include "EngineUtils.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

FString UXenoAuthoringToolset::GetApprovedScene()
{
    FXenoSceneSpec::LoadIfChanged();
    const auto& S=FXenoSceneSpec::Get();
    auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("title"),S.Title);
    O->SetStringField(TEXT("biome"),S.Biome);O->SetStringField(TEXT("crc"),LexToString(S.SpecCrc));
    O->SetBoolField(TEXT("approved_file_loaded"),!S.FilePath.IsEmpty());
    FString Json;FJsonSerializer::Serialize(O,TJsonWriterFactory<>::Create(&Json));return Json;
}
FString UXenoAuthoringToolset::BuildApprovedScene(const FString& ExpectedCrc)
{
    FXenoSceneSpec::LoadIfChanged();
    const auto& S=FXenoSceneSpec::Get();
    if(S.FilePath.IsEmpty()||ExpectedCrc!=LexToString(S.SpecCrc))return TEXT("ERROR: approved scene CRC mismatch");
    if(!GEditor||GEditor->PlayWorld)return TEXT("ERROR: stop PIE before editor authoring");
    UWorld* World=GEditor->GetEditorWorldContext().World();
    if(!World)return TEXT("ERROR: no editor world");
    TArray<AXenoEnvironment*> Owned;
    for(TActorIterator<AXenoEnvironment> I(World);I;++I)if(I->Tags.Contains(TEXT("XenoAuthored")))Owned.Add(*I);
    for(auto* Actor:Owned)Actor->Destroy();
    auto* Environment=World->SpawnActor<AXenoEnvironment>();
    Environment->Tags.Add(TEXT("XenoAuthored"));Environment->SetActorLabel(TEXT("XENO Approved Environment"));
    Environment->BuildPreview();
    auto O=MakeShared<FJsonObject>();O->SetStringField(TEXT("state"),TEXT("authored"));
    O->SetNumberField(TEXT("spec_crc"),S.SpecCrc);O->SetStringField(TEXT("title"),S.Title);
    O->SetStringField(TEXT("transport"),TEXT("Unreal native MCP"));
    FString Json;FJsonSerializer::Serialize(O,TJsonWriterFactory<>::Create(&Json));
    FFileHelper::SaveStringToFile(Json,*FPaths::Combine(FPaths::GetPath(S.FilePath),TEXT("authoring-status.json")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    return Json;
}
