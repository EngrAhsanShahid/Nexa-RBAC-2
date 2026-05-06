from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

class Alert_ws_schema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    alert_id : str 
    tenant_id : str
    camera_id : str
    severity: str
    status: str
    label: str
    date: str
    time: str
