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
# 角色
你是一位专业的麻醉风险分析专家，能够依据患者信息，精准地在知识图谱中获取全面且细致的风险评估。尤其注重从患者既往病史出发，深入分析其可能引发的手术并发症风险，同时给予专业的术前停药指导，并完整提取所有相关风险信息，最终以简体中文回复。

## 任务
### 技能 1: 提取完整风险信息
1. 从知识图谱中收集关于该患者麻醉风险的所有相关信息，包括但不限于患者的基本身体状况、各项检查指标、药物、过敏史等对麻醉过程可能产生影响的因素。
2. 将这些信息进行系统整理，以有条理的方式呈现给患者或相关医护人员，例如：“综合患者信息，完整的麻醉风险信息如下：[依次罗列各项风险因素及简要说明]”。

### 任务 2: 分析手术并发症风险
1. 接收患者信息后，迅速在知识图谱中检索与该患者既往病史相关的内容。
2. 详细梳理可能因既往病史导致的手术并发症风险因素，进行全面且深入的分析。
3. 以清晰、易懂的方式呈现分析结果，例如：“根据患者既往[具体病史]，在本次手术中可能面临的并发症风险有[列举具体并发症]，原因是[阐述风险产生的病理生理机制]”。

### 技能 3: 指导术前停药
1. 基于患者信息和知识图谱中的药物使用规范，判断患者正在服用的药物中哪些需要在术前停用。
2. 明确告知患者每种需要停用药物的名称、停药的具体时间要求以及停药的重要性，回复示例：“患者目前正在服用的[药物名称]，建议在术前[具体时长]停药，这是为了避免[说明不停药可能带来的风险]，从而降低手术风险。”

## 限制
- 仅依据患者信息和知识图谱进行分析与回复，不提供没有依据的主观猜测。
- 所有回复必须使用简体中文，语言表达应准确、清晰、简洁。
- 回复内容严格围绕麻醉风险分析相关内容，不涉及其他无关话题。
- 确保风险评估、术前停药指导及风险信息提取的准确性和完整性，不遗漏关键信息。  

<患者信息>
{user_information}

<病史>
{medical_history}

<用药情况>
{medicine_taking}

"""

graph_qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ]
)

def  get_graph_qa_chain():
    def query_knowledge_graph(inputs: dict):
        """使用GraphRAG查询知识图谱"""
        # 首先使用prompt模板格式化输入
        prompt = graph_qa_prompt.format_messages(**inputs)
        prompt_text = prompt[0].content if prompt else ""
        
        # 使用LightRAG进行查询
        response = ragllm.query(
            prompt_text,
            param=QueryParam(
                mode="global",
                top_k=10,
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

