from typing import Callable
from Chains.graph_qa_chain import get_graph_qa_chain
from Graph.state import MedicalState, InputState
from Chains.assistant2agent_chain import get_primary_assistant_chain
from Chains.information_chain import get_information_chain
from langchain_core.messages import ToolMessage,HumanMessage,AIMessage
from Chains.extract_info_chain import get_extract_info_chain
from Chains.history_chain import get_history_chain
from Chains.risk_chain import get_risk_chain
from typing import List, Dict, Any

def Primary_Assistant(state: MedicalState):
    try:
        primary_chain = get_primary_assistant_chain()
        messages = state.get('messages', [])
        user_information = state.get('user_information', '')
        result = primary_chain.invoke({
            "messages": messages,
            "user_information": user_information
        })
        
        # 确保返回完整的状态
        return {
            "messages": result,
            "user_information": user_information,  # 保持状态
            "medical_history": state.get('medical_history', []),  # 保持状态
            "medicine_taking": state.get('medicine_taking', [])   # 保持状态
        }
    except Exception as e:
        print(f"主助手处理时出错: {str(e)}")
        # 返回默认状态
        return {
            "messages": [],
            "user_information": "",
            "medical_history": [],
            "medicine_taking": []
        }


#用于从Primary_Assistant分支到Agent,同时跟踪dialog_state

def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: MedicalState) -> dict:
        # 获取最后一条消息
        last_message = state["messages"][-1]
        tool_call_id = None
        
        # 从AIMessage中获取tool_call_id
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            tool_call_id = last_message.tool_calls[0]["id"]
        
        if not tool_call_id:
            print("警告：未找到工具调用ID")
            return {
                "messages": state["messages"],
                "dialog_state": new_dialog_state,
            }
            
        return {
            "messages": [
                ToolMessage(
                    content=f'''记住，你现在是{assistant_name}，你的任务尚未完成。反思上述主任医生和患者之间的对话。\n如果患者改变主意或需要帮助处理其他任务，请调用CompleteOrEscalate函数让主要主任医师接管。不提及你是谁——只需作为助理行事。''',
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }
    return entry_node

Entry_Information_Agent = create_entry_node(assistant_name="确认患者身份信息的医疗助手", 
                                            new_dialog_state="verify_information")

def Information_Agent(state: MedicalState):
    try:
        information_chain = get_information_chain()
        messages = state.get('messages', [])
        user_information = state.get('user_information', '')
        
        result = information_chain.invoke({
            "messages": messages,
            "user_information": user_information,
        })
        
        return {
            "messages": result,
            "user_information": user_information,  # 保持状态
            "medical_history": state.get('medical_history', []),
            "medicine_taking": state.get('medicine_taking', [])
        }
    except Exception as e:
        print(f"信息确认助手处理时出错: {str(e)}")
        return {
            "messages": [],
            "user_information": user_information,
            "medical_history": [],
            "medicine_taking": []
        }


def Extract_Info_Agent(state: MedicalState):
    try:
        extract_info_chain = get_extract_info_chain()
        human_messages = [msg for msg in state['messages'] if isinstance(msg, (HumanMessage, AIMessage))][-4:]
        
        # 获取当前状态，如果不存在则使用默认值
        user_information = state.get('user_information', '')
        
        # 消息转换为文本格式
        messages_text = "\n".join([f"{msg.__class__.__name__}: {msg.content}" for msg in human_messages])
        
        result = extract_info_chain.invoke({
            "user_input": messages_text,
            "user_information": user_information,
        })
        
        # 更新user_information
        updated_user_information = f"""
        姓名: {result.patient}
        年龄: {result.age}
        手术: {result.surgery}
        麻醉方式: {result.anesthesia}
        其他信息: {result.additional_info}
        """
        
        # 返回完整状态
        return {
            "messages": state.get('messages', []),  # 保持原有消息
            "user_information": updated_user_information.strip(),
            "medical_history": list(result.medical_history) if result.medical_history else [],
            "medicine_taking": list(result.medicine_taking) if result.medicine_taking else [],
        }
    except Exception as e:
        print(f"提取信息时出错: {str(e)}")
        return {
            "messages": state.get('messages', []),
            "user_information": user_information if user_information else "",
            "medical_history": [],
            "medicine_taking": [],
        }

# 创建Entry_History_Agent
Entry_History_Agent = create_entry_node(
    assistant_name="采集病史的麻醉医生",
    new_dialog_state="history_taking"
)

def History_Agent(state: MedicalState):
    try:
        history_chain = get_history_chain()
        messages = state.get('messages', [])
        user_information = state.get('user_information', '')
        medical_history = state.get('medical_history', [])
        medicine_taking = state.get('medicine_taking', [])
        
        result = history_chain.invoke({
            "messages": messages,
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking,
        })
        
        return {
            "messages": result,
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking,
        }
    except Exception as e:
        print(f"病史采集助手处理时出错: {str(e)}")
        return {
            "messages": [],
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking,
        }

# 创建Entry_Risk_Agent
Entry_Risk_Agent = create_entry_node(
    assistant_name="进行麻醉风险评估的麻醉医生",
    new_dialog_state="risk_assessment"
)

def Risk_Agent(state: MedicalState):
    try:
        risk_chain = get_risk_chain()
        messages = state.get('messages', [])
        user_information = state.get('user_information', '')
        medical_history = state.get('medical_history', [])
        medicine_taking = state.get('medicine_taking', [])
        graph_qa_result = state.get('graph_qa_result', '')
        
        result = risk_chain.invoke({
            "messages": messages,
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking,
            "graph_qa_result": graph_qa_result,
        })
        
        return {
            "messages": result,
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking,
        }
    except Exception as e:
        print(f"风险评估助手处理时出错: {str(e)}")
        return {
            "messages": [],
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking,
        }
    
def Graph_QA_Agent(state: MedicalState):
    """
    使用知识图谱分析患者风险的Agent。
    返回风险分析结果和更新后的状态。
    """
    try:
        # 获取chain
        graph_qa_chain = get_graph_qa_chain()
        
        # 准备输入
        messages = state.get('messages', [])
        user_information = state.get('user_information', '')
        medical_history = state.get('medical_history', [])
        medicine_taking = state.get('medicine_taking', [])
        
        # 调用chain
        result = graph_qa_chain.invoke({
            "messages": messages,
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking,
        })
        
        # 处理返回结果
        risk_analysis = result.get('risk_analysis', '')
        
        # 创建AI消息
        ai_message = AIMessage(
            content=f"""根据知识图谱分析，患者的风险评估如下：

        {risk_analysis}

        请根据这些信息为基础，与患者进行沟通交流，告知麻醉手术风向。
        """
        )
        
        # 返回更新后的状态
        return {
            "messages": messages + [ai_message],
            "user_information": result.get('user_information', user_information),
            "medical_history": result.get('medical_history', medical_history),
            "medicine_taking": result.get('medicine_taking', medicine_taking),
            "graph_qa_result": risk_analysis
        }
        
    except Exception as e:
        print(f"图谱QA助手处理时出错: {str(e)}")
        # 发生错误时返回原始状态
        return {
            "messages": messages,
            "user_information": user_information,
            "medical_history": medical_history,
            "medicine_taking": medicine_taking
        }


    


    


    


    