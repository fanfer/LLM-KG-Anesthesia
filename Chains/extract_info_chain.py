from typing import List
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

class ExtractedInfo(BaseModel):
    """从用户输入中提取的信息。"""
    patient: str = Field(description="患者姓名")
    age: str = Field(description="患者年龄")
    surgery: str = Field(description="手术类型")
    anesthesia: str = Field(description="麻醉方式")
    additional_info: str = Field(description="其他相关信息")
    medical_history: List[str] = Field(description="病史信息列表", default_factory=list)
    medicine_taking: List[str] = Field(description="正在服用的药物列表", default_factory=list)

# 创建解析器
parser = PydanticOutputParser(pydantic_object=ExtractedInfo)

# 系统提示
system = """你是一个专业的医疗信息提取助手。你的任务是从用户输入中提取关键的医疗信息。

你必须严格按照以下JSON格式输出信息：
{format_instructions}

示例输出：
{{
    "patient": "张三",
    "age": "未知",
    "surgery": "未知",
    "anesthesia": "未知",
    "additional_info": "未知",
    "medical_history": [],
    "medicine_taking": []
}}

注意事项：
1. 必须使用JSON格式输出
2. 如果信息不存在，使用"未知"
3. 对于列表类型，如果没有信息则返回空列表[]
4. 不要添加额外的解释或编号
5. 确保JSON格式的正确性
"""

# 人类提示
human = """
当前已知信息：
{user_information}

新的用户输入：
{user_input}

请提取信息并以JSON格式返回。
"""

# 创建提示模板
prompt = ChatPromptTemplate.from_messages([
    ("system", system),
    ("human", human),
])

def get_extract_info_chain():
    """创建信息提取链。"""
    # llm = ChatOpenAI(
    #     model="gpt-4o",
    #     temperature=0.6
    # )
    llm = ChatOllama(
        model="qwen2.5:14b",
        temperature=0.6,
        base_url="http://222.20.98.121:11434",
    )
    
    # 将格式说明注入到提示中
    prompt_with_format = prompt.partial(
        format_instructions=parser.get_format_instructions()
    )
    
    # 创建链
    chain = prompt_with_format | llm | parser
    
    return chain