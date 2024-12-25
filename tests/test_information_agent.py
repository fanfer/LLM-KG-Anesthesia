from Graph.nodes import Information_Agent
from Graph.state import MedicalState
from langchain_core.messages import HumanMessage, AIMessage
import sys
import os

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 模拟一个MedicalState
state = MedicalState(
    messages=[
        HumanMessage(content="您好,我是来做术前检查的。"),
        AIMessage(content="您好,欢迎来做术前检查。请问您的姓名是?"),
        HumanMessage(content="我叫张三,今年40岁。"),
    ],
    user_information="张三,40岁,需要进行心脏搭桥手术",
    patient="张三",
    medical_history=set(),
    medicine_taking=set(),
    prompt=None,
    prompt_with_context=None,
    dialog_state=["verify_personal_information"]
)

# 调用Information_Agent
result = Information_Agent(state)

# 打印结果
print("Information_Agent返回结果:")
print(result)

print("\n更新后的state:")
print("\nmessages:")
for message in state['messages']:
    print(f"{message.__class__.__name__}: {message.content}")

# 模拟用户回复
state['messages'].append(HumanMessage(content="是的,我确实需要做心脏搭桥手术。"))

# 再次调用Information_Agent
result = Information_Agent(state)

print("\n第二次调用Information_Agent返回结果:")
print(result)

print("\n再次更新后的state:")
print("\nmessages:")
for message in state['messages']:
    print(f"{message.__class__.__name__}: {message.content}")