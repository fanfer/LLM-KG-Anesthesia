from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_cors import CORS
import os
import sys
from dotenv import load_dotenv

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

Session(app)

# 用户凭证
USERS = {
    'admin': 'imds1234'
}

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

if __name__ == '__main__':
    if not check_environment():
        print("请检查.env文件配置")
        sys.exit(1)
        
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=True
    ) 