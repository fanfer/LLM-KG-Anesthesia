import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from lightrag import LightRAG, QueryParam
from lightrag.llm import gpt_4o_complete

# 初始化LightRAG
WORKING_DIR = "./dickens"

ragllm = LightRAG(
    working_dir=WORKING_DIR,
    llm_model_func=gpt_4o_complete,
    llm_model_kwargs={
        "base_url": os.environ.get("OPENAI_API_BASE"), 
        "api_key": os.environ.get("OPENAI_API_KEY")
    },
)

system_prompt = """
作为麻醉风险分析专家，请分析以下患者的麻醉风险：

<患者信息>
{user_information}

<病史>
{medical_history}

<用药情况>
{medicine_taking}

注意：
1. 重点关注与患者具体情况相关的风险
2. 评估要基于实际医学证据
3. 信息要便于后续与患者沟通
"""

graph_qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ]
)

def get_graph_qa_chain():
    def query_knowledge_graph(inputs: dict):
        """使用LightRAG查询知识图谱"""
        # 首先使用prompt模板格式化输入
        prompt = graph_qa_prompt.format_messages(**inputs)
        print(prompt)
        print(os.environ.get("OPENAI_API_BASE"))
        print(os.environ.get("OPENAI_API_KEY"))
        prompt_text = prompt[0].content if prompt else ""
        
        # 使用LightRAG进行查询
        response = ragllm.query(
            prompt_text,
            param=QueryParam(
                mode="hybrid",
                top_k=60,
                max_token_for_text_unit=4000,
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

