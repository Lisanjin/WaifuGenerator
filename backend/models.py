from typing import List, Optional, Any
from pydantic import BaseModel
from enum import Enum

class CharacterCard(BaseModel):
    name: str
    description: str
    personality: str
    scenario: str
    first_mes: str
    mes_example: str

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class ReferenceModel(BaseModel):
    id: Optional[str] = None 
    resource_type: str
    reliability_score: int
    resource_url: str 
    file_name: Optional[str] = None 

class CharacterModel(BaseModel):
    character_name: str
    character_aliases: List[str] = []
    source_work_name: str = ""
    source_work_aliases: List[str] = []
    user_requirement: str = ""
    reference: List[ReferenceModel] = []

class SubTaskResult(BaseModel):
    step_id: str
    title: str
    type: str 
    status: TaskStatus
    result_summary: Optional[str] = None
    detail: Any = None 
    reliability_score: int = 1 

class ProcessState(BaseModel):
    process_id: str
    is_finished: bool = False
    character_info: Optional[CharacterModel] = None
    sub_tasks: List[SubTaskResult] = []
    final_json: Optional[str] = None

class UpdateTaskRequest(BaseModel):
    process_id: str
    step_id: str
    new_summary: str

class GenerateRequest(BaseModel):
    process_id: str