function addMessage(content, isUser = false, save = true) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'system'}`;
    
    // 创建头像
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'avatar';
    const icon = document.createElement('i');
    icon.className = isUser ? 'fas fa-user' : 'fas fa-robot';
    avatarDiv.appendChild(icon);
    
    // 创建消息内容
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    // 组装消息
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    // 保存消息到历史记录
    if (save && currentChatId) {
        const chat = chatHistory.find(c => c.id === currentChatId);
        if (chat) {
            chat.messages.push({ content, isUser });
            // 更新对话标题
            if (chat.messages.length === 2) {
                chat.title = content.substring(0, 20) + '...';
                updateChatList();
            }
            saveChatHistory();
        }
    }
}

// WebSocket连接
let socket;
let audioContext;
let audioQueue = [];
let isPlaying = false;

// 初始化WebSocket连接
function initWebSocket() {
    // 创建WebSocket连接
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}`;
    
    console.log('尝试连接WebSocket:', wsUrl);
    socket = io(wsUrl);
    
    // 连接成功
    socket.on('connect', () => {
        console.log('WebSocket连接成功');
        
        // 如果有当前聊天ID，则加入该聊天的房间
        if (currentChatId) {
            console.log('加入房间:', currentChatId);
            socket.emit('join', { chat_id: currentChatId });
        }
    });
    
    // 加入房间成功
    socket.on('joined', (data) => {
        console.log('已加入房间:', data.chat_id);
    });
    
    // 接收音频数据
    socket.on('audio_chunk', (data) => {
        if (data.chat_id === currentChatId) {
            // 将base64编码的音频数据转换为ArrayBuffer
            const audioData = base64ToArrayBuffer(data.audio);
            // 播放音频
            playAudioChunk(audioData);
        }
    });
    
    // 连接错误
    socket.on('error', (error) => {
        console.error('WebSocket错误:', error);
    });
    
    // 断开连接
    socket.on('disconnect', () => {
        console.log('WebSocket连接已断开');
    });
}

// 将base64编码的音频数据转换为ArrayBuffer
function base64ToArrayBuffer(base64) {
    const binaryString = window.atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

// 初始化音频上下文
function initAudioContext() {
    // 创建音频上下文
    try {
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioContext();
        console.log('音频上下文已初始化');
    } catch (e) {
        console.error('无法创建音频上下文:', e);
    }
}

// 播放音频数据
function playAudioChunk(audioData) {
    if (!audioContext) {
        initAudioContext();
    }
    
    // 将音频数据添加到队列
    audioQueue.push(audioData);
    
    // 如果当前没有在播放，则开始播放
    if (!isPlaying) {
        playNextAudio();
    }
}

// 播放队列中的下一个音频
function playNextAudio() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }
    
    isPlaying = true;
    const audioData = audioQueue.shift();
    
    // 解码音频数据
    audioContext.decodeAudioData(audioData, (buffer) => {
        // 创建音频源
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        
        // 播放结束后播放下一个
        source.onended = playNextAudio;
        
        // 开始播放
        source.start(0);
    }, (error) => {
        console.error('解码音频数据失败:', error);
        playNextAudio();
    });
}

// 修改sendMessage函数，支持流式输出
async function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // 添加用户消息到界面
    addMessage(message, true);
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    try {
        // 确保已加入WebSocket房间
        if (socket && socket.connected) {
            socket.emit('join', { chat_id: currentChatId });
        }
        
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                chatId: currentChatId
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 添加AI回复到界面
            addMessage(data.response, false);
            
            // 如果不是流式输出，则播放语音回复
            if (!data.streaming && data.audio_url) {
                playTTS(data.audio_url);
            }
        } else {
            console.error('Error:', data.error);
            addMessage('抱歉，发生了错误，请重试。', false);
        }
    } catch (error) {
        console.error('Error:', error);
        addMessage('抱歉，发生了错误，请重试。', false);
    }
}

