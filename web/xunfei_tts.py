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
import _thread as thread
import os
import wave

class XunfeiTTS(object):
    STATUS_FIRST_FRAME = 0  # 第一帧的标识
    STATUS_CONTINUE_FRAME = 1  # 中间帧标识
    STATUS_LAST_FRAME = 2  # 最后一帧的标识

    def __init__(self, appid, apikey, apisecret):
        self.APPID = appid
        self.APIKey = apikey
        self.APISecret = apisecret

    def create_url(self):
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                               digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        return url + '?' + urlencode(v)

    def convert(self, text, output_path):
        self.output_path = output_path
        self.Text = text
        
        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business) # 3.21以后过期
        self.BusinessArgs = {"aue": "raw", "auf": "audio/L16;rate=16000", "vcn": "x4_lingfeizhe_zl", "tte": "utf8"}
        self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # 删除可能存在的旧文件
        if os.path.exists(self.output_path + '.pcm'):
            os.remove(self.output_path + '.pcm')
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

        websocket.enableTrace(False)
        wsUrl = self.create_url()
        ws = websocket.WebSocketApp(wsUrl, 
                                  on_message=self.on_message, 
                                  on_error=self.on_error, 
                                  on_close=self.on_close)
        ws.on_open = self.on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        
        # 转换PCM到WAV
        if os.path.exists(self.output_path + '.pcm'):
            self.pcm_to_wav(self.output_path + '.pcm', self.output_path)
            os.remove(self.output_path + '.pcm')
            return True
        return False

    def on_error(self, ws, error):
        print("### error:", error)

    def on_close(self, ws, status_code=None, close_msg=None, *args):
        pass

    def on_open(self, ws):
        def run(*args):
            data = {
                "common": self.CommonArgs,
                "business": self.BusinessArgs,
                "data": self.Data,
            }
            ws.send(json.dumps(data))

        thread.start_new_thread(run, ())

    def on_message(self, ws, message):
        try:
            message = json.loads(message)
            code = message["code"]
            sid = message["sid"]
            audio = message["data"]["audio"]
            audio = base64.b64decode(audio)
            status = message["data"]["status"]
            
            if status == 2:
                print("ws is closed")
                ws.close()
            if code != 0:
                errMsg = message["message"]
                print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
            else:
                with open(self.output_path + '.pcm', 'ab') as f:
                    f.write(audio)

        except Exception as e:
            print("receive msg, but parse exception:", e)

    def pcm_to_wav(self, pcm_path, wav_path):
        try:
            with open(pcm_path, 'rb') as pcmfile:
                pcmdata = pcmfile.read()
            with wave.open(wav_path, 'wb') as wavfile:
                wavfile.setnchannels(1)
                wavfile.setsampwidth(2)
                wavfile.setframerate(16000)
                wavfile.writeframes(pcmdata)
            return True
        except Exception as e:
            print(f"Error converting PCM to WAV: {e}")
            return False

# 测试代码
if __name__ == "__main__":
    tts = XunfeiTTS(
        appid='0fd3127e',
        apikey='22c490aacbd823d6cb89dced0a711e09',
        apisecret='YzM0Nzk3ZDgzOWYxYjBiZGRkYmZiMzc2'
    )
    tts.convert("测试语音合成", "test_output.wav") 