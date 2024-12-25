from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

import os
from Graph.router import CompleteOrEscalate


llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0,
    max_tokens=150,  # 限制输出约100字
    api_key=os.environ.get("OPENAI_API_KEY"),
)

class info_with_conclusion(BaseModel):
    name: str = Field(description="患者的姓名。")
    verified_info: str = Field(description="已经确认过的患者的个人基础信息。")
    request: str = Field(description="需要向患者提问，进一步获取的个人基础信息。")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "张三",
                "information": "张三，身高170cm，需要进行心脏搭桥手术",
                "request": "请问您要进行的是全身麻醉吗？"
            }
        }


information_system = '''
你是一个专门用于确认患者身份信息的医疗助手，主治医生在需要核对患者身份信息的时候将工作委派给你，\n
请注意你仅作为助手存在，不要让患者知晓你的存在。\n
\n\n当前患者的信息:\n<Information>\n{user_information}\n</Information>\n
你需要通过设问句的方式，逐条确认患者的姓名、年龄、手术、麻醉方式。禁止一次性询问所有信息。\n
如果你已经完成所有信息确认，或者缺少部分信息，需要由主治医生提供，请通过调用 ###CompleteOrEscalate### 将控制交由主治医生。\n
不要浪费患者的时间，不要编造无效的工具或者功能。\n\n
example:\n
1."请问您是张三先生吗？"\n
2."请问您是要进行胃部肿瘤切除手术吗？"\n
3."请问您是要进行全身麻醉吗？"
'''

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", information_system),
        ("placeholder", "{messages}"),
    ]
)

def get_information_chain():
    llm_with_tools = llm.bind_tools([CompleteOrEscalate])
    information_chain = prompt | llm_with_tools
    return information_chain