// 监听键盘事件
document.getElementById('message-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// 添加提示信息
document.getElementById('message-input').setAttribute('placeholder', '请输入消息...\n按Enter发送，Shift+Enter换行'); 

// 存储聊天历史
let chatHistory = [];

// 生成唯一的聊天ID
function generateChatId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// 当前聊天ID
let currentChatId = generateChatId();

// 创建新聊天
function newChat() {
    currentChatId = generateChatId();
    document.getElementById('chat-messages').innerHTML = `
        <div class="message system">
            <div class="avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                请医生输入患者信息(姓名，年龄，性别，手术，麻醉方式等)
            </div>
        </div>
    `;
    
    // 更新侧边栏
    updateChatList();
    
    // 保存到本地存储
    saveChatHistory();
}

// 更新聊天列表
function updateChatList() {
    const historyDiv = document.getElementById('chat-history');
    historyDiv.innerHTML = '';
    
    chatHistory.forEach(chat => {
        const chatDiv = document.createElement('div');
        chatDiv.className = `chat-item ${chat.id === currentChatId ? 'active' : ''}`;
        chatDiv.onclick = () => loadChat(chat.id);
        
        chatDiv.innerHTML = `
            <i class="fas fa-comments"></i>
            <div class="chat-title">${chat.title}</div>
            <i class="fas fa-trash" onclick="deleteChat('${chat.id}')"></i>
        `;
        
        historyDiv.appendChild(chatDiv);
    });
}

// 加载聊天记录
async function loadChat(chatId) {
    const chat = chatHistory.find(c => c.id === chatId);
    if (!chat) return;
    
    currentChatId = chatId;
    
    try {
        // 从服务器加载完整对话历史
        const response = await fetch(`/load_chat_history/${chatId}`);
        const data = await response.json();
        
        if (response.ok && data.messages) {
            // 显示消息历史
            const messagesDiv = document.getElementById('chat-messages');
            messagesDiv.innerHTML = '';
            
            data.messages.forEach(msg => {
                addMessage(msg.content, msg.isUser, false);
            });
            
            // 更新本地存储的消息
            chat.messages = data.messages;
            saveChatHistory();
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
    
    // 更新侧边栏选中状态
    updateChatList();
}

// 删除聊天记录
async function deleteChat(chatId) {
    event.stopPropagation();
    if (!confirm('确定要删除这个对话吗？')) return;
    
    try {
        // 删除服务器上的对话记录
        await fetch(`/delete_chat/${chatId}`, { method: 'DELETE' });
        
        // 更新本地状态
        chatHistory = chatHistory.filter(c => c.id !== chatId);
        if (currentChatId === chatId) {
            if (chatHistory.length > 0) {
                loadChat(chatHistory[0].id);
            } else {
                newChat();
            }
        }
        
        saveChatHistory();
        updateChatList();
    } catch (error) {
        console.error('Error deleting chat:', error);
    }
}

// 保存聊天记录
function saveChatHistory() {
    localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
}

// 页面加载时初始化
window.addEventListener('load', () => {
    // 初始化WebSocket连接
    initWebSocket();
    
    // 初始化音频上下文
    initAudioContext();
    
    // 加载保存的聊天记录
    const saved = localStorage.getItem('chatHistory');
    if (saved) {
        chatHistory = JSON.parse(saved);
        if (chatHistory.length > 0) {
            loadChat(chatHistory[0].id);
        } else {
            newChat();
        }
    } else {
        newChat();
    }
});

// 播放TTS音频
function playTTS(audioUrl) {
    const audio = document.getElementById('tts-audio');
    audio.src = audioUrl;
    audio.play().catch(error => {
        console.error('Error playing audio:', error);
    });
}

// 查询线程状态的函数
function checkThreadStatus(chatId) {
    fetch(`/thread_status_detailed/${chatId}`)
        .then(response => response.json())
        .then(data => {
            console.log("线程状态:", data);
            
            // 更新UI显示线程状态
            const statusElement = document.getElementById('thread-status');
            if (statusElement) {
                statusElement.textContent = data.message;
                
                // 根据状态设置不同的样式
                statusElement.className = 'status-' + data.status;
            }
            
            // 如果线程仍在运行，继续轮询
            if (data.thread_alive) {
                setTimeout(() => checkThreadStatus(chatId), 2000); // 每2秒查询一次
            }
        })
        .catch(error => {
            console.error("查询线程状态出错:", error);
        });
}