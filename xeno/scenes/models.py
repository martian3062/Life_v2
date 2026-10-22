from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SceneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal[1] = 1
    biome: Literal["hydrothermal_canyon", "brine_glacier", "basalt_caldera"]
    title: str = Field(min_length=3, max_length=48, pattern=r"^[A-Za-z0-9 ,.'-]+$")
    direction: str = Field(min_length=20, max_length=1400)
    seed: int = Field(ge=0, le=2147483647)
    relief: float = Field(ge=0.3, le=1.8)
    rock_density: float = Field(ge=0.2, le=1)
    micro_detail: float = Field(ge=0.2, le=1)
    pool_scale: float = Field(ge=0.5, le=1.6)
    fog_density: float = Field(ge=0, le=1)
    sun_elevation: float = Field(ge=10, le=65)
    sun_azimuth: float = Field(ge=-180, le=180)
    camera_yaw: float = Field(ge=-180, le=180)
    camera_pitch: float = Field(ge=10, le=55)
    camera_distance: float = Field(ge=900, le=5000)
    show_station: bool


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=10, max_length=4000)
    scenario: Literal["auto", "hydrothermal_canyon", "brine_glacier", "basalt_caldera"] = "auto"


PRESETS = {
    "hydrothermal_canyon": SceneSpec(
        biome="hydrothermal_canyon",
        title="Saffron Veil",
        direction=(
            "Layered ochre canyon with eroded shelves, fine sediment bands and runoff grooves. "
            "Pale mineral terraces surround turquoise pools. Foreground fractured slabs and talus "
            "lead to a stepped canyon opening and hazy mesas. Low warm side light, cool fill, "
            "fine rough grain and subdued basin mist. Preserve rover and sampling sightlines."
        ),
        seed=72391,
        relief=1.1,
        rock_density=0.8,
        micro_detail=0.9,
        pool_scale=1.1,
        fog_density=0.26,
        sun_elevation=24,
        sun_azimuth=-35,
        camera_yaw=-65,
        camera_pitch=16,
        camera_distance=2900,
        show_station=True,
    ),
    "brine_glacier": SceneSpec(
        biome="brine_glacier",
        title="Cobalt Divide",
        direction=(
            "Fractured blue glacier with pressure ridges, wind-scoured grooves, branching "
            "crevasses and serrated ice walls. Chalk-white shelves expose layered cyan and navy "
            "depth bands beside reflective brine-like pools. Frost grain and fine hairline cracks "
            "break up each surface. Cool side light and blue-gray haze frame the mission rover."
        ),
        seed=47021,
        relief=1.2,
        rock_density=0.7,
        micro_detail=0.95,
        pool_scale=1.2,
        fog_density=0.22,
        sun_elevation=32,
        sun_azimuth=-55,
        camera_yaw=-65,
        camera_pitch=16,
        camera_distance=2800,
        show_station=True,
    ),
    "basalt_caldera": SceneSpec(
        biome="basalt_caldera",
        title="Ember Crown",
        direction=(
            "Dark volcanic caldera with columnar basalt, fractured plates, granular cinder "
            "drifts and cooled lava lobes. Thin orange fissures lead from foreground broken "
            "columns to a low caldera rim. Fine mineral inclusions, layered edges and rough "
            "near-black rock catch low amber rim light with cool fill and restrained smoky haze."
        ),
        seed=92813,
        relief=1.15,
        rock_density=0.9,
        micro_detail=1,
        pool_scale=0.9,
        fog_density=0.28,
        sun_elevation=18,
        sun_azimuth=-25,
        camera_yaw=-65,
        camera_pitch=16,
        camera_distance=2900,
        show_station=True,
    ),
}
