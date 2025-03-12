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

// 音频播放器管理
class AudioStreamPlayer {
    constructor() {
        this.audioQueue = [];
        this.isPlaying = false;
        this.lastSegmentId = -1;
    }
    
    // 添加新的音频片段到队列
    addSegments(segments) {
        if (!segments || segments.length === 0) return;
        
        // 过滤出新的片段
        const newSegments = segments.filter(segment => segment.id > this.lastSegmentId);
        if (newSegments.length === 0) return;
        
        // 更新最后一个片段ID
        this.lastSegmentId = Math.max(...newSegments.map(segment => segment.id));
        
        // 添加到队列
        this.audioQueue.push(...newSegments);
        
        // 如果当前没有播放，开始播放
        if (!this.isPlaying) {
            this.playNext();
        }
    }
    
    // 播放下一个音频片段
    playNext() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            return;
        }
        
        this.isPlaying = true;
        const segment = this.audioQueue.shift();
        
        const audio = new Audio(segment.url);
        audio.onended = () => {
            this.playNext();
        };
        audio.onerror = (error) => {
            console.error('音频播放错误:', error);
            this.playNext();
        };
        audio.play().catch(error => {
            console.error('音频播放失败:', error);
            this.playNext();
        });
    }
    
    // 清空队列
    clear() {
        this.audioQueue = [];
        this.isPlaying = false;
        this.lastSegmentId = -1;
    }
}

// 创建音频播放器实例
const audioPlayer = new AudioStreamPlayer();

