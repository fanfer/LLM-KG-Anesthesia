from typing import TypedDict, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langgraph.graph import StateGraph, END
import requests
import json
import base64
import time
import sounddevice as sd
import numpy as np
import re
from queue import Queue
from threading import Thread
import hashlib
import websocket
import hmac
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
import _thread as thread
import io

class TTSStreamHandler(StreamingStdOutCallbackHandler):
    def __init__(self):
        super().__init__()
        self.buffer = ""
        self.sentence_end = re.compile(r'[。！？，：；\n]')
        self.audio_queue = Queue()
        self.sample_rate = 16000
        # 启动音频播放线程
        self.player_thread = Thread(target=self._audio_player, daemon=True)
        self.player_thread.start()
    
    def _text_to_speech(self, text):
        """使用讯飞WebSocket API进行文本转语音"""
        app_id = "0fd3127e"
        api_key = "22c490aacbd823d6cb89dced0a711e09"
        api_secret = "YzM0Nzk3ZDgzOWYxYjBiZGRkYmZiMzc2"
        
        # 创建WebSocket参数
        ws_param = self._create_ws_param(app_id, api_key, api_secret, text)
        ws_url = ws_param["url"]
        ws_data = ws_param["data"]
        
        # 创建音频数据缓冲区
        audio_buffer = io.BytesIO()
        audio_received = False
        ws_closed = False
        
        # 定义WebSocket回调函数
        def on_message(ws, message):
            nonlocal audio_received, ws_closed
            try:
                message = json.loads(message)
                code = message["code"]
                if code != 0:
                    print(f"\nTTS API error: {message}")
                    ws_closed = True
                    ws.close()
                    return
                
                audio = message["data"]["audio"]
                audio_data = base64.b64decode(audio)
                audio_buffer.write(audio_data)
                audio_received = True
                
                status = message["data"]["status"]
                if status == 2:  # 最后一帧
                    ws_closed = True
                    ws.close()
            except Exception as e:
                print(f"\nError parsing TTS response: {e}")
                ws_closed = True
                ws.close()
        
        def on_error(ws, error):
            nonlocal ws_closed
            print(f"\nWebSocket error: {error}")
            ws_closed = True
            ws.close()
        
        def on_close(ws, close_status_code, close_msg):
            nonlocal ws_closed
            ws_closed = True
        
        def on_open(ws):
            def run(*args):
                try:
                    ws.send(json.dumps(ws_data))
                except Exception as e:
                    print(f"\nError sending data to WebSocket: {e}")
                    ws.close()
            thread.start_new_thread(run, ())
        
        # 创建WebSocket连接
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.on_open = on_open
        
        # 运行WebSocket连接，直到关闭或超时
        ws_thread = Thread(target=ws.run_forever, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
        ws_thread.daemon = True
        ws_thread.start()
        
        # 等待WebSocket连接关闭或超时
        start_time = time.time()
        timeout = 5  # 5秒超时
        while not ws_closed and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        # 处理音频数据
        if audio_received and audio_buffer.getbuffer().nbytes > 0:
            audio_buffer.seek(0)
            audio_data = np.frombuffer(audio_buffer.read(), dtype=np.int16)
            return audio_data
        else:
            if not audio_received:
                print(f"\n未收到音频数据: {text[:20]}...")
            return None
    
    def _create_ws_param(self, app_id, api_key, api_secret, text):
        """创建WebSocket参数"""
        # 公共参数
        common_args = {"app_id": app_id}
        
        # 业务参数
        business_args = {
            "aue": "raw",
            "auf": "audio/L16;rate=16000",
            "vcn": "x4_lingfeizhe_zl",
            "tte": "utf8",
            "speed": 0
        }
        
        # 数据参数
        data = {
            "status": 2,  # 一次性发送
            "text": str(base64.b64encode(text.encode('utf-8')), "UTF8")
        }
        
        # 生成URL
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"
        
        # 进行hmac-sha256加密
        signature_sha = hmac.new(
            api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')
        
        # 构建authorization
        authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        # 构建URL参数
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        
        # 拼接URL
        url = url + '?' + urlencode(v)
        
        # 构建WebSocket数据
        ws_data = {
            "common": common_args,
            "business": business_args,
            "data": data
        }
        
        return {"url": url, "data": ws_data}

    def _audio_player(self):
        while True:
            try:
                audio_data = self.audio_queue.get()
                if audio_data is not None:
                    print(f"\n开始播放音频片段，长度: {len(audio_data)} 采样点")
                    sd.play(audio_data, self.sample_rate)
                    sd.wait()  # 等待音频播放完成
                    print(f"音频片段播放完成")
                self.audio_queue.task_done()  # 标记任务完成
            except Exception as e:
                print(f"Error playing audio: {e}")
                continue

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        print(f"{token}", end="", flush=True)
        self.buffer += token
        
        if self.sentence_end.search(self.buffer):
            if len(self.buffer.strip()) > 0:
                try:
                    audio_data = self._text_to_speech(self.buffer)
                    if audio_data is not None:
                        self.audio_queue.put(audio_data)
                except Exception as e:
                    print(f"\nError in TTS processing: {e}")
            self.buffer = ""

    def on_llm_end(self, *args, **kwargs) -> None:
        if len(self.buffer.strip()) > 0:
            try:
                audio_data = self._text_to_speech(self.buffer)
                if audio_data is not None:
                    self.audio_queue.put(audio_data)
            except Exception as e:
                print(f"\nError in final TTS processing: {e}")
            self.buffer = ""
    
    def wait_for_audio_completion(self, timeout=30):
        """等待所有音频播放完毕"""
        print("\n等待音频播放完成...")
        try:
            # 使用Queue.join()等待所有任务完成
            self.audio_queue.join()
            print("所有音频任务已处理完成")
            # 额外等待最后一个音频片段播放完成
            time.sleep(3)
        except Exception as e:
            print(f"等待音频播放时发生错误: {e}")
        print("音频播放完成")

# 1. 定义自定义的回调处理器，用于流式输出
handler = TTSStreamHandler()

# 2. 定义 Agent
## 2.1 定义背诵春江花月夜的 Agent
prompt_chunjiang = "请背诵《春江花月夜》全文"
llm_chunjiang = ChatOpenAI(model_name="gpt-4", streaming=True, callbacks=[handler], temperature=0.7)

## 2.2 定义背诵登高的 Agent
prompt_denggao = "请背诵《登高》全文"
llm_denggao = ChatOpenAI(model_name="gpt-4", streaming=True, callbacks=[handler], temperature=0.7)

# 3. 定义图的状态
class GraphState(TypedDict):
    messages: list[BaseMessage]

# 4. 定义图的节点
def agent_chunjiang_node(state: GraphState):
    print("\n\n--Agent 春江花月夜 开始背诵--\n")
    messages = [HumanMessage(content=prompt_chunjiang)]
    response = llm_chunjiang.invoke(messages)
    return {"messages": [response]}

def agent_denggao_node(state: GraphState):
    print("\n\n--Agent 登高 开始背诵--\n")
    messages = [HumanMessage(content=prompt_denggao)]
    response = llm_denggao.invoke(messages)
    return {"messages": [response]}

# 5. 创建图
workflow = StateGraph(GraphState)
workflow.add_node("chunjiang", agent_chunjiang_node)
workflow.add_node("denggao", agent_denggao_node)

# 6. 定义图的流转
workflow.set_entry_point("chunjiang") # 从背诵春江花月夜开始
workflow.add_edge("chunjiang", "denggao") # 背诵完春江花月夜，背
workflow.add_edge("denggao", END) # 背诵结束

# 7. 编译图
graph = workflow.compile()

# 8. 运行图
inputs = {"messages": [HumanMessage(content="开始背诵！")]}
print("开始运行 LangGraph...\n")
for output in graph.stream(inputs):
    # 这里可以处理每个节点的输出，但由于我们已经在回调函数中处理了流式输出，这里可以简化
    pass

print("\n\nLangGraph 运行结束！")

# 等待所有音频播放完毕
handler.wait_for_audio_completion()