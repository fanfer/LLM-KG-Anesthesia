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

async function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    
    if (!message) return;
    if (!currentChatId) {
        alert('请先创建或选择一个对话');
        return;
    }
    
    // 显示用户消息并保存到历史记录
    addMessage(message, true);
    input.value = '';
    
    try {
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                chatId: currentChatId,
                messages: chatHistory.find(c => c.id === currentChatId)?.messages || []
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 显示系统回复，但不再次保存到历史记录（因为已经在addMessage中保存了）
            addMessage(data.response, false, false);
        } else {
            addMessage('Error: ' + data.error, false, false);
        }
    } catch (error) {
        addMessage('Error: ' + error.message, false, false);
    }
}

// 监听键盘事件
document.getElementById('message-input').addEventListener('keydown', function(e) {
    // 如果按下Enter键且没有按住Shift键（Shift+Enter用于换行）
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault(); // 阻止默认的换行行为
        sendMessage();
    }
});

// 添加提示信息
document.getElementById('message-input').setAttribute('placeholder', '请输入消息...\n按Enter发送，Shift+Enter换行'); 

// 存储聊天历史
let chatHistory = [];
let currentChatId = null;

// 创建新聊天
function newChat() {
    // 生成唯一ID
    const chatId = Date.now().toString();
    const chatData = {
        id: chatId,
        title: '新对话',
        messages: []
    };
    
    chatHistory.push(chatData);
    currentChatId = chatId;
    
    // 清空聊天区域
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

// 语音输入
let mediaRecorder;
let audioChunks = [];

document.getElementById('voice-input-btn').addEventListener('click', function() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        // 开始录音
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.readAsDataURL(audioBlob);
                    reader.onloadend = async () => {
                        try {
                            const response = await fetch('/speech-to-text', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ audio: reader.result })
                            });
                            const data = await response.json();
                            if (data.text) {
                                document.getElementById('message-input').value = data.text;
                            }
                        } catch (error) {
                            console.error('Error:', error);
                        }
                    };
                    audioChunks = [];
                };
                mediaRecorder.start();
                this.classList.add('recording');
            });
    } else {
        // 停止录音
        mediaRecorder.stop();
        this.classList.remove('recording');
    }
});

// 语音输出
document.getElementById('voice-output-btn').addEventListener('click', async function() {
    const lastMessage = document.querySelector('.message.system:last-child .message-content');
    if (lastMessage) {
        try {
            const response = await fetch('/text-to-speech', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: lastMessage.textContent })
            });
            const data = await response.json();
            if (data.audio) {
                const audio = new Audio(data.audio);
                audio.play();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
}); 