#include "XenoEnvironment.h"
#include "XenoVisuals.h"
#include "XenoSceneSpec.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "ProceduralMeshComponent.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

using namespace XenoVisuals;

AXenoEnvironment::AXenoEnvironment()
{
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("EnvironmentRoot")));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> C(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> S(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Y(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> T(TEXT("/Engine/BasicShapes/Cone.Cone"));
    Cube = C.Object; Sphere = S.Object; Cylinder = Y.Object; Cone = T.Object;
}

void AXenoEnvironment::BeginPlay()
{
    Super::BeginPlay();
    BuildPreview();
}
void AXenoEnvironment::BuildPreview()
{
    Lit = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_XenoLit.M_XenoLit"));
    TerrainMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_XenoGeology.M_XenoGeology"));
    if(!FXenoSceneSpec::Get().IsIce()&&!FXenoSceneSpec::Get().IsVolcanic())
        TerrainMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Canyon/M_CanyonGround.M_CanyonGround"));
    SkyMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_XenoSkyV2.M_XenoSkyV2"));
    FluidMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_XenoFluid.M_XenoFluid"));
    BuildTerrain();
    BuildGeology();
    BuildLighting();
    if (FXenoSceneSpec::Get().bShowStation) BuildStation();
}

void AXenoEnvironment::EndPlay(const EEndPlayReason::Type Reason)
{
    for (AActor* Actor : LightingActors) if (IsValid(Actor)) Actor->Destroy();
    LightingActors.Empty();
    Super::EndPlay(Reason);
}

void AXenoEnvironment::Destroyed()
{
    for(AActor* Actor:LightingActors)if(IsValid(Actor))Actor->Destroy();
    LightingActors.Empty();Super::Destroyed();
}

void AXenoEnvironment::BuildLighting()
{
    const auto& Spec = FXenoSceneSpec::Get();
    const bool Ice = Spec.IsIce(), Lava = Spec.IsVolcanic();
    auto* SkyTint = UMaterialInstanceDynamic::Create(SkyMaterial,this);
    SkyTint->SetVectorParameterValue(TEXT("Horizon"), Ice ? FLinearColor(0.32f,0.48f,0.58f) :
        (Lava ? FLinearColor(0.28f,0.20f,0.17f) : FLinearColor(0.42f,0.33f,0.23f)));
    SkyTint->SetVectorParameterValue(TEXT("Zenith"), Ice ? FLinearColor(0.035f,0.1f,0.2f) : FLinearColor(0.03f,0.07f,0.12f));
    auto* Dome=Part(this,Sphere,SkyTint,FVector(350,350,0),FVector(500));
    Dome->SetCastShadow(false);Dome->bAffectDistanceFieldLighting=false;
    auto* Sun = GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,3000),FRotator(-Spec.SunElevation,Spec.SunAzimuth+180,0));
    LightingActors.Add(Sun);
    Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    Sun->GetLightComponent()->SetIntensity(Ice ? 3.0f : 3.5f);
    Sun->GetLightComponent()->SetLightColor(Ice ? FLinearColor(0.72f,0.87f,1) : FLinearColor(1,0.78f,0.55f));
    Sun->GetLightComponent()->SetCastShadows(true);
    auto* Fill = GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,2000),FRotator(-45,55,0));
    LightingActors.Add(Fill);
    Fill->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    Fill->GetLightComponent()->SetIntensity(Ice ? 1.3f : 1.4f);
    Fill->GetLightComponent()->SetLightColor(FLinearColor(0.52f,0.67f,0.85f));
    Fill->GetLightComponent()->SetCastShadows(false);
    auto* Sky = GetWorld()->SpawnActor<ASkyLight>();
    LightingActors.Add(Sky);
    Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    Sky->GetLightComponent()->SetIntensity(0.7f);
    Sky->GetLightComponent()->SkyDistanceThreshold = 8000;
    Sky->GetLightComponent()->SetLowerHemisphereColor(Ice ? FLinearColor(0.12f,0.17f,0.2f) : FLinearColor(0.09f,0.075f,0.06f));
    FTimerHandle Capture;
    GetWorld()->GetTimerManager().SetTimer(Capture,FTimerDelegate::CreateWeakLambda(Sky,[Sky]
    { Sky->GetLightComponent()->RecaptureSky(); }),0.5f,false);
    auto* Fog = GetWorld()->SpawnActor<AExponentialHeightFog>();
    LightingActors.Add(Fog);
    Fog->GetComponent()->SetFogDensity(0.002f+Spec.FogDensity*0.014f);
    Fog->GetComponent()->SetFogHeightFalloff(0.16f);
    Fog->GetComponent()->SetFogInscatteringColor(Ice ? FLinearColor(0.25f,0.4f,0.51f) : FLinearColor(0.31f,0.25f,0.19f));
    Fog->GetComponent()->SetFogMaxOpacity(0.75f);
}

