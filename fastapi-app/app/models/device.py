from pydantic import BaseModel


class Camera(BaseModel):
    id: str
    name: str
    online: bool | None = None


class Group(BaseModel):
    id: str
    name: str
