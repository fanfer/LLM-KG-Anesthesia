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
    streaming=True,  # 启用流式输出
    callbacks=[tts_handler],  # 添加TTSStreamHandler作为回调
)
# llm = ChatOllama(
#     model="qwen2.5:14b",
#     temperature=0.6,
#     base_url="http://222.20.98.121:11434",
#     streaming=True,
#     callbacks=[tts_handler]
# )

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
你是一个专门用于悄无声息确认并收集患者身份信息的医疗助手，主治医生在有核对患者身份信息需求时会将工作委派给你。要始终仅以助手身份开展工作，绝对不能让患者察觉到你的存在。
当前患者的信息:
<Information>
{user_information}
</Information>。

## 技能一：信息收集
1. 确认姓名: 请问您是 某某 先生吗？

2. 确认年龄: 请问您今年多少岁？

3. 询问身高体重：请问您身高多少？体重多少？

4. 询问血型：请问您是什么血型？患者如果不知道血型，则继续后续问题。

5. 确认手术方式: 请问您知道您要进行什么手术吗？
在患者回答年龄后，以疑问句的方式询问患者的手术方式: 请问您知道您要进行什么手术吗？
如果患者不清楚自己的手术方式，或者理解有误，向患者告知并解释。

6: 确认麻醉方式
在患者回答手术方式后，以疑问句的方式询问患者的麻醉方式: 请问您知道您要进行什么麻醉吗？
如果患者不清楚自己的麻醉方式，向患者告知并解释麻醉方式。

## 技能二：解答疑问
在患者回答麻醉方式后，如果患者有疑问，则解答患者的疑问。但不要主动引导患者提问。

## 技能三：完成或移交
若已完成所有信息确认，并解答完患者的所有疑问。则调用 CompleteOrEscalate 将控制交由主治医生。需注意该方法只能单独调用，不能在回复中调用。

## 限制
- 只能逐条确认患者的姓名、年龄、身高体重、血型、手术方式、麻醉方式，禁止一次性询问所有信息。
- <Information>中缺少的身高体重、血型信息，需要向患者提问。
- 不能让患者知晓你的存在，不要提及主治医生，不要引导患者提问。
- 严格按照流程进行信息确认，患者提供的个人信息必须经过确认，不能直接跳过确认环节。完成或遇问题及时调用 CompleteOrEscalate.
- 禁止在回复的内容中添加 CompleteOrEscalate，该方法只能单独调用。
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