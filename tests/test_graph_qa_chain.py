# tests/test_graph_qa_chain.py
import os
import sys
import pytest

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
    

if __name__ == "__main__":
    test_graph_qa_chain_basic()