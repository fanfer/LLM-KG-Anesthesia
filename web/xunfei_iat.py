import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import threading
import tempfile
import os
import subprocess
import wave
import io
import logging

# 简单获取日志记录器
logger = logging.getLogger(__name__)

STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

class XunfeiIAT:
    def __init__(self, appid, apikey, apisecret):
        self.APPID = appid
        self.APIKey = apikey
        self.APISecret = apisecret
        
    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        return url
    
    def recognize_audio(self, audio_data):
        """
        识别音频数据
        :param audio_data: base64编码的音频数据
        :return: 识别结果
        """
        result_list = []
        result_lock = threading.Lock()
        websocket_error = [None]  # 使用列表存储错误，以便在回调中修改
        recognition_completed = threading.Event()
        
        try:
            logger.info("开始语音识别处理")
            
            # 检查音频数据格式
            if not audio_data or not isinstance(audio_data, str):
                logger.error(f"无效的音频数据格式: {type(audio_data)}")
                return "无效的音频数据格式，请重试"
                
            # 确保音频数据是base64格式
            if ',' not in audio_data:
                logger.error("音频数据不是有效的Data URL格式")
                return "音频数据格式错误，请重试"
            
            # 解码base64数据
            try:
                audio_bytes = base64.b64decode(audio_data.split(',')[1])
                logger.info(f"成功解码音频数据，大小: {len(audio_bytes)} 字节")
                
                # 检查音频大小
                if len(audio_bytes) < 1000:
                    logger.warning(f"音频数据太小: {len(audio_bytes)} 字节")
                    return "录音时间太短或音量太低，请重试"
            except Exception as e:
                logger.error(f"解码音频数据失败: {e}")
                return f"解码音频数据失败: {str(e)}"
            
            # 收到websocket消息的处理
            def on_message(ws, message):
                try:
                    logger.info(f"收到WebSocket消息: {message[:100]}...")
                    message_json = json.loads(message)
                    code = message_json["code"]
                    if code != 0:
                        error_msg = f"科大讯飞API返回错误: {message_json.get('message', '未知错误')}, 代码: {code}"
                        logger.error(error_msg)
                        websocket_error[0] = error_msg
                        recognition_completed.set()
                        return
                    
                    if 'data' not in message_json:
                        logger.warning("WebSocket消息中没有data字段")
                        return
                        
                    # 检查是否是最终结果
                    is_last = message_json["data"].get("status", 1) == 2
                    
                    # 提取识别结果
                    if 'result' in message_json["data"] and 'ws' in message_json["data"]["result"]:
                        data = message_json["data"]["result"]["ws"]
                        text = ""
                        for i in data:
                            for w in i["cw"]:
                                text += w["w"]
                        
                        with result_lock:
                            result_list.append(text)
                        
                        logger.info(f"识别文本: {text}")
                        
                        # 如果是最终结果，设置事件
                        if is_last:
                            logger.info("收到最终识别结果")
                            recognition_completed.set()
                except Exception as e:
                    logger.error(f"处理WebSocket消息时出错: {e}")
                    websocket_error[0] = f"处理识别结果时出错: {str(e)}"
                    recognition_completed.set()
            
            # 收到websocket错误的处理
            def on_error(ws, error):
                logger.error(f"WebSocket错误: {error}")
                websocket_error[0] = f"WebSocket连接错误: {str(error)}"
                recognition_completed.set()
            
            # 收到websocket关闭的处理
            def on_close(ws, close_status_code, close_reason):
                logger.info(f"WebSocket连接关闭: 状态码={close_status_code}, 原因={close_reason}")
                recognition_completed.set()
            
            # 收到websocket连接建立的处理
            def on_open(ws):
                def run(*args):
                    try:
                        logger.info("WebSocket连接已建立，开始发送音频数据")
                        
                        # 将音频数据分成多个帧发送
                        frameSize = 1280  # 每一帧的音频大小
                        frames = [audio_bytes[i:i+frameSize] for i in range(0, len(audio_bytes), frameSize)]
                        total_frames = len(frames)
                        logger.info(f"音频数据已分割为 {total_frames} 帧")
                        
                        # 发送第一帧
                        if frames:
                            common_args = {"app_id": self.APPID}
                            business_args = {
                                "domain": "iat", 
                                "language": "zh_cn", 
                                "accent": "mandarin", 
                                "vinfo": 1, 
                                "vad_eos": 10000,
                                "dwa": "wpgs",  # 开启动态修正功能
                                "nunum": 0,     # 不过滤数字
                                "ptt": 0        # 不过滤标点
                            }
                            
                            d = {
                                "common": common_args,
                                "business": business_args,
                                "data": {
                                    "status": STATUS_FIRST_FRAME, 
                                    "format": "audio/L16;rate=16000",
                                    "audio": str(base64.b64encode(frames[0]), 'utf-8'),
                                    "encoding": "raw"
                                }
                            }
                            ws.send(json.dumps(d))
                            logger.info("已发送第一帧")
                            
                            # 发送中间帧
                            for i in range(1, len(frames) - 1):
                                d = {
                                    "data": {
                                        "status": STATUS_CONTINUE_FRAME, 
                                        "format": "audio/L16;rate=16000",
                                        "audio": str(base64.b64encode(frames[i]), 'utf-8'),
                                        "encoding": "raw"
                                    }
                                }
                                ws.send(json.dumps(d))
                                
                                # 每发送10帧记录一次日志
                                if i % 10 == 0:
                                    logger.info(f"已发送 {i}/{total_frames} 帧")
                                
                                time.sleep(0.04)  # 控制发送速率
                            
                            # 发送最后一帧
                            if len(frames) > 1:
                                d = {
                                    "data": {
                                        "status": STATUS_LAST_FRAME, 
                                        "format": "audio/L16;rate=16000",
                                        "audio": str(base64.b64encode(frames[-1]), 'utf-8'),
                                        "encoding": "raw"
                                    }
                                }
                                ws.send(json.dumps(d))
                                logger.info("已发送最后一帧")
                            
                            logger.info("所有音频数据已发送完毕")
                    except Exception as e:
                        logger.error(f"发送音频数据时出错: {e}")
                        websocket_error[0] = f"发送音频数据时出错: {str(e)}"
                        recognition_completed.set()
                        ws.close()
                
                threading.Thread(target=run).start()
            
            # 创建websocket连接
            ws_url = self.create_url()
            logger.info(f"创建WebSocket连接: {ws_url[:50]}...")
            
            # 设置更长的超时时间
            websocket.setdefaulttimeout(30)
            
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.on_open = on_open
            
            # 运行websocket连接
            ws_thread = threading.Thread(target=ws.run_forever, 
                                         kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
            ws_thread.daemon = True
            ws_thread.start()
            logger.info("WebSocket线程已启动")
            
            # 等待识别结果
            timeout = 15  # 最多等待15秒
            logger.info(f"等待识别结果，超时时间: {timeout}秒")
            recognition_completed.wait(timeout)
            
            # 检查是否有错误
            if websocket_error[0]:
                logger.error(f"识别过程中出现错误: {websocket_error[0]}")
                return f"语音识别失败: {websocket_error[0]}"
            
            # 返回识别结果
            with result_lock:
                if result_list:
                    result = "".join(result_list)
                    logger.info(f"识别完成，结果: {result}")
                    return result
                else:
                    logger.warning("未获取到识别结果")
                    return "未能识别语音，请重试说话时请靠近麦克风并清晰发音"
                
        except Exception as e:
            logger.error(f"语音识别过程中出现异常: {e}")
            return f"语音识别出错: {str(e)}"