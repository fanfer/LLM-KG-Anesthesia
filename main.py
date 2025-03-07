from typing import Set
import uuid
from langchain_core.messages import ToolMessage, HumanMessage,AIMessage
from Graph.graph import graph
from IPython.display import Image, display
import os
from dotenv import load_dotenv, find_dotenv

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
    # 首先绘制图
    # print("正在生成系统架构图...")
    draw_graph()
    # 初始化打印集合和配置
    _printed = set()
    config = {
        "configurable": {
            "thread_id": "1112312"
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
