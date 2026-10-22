#include "XenoEnvironment.h"
#include "XenoSceneSpec.h"
#include "XenoVisuals.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "ProceduralMeshComponent.h"

using namespace XenoVisuals;

namespace
{
float Noise(float X,float Y,float Scale,int32 Offset=0)
{
    const float S = (FXenoSceneSpec::Get().Seed % 10007)*0.071f;
    return FMath::PerlinNoise2D(FVector2D(X*Scale+S+Offset*4.17f,Y*Scale+Offset*7.13f));
}
FLinearColor GroundColor(float X,float Y,float Z)
{
    const auto& S=FXenoSceneSpec::Get();
    const float N=FMath::Clamp(0.5f+Noise(X,Y,0.003f),0.0f,1.0f);
    if (S.IsIce()) return FMath::Lerp(FLinearColor(0.15f,0.34f,0.43f),FLinearColor(0.65f,0.79f,0.8f),N);
    if (S.IsVolcanic()) return FMath::Lerp(FLinearColor(0.045f,0.052f,0.058f),FLinearColor(0.16f,0.12f,0.105f),N);
    return FMath::Lerp(FLinearColor(0.25f,0.13f,0.065f),FLinearColor(0.57f,0.38f,0.2f),N);
}
UProceduralMeshComponent* MakeMesh(AActor* Owner,const TArray<FVector>& V,const TArray<int32>& T,
    const TArray<FVector>& N,const TArray<FLinearColor>& C,UMaterialInterface* M)
{
    auto* Mesh=NewObject<UProceduralMeshComponent>(Owner);
    Owner->AddInstanceComponent(Mesh); Mesh->SetupAttachment(Owner->GetRootComponent());
    Mesh->RegisterComponent(); Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    TArray<FVector2D> UV; TArray<FProcMeshTangent> Tangents;
    for (int32 I=0;I<V.Num();++I)
    {
        UV.Add(FVector2D(V[I].X,V[I].Y)*0.01f);
        FVector Tangent=FVector::CrossProduct(FVector::RightVector,N[I]).GetSafeNormal();
        if (Tangent.IsNearlyZero()) Tangent=FVector::ForwardVector;
        Tangents.Add(FProcMeshTangent(Tangent,false));
    }
    Mesh->CreateMeshSection_LinearColor(0,V,T,N,UV,C,Tangents,false);
    Mesh->SetMaterial(0,M); return Mesh;
}
UMaterialInstanceDynamic* StoneMaterial(AActor* Owner,UMaterialInterface* Base,FLinearColor Tint)
{
    const auto& S=FXenoSceneSpec::Get();
    auto* M=Material(Owner,Base,Tint,S.IsIce()?0.46f:0.91f);
    if (M) { M->SetScalarParameterValue(TEXT("Biome"),S.IsIce()?1:(S.IsVolcanic()?2:0));
        M->SetScalarParameterValue(TEXT("Detail"),S.MicroDetail); }
    return M;
}
void ScannedCliff(AActor* Owner,FVector Base,FVector HalfSize,int32 Index,float Yaw)
{
    const FString Path=FString::Printf(TEXT("/Game/Canyon/SM_CanyonScan%d.SM_CanyonScan%d"),Index%2,Index%2);
    auto* Mesh=LoadObject<UStaticMesh>(nullptr,*Path);
    if(!Mesh)return;
    const auto Bounds=Mesh->GetBounds();const FVector E=Bounds.BoxExtent;
    const FVector Scale(HalfSize.X/FMath::Max(E.X,1.),HalfSize.Y/FMath::Max(E.Y,1.),HalfSize.Z/FMath::Max(E.Z,1.));
    const FVector Offset=FRotator(0,Yaw,0).RotateVector(FVector(Bounds.Origin.X,Bounds.Origin.Y,Bounds.Origin.Z-E.Z)*Scale);
    Part(Owner,Mesh,nullptr,Base-Offset,Scale,FRotator(0,Yaw,0));
}
}

