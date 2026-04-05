from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    display_name: str
    description: str
