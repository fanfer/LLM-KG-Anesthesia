from typing import Set
import uuid
from langchain_core.messages import ToolMessage, HumanMessage
from Graph.graph import graph
from IPython.display import Image, display
import os

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
    print("正在生成系统架构图...")
    draw_graph()
    # 初始化打印集合和配置
    _printed = set()
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4())
        }
    }

    print("您好,我是您的麻醉医生。请问您怎么称呼?")
    
    while True:
        try:
            question = input("用户 (输入q退出): ")
            if question.lower() == 'q':
                print("AI: 再见!")
                break
                
            # 处理用户输入
            events = graph.stream(
                {"messages": ("user", question)}, 
                config,
                stream_mode="values"
            )
            
            # 打印所有事件
            for event in events:
                _print_event(event, _printed)
                
            # 获取当前状态
            snapshot = graph.get_state(config)
            
            # 处理中断
            while snapshot.next:
                # 直接继续执行,不需要用户确认
                result = graph.invoke(None, config)
                
        except Exception as e:
            print(f"处理对话时出错: {str(e)}")
            continue
        

if __name__ == "__main__":
    main()
