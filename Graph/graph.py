from typing import Literal
from langgraph.graph import StateGraph, START, END
from Graph.state import MedicalState
from Graph.nodes import (
    Entry_Information_Agent,
    Information_Agent,
    Entry_History_Agent,
    History_Agent,
    Entry_Risk_Agent,
    Risk_Agent,
    Extract_Info_Agent,
    Graph_QA_Agent,
    Analgesia_Agent,
    Entry_Analgesia_Agent,
    leave_history_agent
)
from Chains.sequence_primary_agent import Sequence_Primary_Assistant
from langchain_core.messages import ToolMessage,HumanMessage
from Graph.router import CompleteOrEscalate
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver

# 创建状态图
builder = StateGraph(MedicalState)


# 添加初始化节点
def initialize_state(state: MedicalState) -> dict:
    """初始化或确保状态包含所有必需的键。
    只在键不存在时才设置默认值。
    """
    # 创建默认值字典
    defaults = {
        "user_information": "暂无",
        "medical_history": [],
        "medicine_taking": [],
        "extract_info_result": {},
        "current_step": 0
    }
    
    # 只在键不存在时才使用默认值
    return_dict = {
        key: state.get(key, default)
        for key, default in defaults.items()
    }
    return return_dict

# 定义路由函数
def route_agent(state: MedicalState):
    """根据最后一条消息的工具调用决定路由。"""
    tool_calls = state["messages"][-1].tool_calls
    if not tool_calls:
        return END  # 如果没有工具调用，直接结束
    
    def check_complete_or_escalate(tool_call):
        # 处理parallel工具调用
        if tool_call.get("name") == "multi_tool_use.parallel":
            tool_uses = tool_call.get("args", {}).get("tool_uses", [])
            # 检查tool_uses中的每个工具调用
            return any(
                use.get("recipient_name") == CompleteOrEscalate.__name__ 
                for use in tool_uses
            )
        # 处理普通工具调用
        return tool_call.get("name") == CompleteOrEscalate.__name__
    
    # 检查所有工具调用
    did_cancel = any(check_complete_or_escalate(tc) for tc in tool_calls)
    
    if did_cancel:
        return "leave_skill"  # 通过leave_skill返回主助手
    

# 主助手的路由函数
def route_primary_assistant(state: MedicalState):
    """主助手的路由逻辑。"""
    # 首先检查是否需要结束
    route = tools_condition(state)
    if route == END:
        return END
    # 检查工具调用
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        tool_name = tool_calls[0]["name"]
        if tool_name == 'ToHistoryAgent':
            return "enter_history_taking"
        elif tool_name == 'ToRiskAgent':
            return "enter_risk_assessment"
        elif tool_name == 'ToAnalgesiaAgent':
            return "enter_analgesia"
    return END

# 定义leave_skill节点
def pop_dialog_state(state: MedicalState) -> dict:
    """退出当前技能，返回主助手。"""
    messages = []
    if state["messages"][-1].tool_calls:
        messages.append(
            ToolMessage(
                content="正在返回主任医生。请总结之前的对话并继续协助患者。",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        "dialog_state": "pop",
        "messages": messages,
    }

def route_to_workflow(
        state: MedicalState,
) -> Literal[
            "primary_assistant", 
            "risk_assessment",
            "verify_information",
            "history_taking",
            "analgesia"
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    if dialog_state[-1] == "history_taking":
        return ["history_taking","extract_info"]
    return dialog_state[-1]


# 添加所有节点
builder.add_node("initialize", initialize_state)
builder.add_node("primary_assistant", Sequence_Primary_Assistant)
builder.add_node("extract_info", Extract_Info_Agent)
builder.add_node("leave_skill", pop_dialog_state)

# 信息确认相关节点
builder.add_node("enter_verify_information", Entry_Information_Agent)
builder.add_node("verify_information", Information_Agent)

# 病史采集相关节点
builder.add_node("enter_history_taking", Entry_History_Agent)
builder.add_node("history_taking", History_Agent)
builder.add_node("leave_history_agent", leave_history_agent)

# 风险评估相关节点
builder.add_node("enter_risk_assessment", Entry_Risk_Agent)
builder.add_node("graph_qa", Graph_QA_Agent)
builder.add_node("risk_assessment", Risk_Agent)

# 添加镇痛分支
builder.add_node("analgesia", Analgesia_Agent)
builder.add_node("enter_analgesia", Entry_Analgesia_Agent)

# 添加边
# 1. 初始流程
builder.add_edge(START, "initialize")

# 2. 设置extract_info为并行节点
builder.add_edge(
    "enter_history_taking",
    "extract_info"
)

builder.add_conditional_edges("initialize", route_to_workflow, {
    "primary_assistant": "primary_assistant",
    "verify_information": "verify_information",
    "history_taking": "history_taking",
    "risk_assessment": "risk_assessment",
    "analgesia": "analgesia",
    "extract_info": "extract_info"
})

builder.add_edge(
    "extract_info",
    "leave_history_agent"
)

# 3. 主助手的条件边
builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    [
        "enter_verify_information",
        "enter_history_taking",
        "enter_risk_assessment",
        "enter_analgesia",
        END,
    ],
)

# 4. 信息确认流程
builder.add_edge("enter_verify_information", "verify_information")
builder.add_conditional_edges(
    "verify_information",
    route_agent,
    {
        "primary_assistant": "primary_assistant",
        "leave_skill": "leave_skill",
        END: END
    }
)

# 5. 病史采集流程
builder.add_edge("enter_history_taking", "history_taking")
builder.add_conditional_edges(
    "history_taking",
    route_agent,
    {
        "primary_assistant": "primary_assistant",
        "leave_skill": "leave_skill",
        END: END
    }
)

# 添加镇痛相关的边
builder.add_edge("enter_analgesia", "analgesia")
builder.add_conditional_edges(
    "analgesia",
    route_agent,
    {
        "primary_assistant": "primary_assistant",
        "leave_skill": "leave_skill",
        END: END
    }
)

# 6. 风险评估流程
builder.add_edge("enter_risk_assessment", "graph_qa")
builder.add_edge("graph_qa", "risk_assessment")
builder.add_conditional_edges(
    "risk_assessment",
    route_agent,
    {
        "primary_assistant": "primary_assistant",
        "leave_skill": "leave_skill",
        END: END
    }
)

# 7. leave_skill返回主助手
builder.add_edge("leave_skill", "primary_assistant")

# 编译图
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

