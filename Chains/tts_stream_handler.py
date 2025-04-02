from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import re
from queue import Queue
from threading import Thread
import json
import base64
import time
import numpy as np
import sounddevice as sd
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
from typing import Any
import os
import wave
import threading
import logging

# 简单获取日志记录器
logger = logging.getLogger(__name__)

# 存储当前活动的会话ID
_current_session_id = threading.local()
# 添加一个全局默认会话ID
_default_session_id = None

class TTSStreamHandler(StreamingStdOutCallbackHandler):
    def __init__(self, app_id="0fd3127e", api_key="22c490aacbd823d6cb89dced0a711e09", api_secret="YzM0Nzk3ZDgzOWYxYjBiZGRkYmZiMzc2"):
        super().__init__()
        self.buffer = ""
        self.sentence_end = re.compile(r'[。！？；.?;\n]')
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        
        # 按会话ID存储音频片段
        self.session_audio_segments = {}  # 格式: {session_id: [segments]}
        self.session_counters = {}  # 格式: {session_id: counter}
        
        # 创建音频根目录
        self.audio_root_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'static', 'audio')
        os.makedirs(self.audio_root_dir, exist_ok=True)
    
    def set_current_session_id(self, session_id):
        """设置当前活动的会话ID"""
        global _default_session_id
        
        # 设置全局默认会话ID
        _default_session_id = session_id
        
        if not hasattr(_current_session_id, 'value'):
            _current_session_id.value = {}
        
        # 使用当前线程ID作为键
        thread_id = threading.current_thread().ident
        _current_session_id.value[thread_id] = session_id
    
    def _get_session_id(self):
        """获取当前会话ID"""
        # 从线程本地存储获取会话ID
        thread_id = threading.current_thread().ident
        if hasattr(_current_session_id, 'value') and thread_id in _current_session_id.value:
            session_id = _current_session_id.value[thread_id]
            return session_id
        
        # 如果没有找到，尝试使用全局默认会话ID
        global _default_session_id
        if _default_session_id is not None:
            return _default_session_id
        
        # 如果没有找到，返回默认值
        return 'default'
    
    def _ensure_session_initialized(self, session_id):
        """确保会话已初始化"""
        if session_id not in self.session_audio_segments:
            self.session_audio_segments[session_id] = []
        
        if session_id not in self.session_counters:
            self.session_counters[session_id] = 0
        
        # 确保会话音频目录存在
        session_dir = os.path.join(self.audio_root_dir, str(session_id))
        os.makedirs(session_dir, exist_ok=True)
        
        return session_dir
    
    def _text_to_speech(self, text):
        """使用讯飞WebSocket API进行文本转语音并保存为文件"""
        # 获取当前会话ID
        session_id = self._get_session_id()
        
        # 确保会话已初始化
        session_dir = self._ensure_session_initialized(session_id)
        
        # 创建WebSocket参数
        ws_param = self._create_ws_param(self.app_id, self.api_key, self.api_secret, text)
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
                    logger.info(f"\nTTS API error: {message}")
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
                logger.info(f"\nError parsing TTS response: {e}")
                ws_closed = True
                ws.close()
        
        def on_error(ws, error):
            nonlocal ws_closed
            logger.info(f"\nWebSocket error: {error}")
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
                    logger.info(f"\nError sending data to WebSocket: {e}")
                    ws.close()
            thread.start_new_thread(run, ())
        
        # 尝试最多3次
        max_retries = 3
        for retry in range(max_retries):
            try:
                # 重置状态
                audio_buffer = io.BytesIO()
                audio_received = False
                ws_closed = False
                
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
                timeout = 10  # 10秒超时
                while not ws_closed and time.time() - start_time < timeout:
                    time.sleep(0.1)
                
                # 处理音频数据
                if audio_received and audio_buffer.getbuffer().nbytes > 0:
                    audio_buffer.seek(0)
                    audio_data = np.frombuffer(audio_buffer.read(), dtype=np.int16)
                    
                    # 获取当前会话的计数器
                    segment_id = self.session_counters[session_id]
                    self.session_counters[session_id] += 1
                    
                    # 保存音频片段到文件
                    segment_filename = f"segment_{segment_id}.wav"
                    segment_path = os.path.join(session_dir, segment_filename)
                    
                    # 保存为WAV文件
                    with wave.open(segment_path, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(audio_data.tobytes())
                    
                    # 添加到会话的音频片段列表
                    segment = {
                        'id': segment_id,
                        'filename': segment_filename,
                        'path': segment_path,
                        'url': f'/static/audio/{session_id}/{segment_filename}',
                        'text': text,
                        'session_id': session_id
                    }
                    self.session_audio_segments[session_id].append(segment)
                    
                    return segment_path
                else:
                    if not audio_received:
                        logger.info(f"\n未收到音频数据: {text[:20]}...")
                        # 如果不是最后一次重试，则继续尝试
                        if retry < max_retries - 1:
                            logger.info(f"\n尝试重新连接 (尝试 {retry+2}/{max_retries})...")
                            continue
            except Exception as e:
                logger.info(f"\nTTS处理出错: {e}")
                # 如果不是最后一次重试，则继续尝试
                if retry < max_retries - 1:
                    logger.info(f"\n尝试重新连接 (尝试 {retry+2}/{max_retries})...")
                    continue
        
        # 所有重试都失败，返回None
        return None
    
    def _create_ws_param(self, app_id, api_key, api_secret, text):
        """创建WebSocket参数"""
        # 公共参数
        common_args = {"app_id": app_id}
        
        # 业务参数
        business_args = {
            "aue": "raw",
            "auf": "audio/L16;rate=16000",
            "vcn": "xiaoyan",
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

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.buffer += token
        
        # 获取当前会话ID
        session_id = self._get_session_id()
        
        if self.sentence_end.search(self.buffer):
            if len(self.buffer.strip()) > 0:
                try:
                    segment_path = self._text_to_speech(self.buffer)
                    if segment_path is None:
                        logger.warning(f"无法为文本生成音频: {self.buffer[:20]}...")
                except Exception as e:
                    logger.error(f"Error in TTS processing: {e}")
            self.buffer = ""

    def on_llm_end(self, *args, **kwargs) -> None:
        # 获取当前会话ID
        session_id = self._get_session_id()
        
        if len(self.buffer.strip()) > 0:
            try:
                segment_path = self._text_to_speech(self.buffer)
                if segment_path is None:
                    logger.info(f"\n警告: 无法为最终文本生成音频: {self.buffer[:20]}...")
            except Exception as e:
                logger.info(f"\nError in final TTS processing: {e}")
            self.buffer = ""
    
    def get_audio_segments(self, session_id=None):
        """返回指定会话的音频片段信息"""
        if session_id is None:
            session_id = self._get_session_id()
        
        # 确保会话已初始化
        self._ensure_session_initialized(session_id)
        
        return self.session_audio_segments.get(session_id, [])
    
    def clear_audio_segments(self, session_id=None):
        """清除指定会话的音频片段"""
        if session_id is None:
            session_id = self._get_session_id()
        
        if session_id in self.session_audio_segments:
            self.session_audio_segments[session_id] = []
            self.session_counters[session_id] = 0
    
    def delete_segments(self, segment_ids, session_id=None):
        """删除指定会话的音频片段文件"""
        if session_id is None:
            session_id = self._get_session_id()
        
        # 确保会话已初始化
        self._ensure_session_initialized(session_id)
        
        if not segment_ids:
            return 0
        
        deleted_count = 0
        segments = self.session_audio_segments.get(session_id, [])
        
        # 如果segment_ids包含-1，表示删除所有片段
        if -1 in segment_ids:
            # 删除所有音频片段
            for segment in segments:
                try:
                    if os.path.exists(segment['path']):
                        os.remove(segment['path'])
                        deleted_count += 1
                    else:
                        logger.info(f"音频文件不存在: {segment['path']}")
                except Exception as e:
                    logger.error(f"删除音频文件失败: {e}")
            
            # 清空音频片段列表
            self.session_audio_segments[session_id] = []
            return deleted_count
        
        # 删除指定的音频片段
        segments_to_keep = []
        for segment in segments:
            if segment['id'] in segment_ids:
                try:
                    if os.path.exists(segment['path']):
                        os.remove(segment['path'])
                        #logger.info(f"成功删除音频文件: {segment['path']}")
                        deleted_count += 1
                    else:
                        logger.info(f"音频文件不存在: {segment['path']}")
                except Exception as e:
                    logger.error(f"删除音频文件失败: {e}")
                    # 如果删除失败，不要保留这个片段
            else:
                segments_to_keep.append(segment)
        
        # 更新音频片段列表
        self.session_audio_segments[session_id] = segments_to_keep
        logger.info(f"更新后会话 {session_id} 的音频片段列表长度: {len(segments_to_keep)}")
        
        return deleted_count

    def cleanup_old_segments(self, max_age_seconds=3600):
        """清理所有会话中超过指定时间的音频片段"""
        deleted_count = 0
        
        for session_id, segments in list(self.session_audio_segments.items()):
            # 清理当前会话的过期片段
            current_time = time.time()
            segments_to_keep = []
            
            for segment in segments:
                try:
                    if os.path.exists(segment['path']):
                        file_mtime = os.path.getmtime(segment['path'])
                        if current_time - file_mtime > max_age_seconds:
                            # 文件超过最大保留时间，删除它
                            os.remove(segment['path'])
                            deleted_count += 1
                        else:
                            segments_to_keep.append(segment)
                    else:
                        # 文件不存在，不需要保留其信息
                        deleted_count += 1
                except Exception as e:
                    logger.info(f"清理音频文件失败: {e}")
                    segments_to_keep.append(segment)
            
            # 更新会话的音频片段列表
            self.session_audio_segments[session_id] = segments_to_keep
            
            # 如果会话没有音频片段，考虑清理会话
            if not segments_to_keep:
                # 清理会话目录
                session_dir = os.path.join(self.audio_root_dir, str(session_id))
                try:
                    if os.path.exists(session_dir) and os.path.isdir(session_dir):
                        # 只删除空目录
                        if not os.listdir(session_dir):
                            os.rmdir(session_dir)
                except Exception as e:
                    logger.info(f"清理会话目录失败: {e}")
        
        return deleted_count

# 创建TTSStreamHandler实例
tts_handler = TTSStreamHandler()