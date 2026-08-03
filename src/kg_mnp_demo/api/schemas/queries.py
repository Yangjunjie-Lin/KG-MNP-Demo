from pydantic import BaseModel


class CompetencyExecuteRequest(BaseModel):
    case_id: str
