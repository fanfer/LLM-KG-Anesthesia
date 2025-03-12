from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from typing import Any
import re
from queue import Queue
from threading import Thread
import time
import base64
import json
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
import numpy as np
import sounddevice as sd
import traceback

class StreamTTSHandler(StreamingStdOutCallbackHandler):
    """流式文本转语音处理器，用于将LLM生成的文本实时转换为语音"""
    
    def __init__(self, app_id=None, api_key=None, api_secret=None, callback=None):
        """初始化流式TTS处理器
        
        Args:
            app_id: 讯飞API的app_id
            api_key: 讯飞API的api_key
            api_secret: 讯飞API的api_secret
            callback: 回调函数，用于将音频数据发送给前端
        """
        super().__init__()
        self.buffer = ""
        self.sentence_end = re.compile(r'[。！？，：；\n]')
        self.audio_queue = Queue()
        self.sample_rate = 16000
        self.app_id = app_id or "0fd3127e"
        self.api_key = api_key or "22c490aacbd823d6cb89dced0a711e09"
        self.api_secret = api_secret or "YzM0Nzk3ZDgzOWYxYjBiZGRkYmZiMzc2"
        self.callback = callback
        
        # 启动音频处理线程
        self.player_thread = Thread(target=self._audio_processor, daemon=True)
        self.player_thread.start()
    
    def _text_to_speech(self, text):
        """将文本转换为语音"""
        try:
            print(f"开始TTS转换，文本长度: {len(text)}")
            # 使用讯飞TTS将文本转换为语音
            audio_data = self.tts.tts(text)
            if audio_data is not None:
                print(f"TTS转换成功，音频数据长度: {len(audio_data)} 采样点")
                return audio_data
            else:
                print("TTS转换失败，未返回音频数据")
                return None
        except Exception as e:
            print(f"TTS转换出错: {e}")
            traceback.print_exc()
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
            "speed": 70
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

    def _audio_processor(self):
        """音频处理线程，从队列中获取音频数据并处理"""
        while True:
            try:
                audio_data = self.audio_queue.get()
                if audio_data is not None:
                    # 如果有回调函数，则调用回调函数处理音频数据
                    if self.callback:
                        print(f"调用回调函数处理音频数据，长度: {len(audio_data)} 采样点")
                        self.callback(audio_data)
                    else:
                        # 否则直接播放音频
                        print(f"开始播放音频片段，长度: {len(audio_data)} 采样点")
                        sd.play(audio_data, self.sample_rate)
                        sd.wait()  # 等待音频播放完成
                        print(f"音频片段播放完成")
                self.audio_queue.task_done()  # 标记任务完成
            except Exception as e:
                print(f"Error processing audio: {e}")
                continue

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """处理LLM生成的新token"""
        # 调用父类方法，打印token
        super().on_llm_new_token(token, **kwargs)
        
        # 将token添加到缓冲区
        self.buffer += token
        
        # 如果缓冲区中有句子结束标志，则将缓冲区中的文本转换为语音
        if self.sentence_end.search(self.buffer):
            if len(self.buffer.strip()) > 0:
                try:
                    print(f"转换文本到语音: {self.buffer[:20]}...")
                    audio_data = self._text_to_speech(self.buffer)
                    if audio_data is not None:
                        print(f"获取到音频数据，长度: {len(audio_data)} 采样点")
                        self.audio_queue.put(audio_data)
                    else:
                        print("未获取到音频数据")
                except Exception as e:
                    print(f"Error in TTS processing: {e}")
            self.buffer = ""

    def on_llm_end(self, *args, **kwargs) -> None:
        """处理LLM生成结束事件"""
        # 如果缓冲区中还有文本，则将其转换为语音
        if len(self.buffer.strip()) > 0:
            try:
                audio_data = self._text_to_speech(self.buffer)
                if audio_data is not None:
                    self.audio_queue.put(audio_data)
            except Exception as e:
                print(f"Error in final TTS processing: {e}")
            self.buffer = ""
    
    def wait_for_audio_completion(self, timeout=30):
        """等待所有音频播放完毕"""
        print("等待音频播放完成...")
        try:
            # 使用Queue.join()等待所有任务完成
            self.audio_queue.join()
            print("所有音频任务已处理完成")
            # 额外等待最后一个音频片段播放完成
            time.sleep(1)
        except Exception as e:
            print(f"等待音频播放时发生错误: {e}")
        print("音频播放完成") 