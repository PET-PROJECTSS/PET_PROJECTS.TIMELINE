from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import SCHEMA_VERSION


class Viewport(BaseModel):
    panX: float = 0
    panY: float = 0
    scale: float = Field(default=1, ge=0.1, le=10)


class Substep(BaseModel):
    id: str
    title: str = ""
    done: bool = False


class Node(BaseModel):
    id: str
    x: float
    y: float
    width: float = Field(default=320, ge=100, le=5000)
    height: float = Field(default=200, ge=100, le=5000)
    title: str = ""
    type: str = "Path"
    done: bool = False
    note: str = ""
    due: str = ""
    duration: str = ""
    substeps: list[Substep] = []

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in ("Path", "Goal"):
            raise ValueError("node.type должен быть Path или Goal")
        return v

    @field_validator("substeps")
    @classmethod
    def check_substeps(cls, v: list[Substep], info) -> list[Substep]:
        if info.data.get("type") == "Goal" and v:
            raise ValueError("Goal-узел не может содержать подэтапы")
        ids = [step.id for step in v]
        if len(ids) != len(set(ids)):
            raise ValueError("В узле дублируются id подэтапов")
        return v


class Link(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    from_: str = Field(alias="from")
    to: str
    label: str = ""


class RoadmapData(BaseModel):
    uid: int = 0
    schema_version: int = SCHEMA_VERSION
    nodes: list[Node] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    viewport: Viewport = Field(default_factory=Viewport)

    @model_validator(mode="after")
    def check_graph(self):
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("В payload дублируются id узлов")
        id_set = set(ids)
        incoming: dict[str, int] = {}
        for link in self.links:
            if link.from_ not in id_set:
                raise ValueError(f"Связь {link.id} ссылается на несуществующий узел {link.from_}")
            if link.to not in id_set:
                raise ValueError(f"Связь {link.id} ссылается на несуществующий узел {link.to}")
            incoming[link.to] = incoming.get(link.to, 0) + 1
        for node in self.nodes:
            if node.type == "Goal" and incoming.get(node.id, 0) > 1:
                raise ValueError(f"К Goal-узлу {node.id} ведёт более одной связи")
        return self


class RoadmapPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any]
    base_version: int | None = None

    @field_validator("payload")
    @classmethod
    def check_payload(cls, v: dict[str, Any]) -> dict[str, Any]:
        RoadmapData.model_validate(v)
        return v


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)
