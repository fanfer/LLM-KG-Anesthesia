from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from langchain_core.messages import AIMessage, HumanMessage
from flask_session import Session
from flask_cors import CORS
import os
import sys
from dotenv import load_dotenv
import json
from datetime import datetime
from openai import OpenAI
import tempfile
import base64
import time
from xunfei_tts import XunfeiTTS

# 获取项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 加载环境变量
load_dotenv(os.path.join(ROOT_DIR, '.env'))

sys.path.append(ROOT_DIR)
from Graph.graph import graph

# 验证环境变量是否加载
print("OpenAI API Key:", os.getenv('OPENAI_API_KEY', 'Not found'))
print("OpenAI API Base:", os.getenv('OPENAI_API_BASE', 'Not found'))

app = Flask(__name__)
CORS(app)  # 启用CORS

# Session配置
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_COOKIE_SECURE=False,  # 开发环境设为False
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800,  # 30分钟
    SESSION_FILE_DIR=os.path.join(ROOT_DIR, 'flask_session')  # 指定session文件存储位置
)

# 确保session目录存在
os.makedirs(os.path.join(ROOT_DIR, 'flask_session'), exist_ok=True)

# 创建音频文件存储目录
AUDIO_DIR = os.path.join(ROOT_DIR, 'web/static/audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

Session(app)

# 初始化科大讯飞TTS
tts = XunfeiTTS(
    appid='0fd3127e',
    apikey='22c490aacbd823d6cb89dced0a711e09',
    apisecret='YzM0Nzk3ZDgzOWYxYjBiZGRkYmZiMzc2'
)

# 用户凭证
USERS = {
    'admin': 'imds1234'
}

# 在文件开头添加对话记录目录配置
CHAT_LOGS_DIR = os.path.join(ROOT_DIR, 'chat_logs')
os.makedirs(CHAT_LOGS_DIR, exist_ok=True)

def save_chat_message(chat_id, message, is_user=True):
    """保存对话消息到文件"""
    chat_file = os.path.join(CHAT_LOGS_DIR, f'{chat_id}.txt')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    role = 'User' if is_user else 'Assistant'
    
    with open(chat_file, 'a', encoding='utf-8') as f:
        f.write(f'[{timestamp}] {role}: {message}\n')

def check_environment():
    required_vars = ['OPENAI_API_KEY', 'OPENAI_API_BASE']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("错误: 以下环境变量未设置:")
        for var in missing_vars:
            print(f"- {var}")
        return False
    return True

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chat'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 添加调试信息
    print("Login request:", request.method)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print(f"Login attempt - username: {username}")
        
        if username in USERS and USERS[username] == password:
            session['username'] = username
            print("Login successful, redirecting to chat")
            return redirect(url_for('chat'))
        print("Invalid credentials")
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/chat')
def chat():
    # 添加调试信息
    print("Chat route accessed")
    print("Session:", session)
    if 'username' not in session:
        print("No username in session, redirecting to login")
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    message = data.get('message')
    chat_id = data.get('chatId')
    
    if not message or not chat_id:
        return jsonify({'error': 'Invalid request'}), 400

    try:
        # 检查是否是第一条消息
        chat_file = os.path.join(CHAT_LOGS_DIR, f'{chat_id}.txt')
        is_first_message = not os.path.exists(chat_file)
        
        if is_first_message:
            # 初始化系统消息
            graph.update_state(
                {"configurable": {"thread_id": chat_id}},
                {
                    "dialog_state": "verify_information",
                    "user_information": message,
                }
            )
        
        # 保存用户消息
        save_chat_message(chat_id, message, is_user=True)
        
        # 使用graph处理消息
        events = graph.stream(
            {"messages": ("human", message)},
            {"configurable": {"thread_id": chat_id}},
            stream_mode="values"
        )
        
        # 获取最后一条需要显示的AI消息
        last_message = None
        for event in events:
            if 'messages' in event and event['messages']:
                message = event['messages']
                if isinstance(message, list):
                    message = message[-1]
                last_message = message.content
        
        if last_message is None:
            return jsonify({'error': 'No response generated'}), 500
        
        # 保存AI响应
        save_chat_message(chat_id, last_message, is_user=False)
        
        try:
            # 生成语音文件
            audio_filename = f"{chat_id}_{int(time.time())}.wav"
            audio_path = os.path.join(AUDIO_DIR, audio_filename)
            
            # 尝试进行语音合成
            if tts.convert(last_message, audio_path):
                audio_url = url_for('static', filename=f'audio/{audio_filename}')
            else:
                print("语音合成失败")
                audio_url = None
                
            return jsonify({
                'response': last_message,
                'audio_url': audio_url
            })
        except Exception as e:
            print(f"语音合成错误: {e}")
            # 即使语音合成失败，也返回文本响应
            return jsonify({
                'response': last_message,
                'audio_url': None
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/load_chat_history/<chat_id>')
def load_chat_history(chat_id):
    """加载完整的对话历史"""
    try:
        chat_file = os.path.join(CHAT_LOGS_DIR, f'{chat_id}.txt')
        if not os.path.exists(chat_file):
            return jsonify({'messages': []})
            
        messages = []
        with open(chat_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '] User: ' in line:
                    content = line.split('] User: ', 1)[1].strip()
                    messages.append({'content': content, 'isUser': True})
                elif '] Assistant: ' in line:
                    content = line.split('] Assistant: ', 1)[1].strip()
                    messages.append({'content': content, 'isUser': False})
                    
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(Exception)
def handle_error(error):
    print(f"Error occurred: {error}")
    return str(error), 500

# 添加测试路由
@app.route('/test_session')
def test_session():
    return jsonify({
        'session': dict(session),
        'cookie': request.cookies
    })

@app.route('/delete_chat/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """删除对话记录"""
    try:
        chat_file = os.path.join(CHAT_LOGS_DIR, f'{chat_id}.txt')
        if os.path.exists(chat_file):
            os.remove(chat_file)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

client = OpenAI()

@app.route('/speech-to-text', methods=['POST'])
def speech_to_text():
    try:
        audio_data = request.json.get('audio')
        
        # 将base64音频数据转换为临时文件
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
            temp_file.write(base64.b64decode(audio_data.split(',')[1]))
            temp_file_path = temp_file.name
        
        # 使用OpenAI API转换语音为文本
        with open(temp_file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        
        os.unlink(temp_file_path)  # 删除临时文件
        return jsonify({'text': transcript.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    try:
        text = request.json.get('text')
        
        # 使用OpenAI API转换文本为语音
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",  # 使用男性的声音
            input=text
        )
        
        # 将音频数据转换为base64
        audio_base64 = base64.b64encode(response.content).decode('utf-8')
        return jsonify({'audio': f'data:audio/mp3;base64,{audio_base64}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not check_environment():
        print("请检查.env文件配置")
        sys.exit(1)
        
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=True
    ) 