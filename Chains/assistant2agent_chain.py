import os
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticToolsParser
from langchain.schema import AIMessage
from langchain.schema.runnable import RunnableSequence, RunnableLambda


llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0,
    api_key=os.environ.get("OPENAI_API_KEY"),
)

class ToInformationAgent(BaseModel):
    """将工作转交给专门的医生以核实患者的个人信息。"""
    name: str = Field(
        description="患者的姓名。"
    )
    information: str = Field(
        description="患者的个人基础信息，和已经提供的其他病历中的信息、其他相关信息。"
    )
    request: str = Field(
        description="需要向患者提问，进一步获取的个人基础信息。"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "张三",
                "information": "张三，身高170cm，体重80kg，无吸烟酗酒史，患有糖尿病，无其他基础疾病，需要进行心脏搭桥手术，进行全身麻醉。",
                "request": "请向患者提问，获取患者的年龄、性别。"
            }
        }

class ToHistoryAgent(BaseModel):
    """将工作转交给专门的医生以了解患者的既往病史。"""
    name: str = Field(
        description="患者的姓名。"
    )
    information: str = Field(
        description="已知的患者的个人基础信息，和已经提供的其他病历中的信息、其他相关信息。"
    )
    request: str = Field(
        description="需要向患者提问，进一步获取的既往病史信息。"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "张三",
                "information": "张三，男，59岁，身高170cm，体重80kg，无吸烟酗酒史，患有糖尿病，无其他基础疾病，需要进行心脏搭桥手术，进行全身麻醉。",
                "request": "请向患者提问，明确患者是否能正常活动，是否有家族遗传病史。"
            }
        }

class ToRiskAgent(BaseModel):
    """将工作转交给专门的医生以对患者进行术前评估。"""
    name: str = Field(
        description="患者的姓名。"
    )
    information: str = Field(
        description="已知的患者的个人基础信息，和已经提供的其他病历中的信息、其他相关信息。"
    )
    request: str = Field(
        description="需要向患者提问，进一步获取的术前准备信息。"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "张三",
                "information": "张三，男，59岁，身高170cm，体重80kg，无抽烟酗酒史，患有糖尿病，无其他基础疾病，需要进行心脏搭桥手术，进行全身麻醉。已经禁食24小时。",
                "request": "请向患者提问，明确患者是否有牙齿松动和运动功能障碍。"
            }
        }

class ToAnesthesiaAgent(BaseModel):
    """将工作转交给专门的医生以对患者进行术前评估。"""
    name: str = Field(
        description="患者的姓名。"
    )
    information: str = Field(
        description="已知的患者的个人基础信息，和已经提供的其他病历中的信息、其他相关信息。"
    )
    request: str = Field(
        description="需要向患者告知的麻醉手术过程中的风险问题和可能采取的措施。"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "张三",
                "information": "张三，男，59岁，身高170cm，体重80kg，无吸烟酗酒史，患有糖尿病，无其他基础疾病，需要进行心脏搭桥手术，进行全身麻醉。已经禁食24小时。",
                "request": "请向患者告知，麻醉过程中可能出现窒息。"
            }
        }

system = '''你是一位主治医生，负责管理患者的诊疗流程。你的主要职责是根据患者的需求和情况，将具体任务分配给专门的医疗助手。注意你不直接与患者对话，而是通过函数调用来分配任务。

你可以通过以下函数调用来分配任务:
- ToInformationAgent: 用于确认和核实患者的基本信息
- ToHistoryAgent: 用于收集患者的病史和既往史
- ToRiskAgent: 用于评估手术风险并告知患者
- ToAnesthesiaAgent: 用于评估麻醉风险并告知患者

重要提示:
1. 每次只能调用一个函数分配一项任务
2. 不要向患者提及有不同的医疗助手
3. 一般应该先核实基本信息，然后采集患者的病史和既往史，根据患者的病史和既往史，评估手术风险，然后告知患者麻醉风险。

当前患者信息:
<Information>
{user_information}
</Information>

请仔细倾听患者的需求,并通过合适的函数调用来分配相应的任务。'''

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("placeholder", "{messages}"),
    ]
)

def get_primary_assistant_chain():
    llm_with_tools = llm.bind_tools([ToInformationAgent, ToHistoryAgent, ToRiskAgent, ToAnesthesiaAgent])
    
    def process_response(result):
        """处理LLM响应，确保工具调用的正确处理"""
        if isinstance(result, list) and len(result) > 0:
            # 如果是列表，取第一个元素
            result = result[0]
            
        if hasattr(result, 'tool_calls') and result.tool_calls:
            # 只保留第一个工具调用
            tool_call = result.tool_calls[0]
            # 创建新的AIMessage，只包含第一个工具调用
            return AIMessage(
                content=result.content if hasattr(result, 'content') else "",
                tool_calls=[tool_call]
            )
        return result
    
    # 使用pipe方法构建chain
    chain = (prompt | llm_with_tools).pipe(process_response)
    
    return chain
