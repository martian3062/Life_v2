#include "XenoPhysicsField.h"
#include "XenoEnvironment.h"
#include "XenoVisuals.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/ConstructorHelpers.h"

bool AXenoPhysicsField::bReferenceLoaded=false;
FString AXenoPhysicsField::ReferenceDataset;

AXenoPhysicsField::AXenoPhysicsField()
{
    PrimaryActorTick.bCanEverTick=true;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("ReferenceRoot")));
    Surface=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("DensitySurface"));
    Surface->SetupAttachment(GetRootComponent());
    Surface->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Arrows=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("VelocityArrows"));
    Arrows->SetupAttachment(GetRootComponent());
    Arrows->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Shape(TEXT("/Engine/BasicShapes/Cone.Cone"));
    Arrows->SetStaticMesh(Shape.Object);
    Label=CreateDefaultSubobject<UTextRenderComponent>(TEXT("ReferenceLabel"));
    Label->SetupAttachment(GetRootComponent());
    Label->SetHorizontalAlignment(EHTA_Center);Label->SetWorldSize(18);
    Label->SetRelativeLocation(FVector(0,-480,100));Label->SetRelativeRotation(FRotator(0,-90,0));
    Label->SetTextRenderColor(FColor(190,235,235));
}

void AXenoPhysicsField::BeginPlay()
{
    Super::BeginPlay();
    const FString Path=FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_WELL_FIELD_FILE"));
    FString Json;
    bReferenceLoaded=false;
    if(Path.IsEmpty() || !FFileHelper::LoadFileToString(Json,*Path) || Json.Len()>12000000){SetActorHiddenInGame(true);return;}
    TSharedPtr<FJsonObject> O;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),O)||!O.IsValid())return;
    double Version=0,X=0,Y=0;
    FString Mode,Dataset;
    if(!O->TryGetNumberField(TEXT("version"),Version)||Version!=1||
       !O->TryGetStringField(TEXT("mode"),Mode)||Mode!=TEXT("recorded_reference")||
       !O->TryGetStringField(TEXT("dataset"),Dataset)||
       !O->TryGetNumberField(TEXT("nx"),X)||!O->TryGetNumberField(TEXT("ny"),Y)||
       X<2||X>64||Y<2||Y>64)return;
    NX=static_cast<int32>(X);NY=static_cast<int32>(Y);
    const TArray<TSharedPtr<FJsonValue>> *D=nullptr,*V=nullptr,*T=nullptr;
    if(!O->TryGetArrayField(TEXT("density"),D)||!O->TryGetArrayField(TEXT("velocity"),V)||
       !O->TryGetArrayField(TEXT("times"),T)||D->Num()<2||D->Num()>51||
       V->Num()!=D->Num()||T->Num()!=D->Num())return;
    auto Read=[&](const TArray<TSharedPtr<FJsonValue>>& Frames,int32 Count,float Min,float Max,TArray<TArray<float>>& Out)
    {
        for(const auto& F:Frames)
        {
            const TArray<TSharedPtr<FJsonValue>>* Values=nullptr;
            if(!F->TryGetArray(Values)||Values->Num()!=Count)return false;
            TArray<float> Row;Row.Reserve(Count);
            for(const auto& Value:*Values){double N=0;if(!Value->TryGetNumber(N)||!FMath::IsFinite(N)||N<Min||N>Max)return false;Row.Add(static_cast<float>(N));}
            Out.Add(MoveTemp(Row));
        }
        return true;
    };
    if(!Read(*D,NX*NY,0,255,Density)||!Read(*V,NX*NY*2,-32767,32767,Velocity))return;
    for(const auto& Value:*T)
    {
        double Time=0;if(!Value->TryGetNumber(Time)||!FMath::IsFinite(Time)||(!Times.IsEmpty()&&Time<=Times.Last()))return;
        Times.Add(static_cast<float>(Time));
    }
    auto* Lit=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_XenoLit.M_XenoLit"));
    Surface->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_XenoReference.M_XenoReference")));
    Arrows->SetMaterial(0,XenoVisuals::Material(this,Lit,FLinearColor(.65f,.96f,.85f),.5f,0,.4f));
    TArray<int32> Triangles;TArray<FLinearColor> Colors;TArray<FProcMeshTangent> Tangents;
    for(int32 I=0;I<NX;++I)for(int32 J=0;J<NY;++J)
    {
        Vertices.Add(FVector((I/static_cast<float>(NX-1)-.5f)*300,(J/static_cast<float>(NY-1)-.5f)*900,0));
        Normals.Add(FVector::UpVector);UV.Add(FVector2D(I/static_cast<float>(NX),J/static_cast<float>(NY)));
        Colors.Add(FLinearColor::White);Tangents.Add(FProcMeshTangent(1,0,0));
        if(I<NX-1&&J<NY-1){const int32 K=I*NY+J;Triangles.Append({K,K+1,K+NY,K+1,K+NY+1,K+NY});}
        if(I%6==0&&J%6==0)Arrows->AddInstance(FTransform());
    }
    Surface->CreateMeshSection_LinearColor(0,Vertices,Triangles,Normals,UV,Colors,Tangents,false);
    SetActorLocation(FVector(-200,-150,AXenoEnvironment::HeightAt(-200,-150)+120));
    bReferenceLoaded=true;ReferenceDataset=Dataset;
    UpdateField(0);
    if(!FPlatformMisc::GetEnvironmentVariable(TEXT("XENO_LIVE_PHYSICS_DIR")).IsEmpty())SetActorHiddenInGame(true);
    UE_LOG(LogTemp,Display,TEXT("XENO_WELL_LOADED dataset=%s frames=%d grid=%dx%d mode=recorded_reference"),*Dataset,Density.Num(),NX,NY);
}