float AXenoEnvironment::HeightAt(float X,float Y)
{
    const auto& S=FXenoSceneSpec::Get();
    const float R=FVector2D(X-350,Y-350).Size();
    const float Rise=FMath::Pow(FMath::Clamp((R-1800)/7500,0.0f,1.0f),1.4f);
    const float N=Noise(X,Y,0.00045f), Fine=Noise(X,Y,0.005f), Grain=Noise(X,Y,0.025f);
    float Z=-24+Fine*13+Grain*2.5f*S.MicroDetail+Rise*(650+N*750+FMath::Abs(Noise(X,Y,0.0009f))*1000)*S.Relief;
    if (S.IsIce())
    {
        const float Crack=X+1200+FMath::Sin(Y*0.0009f)*220;
        Z-=105*FMath::Exp(-FMath::Square(Crack/95));
        Z+=18*FMath::Abs(FMath::Sin((X+Y*.4f)*0.004f))*S.Relief;
    }
    else if (S.IsVolcanic()) Z+=Fine*16+FMath::Abs(Noise(X,Y,0.014f))*13*S.Relief;
    else Z+=FMath::Sin(Y*0.013f+X*0.002f)*3.5f*S.MicroDetail;
    return Z;
}

void AXenoEnvironment::BuildTerrain()
{
    auto* M=StoneMaterial(this,TerrainMaterial,FLinearColor::White);
    // Dense near field and coarser outer field. The outer tile has a matching central hole.
    for (int32 Tile=0;Tile<2;++Tile)
    {
        const int32 Count=Tile==0?257:193;
        const float Radius=Tile==0?3000:12000;
        TArray<FVector> V,N; TArray<int32> T; TArray<FLinearColor> C;
        for (int32 Y=0;Y<Count;++Y)
        for (int32 X=0;X<Count;++X)
        {
            const float WX=-Radius+X*2*Radius/(Count-1), WY=-Radius+Y*2*Radius/(Count-1);
            const float Z=HeightAt(WX,WY);
            V.Add(FVector(WX,WY,Z));
            N.Add(FVector(HeightAt(WX-3,WY)-HeightAt(WX+3,WY),HeightAt(WX,WY-3)-HeightAt(WX,WY+3),6).GetSafeNormal());
            C.Add(GroundColor(WX,WY,Z));
            if (X<Count-1 && Y<Count-1)
            {
                if (Tile==1 && WX>=-3000 && WX<3000 && WY>=-3000 && WY<3000) continue;
                const int32 A=Y*Count+X; T.Append({A,A+Count,A+1,A+1,A+Count,A+Count+1});
            }
        }
        MakeMesh(this,V,T,N,C,M);
    }
}

void AXenoEnvironment::Rock(FVector Position,FVector Scale,int32 Seed,FLinearColor Tint)
{
    if(!FXenoSceneSpec::Get().IsIce()&&!FXenoSceneSpec::Get().IsVolcanic())
    {
        const FString Path=FString::Printf(TEXT("/Game/Canyon/SM_CanyonRock%d.SM_CanyonRock%d"),FMath::Abs(Seed)%4,FMath::Abs(Seed)%4);
        if(auto* Mesh=LoadObject<UStaticMesh>(nullptr,*Path))
        {
            Part(this,Mesh,nullptr,Position,Scale/FVector(100,85,75),FRotator(0,Seed%360,0));return;
        }
    }
    const int32 Rings=18,Sides=28;
    FRandomStream Rand(Seed); const float Phase=Rand.FRandRange(0,30);
    TArray<FVector> V,N; TArray<int32> T; TArray<FLinearColor> C;
    for (int32 R=0;R<=Rings;++R)
    for (int32 I=0;I<=Sides;++I)
    {
        const float A=I*2*PI/Sides,B=R*PI/Rings;
        const FVector D(FMath::Sin(B)*FMath::Cos(A),FMath::Sin(B)*FMath::Sin(A),FMath::Cos(B));
        const float Broad=FMath::PerlinNoise3D(D*2.6f+FVector(Phase));
        const float Fine=FMath::PerlinNoise3D(D*8+FVector(Phase*2));
        const float LayerOffset=FMath::Sin(D.Z*20+Broad*3)*0.035f;
        FVector P=D*(0.94f+Broad*.25f+Fine*.07f+LayerOffset)*Scale;
        P.Z=FMath::Max(P.Z,-Scale.Z*.65f);
        const bool FlatTop=Scale.X>350 && P.Z>Scale.Z*.5f;
        if(FlatTop) P.Z=Scale.Z*.5f;
        V.Add(Position+P); N.Add(FlatTop?FVector::UpVector:FVector(D.X/Scale.X,D.Y/Scale.Y,D.Z/Scale.Z).GetSafeNormal());
        C.Add(FLinearColor::White*(.85f+Fine*.2f));
        if (R<Rings && I<Sides)
        {
            const int32 K=R*(Sides+1)+I;
            T.Append({K,K+1,K+Sides+1,K+1,K+Sides+2,K+Sides+1});
        }
    }
    MakeMesh(this,V,T,N,C,StoneMaterial(this,TerrainMaterial,Tint));
}