async function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // 添加用户消息到界面
    addMessage(message, true);
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    try {
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
            
            // 处理音频片段
            if (data.audio_segments && data.audio_segments.length > 0) {
                audioPlayer.addSegments(data.audio_segments);
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
    
    // 按ID倒序排列（假设ID包含时间戳，较新的在前面）
    const sortedChats = [...chatHistory].sort((a, b) => {
        // 从ID中提取时间戳部分（假设格式为chat_TIMESTAMP_randomstring）
        const timeA = a.id.split('_')[1] || 0;
        const timeB = b.id.split('_')[1] || 0;
        return timeB - timeA;  // 倒序排列
    });
    
    if (sortedChats.length === 0) {
        historyDiv.innerHTML = '<div class="no-chats">没有聊天记录</div>';
        return;
    }
    
    sortedChats.forEach(chat => {
        const chatDiv = document.createElement('div');
        chatDiv.className = `chat-item ${chat.id === currentChatId ? 'active' : ''}`;
        chatDiv.onclick = () => loadChat(chat.id);
        
        // 格式化日期（从ID中提取时间戳）
        let dateStr = '';
        try {
            const timestamp = parseInt(chat.id.split('_')[1]);
            if (!isNaN(timestamp)) {
                const date = new Date(timestamp);
                dateStr = `${date.getMonth()+1}月${date.getDate()}日 ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
            }
        } catch (e) {
            console.error('Error parsing date:', e);
        }
        
        chatDiv.innerHTML = `
            <i class="fas fa-comments"></i>
            <div class="chat-info">
                <div class="chat-title">${chat.title || '新对话'}</div>
                ${dateStr ? `<div class="chat-date">${dateStr}</div>` : ''}
            </div>
            <div class="chat-actions">
                <i class="fas fa-download download-chat" onclick="event.stopPropagation(); downloadChat('${chat.id}')" title="下载对话"></i>
                <i class="fas fa-trash delete-chat" onclick="event.stopPropagation(); deleteChat('${chat.id}')" title="删除对话"></i>
            </div>
        `;
        
        historyDiv.appendChild(chatDiv);
    });
}

// 加载聊天记录
async function loadChat(chatId) {
    try {
        // 从服务器加载完整对话历史
        const response = await fetch(`/load_chat_history/${chatId}`);
        const data = await response.json();
        
        if (response.ok && data.messages) {
            // 更新当前聊天ID
            currentChatId = chatId;
            
            // 显示消息历史
            const messagesDiv = document.getElementById('chat-messages');
            messagesDiv.innerHTML = '';
            
            // 如果没有消息，添加欢迎消息
            if (data.messages.length === 0) {
                messagesDiv.innerHTML = `
                    <div class="message system">
                        <div class="avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="message-content">
                            请医生输入患者信息(姓名，年龄，性别，手术，麻醉方式等)
                        </div>
                    </div>
                `;
            } else {
                // 显示所有消息
                data.messages.forEach(msg => {
                    addMessage(msg.content, msg.isUser, false);
                });
            }
            
            // 更新本地存储的聊天记录
            const chatIndex = chatHistory.findIndex(c => c.id === chatId);
            if (chatIndex >= 0) {
                chatHistory[chatIndex].messages = data.messages;
                
                // 更新聊天标题（使用第一条用户消息）
                const firstUserMsg = data.messages.find(msg => msg.isUser);
                if (firstUserMsg) {
                    const title = firstUserMsg.content.substring(0, 20) + (firstUserMsg.content.length > 20 ? '...' : '');
                    chatHistory[chatIndex].title = title;
                }
            } else {
                // 如果本地没有这个聊天记录，添加它
                const title = data.messages.length > 0 && data.messages[0].isUser 
                    ? data.messages[0].content.substring(0, 20) + '...' 
                    : `对话 ${chatId.substring(5, 10)}...`;
                    
                chatHistory.push({
                    id: chatId,
                    title: title,
                    messages: data.messages
                });
            }
            
            saveChatHistory();
            
            // 滚动到底部
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
    
    // 更新侧边栏选中状态
    updateChatList();
}

// 下载当前聊天记录
function downloadCurrentChat() {
    if (currentChatId) {
        downloadChat(currentChatId);
    } else {
        alert('没有可下载的对话');
    }
}

// 下载聊天记录
function downloadChat(chatId) {
    try {
        // 显示下载中的提示
        const downloadStatus = document.createElement('div');
        downloadStatus.className = 'download-status';
        downloadStatus.textContent = '正在准备下载...';
        document.body.appendChild(downloadStatus);
        
        // 直接使用location.href下载
        window.location.href = `/download_chat/${chatId}`;
        
        // 设置超时，移除状态提示
        setTimeout(() => {
            if (document.body.contains(downloadStatus)) {
                document.body.removeChild(downloadStatus);
            }
        }, 3000);
    } catch (error) {
        console.error('Error downloading chat:', error);
        alert('下载聊天记录失败，请重试');
    }
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

// 从服务器获取所有可用的聊天记录
async function fetchAllChats() {
    try {
        // 获取聊天记录目录中的所有文件
        const response = await fetch('/api/list_chats');
        const data = await response.json();
        
        if (response.ok && data.chats) {
            // 更新本地聊天历史
            const existingIds = chatHistory.map(chat => chat.id);
            
            // 添加新的聊天记录
            data.chats.forEach(chatId => {
                if (!existingIds.includes(chatId)) {
                    chatHistory.push({
                        id: chatId,
                        title: `对话 ${chatId.substring(5, 10)}...`,
                        messages: []
                    });
                }
            });
            
            saveChatHistory();
            updateChatList();
            
            // 如果有聊天记录但没有当前选中的聊天，选择第一个
            if (chatHistory.length > 0 && (!currentChatId || !chatHistory.find(c => c.id === currentChatId))) {
                loadChat(chatHistory[0].id);
            }
        }
    } catch (error) {
        console.error('Error fetching chat list:', error);
    }
}

// 页面加载时初始化
window.addEventListener('load', async () => {
    // 加载保存的聊天记录
    const saved = localStorage.getItem('chatHistory');
    if (saved) {
        chatHistory = JSON.parse(saved);
    } else {
        chatHistory = [];
    }
    
    // 从服务器获取所有可用的聊天记录
    await fetchAllChats();
    
    // 如果没有聊天记录，创建新的聊天
    if (chatHistory.length === 0) {
        newChat();
    }
});

// 轮询获取新的音频片段
function pollAudioSegments() {
    if (!currentChatId) return;
    
    fetch(`/api/audio_segments/${currentChatId}`)
    .then(response => response.json())
    .then(data => {
        if (data.audio_segments && data.audio_segments.length > 0) {
            audioPlayer.addSegments(data.audio_segments);
        }
    })
    .catch(error => {
        console.error('Error polling audio segments:', error);
    });
}

// 每秒轮询一次
setInterval(pollAudioSegments, 1000); 