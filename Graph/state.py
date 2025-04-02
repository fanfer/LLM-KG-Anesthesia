from typing import Annotated, List, Literal, Optional, TypedDict
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages

def add_string_history(existing_history: set[str], new_entries: list[str]) -> set[str]:
    """
    Adds new medical history entries to the existing history if they are not already present.

    :param existing_history: The current set of medical history entries.
    :param new_entries: The new entries to be added.
    :return: The updated set of medical history entries.
    """
    return existing_history.union(new_entries)

# 定义状态 跟踪消息列表
def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]

class MedicalState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        messages: message list
        patient: patient's name
        user_information: user information
        medical_history: the medical history of patient
        medicine_taking: what medicine the patient is taking 
        prompt: prompt template object
        prompt_with_context: prompt template with context from vector search
        extract_info_result: result from extract info node
    """
    messages: Annotated[list[AnyMessage], add_messages]
    patient: str
    user_information: str
    medical_history: Annotated[set[str], add_string_history]
    medicine_taking: Annotated[set[str], add_string_history]
    graph_qa_result: str
    prompt: object
    prompt_with_context: object
    extract_info_result: dict
    dialog_state: Annotated[
        list[
            Literal[
                "primary_assistant", 
                "risk_assessment",
                "history_taking",
                "verify_information",
                "analgesia"
            ]
        ],
        update_dialog_stack,
    ]
    agent_id: int
    current_step: int 
    graph_is_qa: bool
    session_id: str
    risk_count: int = 0

class InputState(TypedDict):
    messages: Annotated[list[AnyMessage],add_messages]
    
