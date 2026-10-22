#include "XenoLivePhysics.h"
#include "XenoRover.h"
#include "XenoEnvironment.h"
#include "XenoSceneSpec.h"
#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
bool AXenoLivePhysics::bLive=false;
int32 AXenoLivePhysics::LiveFrame=-1;
namespace {
void WriteJson(const FString& Path,const TSharedRef<FJsonObject>& Object)
{
    FString Json;FJsonSerializer::Serialize(Object,TJsonWriterFactory<>::Create(&Json));
    const FString Temp=Path+TEXT(".ue-tmp");
    if(FFileHelper::SaveStringToFile(Json,*Temp,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
        IFileManager::Get().Move(*Path,*Temp,true);
}
}
AXenoLivePhysics::AXenoLivePhysics()
{
    PrimaryActorTick.bCanEverTick=true;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("LiveRoot")));
    Surface=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ThermalSurface"));
    Surface->SetupAttachment(GetRootComponent());Surface->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Label=CreateDefaultSubobject<UTextRenderComponent>(TEXT("LiveLabel"));Label->SetupAttachment(GetRootComponent());
    Label->SetWorldSize(14);Label->SetHorizontalAlignment(EHTA_Center);Label->SetRelativeRotation(FRotator(0,-90,0));
    Label->SetTextRenderColor(FColor(180,235,218));
}
void AXenoLivePhysics::BeginPlay()
{
    Super::BeginPlay();bLive=false;
    Directory=FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_LIVE_PHYSICS_DIR"));
    if(Directory.IsEmpty()){SetActorHiddenInGame(true);SetActorTickEnabled(false);return;}
    TArray<int32> T;TArray<FLinearColor> C;TArray<FProcMeshTangent> Tangents;
    for(int32 I=0;I<64;++I)for(int32 J=0;J<64;++J)
    {
        const float X=(I/63.f-.5f)*2,Y=(J/63.f-.5f)*2;
        // Square-to-disc mapping fills the first canyon pool without a floating test panel.
        Vertices.Add(FVector(X*FMath::Sqrt(1-Y*Y*.5f)*375,Y*FMath::Sqrt(1-X*X*.5f)*234,0));
        Normals.Add(FVector::UpVector);UV.Add(FVector2D(I/63.f,J/63.f));C.Add(FLinearColor(.03f,.23f,.19f));
        Tangents.Add(FProcMeshTangent(1,0,0));
        if(I<63&&J<63){int32 K=I*64+J;T.Append({K,K+1,K+64,K+1,K+65,K+64});}
    }
    Surface->CreateMeshSection_LinearColor(0,Vertices,T,Normals,UV,C,Tangents,false);
    Surface->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_XenoThermal.M_XenoThermal")));
    ExportTerrain();
}
void AXenoLivePhysics::SetTarget(FVector2D Position){Target=Position;}
void AXenoLivePhysics::ExportTerrain()
{
    auto O=MakeShared<FJsonObject>();O->SetNumberField(TEXT("crc"),FXenoSceneSpec::Get().SpecCrc);
    O->SetNumberField(TEXT("n"),129);TArray<TSharedPtr<FJsonValue>> H;
    for(int32 X=0;X<129;++X)for(int32 Y=0;Y<129;++Y)
        H.Add(MakeShared<FJsonValueNumber>(AXenoEnvironment::HeightAt(-4000+X*62.5f,-4000+Y*62.5f)/100));
    O->SetArrayField(TEXT("heights_m"),H);WriteJson(FPaths::Combine(Directory,TEXT("terrain.json")),O);
    TerrainCrc=FXenoSceneSpec::Get().SpecCrc;
}
void AXenoLivePhysics::Tick(float Dt)
{
    Super::Tick(Dt);RenderFrames++;RenderSeconds+=Dt;Poll+=Dt;if(Poll<.1f)return;Poll=0;
    if(RenderSeconds>=1)
    {
        auto Status=MakeShared<FJsonObject>();Status->SetBoolField(TEXT("live_physics"),bLive);
        Status->SetNumberField(TEXT("live_frame"),LiveFrame);Status->SetNumberField(TEXT("scene_crc"),FXenoSceneSpec::Get().SpecCrc);
        Status->SetNumberField(TEXT("game_fps_average"),RenderFrames/RenderSeconds);
        Status->SetNumberField(TEXT("wall_time_unix"),FDateTime::UtcNow().ToUnixTimestamp());
        WriteJson(FPaths::Combine(Directory,TEXT("native-status.json")),Status);
        RenderFrames=0;RenderSeconds=0;
    }
    if(bLive&&GetWorld()->TimeSeconds-LastPoseTime>3){bLive=false;if(Rover)Rover->DisablePhysicsPose();}
    if(TerrainCrc!=FXenoSceneSpec::Get().SpecCrc)ExportTerrain();
    auto Control=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> XY;
    XY.Add(MakeShared<FJsonValueNumber>(Target.X*100));XY.Add(MakeShared<FJsonValueNumber>(-Target.Y*100));
    Control->SetArrayField(TEXT("target_m"),XY);WriteJson(FPaths::Combine(Directory,TEXT("control.json")),Control);
    const auto& Spec=FXenoSceneSpec::Get();
    const float Scale=Spec.PoolScale;Surface->SetRelativeScale3D(FVector(Scale,Scale,1));
    SetActorLocation(FVector(-1000,500,AXenoEnvironment::HeightAt(-1000,500)+20));
    Surface->SetVisibility(!Spec.IsIce()&&!Spec.IsVolcanic());Label->SetVisibility(!Spec.IsIce()&&!Spec.IsVolcanic());
    Label->SetRelativeLocation(FVector(0,-340*Scale,48));
    FString Json;TSharedPtr<FJsonObject> O;
    if(!FFileHelper::LoadFileToString(Json,*FPaths::Combine(Directory,TEXT("state.json")))||Json.Len()>500000||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),O)||!O.IsValid())return;
    double Timestamp=0,Version=0,F=0;
    if(!O->TryGetNumberField(TEXT("version"),Version)||Version!=1||!O->TryGetNumberField(TEXT("wall_time_unix"),Timestamp)||
       FMath::Abs(FDateTime::UtcNow().ToUnixTimestamp()-Timestamp)>3||!O->TryGetNumberField(TEXT("frame"),F))
    {bLive=false;if(Rover)Rover->DisablePhysicsPose();Label->SetText(FText::FromString(TEXT("THERMAL WORKER OFFLINE")));return;}
    if(F==Frame)return;
    const TArray<TSharedPtr<FJsonValue>>* Temp=nullptr;
    const TSharedPtr<FJsonObject>* R=nullptr;
    if(!O->TryGetArrayField(TEXT("temperature"),Temp)||Temp->Num()!=4096||!O->TryGetObjectField(TEXT("rover"),R))return;
    const TArray<TSharedPtr<FJsonValue>> *P=nullptr,*Q=nullptr,*Travel=nullptr;
    if(!(*R)->TryGetArrayField(TEXT("position_m"),P)||P->Num()!=3||!(*R)->TryGetArrayField(TEXT("quaternion_xyzw"),Q)||Q->Num()!=4||
       !(*R)->TryGetArrayField(TEXT("suspension_compression_m"),Travel)||Travel->Num()!=6)return;
    auto Finite=[](const TArray<TSharedPtr<FJsonValue>>& A){for(auto V:A){double N=0;if(!V->TryGetNumber(N)||!FMath::IsFinite(N)||FMath::Abs(N)>10000)return false;}return true;};
    if(!Finite(*P)||!Finite(*Q)||!Finite(*Travel)||!Finite(*Temp))return;
    if(Rover)Rover->SetPhysicsPose(FVector((*P)[0]->AsNumber()*100,-(*P)[1]->AsNumber()*100,(*P)[2]->AsNumber()*100-69),
        FQuat(-(*Q)[0]->AsNumber(),(*Q)[1]->AsNumber(),-(*Q)[2]->AsNumber(),(*Q)[3]->AsNumber()).GetNormalized(),*Travel);
    TArray<FLinearColor> Colors;
    for(int32 K=0;K<4096;++K)
    {
        const float Heat=FMath::Clamp((*Temp)[K]->AsNumber(),0.,1.);
        Vertices[K].Z=Heat*2;Colors.Add(FMath::Lerp(FLinearColor(.015f,.16f,.135f),FLinearColor(.40f,.58f,.26f),Heat));
    }
    Surface->UpdateMeshSection_LinearColor(0,Vertices,Normals,UV,Colors,TArray<FProcMeshTangent>());
    const double Time=O->GetObjectField(TEXT("thermal"))->GetNumberField(TEXT("time"));
    Label->SetText(FText::FromString(FString::Printf(TEXT("LIVE THERMAL FLOW  /  t %.1f"),Time)));
    Frame=static_cast<int32>(F);LiveFrame=Frame;LastPoseTime=GetWorld()->TimeSeconds;
    if(!bLive)UE_LOG(LogTemp,Display,TEXT("XENO_LIVE_PHYSICS_CONNECTED frame=%d"),Frame);
    bLive=true;
}