void AXenoEnvironment::BuildWall()
{
    const auto& S=FXenoSceneSpec::Get();
    if(!S.IsIce()&&!S.IsVolcanic())
    {
        FRandomStream Random(S.Seed+531);
        for(int32 I=0;I<14;++I)
        {
            const float A=I*2*PI/14,Radius=Random.FRandRange(5100,6500);
            const float X=350+FMath::Cos(A)*Radius,Y=350+FMath::Sin(A)*Radius;
            ScannedCliff(this,FVector(X,Y,HeightAt(X,Y)-140),
                FVector(Random.FRandRange(750,1200),Random.FRandRange(600,950),Random.FRandRange(550,850)*S.Relief),I,
                FMath::RadiansToDegrees(A)+90);
        }
        return;
    }
    const int32 Sides=320,Rings=56;
    TArray<FVector> V,N; TArray<int32> T; TArray<FLinearColor> C;
    for (int32 J=0;J<=Rings;++J)
    for (int32 I=0;I<=Sides;++I)
    {
        const float A=I*2*PI/Sides, H=static_cast<float>(J)/Rings;
        const float Ridge=Noise(FMath::Cos(A)*5000,FMath::Sin(A)*5000,.001f);
        const float Peak=(950+300*FMath::Sin(A*5)+300*Ridge)*S.Relief;
        const float Stratum=FMath::Sin(H*45+Ridge*3)*12+FMath::Floor(H*9)*27;
        const float Gully=FMath::Pow(FMath::Abs(FMath::Sin(A*27+Ridge)),5)*140;
        float Radius=4700+Ridge*680+H*580+Stratum+Gully;
        if (S.IsIce()) Radius=4500+Ridge*450+H*400+FMath::Abs(FMath::Sin(A*51))*70;
        if (S.IsVolcanic()) Radius=5100+Ridge*950+H*850+Stratum*0.3f;
        const float X=350+FMath::Cos(A)*Radius,Y=350+FMath::Sin(A)*Radius;
        const float Z=HeightAt(X,Y)+H*Peak-100;
        V.Add(FVector(X,Y,Z)); N.Add(FVector(-FMath::Cos(A),-FMath::Sin(A),0.25f).GetSafeNormal());
        const float Bands=.5f+.5f*FMath::Sin(Z*(S.IsIce()?.008f:.009f)+Ridge*3);
        FLinearColor Color=FMath::Lerp(FLinearColor(.27f,.16f,.095f),FLinearColor(.43f,.29f,.17f),Bands);
        if (S.IsIce()) Color=FMath::Lerp(FLinearColor(.06f,.22f,.36f),FLinearColor(.58f,.79f,.86f),H*.6f+Bands*.4f);
        if (S.IsVolcanic()) Color=FMath::Lerp(FLinearColor(.065f,.07f,.08f),FLinearColor(.23f,.18f,.14f),Bands);
        C.Add(Color);
        if (J<Rings && I<Sides) { const int32 K=J*(Sides+1)+I; T.Append({K,K+1,K+Sides+1,K+1,K+Sides+2,K+Sides+1}); }
    }
    MakeMesh(this,V,T,N,C,StoneMaterial(this,TerrainMaterial,FLinearColor::White));
}

