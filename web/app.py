from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, make_response
from langchain_core.messages import AIMessage, HumanMessage
from flask_session import Session
from flask_cors import CORS
import os
import sys
import logging
from dotenv import load_dotenv
import json
from datetime import datetime
from openai import OpenAI
import tempfile
import base64
import time
from xunfei_tts import XunfeiTTS
import threading
from threading import Lock
import traceback
from xunfei_iat import XunfeiIAT
import sounddevice as sd
import soundfile as sf

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.log'))
    ]
)
logger = logging.getLogger(__name__)

# 获取项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 加载环境变量
load_dotenv(os.path.join(ROOT_DIR, '.env'))

sys.path.append(ROOT_DIR)
from Graph.graph import graph
from Chains.graph_qa_chain import get_graph_qa_chain
from Chains.tts_stream_handler import tts_handler
# 验证环境变量是否加载
logger.info("OpenAI API Key: %s", os.getenv('OPENAI_API_KEY', 'Not found'))
logger.info("OpenAI API Base: %s", os.getenv('OPENAI_API_BASE', 'Not found'))

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

# 初始化科大讯飞IAT（语音识别）
iat = XunfeiIAT(
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

# 全局变量
graph_qa_threads = {}
graph_qa_results = {}
graph_qa_locks = {}
graph_qa_thread_started = {}
graph_qa_thread_completed = {}
graph_qa_events = {}  # 新增：存储每个会话的事件对象

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
        logger.error("错误: 以下环境变量未设置:")
        for var in missing_vars:
            logger.error("- %s", var)
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
    logger.info("Login request: %s", request.method)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        logger.info("Login attempt - username: %s", username)
        
        if username in USERS and USERS[username] == password:
            session['username'] = username
            logger.info("Login successful, redirecting to chat")
            return redirect(url_for('chat'))
        logger.warning("Invalid credentials")
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/chat')
def chat():
    # 添加调试信息
    logger.info("Chat route accessed")
    logger.debug("Session: %s", session)
    if 'username' not in session:
        logger.info("No username in session, redirecting to login")
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

def run_graph_qa_in_background(graph, config, current_state, session_id):
    """在后台线程中运行graph_qa_chain，每个会话只运行一次"""
    try:
        logger.info("会话 %s: 开始在后台执行知识图谱查询...", session_id)
        graph_qa_chain = get_graph_qa_chain()
        # 执行图谱查询
        result = graph_qa_chain.invoke({
            "messages": current_state["messages"],
            "user_information": current_state["user_information"],
            "medical_history": current_state["medical_history"],
            "medicine_taking": current_state["medicine_taking"]
        })
        
        # 使用锁保护共享数据的更新
        with graph_qa_locks[session_id]:
            graph_qa_results[session_id] = result
            graph_qa_thread_completed[session_id] = True
            
        logger.info("会话 %s: 知识图谱查询完成，结果已保存", session_id)
        
        # 获取最新状态
        latest_state = graph.get_state(config).values
        
        # 更新图状态
        graph.update_state(
            config,
            {
                "graph_qa_result": result.get("risk_analysis", ""),
                "graph_is_qa": True
            }
        )
        logger.info("会话 %s: 已更新图状态，设置graph_is_qa为True", session_id)
        
        # 设置事件，通知等待的Risk_Agent
        if session_id in graph_qa_events:
            graph_qa_events[session_id].set()
            logger.info("会话 %s: 已设置事件通知", session_id)
            
    except Exception as e:
        logger.error("会话 %s: 后台图谱查询出错: %s", session_id, str(e))
        # 即使出错也标记为完成并设置事件
        with graph_qa_locks[session_id]:
            graph_qa_thread_completed[session_id] = True
            
        # 更新图状态，即使出错也设置graph_is_qa为True
        graph.update_state(
            config,
            {
                "graph_qa_result": "知识图谱查询出错，使用有限信息进行评估",
                "graph_is_qa": True
            }
        )
        
        # 设置事件，通知等待的Risk_Agent
        if session_id in graph_qa_events:
            graph_qa_events[session_id].set()
            logger.info("会话 %s: 错误情况下已设置事件通知", session_id)

@app.route('/send_message', methods=['POST'])
def send_message():
    global graph_qa_threads, graph_qa_results, graph_qa_locks, graph_qa_thread_started, graph_qa_thread_completed
    
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    message = data.get('message')
    chat_id = data.get('chatId')
    
    if not message or not chat_id:
        return jsonify({'error': 'Invalid request'}), 400

    try:
        # 创建会话ID
        username = session['username']
        session_id = chat_id  # 使用chat_id作为会话ID
        
        # 初始化会话相关的线程状态（如果不存在）
        if session_id not in graph_qa_locks:
            graph_qa_locks[session_id] = Lock()
            graph_qa_thread_started[session_id] = False
            graph_qa_thread_completed[session_id] = False
            graph_qa_results[session_id] = None
        
        # 检查是否是第一条消息
        chat_file = os.path.join(CHAT_LOGS_DIR, f'{chat_id}.txt')
        is_first_message = not os.path.exists(chat_file)
        
        if is_first_message:
            # 初始化系统消息
            graph.update_state(
                {"configurable": {"thread_id": session_id}},
                {
                    "dialog_state": "verify_information",
                    "user_information": message,
                    "session_id": session_id,  # 添加session_id到状态中
                }
            )
        
        # 保存用户消息
        save_chat_message(chat_id, message, is_user=True)
        
        # 使用graph处理消息
        config = {"configurable": {"thread_id": session_id}}
        events = graph.stream(
            {"messages": ("human", message)},
            config,
            stream_mode="values"
        )
        
        # 获取最后一条需要显示的AI消息
        last_message = None
        current_dialog_state = None
        
        for event in events:
            if "current_step" in event:
                current_step = event["current_step"]
                if current_step == 100:
                    # 播放完成音频
                    audio_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'static', 'audio', 'output.wav')
                    if os.path.exists(audio_file):
                        data, fs = sf.read(audio_file)
                        sd.play(data, fs)
                        sd.wait()  # 等待音频播放完成
                        logger.info("音频播放完成")
                        current_step = 5
                        # 更新状态
                        graph.update_state(
                            config,
                            {"current_step": current_step}
                        )
                    else:
                        logger.warning(f"音频文件不存在: {audio_file}")
            # 在事件流中检查状态并处理多线程
            if 'dialog_state' in event:
                current_dialog_state = event['dialog_state'][-1] if event['dialog_state'] else None
                
                # 如果状态为analgesia且线程尚未启动，则启动线程
                if current_dialog_state == "analgesia" and not graph_qa_thread_started[session_id]:
                    with graph_qa_locks[session_id]:
                        graph_qa_thread_started[session_id] = True
                    
                    # 获取当前状态用于后台查询
                    current_state = graph.get_state(config).values
                    
                    # 创建并启动后台线程
                    bg_thread = threading.Thread(
                        target=run_graph_qa_in_background,
                        args=(graph, config, current_state, session_id),
                        daemon=True
                    )
                    bg_thread.start()
                    graph_qa_threads[session_id] = bg_thread
                    logger.info("会话 %s: 已启动知识图谱查询后台线程", session_id)
                
                # 如果状态为risk_assessment且查询已完成，更新状态
                elif graph_qa_thread_completed[session_id]:
                    with graph_qa_locks[session_id]:
                        if graph_qa_results[session_id] is not None:
                            graph.update_state(
                                config,
                                {
                                    "graph_qa_result": graph_qa_results[session_id]["risk_analysis"],
                                    "graph_is_qa": True
                                }
                            )
                            logger.info("会话 %s: 已将知识图谱查询结果应用到risk_assessment状态", session_id)
                            # 清除结果，避免重复使用
                            graph_qa_results[session_id] = None
            
            # 处理消息
            if 'messages' in event and event['messages']:
                message = event['messages']
                if isinstance(message, list):
                    message = message[-1]
                last_message = message.content
        
        if last_message is None:
            return jsonify({'error': 'No response generated'}), 500
        
        # 保存AI响应
        save_chat_message(chat_id, last_message, is_user=False)
        audio_segments = tts_handler.get_audio_segments()
        
        # 返回响应，但不需要生成音频文件，因为音频已经在流式过程中播放
        return jsonify({
            'response': last_message,
            'audio_segments': audio_segments
        })
    except Exception as e:
        traceback.print_exc()
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
    logger.error("Error occurred: %s", error)
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

