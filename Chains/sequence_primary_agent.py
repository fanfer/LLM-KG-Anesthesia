from typing import List, Dict, Any
from langchain_core.messages import AIMessage, ToolMessage
import json

def create_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """创建工具调用对象"""
    return {
        "id": "call_" + name.lower(),
        "name": name,
        "type": "function",
        "args": args
    }

def Sequence_Primary_Assistant(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    按顺序执行的Primary Assistant。
    按固定顺序调用ToHistoryAgent，不使用LLM。
    """
    try:
        user_information = state.get('user_information', '')
        current_step = state.get('current_step', 0)  # 使用current_step跟踪进度
        
        # 定义固定的调用序列
        steps = [
            {
                "name": "ToHistoryAgent",
                "args": {
                    "name": "患者",
                    "information": user_information,
                    "request": "请收集患者的基础病史信息。",
                    "agent_id": 1
                }
            },
            {
                "name": "ToHistoryAgent",
                "args": {
                    "name": "患者",
                    "information": user_information,
                    "request": "请收集患者的手术经历。",
                    "agent_id": 2
                }
            },
            {
                "name": "ToHistoryAgent",
                "args": {
                    "name": "患者",
                    "information": user_information,
                    "request": "请评估患者的当前状况。",
                    "agent_id": 3
                }
            },
            {
                "name": "ToAnalgesiaAgent",
                "args": {
                    "name": "患者",
                    "information": user_information,
                }
            },
            {
                "name": "ToRiskAgent",
                "args": {
                    "name": "患者",
                    "information": user_information,
                    "request": "请告知患者手术风险。",
                }
            },

        ]
        
        # 如果已经完成所有步骤，返回空消息
        if current_step >= len(steps):
            message = AIMessage(
                content="谢谢您的配合，术前谈话已完成。请你在术前谈话记录表中签字确认。",
            )
            return {
                "messages": message,
                "current_step": current_step
            }
        
        # 获取当前步骤
        current_action = steps[current_step]
        
        # 创建工具调用
        tool_call = create_tool_call(
            current_action["name"],
            current_action["args"]
        )
        
        # 创建消息
        message = AIMessage(
            content="",
            tool_calls=[tool_call]
        )
        
        # 返回结果，包括更新后的current_step
        return {
            "messages": message,
            "current_step": current_step + 1
        }
        
    except Exception as e:
        print(f"序列执行助手处理时出错: {str(e)}")
        return {
            "messages": [],
            "current_step": 0
        } 