void AXenoEnvironment::Column(FVector P,float Radius,float Height,int32 Seed)
{
    FRandomStream R(Seed); TArray<FVector> V,N; TArray<int32>T; TArray<FLinearColor>C;
    const FLinearColor Tint(.11f,.125f,.14f);
    for (int32 Side=0;Side<6;++Side)
    {
        const float A=Side*PI/3,B=(Side+1)*PI/3;
        const float Top=Height*R.FRandRange(.86f,1.12f); const int32 K=V.Num();
        const FVector D(FMath::Cos((A+B)*.5f),FMath::Sin((A+B)*.5f),.05f);
        V.Append({P+FVector(FMath::Cos(A)*Radius,FMath::Sin(A)*Radius,0),
            P+FVector(FMath::Cos(B)*Radius,FMath::Sin(B)*Radius,0),
            P+FVector(FMath::Cos(A)*Radius*.91f,FMath::Sin(A)*Radius*.91f,Top),
            P+FVector(FMath::Cos(B)*Radius*.91f,FMath::Sin(B)*Radius*.91f,Top)});
        T.Append({K,K+2,K+1,K+1,K+2,K+3});
        for(int32 J=0;J<4;++J){N.Add(D);C.Add(FLinearColor::White);}
        const int32 TopK=V.Num();
        V.Append({P+FVector(0,0,Top),V[K+2],V[K+3]});T.Append({TopK,TopK+2,TopK+1});
        for(int32 J=0;J<3;++J){N.Add(FVector::UpVector);C.Add(FLinearColor(.7f,.7f,.7f));}
    }
    MakeMesh(this,V,T,N,C,StoneMaterial(this,TerrainMaterial,Tint));
}

void AXenoEnvironment::Pool(FVector2D Center,float RX,float RY,float Level)
{
    const auto& S=FXenoSceneSpec::Get();
    const int32 Sides=128,Rings=10;
    // Concentric mineral/ice shelves step down to a flat reflective surface.
    TArray<FVector> V,N;TArray<int32>T;TArray<FLinearColor>C;
    for (int32 R=0;R<=Rings;++R)
    for (int32 I=0;I<=Sides;++I)
    {
        const float A=I*2*PI/Sides,F=.86f+R*.041f;
        const float W=1+.035f*FMath::Sin(A*7)+.02f*FMath::Sin(A*13);
        const float X=Center.X+FMath::Cos(A)*RX*F*W,Y=Center.Y+FMath::Sin(A)*RY*F*W;
        float Z=Level+5+(Rings-R)*1.2f+FMath::Floor(R/2.0f)*3.5f;
        Z=FMath::Lerp(Z,HeightAt(X,Y),FMath::Clamp((F-1.15f)*8,0.0f,1.0f));
        V.Add(FVector(X,Y,Z));N.Add(FVector::UpVector);
        FLinearColor Color=R%3==0?FLinearColor(.63f,.55f,.37f):FLinearColor(.79f,.74f,.6f);
        if(S.IsIce())Color=FMath::Lerp(FLinearColor(.13f,.36f,.5f),FLinearColor(.75f,.87f,.9f),R*.1f);
        if(S.IsVolcanic())Color=R%3==0?FLinearColor(.12f,.07f,.04f):FLinearColor(.055f,.06f,.065f);
        C.Add(Color);
        if(R<Rings&&I<Sides){const int32 K=R*(Sides+1)+I;T.Append({K,K+1,K+Sides+1,K+1,K+Sides+2,K+Sides+1});}
    }
    MakeMesh(this,V,T,N,C,StoneMaterial(this,TerrainMaterial,FLinearColor::White));
    V.Empty();N.Empty();T.Empty();C.Empty();
    V.Add(FVector(Center,Level+18));N.Add(FVector::UpVector);C.Add(FLinearColor(.025f,.2f,.23f));
    for(int32 I=0;I<=Sides;++I)
    {
        const float A=I*2*PI/Sides,W=1+.035f*FMath::Sin(A*7)+.02f*FMath::Sin(A*13);
        V.Add(FVector(Center.X+FMath::Cos(A)*RX*.9f*W,Center.Y+FMath::Sin(A)*RY*.9f*W,Level+18));
        N.Add(FVector::UpVector);C.Add(S.IsVolcanic()?FLinearColor(1,.18f,.015f):FLinearColor(.04f,.36f,.36f));
        if(I<Sides)T.Append({0,I+2,I+1});
    }
    auto* Fluid=Material(this,FluidMaterial,S.IsIce()?FLinearColor(.12f,.4f,.58f):
        (S.IsVolcanic()?FLinearColor(1,.22f,.025f):FLinearColor(.12f,.67f,.56f)),.12f,.22f,S.IsVolcanic()?2.5f:.04f);
    MakeMesh(this,V,T,N,C,Fluid);
}

