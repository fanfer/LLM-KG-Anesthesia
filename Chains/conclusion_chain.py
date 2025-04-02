from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
import os
from Graph.router import CompleteOrEscalate
from .tts_stream_handler import tts_handler


llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0,
    api_key=os.environ.get("OPENAI_API_KEY"),
)
# llm = ChatOllama(
#     model="llama3.3:70b",
#     temperature=0.6,
#     base_url="http://222.20.98.121:11434",
#     streaming=True,
#     callbacks=[tts_handler]
# )

conclusion_system = '''
# 角色
你是一个专门用于根据对话和信息，总结患者信息和麻醉风险结论的医疗助手。
<Information>
{user_information}
</Information>。

<RiskAnalysis>
{risk_analysis}
</RiskAnalysis>

限制：
1. 不能让患者知晓你的存在，不要提及主治医生，不要引导患者提问。
2. 总结患者信息和麻醉风险结论，以简体中文回复, 限制在200字以内。
'''

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", conclusion_system),
        ("placeholder", "{messages}"),
    ]
)

def get_conclusion_chain():
    conclusion_chain = prompt | llm
    return conclusion_chain