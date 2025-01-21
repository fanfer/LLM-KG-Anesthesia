import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from nano_graphrag import GraphRAG, QueryParam

# 初始化LightRAG
WORKING_DIR = "./dickens"

ragllm = GraphRAG(
    working_dir=WORKING_DIR,
)

system_prompt = """
作为麻醉风险分析专家，请根据以下患者信息在知识图谱中获取风险评估：

<患者信息>
{user_information}

<病史>
{medical_history}

<用药情况>
{medicine_taking}

重点关注：
1. 患者的既往病史可能导致的手术并发症风险
2. 患者目前用药情况，指导患者进行术前停药
3. 请确保从知识图谱中提取所有完整的风险信息
4. 使用简体中文回复
"""

graph_qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ]
)

def get_graph_qa_chain():
    def query_knowledge_graph(inputs: dict):
        """使用GraphRAG查询知识图谱"""
        # 首先使用prompt模板格式化输入
        prompt = graph_qa_prompt.format_messages(**inputs)
        print(prompt)
        prompt_text = prompt[0].content if prompt else ""
        
        # 使用LightRAG进行查询
        response = ragllm.query(
            prompt_text,
            param=QueryParam(
                mode="global",
                top_k=60,
            )
        )
        
        # 返回完整的状态
        return {
            "messages": inputs.get("messages", []),
            "risk_analysis": response,
            "user_information": inputs.get("user_information", ""),
            "medical_history": inputs.get("medical_history", []),
            "medicine_taking": inputs.get("medicine_taking", [])
        }
    
    # 使用RunnableLambda包装查询函数
    return RunnableLambda(query_knowledge_graph)

