from pydantic import BaseModel


class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = True
    reason: str

    class Config:
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "缺少必要的信息，请向直接患者提问，获取该部分信息。",
            },
            "example 2": {
                "cancel": True,
                "reason": "我已经完成了所有提问，请交由其他助手继续对话。",
            },
        }