void AXenoEnvironment::BuildStation()
{
    const FVector Base(-720, 1100, HeightAt(-720,1100));
    auto* White = Material(this, Lit, FLinearColor(0.64f,0.67f,0.62f), 0.5f, 0.2f);
    auto* Dark = Material(this, Lit, FLinearColor(0.025f,0.045f,0.06f), 0.5f, 0.4f);
    auto* Metal = Material(this, Lit, FLinearColor(0.18f,0.2f,0.21f), 0.5f, 0.6f);
    auto* Teal = Material(this, Lit, FLinearColor(0.04f,0.65f,0.58f), 0.5f, 0.1f, 1.8f);
    Part(this,Cube,Metal,Base+FVector(0,0,22),FVector(2.5f,2.1f,0.12f));
    Part(this,Cube,White,Base+FVector(0,0,110),FVector(1.9f,1.5f,1.45f));
    Part(this,Cube,Dark,Base+FVector(0,-77,125),FVector(1.4f,0.04f,0.55f));
    Part(this,Cube,Teal,Base+FVector(0,-80,87),FVector(1.3f,0.025f,0.035f));
    Part(this,Cube,Metal,Base+FVector(0,0,190),FVector(2.05f,1.65f,0.08f));
    Part(this,Cylinder,Metal,Base+FVector(140,0,200),FVector(0.06f,0.06f,4));
    Part(this,Sphere,White,Base+FVector(140,0,395),FVector(1.0f,1.0f,0.15f),FRotator(25,0,0));
    Part(this,Sphere,Teal,Base+FVector(140,0,425),FVector(0.13f));
    Part(this,Cube,Dark,Base+FVector(-230,0,135),FVector(2.0f,1.55f,0.06f),FRotator(0,0,20));
    Part(this,Cylinder,Metal,Base+FVector(-230,0,65),FVector(0.08f,0.08f,1.3f));
    for (int32 I=0; I<6; ++I)
        Part(this,Cube,Teal,Base+FVector(-310+I*30,0,141),FVector(0.018f,1.45f,0.015f),FRotator(0,0,20));
}

void AXenoEnvironment::Ring(FVector2D Position, float Radius, FLinearColor Color)
{
    auto* M = Material(this, Lit, Color, 0.6f, 0.0f, 1.4f);
    for (int32 I=0; I<24; ++I)
    {
        const float Angle=2*PI*I/24;
        const float X=Position.X+FMath::Cos(Angle)*Radius, Y=Position.Y+FMath::Sin(Angle)*Radius;
        Part(this,Cube,M,FVector(X,Y,HeightAt(X,Y)+3),FVector(0.025f,0.15f,0.012f),FRotator(0,FMath::RadiansToDegrees(Angle),0));
    }
}

void AXenoEnvironment::AddSampleSite(FVector2D Position, float AppearanceHue)
{
    const FLinearColor Color = FLinearColor::MakeFromHSV8(static_cast<uint8>(AppearanceHue*255),80,190);
    FRandomStream Random(static_cast<int32>(AppearanceHue*100000));
    Ring(Position, 90, FLinearColor(0.04f,0.6f,0.5f));
    for (int32 I=0; I<6; ++I)
    {
        const float X=Position.X+Random.FRandRange(-55,55), Y=Position.Y+Random.FRandRange(-55,55);
        Rock(FVector(X,Y,HeightAt(X,Y)),FVector(Random.FRandRange(18,40),Random.FRandRange(18,40),Random.FRandRange(22,65)),
             I+static_cast<int32>(AppearanceHue*1000), Color*0.45f);
    }
    const float X=Position.X-105, Y=Position.Y+30;
    auto* Marker = Material(this,Lit,FLinearColor(0.1f,0.75f,0.65f),0.5f,0.2f,1.8f);
    auto* Dark = Material(this,Lit,FLinearColor(0.08f,0.1f,0.11f),0.75f,0.4f);
    Part(this,Cylinder,Dark,FVector(X,Y,HeightAt(X,Y)+58),FVector(0.035f,0.035f,1.16f));
    Part(this,Cube,Marker,FVector(X,Y,HeightAt(X,Y)+118),FVector(0.19f,0.055f,0.14f));
}