@app.route('/api/list_chats')
def list_chats():
    """列出所有可用的聊天记录"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        # 获取聊天记录目录中的所有文件
        chat_files = [f.replace('.txt', '') for f in os.listdir(CHAT_LOGS_DIR) 
                     if f.endswith('.txt')]
        return jsonify({'chats': chat_files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_chat/<chat_id>')
def download_chat(chat_id):
    """下载聊天记录"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        chat_file = os.path.join(CHAT_LOGS_DIR, f'{chat_id}.txt')
        if not os.path.exists(chat_file):
            return jsonify({'error': 'Chat not found'}), 404
            
        # 读取聊天记录并格式化为更易读的格式
        formatted_content = ["=== Medical Assistant System - Consultation Record ===\n\n"]
        with open(chat_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '] User: ' in line:
                    timestamp, content = line.split('] User: ', 1)
                    timestamp = timestamp.strip('[')
                    formatted_content.append(f"Time: {timestamp}\nDoctor: {content}")
                elif '] Assistant: ' in line:
                    timestamp, content = line.split('] Assistant: ', 1)
                    timestamp = timestamp.strip('[')
                    formatted_content.append(f"Time: {timestamp}\nAssistant: {content}\n")
        
        # 添加导出信息
        export_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_content.append(f"\n=== Export Time: {export_time} ===\n")
        
        # 将格式化后的内容合并为字符串
        chat_content = ''.join(formatted_content)
            
        # 创建响应
        response = make_response(chat_content)
        
        # 获取当前日期时间作为文件名的一部分
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 设置文件名和内容类型 (使用纯ASCII字符)
        response.headers['Content-Disposition'] = f'attachment; filename=chat_record_{current_time}.txt'
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

client = OpenAI()

@app.route('/speech-to-text', methods=['POST'])
def speech_to_text():
    try:
        logger.info("收到语音转文本请求")
        
        if not request.json:
            logger.error("请求中没有JSON数据")
            return jsonify({'error': '无效的请求格式'}), 400
            
        audio_data = request.json.get('audio')
        if not audio_data:
            logger.error("请求中没有音频数据")
            return jsonify({'error': '请求中没有音频数据'}), 400
            
        logger.info("开始调用科大讯飞语音识别")
        start_time = time.time()
        
        # 使用科大讯飞IAT进行语音识别
        text = iat.recognize_audio(audio_data)
        
        end_time = time.time()
        logger.info(f"语音识别完成，耗时: {end_time - start_time:.2f}秒")
        
        if text and not text.startswith("语音识别出错") and not text.startswith("未能识别"):
            logger.info(f"识别成功，文本长度: {len(text)}")
            return jsonify({'text': text})
        else:
            logger.warning(f"识别结果不理想: {text}")
            return jsonify({'error': text}), 500
            
    except Exception as e:
        error_msg = f"语音识别过程中出现异常: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

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

# 清理过期的会话数据
def clean_expired_sessions(max_age=3600):  # 默认1小时过期
    current_time = time.time()
    expired_sessions = []
    
    # 查找过期的会话
    for session_id in list(graph_qa_thread_started.keys()):
        if session_id in session_last_access and current_time - session_last_access[session_id] > max_age:
            expired_sessions.append(session_id)
    
    # 清理过期的会话数据
    for session_id in expired_sessions:
        with graph_qa_locks.get(session_id, Lock()):
            if session_id in graph_qa_threads:
                del graph_qa_threads[session_id]
            if session_id in graph_qa_results:
                del graph_qa_results[session_id]
            if session_id in graph_qa_thread_started:
                del graph_qa_thread_started[session_id]
            if session_id in graph_qa_thread_completed:
                del graph_qa_thread_completed[session_id]
            if session_id in graph_qa_locks:
                del graph_qa_locks[session_id]
            if session_id in session_last_access:
                del session_last_access[session_id]
            if session_id in graph_qa_events:
                del graph_qa_events[session_id]  # 清理事件对象

# 跟踪会话最后访问时间
session_last_access = {}

# 在每次请求开始时更新会话访问时间
@app.before_request
def update_session_access_time():
    if 'user_id' in session and request.path != '/static/':
        user_id = session['user_id']
        chat_id = request.args.get('chat_id') or request.form.get('chat_id') or ''
        if chat_id:
            session_id = f"{user_id}_{chat_id}"
            session_last_access[session_id] = time.time()

@app.route('/thread_status/<chat_id>', methods=['GET'])
def thread_status(chat_id):
    """查询指定聊天的线程状态"""
    session_id = chat_id  # 使用chat_id作为会话ID
    
    status = {
        "thread_exists": session_id in graph_qa_threads,
        "thread_started": graph_qa_thread_started.get(session_id, False),
        "thread_completed": graph_qa_thread_completed.get(session_id, False),
        "has_results": graph_qa_results.get(session_id) is not None,
        "is_alive": False
    }
    
    # 检查线程是否仍在运行
    if session_id in graph_qa_threads:
        thread = graph_qa_threads[session_id]
        status["is_alive"] = thread.is_alive()
    
    return jsonify(status)

@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.root_path, 'static', 'favicon.ico'))

