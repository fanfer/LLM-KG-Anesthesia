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
                您好，我是您的麻醉医生。请问您怎么称呼？
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
function loadChat(chatId) {
    const chat = chatHistory.find(c => c.id === chatId);
    if (!chat) return;
    
    currentChatId = chatId;
    
    // 显示消息历史
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '';
    
    chat.messages.forEach(msg => {
        addMessage(msg.content, msg.isUser, false);
    });
    
    // 更新侧边栏选中状态
    updateChatList();
}

// 删除聊天记录
function deleteChat(chatId) {
    event.stopPropagation();
    if (!confirm('确定要删除这个���话吗？')) return;
    
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