void AXenoPhysicsField::UpdateField(int32 Index)
{
    TArray<FLinearColor> Colors;
    int32 Arrow=0;
    for(int32 I=0;I<NX;++I)for(int32 J=0;J<NY;++J)
    {
        const int32 K=I*NY+J;const float D=Density[Index][K]/255;
        Vertices[K].Z=D*65;
        Colors.Add(FMath::Lerp(FLinearColor(.015f,.12f,.25f),FLinearColor(.95f,.37f,.035f),D));
        if(I%6==0&&J%6==0)
        {
            const FVector Flow(Velocity[Index][K*2]/32767,Velocity[Index][K*2+1]/32767,0);
            const float Length=FMath::Max(Flow.Size()*90,2.0f);
            const FQuat Rotation=FQuat::FindBetweenNormals(FVector::UpVector,Flow.GetSafeNormal(SMALL_NUMBER,FVector::ForwardVector));
            Arrows->UpdateInstanceTransform(Arrow++,FTransform(Rotation,Vertices[K]+FVector(0,0,18),FVector(.09f,.09f,Length/100)),false,false,true);
        }
    }
    Arrows->MarkRenderStateDirty();
    Surface->UpdateMeshSection_LinearColor(0,Vertices,Normals,UV,Colors,TArray<FProcMeshTangent>());
    Label->SetText(FText::FromString(FString::Printf(TEXT("THE WELL / RECORDED GAS FLOW\nt = %.2f simulation units / P: hide"),Times[Index])));
    Frame=Index;
}

void AXenoPhysicsField::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(!bReferenceLoaded||IsHidden())return;
    Elapsed+=DeltaSeconds;Poll+=DeltaSeconds;
    if(Poll<.1f)return;Poll=0;
    const float Time=Times[0]+FMath::Fmod(Elapsed,20.0f)/20*(Times.Last()-Times[0]);
    int32 Index=0;while(Index<Times.Num()-1&&Times[Index+1]<=Time)++Index;
    if(Index!=Frame)UpdateField(Index);
    SetActorLocation(FVector(-200,-150,AXenoEnvironment::HeightAt(-200,-150)+120));
}