@app.route('/api/audio_segments/<chat_id>', methods=['GET'])
def get_audio_segments(chat_id):
    """获取指定会话的音频片段"""
    try:
        session_id = chat_id
        
        # 获取当前对话状态
        config = {"configurable": {"thread_id": session_id}}
        state = graph.get_state(config).values
        current_dialog_state = state.get('dialog_state', ['verify_information'])[-1]
        
        audio_segments = tts_handler.get_audio_segments()
        
        return jsonify({'audio_segments': audio_segments})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_played_segments', methods=['POST'])
def delete_played_segments():
    """删除已播放的音频片段"""
    try:
        data = request.json
        chat_id = data.get('chatId')
        segment_ids = data.get('segmentIds', [])
        
        if not chat_id or not segment_ids:
            return jsonify({'error': '无效的请求参数'}), 400
        
        # 获取当前对话状态
        config = {"configurable": {"thread_id": chat_id}}
        
        # 删除已播放的音频片段
        deleted_count = tts_handler.delete_segments(segment_ids)
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
    except Exception as e:
        logger.error(f"删除音频片段出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 在app.py中添加
def cleanup_audio_files():
    """定期清理过期的音频文件"""
    while True:
        try:
            # 每小时清理一次
            time.sleep(3600)
            deleted = tts_handler.cleanup_old_segments()
            if deleted > 0:
                logger.info(f"定期清理: 已删除 {deleted} 个过期音频文件")
        except Exception as e:
            logger.error(f"定期清理音频文件出错: {str(e)}")

# 启动清理线程
cleanup_thread = threading.Thread(target=cleanup_audio_files, daemon=True)
cleanup_thread.start()

@app.route('/end_session/<chat_id>', methods=['POST'])
def end_session(chat_id):
    """结束会话，清理相关资源"""
    try:
        # 删除所有相关的音频文件
        deleted_count = tts_handler.delete_segments([-1])  # -1表示删除所有片段
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/audio_stream/<chat_id>')
def audio_stream(chat_id):
    """使用SSE向客户端推送新的音频片段"""
    def generate():
        # 发送初始消息
        yield "data: {\"type\": \"connected\", \"message\": \"Connected to audio stream\"}\n\n"
        
        # 记录已发送的最后一个片段ID
        last_sent_id = -1
        
        while True:
            try:
                # 获取音频片段
                audio_segments = tts_handler.get_audio_segments()
                
                # 过滤出新的片段
                new_segments = [s for s in audio_segments if s['id'] > last_sent_id]
                
                if new_segments:
                    # 更新最后发送的ID
                    last_sent_id = max(s['id'] for s in new_segments)
                    
                    # 发送新片段
                    yield f"data: {json.dumps({'type': 'audio_segments', 'segments': new_segments})}\n\n"
                
                # 短暂休眠，避免CPU占用过高
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"音频流发送错误: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                break
    
    # 设置响应头
    response = app.response_class(
        response=generate(),
        status=200,
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 禁用Nginx缓冲
    return response

if __name__ == '__main__':
    if not check_environment():
        logger.error("请检查.env文件配置")
        sys.exit(1)
        
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=True
    ) 