void AXenoEnvironment::ScatterPebbles()
{
    const auto& S=FXenoSceneSpec::Get(); FRandomStream R(S.Seed+93);
    auto* Pebbles=NewObject<UInstancedStaticMeshComponent>(this);
    AddInstanceComponent(Pebbles);Pebbles->SetupAttachment(GetRootComponent());
    Pebbles->SetStaticMesh(Sphere);Pebbles->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if(!S.IsIce()&&!S.IsVolcanic())
        Pebbles->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Canyon/SM_CanyonRock0.SM_CanyonRock0")));
    Pebbles->SetMaterial(0,StoneMaterial(this,TerrainMaterial,S.IsIce()?FLinearColor(.43f,.6f,.65f):
        (S.IsVolcanic()?FLinearColor(.085f,.09f,.1f):FLinearColor(.24f,.17f,.1f))));
    if(!S.IsIce()&&!S.IsVolcanic())
        Pebbles->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Canyon/M_CanyonRock.M_CanyonRock")));
    Pebbles->RegisterComponent();
    for(int32 I=0;I<static_cast<int32>(1800*S.RockDensity);++I)
    {
        const float X=R.FRandRange(-2800,3400),Y=R.FRandRange(-2200,3500),Size=R.FRandRange(2,12);
        const float Z=HeightAt(X,Y)+Size*.15f;
        Pebbles->AddInstance(FTransform(FRotator(R.FRandRange(-20,20),R.FRandRange(0,360),0),FVector(X,Y,Z),
            FVector(Size*.025f,Size*.016f,Size*.012f)));
    }
}

void AXenoEnvironment::BuildGeology()
{
    const auto& S=FXenoSceneSpec::Get();FRandomStream R(S.Seed);
    BuildWall();ScatterPebbles();
    for(int32 I=0;I<static_cast<int32>(165*S.RockDensity);++I)
    {
        const float X=R.FRandRange(-3300,3700),Y=R.FRandRange(-2500,4100);
        if(X>-150&&X<1100&&Y>-180&&Y<1050)continue;
        const float Size=R.FRandRange(28,150);
        FLinearColor Color=S.IsIce()?FLinearColor(.25f,.48f,.6f):
            (S.IsVolcanic()?FLinearColor(.10f,.11f,.12f):FLinearColor(.36f,.23f,.13f));
        Rock(FVector(X,Y,HeightAt(X,Y)),FVector(Size,Size*R.FRandRange(.6f,1.4f),Size*R.FRandRange(.45f,1.1f)),S.Seed+I,Color);
    }
    if(S.IsVolcanic())
    {
        for(int32 Cluster=0;Cluster<4;++Cluster)
        {
            const FVector2D Center(Cluster%2==0?-1650:2100,Cluster<2?1550:3250);
            for(int32 I=0;I<24;++I)
            {
                const float X=Center.X+R.FRandRange(-400,400),Y=Center.Y+R.FRandRange(-300,300);
                Column(FVector(X,Y,HeightAt(X,Y)-15),R.FRandRange(45,85),R.FRandRange(160,650)*S.Relief,S.Seed+I);
            }
        }
        for(int32 I=0;I<7;++I)
        {
            const FVector2D P(-1250+FMath::Sin(I*.8f)*320,50+I*330);
            Pool(P,65*S.PoolScale,240*S.PoolScale,HeightAt(P.X,P.Y)-9);
        }
    }
    else
    {
        const FVector2D Pools[]={FVector2D(-1000,500),FVector2D(-1550,1400),FVector2D(1550,1900)};
        for(int32 I=0;I<3;++I)
        {
            const auto P=Pools[I];Pool(P,(I==0?430:300)*S.PoolScale,(I==0?270:210)*S.PoolScale,HeightAt(P.X,P.Y));
        }
        if(S.IsIce())
        {
            for(int32 I=0;I<14;++I)
            {
                const float X=-2050+R.FRandRange(-160,160),Y=-600+I*270;
                Rock(FVector(X,Y,HeightAt(X,Y)),FVector(R.FRandRange(100,180),70,R.FRandRange(180,530)*S.Relief),
                    S.Seed+I,FLinearColor(.23f,.5f,.66f));
            }
        }
        else
        {
            for(int32 I=0;I<4;++I)
            {
                const float X=-3000+I*1800,Y=3100+R.FRandRange(-250,350);
                ScannedCliff(this,FVector(X,Y,HeightAt(X,Y)-100),FVector(650,450,R.FRandRange(400,600)*S.Relief),I,180+R.FRandRange(-25,25));
            }
        }
    }
}
