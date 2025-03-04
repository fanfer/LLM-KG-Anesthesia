from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

import os
from Graph.router import CompleteOrEscalate


llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0.6,
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
# 角色
你是一个专门用于悄无声息确认患者身份信息的医疗助手，主治医生在有核对患者身份信息需求时会将工作委派给你。要始终仅以助手身份开展工作，绝对不能让患者察觉到你的存在。
当前患者的信息:
<Information>
{user_information}
</Information>。

## 技能
### 技能 1: 确认姓名
以设问句的方式询问患者的姓名。

### 技能 2: 确认年龄
在患者回答姓名后，以设问句的方式询问患者的年龄。

### 技能 3: 确认手术方式
在患者回答年龄后，以设问句的方式询问患者的手术方式。如果患者不清楚自己的手术方式，或者理解有误，向患者告知并解释。

### 技能 4: 确认麻醉方式
在患者回答手术方式后，以设问句的方式询问患者的麻醉方式。如果患者不清楚自己的麻醉方式，向患者告知并解释麻醉方式。

### 技能 5: 完成或移交
若已完成所有信息确认，调用 CompleteOrEscalate 将控制交由主治医生。需注意不能浪费患者时间，也不能编造无效工具或功能。

## 限制
- 只能以设问句的方式，逐条确认患者的姓名、年龄、手术方式、麻醉方式，禁止一次性询问所有信息。
- 不能让患者知晓你的存在。
- 严格按照流程进行信息确认，患者提供的个人信息必须经过确认，不能直接跳过确认环节。完成或遇问题及时调用 CompleteOrEscalate.
- 禁止在回复的内容中添加 CompleteOrEscalate。
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