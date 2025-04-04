from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
from Graph.router import CompleteOrEscalate
from langchain_community.tools.tavily_search import TavilySearchResults
import os
from langchain_ollama import ChatOllama
from .tts_stream_handler import tts_handler

llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0,
    api_key=os.environ.get("OPENAI_API_KEY"),
    streaming=True,  # 启用流式输出
    callbacks=[tts_handler],  # 添加TTSStreamHandler作为回调
)
# llm = ChatOllama(
#     model="llama3.3:70b",
#     temperature=0.6,
#     base_url="http://222.20.98.120:11434",
#     streaming=True,
#     callbacks=[tts_handler]
# )

analgesia_system = '''
你是一位专业的麻醉医生，正在向患者介绍术后镇痛的相关信息。主任医生已将这项重要工作委派给你。

你需要完成以下任务:

<镇痛评估和介绍>
1. 镇痛方案介绍:
- 解释术后镇痛的重要性
- 介绍什么是镇痛泵、介绍镇痛泵的费用
- 说明镇痛泵的作用和可能的副作用
- 确认患者是否需要使用镇痛泵

<相关信息>
镇痛泵的使用一般情况下是一天，某些大手术镇痛泵的使用天数可以达到2天。不同地区的医疗水平和物价水平也会影响镇痛泵的费用。
镇痛泵的部分费用可以获得医保报销，尤其是药物成分的费用，而外部材料费用（即镇痛泵的硬件部分）通常需要完全自费。
耳鼻喉，口腔，头颅，甲状腺手术不适用镇痛泵，容易引起术后不良反应，不推荐使用。

<注意事项>
1. 使用通俗易懂的语言解释专业术语
2. 每次只提出一个问题，耐心倾听患者回答
3. 确保患者充分理解所有信息
4. 最后一定要提问：是否愿意医保报销范围以外的药物或者耗材？

当前患者信息:
<Information>
患者基本信息:
{user_information}

已知病史:
{medical_history}

用药情况:
{medicine_taking}
</Information>

请记住:一次仅提一个问题,待患者回答后再进行下一个提问。如患者提出问题,应优先回答并确保患者理解。

完成全部评估后,使用"CompleteOrEscalate"向主任医生提交评估结果。注意只能单独调用CompleteOrEscalate，不能在回答的同时调用。
'''


analgesia_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", analgesia_system),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

def get_analgesia_chain():
    analgesia_tools = [TavilySearchResults(max_results=2)]
    llm_with_tools = llm.bind_tools(analgesia_tools + [CompleteOrEscalate])
    analgesia_chain = analgesia_prompt | llm_with_tools
    return analgesia_chain
