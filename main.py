from typing import Set
import uuid
from langchain_core.messages import ToolMessage, HumanMessage,AIMessage
from Graph.graph import graph
from IPython.display import Image, display
import os
from dotenv import load_dotenv, find_dotenv
from Chains.graph_qa_chain import get_graph_qa_chain
import threading
from threading import Lock, Event

# 初始化Graph RAG Chain
graph_qa_chain = get_graph_qa_chain()

graph_qa_result = None
graph_qa_thread_started = False
graph_qa_thread_completed = Event()  # 使用Event而不是布尔标志
graph_qa_lock = Lock()

def run_graph_qa_in_background(graph, config, current_state):
    """在后台线程中运行graph_qa_chain，只运行一次"""
    global graph_qa_result
    
    try:
        print("开始在后台执行知识图谱查询...")
        
        # 执行图谱查询
        result = graph_qa_chain.invoke({
            "messages": current_state["messages"],
            "user_information": current_state["user_information"],
            "medical_history": current_state["medical_history"],
            "medicine_taking": current_state["medicine_taking"]
        })
        
        # 使用锁保护共享数据的更新
        with graph_qa_lock:
            graph_qa_result = result
        
        # 设置完成事件
        graph_qa_thread_completed.set()
        print("知识图谱查询完成，结果已保存")
        
        # 获取最新状态并更新
        latest_state = graph.get_state(config)
        if latest_state.get("dialog_state", [])[-1] == "risk_assessment":
            graph.update_state(
                config,
                {
                    "graph_qa_result": result,
                    "graph_is_qa": True
                }
            )
            
    except Exception as e:
        print(f"后台图谱查询出错: {str(e)}")
        # 即使出错也设置完成事件
        graph_qa_thread_completed.set()
    """在后台线程中运行graph_qa_chain，只运行一次"""
    global graph_qa_result, graph_qa_thread_completed
    
    try:
        print("开始在后台执行知识图谱查询...")
        
        # 执行图谱查询
        result = graph_qa_chain.invoke(
            {
                "messages": current_state["messages"],
                "user_information": current_state["user_information"],
                "medical_history": current_state["medical_history"],
                "medicine_taking": current_state["medicine_taking"]
            }
        )
        
        # 使用锁保护共享数据的更新
        with graph_qa_lock:
            graph_qa_result = result
            graph_qa_thread_completed = True
            
        print("知识图谱查询完成，结果已保存")
        
        # 获取最新状态
        latest_state = graph.get_state(config).values
        
        # 如果状态已经变为risk_assessment，更新图状态
        if latest_state["dialog_state"][-1] == "risk_assessment":
            graph.update_state(
                config,
                {
                    "graph_qa_result": result,
                    "graph_is_qa": True
                }
            )
            print("状态已更新为risk_assessment，已应用查询结果")
            
    except Exception as e:
        print(f"后台图谱查询出错: {str(e)}")
        # 即使出错也标记为完成
        with graph_qa_lock:
            graph_qa_thread_completed = True

def draw_graph():
    """绘制并保存图结构。"""
    try:
        # 获取图的Mermaid表示并绘制
        graph_image = graph.get_graph().draw_mermaid_png()
        
        # 保存图片
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        with open(os.path.join(output_dir, "graph.png"), "wb") as f:
            f.write(graph_image)
        
        print(f"图已保存到 {os.path.join(output_dir, 'graph.png')}")
        
        # 如果在Jupyter环境中，也显示图片
        try:
            display(Image(graph_image))
        except:
            pass
            
    except Exception as e:
        print(f"绘制图时出错: {str(e)}")
        print("提示：确保已安装graphviz，可以使用以下命令安装：")
        print("Mac: brew install graphviz")
        print("Linux: sudo apt-get install graphviz")
        print("Windows: pip install graphviz")

def _print_event(event: dict, _printed: Set[str], max_length=1500):
    """打印事件内容，避免重复打印。"""
    # current_state = event.get("dialog_state")
    # if current_state:
    #     print("当前状态:", current_state[-1])
    
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (已截断)"
            print(msg_repr)
            _printed.add(message.id)

def main():
    global graph_qa_thread_started, graph_qa_thread_completed, graph_qa_result
    
    # 首先绘制图
    #draw_graph()
    # 初始化打印集合和配置
    _printed = set()
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4())
        }
    }

    print("请医生输入患者的姓名、年龄、性别、手术方式和麻醉类型。")
    message = AIMessage(content="请医生输入患者的姓名、年龄、性别、手术方式和麻醉类型。")
    graph.update_state(
        config,
        {
            "dialog_state": "verify_information"
        }
    )
    
    while True:
        try:
            current_state = graph.get_state(config).values
            
            # 检查当前状态
            current_dialog_state = current_state["dialog_state"][-1] if current_state["dialog_state"] else None
            
            # 如果状态为analgesia且线程尚未启动，则启动线程
            if current_dialog_state == "analgesia" and not graph_qa_thread_started:
                with graph_qa_lock:
                    graph_qa_thread_started = True
                
                # 创建并启动后台线程
                bg_thread = threading.Thread(
                    target=run_graph_qa_in_background,
                    args=(graph, config, current_state),
                    daemon=True
                )
                bg_thread.start()
                print("已启动知识图谱查询后台线程")
            
            # 如果状态为risk_assessment且查询已完成，更新状态
            elif current_dialog_state == "risk_assessment" and graph_qa_thread_completed:
                with graph_qa_lock:
                    if graph_qa_result is not None:
                        graph.update_state(
                            config,
                            {
                                "graph_qa_result": graph_qa_result,
                                "graph_is_qa": True
                            }
                        )
                        print("已将知识图谱查询结果应用到risk_assessment状态")
                        # 清除结果，避免重复使用
                        graph_qa_result = None
            
            print(f"当前状态: {current_dialog_state}")
            question = input("用户 (输入q退出): ")
            if question.lower() == 'q':
                print("AI: 再见!")
                break
                
            # 创建HumanMessage对象
            message = HumanMessage(content=question)
            
            # 打印所有事件
            for event in graph.stream(
                {"messages": [message]}, 
                config,
                stream_mode="values"  # 使用messages模式支持流式输出
            ):
                _print_event(event, _printed)
                
        except Exception as e:
            print(f"处理对话时出错: {str(e)}")
            continue
        

if __name__ == "__main__":

    os.environ["OPENAI_API_BASE"] = "https://aihubmix.com/v1"
    os.environ["OPENAI_API_KEY"] = "sk-dsDP2qW6CMnV4WFI11A15e972dC14d928eB985407cDb8cE1"
    os.environ["OPENAI_BASE_URL"] = "https://aihubmix.com/v1"
    main()
