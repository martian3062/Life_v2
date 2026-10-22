#include "XenoRover.h"
#include "XenoEnvironment.h"
#include "XenoVisuals.h"
#include "Dom/JsonValue.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"

using namespace XenoVisuals;

AXenoRover::AXenoRover()
{
    PrimaryActorTick.bCanEverTick = true;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("RoverRoot")));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> C(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Y(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> S(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    Cube=C.Object; Cylinder=Y.Object; Sphere=S.Object;
}

void AXenoRover::BeginPlay()
{
    Super::BeginPlay();
    auto* Base=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_XenoLit.M_XenoLit"));
    auto* White=Material(this,Base,FLinearColor(0.74f,0.77f,0.69f),0.5f,0.15f);
    auto* Dark=Material(this,Base,FLinearColor(0.018f,0.025f,0.03f),0.95f);
    auto* Steel=Material(this,Base,FLinearColor(0.18f,0.22f,0.24f),0.5f,0.7f);
    auto* Gold=Material(this,Base,FLinearColor(0.8f,0.38f,0.08f),0.5f,0.45f);
    auto* Solar=Material(this,Base,FLinearColor(0.018f,0.06f,0.13f),0.35f,0.4f);
    Beacon=Material(this,Base,FLinearColor(0.025f,0.7f,0.62f),0.3f,0.1f,2);
    Part(this,Cube,Steel,FVector(0,0,46),FVector(1.5f,0.85f,0.2f));
    Part(this,Cube,White,FVector(0,0,69),FVector(1.4f,0.95f,0.37f));
    Part(this,Cube,Gold,FVector(72,0,69),FVector(0.025f,0.94f,0.22f));
    for (int32 Side : {-1,1})
    for (int32 X : {-62,0,62})
    {
        Wheels.Add(Part(this,Cylinder,Dark,FVector(X,Side*61,28),FVector(0.52f,0.52f,0.27f),FRotator(0,0,90)));
        Part(this,Cylinder,Gold,FVector(X,Side*76,28),FVector(0.28f,0.28f,0.025f),FRotator(0,0,90));
        Part(this,Cube,Steel,FVector(X,Side*43,43),FVector(0.1f,0.45f,0.08f),FRotator(0,0,Side*20));
    }
    Part(this,Cube,Solar,FVector(-24,0,96),FVector(0.85f,1.28f,0.035f));
    for (int32 I=0;I<5;++I)
        Part(this,Cube,Steel,FVector(-62+I*19,0,99),FVector(0.014f,1.25f,0.01f));
    Part(this,Cylinder,Steel,FVector(35,0,126),FVector(0.07f,0.07f,0.85f));
    Part(this,Cube,White,FVector(35,0,174),FVector(0.35f,0.65f,0.29f));
    Part(this,Cube,Dark,FVector(54,0,176),FVector(0.025f,0.57f,0.21f));
    for (int32 Side : {-1,1})
        Part(this,Sphere,Beacon,FVector(57,Side*19,176),FVector(0.12f));
    Part(this,Cube,Steel,FVector(108,0,65),FVector(0.8f,0.1f,0.1f),FRotator(-25,0,0));
    Part(this,Cylinder,Gold,FVector(146,0,47),FVector(0.2f,0.2f,0.32f));
    Part(this,Cylinder,Steel,FVector(-52,35,139),FVector(0.025f,0.025f,0.95f));
    Part(this,Sphere,Beacon,FVector(-52,35,190),FVector(0.09f));
    // Chassis fasteners, panel ribs, wheel grousers and instrument brackets.
    for(int32 Side:{-1,1})for(int32 X=-55;X<=55;X+=22)
    {
        Part(this,Cylinder,Steel,FVector(X,Side*48.5f,76),FVector(.035f,.035f,.025f),FRotator(0,0,90));
        Part(this,Cube,Steel,FVector(X,Side*46,59),FVector(.012f,.025f,.15f));
    }
    for(auto& Wheel:Wheels)for(int32 I=0;I<18;++I)
    {
        const float A=I*2*PI/18;
        auto* Tread=Part(this,Cube,Steel,FVector::ZeroVector,FVector(.055f,.30f,.025f));
        Tread->AttachToComponent(Wheel,FAttachmentTransformRules::KeepRelativeTransform);
        Tread->SetRelativeLocation(FVector(50*FMath::Cos(A),50*FMath::Sin(A),0));
        Tread->SetRelativeScale3D(FVector(.11f,.08f,1.06f));
        Tread->SetRelativeRotation(FRotator(0,FMath::RadiansToDegrees(A),0));
    }
    SetObservedPosition(FVector2D::ZeroVector);
    SetActorLocation(Destination);
}

void AXenoRover::SetObservedPosition(FVector2D Position)
{
    // Metres -> cm with the documented 100x presentation magnification.
    Destination=FVector(Position.X*10000,Position.Y*10000,0);
    Destination.Z=AXenoEnvironment::HeightAt(Destination.X,Destination.Y);
}

void AXenoRover::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(bPhysicsPose)
    {
        const FVector Next=FMath::VInterpTo(GetActorLocation(),PhysicsPosition,DeltaSeconds,18);
        const float Spin=FVector::Dist2D(GetActorLocation(),Next)/26.f*180.f/PI;
        SetActorLocationAndRotation(Next,FQuat::Slerp(GetActorQuat(),PhysicsRotation,FMath::Clamp(DeltaSeconds*18,0.f,1.f)));
        for(auto& Wheel:Wheels)Wheel->AddLocalRotation(FRotator(0,Spin,0));
        return;
    }
    const FVector Previous=GetActorLocation();
    FVector Next=FMath::VInterpTo(Previous,Destination,DeltaSeconds,2.0f);
    Next.Z=AXenoEnvironment::HeightAt(Next.X,Next.Y);
    SetActorLocation(Next);
    const FVector Direction=Destination-Previous;
    if (Direction.Size2D()>8) SetActorRotation(FMath::RInterpTo(GetActorRotation(),FRotator(0,Direction.Rotation().Yaw,0),DeltaSeconds,2));
    const float Spin=FVector::Dist2D(Previous,Next)/26.0f*180.0f/PI;
    for (const auto& Wheel : Wheels) Wheel->AddLocalRotation(FRotator(0,Spin,0));
    if (Beacon) Beacon->SetScalarParameterValue(TEXT("Glow"),1.5f+0.4f*FMath::Sin(GetWorld()->TimeSeconds*2));
}

void AXenoRover::SetPhysicsPose(FVector Position,FQuat Rotation,const TArray<TSharedPtr<FJsonValue>>& Travel)
{
    PhysicsPosition=Position;PhysicsRotation=Rotation;
    for(int32 I=0;I<Wheels.Num()&&I<Travel.Num();++I)
    {
        FVector L=Wheels[I]->GetRelativeLocation();L.Z=28+Travel[I]->AsNumber()*100;
        Wheels[I]->SetRelativeLocation(L);
    }
    bPhysicsPose=true;
}
