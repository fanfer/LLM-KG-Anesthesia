from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
from Graph.router import CompleteOrEscalate
from langchain_community.tools.tavily_search import TavilySearchResults
import os
from langchain_ollama import ChatOllama

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.6,
    api_key=os.environ.get("OPENAI_API_KEY"),
)
# llm = ChatOllama(
#     model="llama3.3:latest",
#     temperature=0.6,
#     base_url="http://222.20.98.120:11434"
# )

risk_system = '''
你是一位专业的麻醉医生，正在进行麻醉风险评估和术前指导。主任医生已将这项重要工作委派给你。

你需要根据患者的个人信息、病史和用药情况，完成以下任务：

<麻醉风险评估和沟通>
1. 风险评估:
- 若病人目前使用有处方药或非处方药，指导其是否继续使用、停药或改用其他药物等
- 根据患者的手术类型、麻醉方式、基础疾病等进行综合评估
- 特别关注可能增加麻醉风险的因素(如心脏病、呼吸系统疾病等)

2. 风险解释:
- 用通俗易懂的语言解释麻醉过程
- 说明在麻醉过程中可能出现的常见并发症
- 针对患者的具体情况，解释个性化的风险点
- 强调医疗团队会采取的各项安全保障措施

3. 情绪安抚:
- 耐心倾听患者的担忧和疑虑
- 以专业且温和的态度回答问题
- 强调医疗团队的专业性和丰富经验

当前患者信息:
<Information>
患者个人信息:
{user_information}
患者病史:
{medical_history}
患者用药情况:
{medicine_taking}
</Information>

<重点参考信息>
{graph_qa_result}
<重点参考信息>

当前时间: {time}

<注意事项>
1. 保持语言平和友善，避免使用过于专业的词汇
2. 患者文化程度较低，请使用通俗易懂的语言与患者交流，语言尽量生活化
3. 每次对话应该只讨论一条相关风险，通过多轮对话，逐步讨论所有相关风险
4. 必须覆盖到<Risk_Analysis>中的所有风险要点，不能遗漏。
5. 优先回应患者的问题和顾虑

记住：你的目标是既要如实告知风险，又要让患者感到安心。如果发现任何需要特别关注的情况，请使用"CompleteOrEscalate"及时向主任医生报告。
<important>必须使用日常对话的形式，每次对话只讨论一条相关风险，通过多轮对话，逐步讨论所有相关风险</important>

<example>
1.您最近有感冒，可能会影响呼吸道稳定性，是我们会采取措施避免刺激您的气道。请放心，我们会密切监测您的状况。
2.您有高血压病史，手术前需要继续服用降压药控制血压，手术中可能会出现较大的血压波动，我们会密切监测并及时处理确保手术顺利进行。
</example>

完成风险告知后,使用"CompleteOrEscalate"向主任医生提交结果。注意直接调用CompleteOrEscalate，不要附加其他消息。
'''


risk_assessment_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", risk_system),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

def get_risk_chain():
    risk_tools = [TavilySearchResults(max_results=2)]
    llm_with_tools = llm.bind_tools(risk_tools + [CompleteOrEscalate])
    risk_chain = risk_assessment_prompt | llm_with_tools
    return risk_chain 