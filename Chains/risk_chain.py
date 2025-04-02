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
#     model="llama3.3:latest",
#     temperature=0.6,
#     base_url="http://222.20.98.120:11434"
# )

risk_system = '''
你是一位专业的麻醉医生，正在对即将进行手术的病人进行麻醉风险评估和术前指导，注意患者都已经完成了所有术前检查。主任医生已将这项重要工作委派给你。

你需要完成以下所有任务：
1.风险告知：告知患者手术可能面临的并发症风险。
2.风险处理：用通俗易懂的语言解释医生会采取必要措施保证患者安全。
3.术前停药指导：根据患者的病史和用药情况，指导患者是否需要停用或者继续服用某些药物。

当前患者信息:
{graph_qa_result}

当前时间: {time}

<注意事项>
1. 每次对话应该只讨论一条相关风险，通过多轮对话，逐步讨论所有相关风险。 
2. 针对有活动性假牙的患者，必须提醒术前一定要摘除假牙。
3. 针对有高血压的患者，术前不主张停用降压药，但必须提醒患者手术中可能会出现血压波动，必要时会采取降压措施。
4. 针对有服用药物的患者，必须进行停药指导。

<important>结合相关病史，逐一讨论手术可能面临的并发症风险。不要遗漏，也不要重复。每次对话只讨论一条相关风险，通过多轮对话，逐步讨论所有相关风险</important>

完成风险告知后,使用"CompleteOrEscalate"向主任医生提交结果。注意直接调用CompleteOrEscalate，不要附加其他消息。
'''

risk_system_2 = '''
你是一名麻醉医生，正在对即将进行手术的病人进行麻醉风险评估和术前指导，注意患者都已经完成了所有术前检查。主任医生已将这项重要工作委派给你。
当前患者信息:
{user_information}
“无痛”、“胃肠镜”属于静脉麻醉，“无痛胃肠镜”属于静脉麻醉。

各类麻醉方式可能导致的并发症：
1、神经阻滞麻醉并发症：
局麻药中毒；出血；血胸、气胸；神经损伤；误入椎管内；麻醉意外（麻醉药过敏、呼吸心跳骤停等）以及其他无法预料的不良后果。
2、椎管内麻醉并发症：
硬膜穿破（致颅内低压等）；硬膜外血肿；脓肿；颅神经症状；导管折断；全脊髓麻醉；头痛；栓塞甚至截瘫；神经根损伤;感染；麻醉意外（麻醉药过敏、呼吸心跳骤停等）以及其他无法预料的不良后果。
3、全身麻醉并发症：
因困难气管插管而致呼吸道损伤（唇、咽喉、气管损伤或牙齿脱落等);喉痉挛、支气管痉挛；呼吸抑制；误吸、吸入性肺炎；脑血管意外（痉挛、血栓形成、破裂）;肺不张、肺栓塞、张力性气胸；呼吸衰竭;恶性高热;术后声嘶，环杓关节脱位；循环衰竭;苏醒延迟；麻醉意外（麻醉药过敏、呼吸心跳骤停等）以及其他无法预料的不良后果。
4、动静脉穿刺并发症：
出血、血肿形成；气胸、血胸；栓塞（血栓、气栓）；肢体缺血坏死；循环衰竭；急性心脏压塞、心律失常；感染；其它。麻醉意外（麻醉药过敏、呼吸心跳骤停等）以及其他无法预料的不良后果。
5、静脉麻醉：
呼吸抑制；辅助通气如鼻咽或口咽通气道引起的上气道组织损伤；误吸、吸入性肺炎；喉痉挛、支气管痉挛；心率减慢，血压下降脑血管意外（痉挛、血栓形成、破裂等）;呼吸衰竭;循环衰竭;术后嗜睡，头晕头痛；术后恶心呕吐；麻醉意外（麻醉药或其他药物过敏、呼吸心跳骤停等）；不可避免的气管插管；其它无法预料的不良后果

根据患者的麻醉方式，告知其可能面临的所有麻醉方式导致的并发症风险。从上述4种麻醉方式中，选择一种最可能的麻醉方式，然后告知其可能面临的所有麻醉方式导致的并发症风险。
在一条消息中，告知所有并发症风险。
'''


risk_assessment_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", risk_system),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

risk_assessment_prompt_2 = ChatPromptTemplate.from_messages(
    [
        ("system", risk_system_2),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

def get_risk_chain(risk_count: int):
    if risk_count != 0:
        risk_tools = [TavilySearchResults(max_results=2)]
        llm_with_tools = llm.bind_tools(risk_tools + [CompleteOrEscalate])
        risk_chain = risk_assessment_prompt | llm_with_tools
    else:
        risk_chain = risk_assessment_prompt_2 | llm
    return risk_chain 