from pydantic import BaseModel, ConfigDict, Field
from app.config import *

class SchedulePayload(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    columns: dict
    global_data: dict = Field(alias="global")
    file_name: str
    data_size: list[int]
    model: str
    stored_file: str
    stored_path: str
    uploaded_by: str | None = None

class PredictRequest(BaseModel):
    pickle_file: str
    features: list[float] | None = None
    inputs: dict | None = None
    threshold: float | None = DEFAULT_THRESHOLD
    positive_label: str | None = None