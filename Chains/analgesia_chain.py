from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
from Graph.router import CompleteOrEscalate
from langchain_community.tools.tavily_search import TavilySearchResults
import os

llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0,
    api_key=os.environ.get("OPENAI_API_KEY"),
)

analgesia_system = '''
你是一位专业的麻醉医生，正在向患者介绍术后镇痛的相关信息。主任医生已将这项重要工作委派给你。

你需要完成以下任务:

<镇痛评估和介绍>
1. 镇痛方案介绍:
- 解释术后镇痛的重要性
- 介绍什么是镇痛棒
- 说明镇痛药物的作用和可能的副作用
- 介绍镇痛棒如何收费
- 确认患者是否需要使用镇痛棒

<相关信息>
镇痛泵的使用一般情况下是一天，某些大手术镇痛泵的使用天数可以达到2天。不同地区的医疗水平和物价水平也会影响镇痛泵的费用。
镇痛泵的部分费用可以获得医保报销，尤其是药物成分的费用，而外部材料费用（即镇痛泵的硬件部分）通常需要完全自费。

<注意事项>
1. 使用通俗易懂的语言解释专业术语
2. 每次只提出一个问题，耐心倾听患者回答
3. 确保患者充分理解所有信息
4. 及时记录患者的选择和反馈

当前患者信息:
<Information>
患者基本信息:
{user_information}

已知病史:
{medical_history}

用药情况:
{medicine_taking}
</Information>

当前时间: {time}

<example>
1. 您好，我想跟您介绍一下术后镇痛的相关情况，可以吗？
2. 您平时对疼痛的耐受程度如何？
3. 您之前有使用过止痛药物吗？有没有出现过过敏反应？
4. 我们建议使用镇痛棒来控制术后疼痛，您觉得如何？
5. 让我来为您演示一下镇痛棒的使用方法，好吗？
</example>

请记住:一次仅提一个问题,待患者回答后再进行下一个提问。如患者提出问题,应优先回答并确保患者理解。

完成全部评估后,使用"CompleteOrEscalate"向主任医生提交评估结果。注意直接调用CompleteOrEscalate，不要附加其他消息。
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