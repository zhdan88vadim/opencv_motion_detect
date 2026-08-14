from pydantic import BaseModel


class ROISettings(BaseModel):
    x: float
    y: float
    width: float
    height: float
    enabled: bool = True


class CameraROIRequest(BaseModel):
    camera_name: str
    roi: ROISettings
