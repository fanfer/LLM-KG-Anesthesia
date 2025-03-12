# tests/test_graph_qa_chain.py
import os
import sys
import pytest
import asyncio
import uuid

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Chains.graph_qa_chain import get_graph_qa_chain
from langchain_core.messages import HumanMessage, AIMessage

def test_graph_qa_chain_basic():
    """测试GraphQA链的基本功能"""
    # 准备测试数据
    test_data = {
        "messages": [
            HumanMessage(content="请分析病人的风险。"),
        ],
        "user_information": """
        姓名: 张三
        年龄: 45
        手术: 腹腔镜胆囊切除术
        麻醉方式: 全身麻醉
        其他信息: 有轻度高血压
        """,
        "medical_history": [
            "高血压病史2年",
            "服用降压药物",
            "无其他重大疾病"
        ],
        "medicine_taking": [
            "缬沙坦 80mg 每日一次",
            "阿司匹林 100mg 每日一次"
        ]
    }
    
    # 获取chain
    chain = get_graph_qa_chain()
    
    # 执行chain
    result = chain.invoke(test_data)
    print(result)
    

# 添加流式传输测试函数
async def test_graph_qa_chain_stream():
    # 测试数据
    test_data = {
        "messages": [
            HumanMessage(content="请分析病人的风险。"),
        ],
        "user_information": """
        姓名: 张三
        年龄: 45
        手术: 腹腔镜胆囊切除术
        麻醉方式: 全身麻醉
        其他信息: 有轻度高血压
        """,
        "medical_history": [
            "高血压病史2年",
            "服用降压药物",
            "无其他重大疾病"
        ],
        "medicine_taking": [
            "缬沙坦 80mg 每日一次",
            "阿司匹林 100mg 每日一次"
        ]
    }
    
    # 获取chain
    chain = get_graph_qa_chain()
    
    # 配置
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4())
        }
    }
    
    print("开始流式输出...")
    
    # 方法1：使用astream_events方法流式输出
    async for event in chain.astream_events(
        test_data,
        config,
        version="v2"  # 使用v2版本的事件格式
    ):
        # 检查是否是聊天模型流式事件
        if event.get("event") == "on_chat_model_stream":
            data = event.get("data", {})
            chunk = data.get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                print(f"{chunk.content}", end="", flush=True)
    
    print("\n\n流式输出完成")

# 添加同步流式传输测试函数
def test_graph_qa_chain_stream_sync():
    # 测试数据
    test_data = {
        "messages": [
            HumanMessage(content="请分析病人的风险。"),
        ],
        "user_information": """
        姓名: 张三
        年龄: 45
        手术: 腹腔镜胆囊切除术
        麻醉方式: 全身麻醉
        其他信息: 有轻度高血压
        """,
        "medical_history": [
            "高血压病史2年",
            "服用降压药物",
            "无其他重大疾病"
        ],
        "medicine_taking": [
            "缬沙坦 80mg 每日一次",
            "阿司匹林 100mg 每日一次"
        ]
    }
    
    # 获取chain
    chain = get_graph_qa_chain()
    
    # 配置
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4())
        }
    }
    
    print("开始同步流式输出...")
    
    # 使用stream方法流式输出
    for chunk in chain.stream(
        test_data,
        config,
        stream_mode="values"  # 使用values模式
    ):
        if isinstance(chunk, dict) and "messages" in chunk:
            for message in chunk["messages"]:
                if hasattr(message, "content") and message.content:
                    print(f"{message.content}", end="", flush=True)
    
    print("\n\n同步流式输出完成")

if __name__ == "__main__":
    print("请选择测试方法：")
    print("1. 基本测试（非流式）")
    print("2. 异步流式测试")
    print("3. 同步流式测试")
    
    choice = input("请输入选择（1-3）：")
    
    if choice == "1":
        test_graph_qa_chain_basic()
    elif choice == "2":
        asyncio.run(test_graph_qa_chain_stream())
    elif choice == "3":
        test_graph_qa_chain_stream_sync()
    else:
        print("无效选择，默认使用同步流式测试")
        test_graph_qa_chain_stream_sync()