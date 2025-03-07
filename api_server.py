from flask import Flask, request, jsonify, Response, stream_with_context
import os
import sys
import json
from dotenv import load_dotenv
from datetime import datetime
from openai import OpenAI
from functools import wraps

# 获取项目根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
# 加载环境变量
load_dotenv(os.path.join(ROOT_DIR, '.env'))

sys.path.append(ROOT_DIR)
from Graph.graph import graph

app = Flask(__name__)

# API密钥设置
API_KEY = "imds1234"

# 配置对话记录目录
CHAT_LOGS_DIR = os.path.join(ROOT_DIR, 'chat_logs')
os.makedirs(CHAT_LOGS_DIR, exist_ok=True)

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == API_KEY:
            return f(*args, **kwargs)
        return jsonify({'error': '无效的API密钥'}), 401
    return decorated_function

def save_chat_message(uid, message, is_user=True):
    """保存对话消息到文件"""
    chat_file = os.path.join(CHAT_LOGS_DIR, f'{uid}.txt')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    role = 'User' if is_user else 'Assistant'
    
    with open(chat_file, 'a', encoding='utf-8') as f:
        f.write(f'[{timestamp}] {role}: {message}\n')

def check_environment():
    """检查必要的环境变量是否设置"""
    required_vars = ['OPENAI_API_KEY', 'OPENAI_API_BASE']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("错误: 以下环境变量未设置:")
        for var in missing_vars:
            print(f"- {var}")
        return False
    return True

def format_sse(data: dict, event=None) -> str:
    """格式化SSE消息"""
    msg = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    return msg

def process_chat(user_message: str, uid: str):
    """处理聊天消息并返回事件流"""
    # 检查是否是第一条消息
    chat_file = os.path.join(CHAT_LOGS_DIR, f'{uid}.txt')
    is_first_message = not os.path.exists(chat_file)
    
    # 如果是第一条消息，初始化状态
    if is_first_message:
        graph.update_state(
            {"configurable": {"thread_id": uid}},
            {
                "dialog_state": "verify_information",
                "user_information": user_message,
            }
        )
    
    # 保存用户消息
    save_chat_message(uid, user_message, is_user=True)
    
    # 使用graph处理消息
    return graph.stream(
        {"messages": ("human", user_message)},
        {"configurable": {"thread_id": uid}},
        stream_mode="values"
    )

@app.route('/chat', methods=['POST'])
@require_api_key
def chat():
    """处理对话请求 - 支持流式和普通响应"""
    data = request.json
    if not data or 'message' not in data or 'uid' not in data:
        return jsonify({'error': '缺少必要参数'}), 400

    user_message = data['message']
    uid = data['uid']
    stream = data.get('stream', False)  # 默认为非流式响应

    if not stream:
        try:
            events = process_chat(user_message, uid)
            
            # 获取最后一条AI响应
            last_message = None
            for event in events:
                if 'messages' in event and event['messages']:
                    event_message = event['messages']
                    if isinstance(event_message, list):
                        event_message = event_message[-1]
                    last_message = event_message.content
            
            if last_message is None:
                return jsonify({'error': '未生成响应'}), 500
            
            # 保存AI响应
            save_chat_message(uid, last_message, is_user=False)
            
            return jsonify({
                'uid': uid,
                'response': last_message
            })
        except Exception as e:
            error_msg = str(e)
            print(f"处理对话时出错: {error_msg}")
            return jsonify({'error': error_msg}), 500

    def generate():
        try:
            events = process_chat(user_message, uid)
            current_response = []
            
            for event in events:
                if 'messages' in event and event['messages']:
                    event_message = event['messages']
                    if isinstance(event_message, list):
                        event_message = event_message[-1]
                    
                    response_content = event_message.content
                    current_response.append(response_content)
                    
                    # 发送流式响应
                    yield format_sse({
                        'uid': uid,
                        'response': response_content,
                        'type': 'message'
                    })
            
            # 保存完整的AI响应
            if current_response:
                complete_response = current_response[-1]
                save_chat_message(uid, complete_response, is_user=False)
            
            # 发送完成信号
            yield format_sse({
                'uid': uid,
                'type': 'done'
            }, event='done')
            
        except Exception as e:
            error_msg = str(e)
            print(f"处理对话时出错: {error_msg}")
            yield format_sse({
                'error': error_msg,
                'type': 'error'
            }, event='error')

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # 禁用Nginx缓冲
        }
    )

@app.route('/history/<uid>', methods=['GET'])
@require_api_key
def get_chat_history(uid):
    """获取指定UID的对话历史"""
    try:
        chat_file = os.path.join(CHAT_LOGS_DIR, f'{uid}.txt')
        if not os.path.exists(chat_file):
            return jsonify({'messages': []})
            
        messages = []
        with open(chat_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '] User: ' in line:
                    content = line.split('] User: ', 1)[1].strip()
                    messages.append({'content': content, 'role': 'user'})
                elif '] Assistant: ' in line:
                    content = line.split('] Assistant: ', 1)[1].strip()
                    messages.append({'content': content, 'role': 'assistant'})
                    
        return jsonify({
            'uid': uid,
            'messages': messages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear/<uid>', methods=['DELETE'])
@require_api_key
def clear_chat_history(uid):
    """清除指定UID的对话历史"""
    try:
        chat_file = os.path.join(CHAT_LOGS_DIR, f'{uid}.txt')
        if os.path.exists(chat_file):
            os.remove(chat_file)
        return jsonify({
            'uid': uid,
            'success': True,
            'message': '对话历史已清除'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(Exception)
def handle_error(error):
    """全局错误处理"""
    print(f"Error occurred: {error}")
    return jsonify({'error': str(error)}), 500

if __name__ == '__main__':
    if not check_environment():
        print("请检查.env文件配置")
        sys.exit(1)
        
    app.run(
        host='0.0.0.0',
        port=8000,
        debug=True
    ) 