from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_cors import CORS  # 添加CORS支持
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Graph.graph import graph

app = Flask(__name__)
CORS(app)  # 启用CORS

# 更安全的密钥设置
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True  # 启用安全cookie
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30分钟session过期

Session(app)

# 用户凭证
USERS = {
    'admin': 'imds1234'
}

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chat'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['username'] = username
            return redirect(url_for('chat'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    message = data.get('message')
    chat_id = data.get('chatId')
    chat_messages = data.get('messages', [])
    
    if not message or not chat_id:
        return jsonify({'error': 'Invalid request'}), 400

    try:
        # 构建完整的消息历史
        messages = []
        for msg in chat_messages:
            if msg['isUser']:
                messages.append(("user", msg['content']))
            else:
                messages.append(("assistant", msg['content']))
        
        # 添加当前消息
        # messages.append(("user", message))
        
        # 使用graph处理消息
        events = graph.stream(
            {"messages": messages},  # 传递完整的消息历史
            {"configurable": {"thread_id": chat_id}},
            stream_mode="values"
        )
        
        # 只获取最后一条AI消息
        last_message = None
        for event in events:
            if 'messages' in event and event['messages']:
                message = event['messages']
                if isinstance(message, list):
                    message = message[-1]
                last_message = message.content
        
        # 如果没有获取到消息，返回错误
        if last_message is None:
            return jsonify({'error': 'No response generated'}), 500
            
        return jsonify({'response': last_message})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(
        host='0.0.0.0', 
        port=8080,  # 改用8080端口
        debug=True
    ) 