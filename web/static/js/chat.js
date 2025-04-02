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
        this.playedSegments = []; // 存储已播放的片段ID
        this.retryMap = new Map(); // 存储重试次数的映射
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
        
        // 检查URL是否有效
        if (!segment || !segment.url) {
            console.error('无效的音频片段:', segment);
            // 显示错误提示
            this._showErrorToast('音频片段无效，已跳过');
            this.notifySegmentPlayed(segment ? segment.id : -1); // 标记为已播放
            this.playNext(); // 继续播放下一个
            return;
        }
        
        // 获取当前片段的重试次数
        const segmentId = segment.id;
        const retryCount = this.retryMap.get(segmentId) || 0;
        
        console.log('开始播放音频片段:', segmentId, segment.url, '重试次数:', retryCount);
        
        const audio = new Audio(segment.url);
        
        // 设置超时，防止音频加载过久
        const loadTimeout = setTimeout(() => {
            console.warn('音频加载超时:', segment.url);
            
            // 检查是否可以重试
            if (retryCount < 1) {
                console.log('音频加载超时，尝试重试:', segmentId);
                this._showErrorToast('音频加载超时，正在重试...');
                
                // 更新重试次数
                this.retryMap.set(segmentId, retryCount + 1);
                
                // 将片段重新添加到队列前面
                this.audioQueue.unshift(segment);
                
                // 清除超时并继续下一个
                clearTimeout(loadTimeout);
                this.playNext();
            } else {
                // 已达到最大重试次数
                this._showErrorToast('音频加载超时，已跳过');
                this.retryMap.delete(segmentId); // 清除重试记录
                audio.onerror(new Error('音频加载超时'));
            }
        }, 5000);
        
        // 音频加载完成时清除超时
        audio.onloadeddata = () => {
            clearTimeout(loadTimeout);
        };
        
        audio.onended = () => {
            console.log('音频片段播放完成:', segmentId);
            // 清除重试记录
            this.retryMap.delete(segmentId);
            // 通知服务器该片段已播放完成
            this.notifySegmentPlayed(segmentId);
            this.playNext();
        };
        
        audio.onerror = (error) => {
            clearTimeout(loadTimeout);
            console.error('音频播放错误:', error, segment.url);
            
            // 检查是否可以重试
            if (retryCount < 1) {
                console.log('音频播放错误，尝试重试:', segmentId);
                this._showErrorToast('音频播放失败，正在重试...');
                
                // 更新重试次数
                this.retryMap.set(segmentId, retryCount + 1);
                
                // 将片段重新添加到队列前面
                this.audioQueue.unshift(segment);
                
                // 继续下一个
                this.playNext();
            } else {
                // 已达到最大重试次数
                this._showErrorToast('音频播放失败，已跳过');
                this.retryMap.delete(segmentId); // 清除重试记录
                this.notifySegmentPlayed(segmentId); // 即使出错也标记为已播放
                this.playNext();
            }
        };
        
        // 添加加载事件处理
        audio.onloadstart = () => console.log('音频开始加载:', segmentId);
        audio.oncanplay = () => console.log('音频可以播放:', segmentId);
        
        // 尝试播放音频
        audio.play().catch(error => {
            console.error('音频播放失败:', error, segment.url);
            
            // 检查是否可以重试
            if (retryCount < 1) {
                console.log('音频播放失败，尝试重试:', segmentId);
                this._showErrorToast('音频播放失败，正在重试...');
                
                // 更新重试次数
                this.retryMap.set(segmentId, retryCount + 1);
                
                // 将片段重新添加到队列前面
                this.audioQueue.unshift(segment);
                
                // 继续下一个
                this.playNext();
            } else {
                // 已达到最大重试次数
                this._showErrorToast('音频播放失败，已跳过');
                this.retryMap.delete(segmentId); // 清除重试记录
                this.notifySegmentPlayed(segmentId); // 即使出错也标记为已播放
                this.playNext();
            }
        });
    }
    
    // 显示错误提示
    _showErrorToast(message) {
        // 创建或获取toast容器
        let toastContainer = document.getElementById('audio-toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'audio-toast-container';
            toastContainer.style.position = 'fixed';
            toastContainer.style.bottom = '20px';
            toastContainer.style.right = '20px';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }
        
        // 创建toast元素
        const toast = document.createElement('div');
        toast.className = 'audio-error-toast';
        toast.style.backgroundColor = 'rgba(255, 0, 0, 0.8)';
        toast.style.color = 'white';
        toast.style.padding = '10px 15px';
        toast.style.borderRadius = '4px';
        toast.style.marginTop = '10px';
        toast.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
        toast.style.display = 'flex';
        toast.style.alignItems = 'center';
        toast.style.transition = 'opacity 0.5s';
        
        // 添加图标
        const icon = document.createElement('i');
        icon.className = 'fas fa-exclamation-circle';
        icon.style.marginRight = '10px';
        toast.appendChild(icon);
        
        // 添加消息
        const messageSpan = document.createElement('span');
        messageSpan.textContent = message;
        toast.appendChild(messageSpan);
        
        // 添加到容器
        toastContainer.appendChild(toast);
        
        // 3秒后自动消失
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 500);
        }, 3000);
    }
    
    // 通知服务器片段已播放完成
    notifySegmentPlayed(segmentId) {
        // 避免重复通知
        if (this.playedSegments.includes(segmentId) && segmentId !== -1) return;
        
        // 如果是-1（删除所有片段）或者是普通片段ID
        if (segmentId === -1) {
            // 立即发送删除所有片段的请求
            fetch('/api/delete_played_segments', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    chatId: currentChatId,
                    segmentIds: [-1]
                })
            })
            .then(response => {
                if (response.ok) {
                    console.log('已通知服务器删除所有音频片段');
                    this.playedSegments = []; // 清空已通知的片段列表
                }
            })
            .catch(error => {
                console.error('通知服务器删除音频片段失败:', error);
            });
        } else {
            this.playedSegments.push(segmentId);
            
            // 立即发送删除请求，不等待积累
            fetch('/api/delete_played_segments', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    chatId: currentChatId,
                    segmentIds: this.playedSegments
                })
            })
            .then(response => {
                if (response.ok) {
                    console.log('已通知服务器删除播放完成的音频片段');
                    this.playedSegments = []; // 清空已通知的片段列表
                }
            })
            .catch(error => {
                console.error('通知服务器删除音频片段失败:', error);
            });
        }
    }
    
    // 清空队列
    clear() {
        this.audioQueue = [];
        this.isPlaying = false;
        this.lastSegmentId = -1;
        this.retryMap.clear(); // 清空重试记录
        
        // 立即通知服务器删除所有片段
        this.notifySegmentPlayed(-1);
    }
}

// 创建音频播放器实例
const audioPlayer = new AudioStreamPlayer();

// 音频流连接管理
let audioEventSource = null;

// 连接到音频流
function connectToAudioStream(chatId) {
    // 如果已经有连接，先关闭
    if (audioEventSource) {
        audioEventSource.close();
        audioEventSource = null;
    }
    
    // 创建新的EventSource连接
    audioEventSource = new EventSource(`/api/audio_stream/${chatId}`);
    
    // 连接建立时的处理
    audioEventSource.onopen = function() {
        console.log('已连接到音频流');
    };
    
    // 接收消息的处理
    audioEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'audio_segments' && data.segments && data.segments.length > 0) {
                // 处理新的音频片段
                audioPlayer.addSegments(data.segments);
            } else if (data.type === 'audio_errors' && data.errors && data.errors.length > 0) {
                // 处理音频错误信息
                console.warn('收到音频错误信息:', data.errors);
                
                // 显示错误提示
                for (const error of data.errors) {
                    const errorMessage = `音频片段 #${error.id} 播放失败: ${error.error}`;
                    audioPlayer._showErrorToast(errorMessage);
                }
            } else if (data.type === 'error') {
                // 处理服务器错误
                console.error('服务器错误:', data.message);
                audioPlayer._showErrorToast(`服务器错误: ${data.message}`);
            } else if (data.type === 'timeout') {
                // 处理连接超时
                console.warn('音频流连接超时:', data.message);
                audioPlayer._showErrorToast('音频流连接超时，请刷新页面');
                
                // 关闭连接
                if (audioEventSource) {
                    audioEventSource.close();
                    audioEventSource = null;
                }
            }
        } catch (error) {
            console.error('处理音频流消息出错:', error);
        }
    };
    
    // 错误处理
    audioEventSource.onerror = function(error) {
        console.error('音频流连接错误:', error);
        audioPlayer._showErrorToast('音频流连接错误，尝试重新连接中...');
        
        // 尝试重新连接
        setTimeout(() => {
            if (audioEventSource) {
                audioEventSource.close();
                audioEventSource = null;
                connectToAudioStream(chatId);
            }
        }, 3000);
    };
}

// 关闭音频流连接
function closeAudioStream() {
    if (audioEventSource) {
        audioEventSource.close();
        audioEventSource = null;
    }
}

// 添加标记变量
let hasPlayedCompletionAudio = false;

// 播放完成音频
function playCompletionAudio() {
    if (hasPlayedCompletionAudio) {
        return; // 如果已经播放过,直接返回
    }
    const audio = document.getElementById('tts-audio');
    audio.src = '/static/output.wav';
    audio.play().catch(error => {
        console.error('播放完成音频失败:', error);
    });
    hasPlayedCompletionAudio = true; // 标记为已播放
}

async function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // 清空音频队列并删除所有相关的音频文件
    audioPlayer.clear();
    
    // 在发送新消息前，确保删除当前会话的所有音频文件
    try {
        await fetch('/api/delete_played_segments', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chatId: currentChatId,
                segmentIds: [-1]  // -1表示删除所有片段
            })
        });
        console.log('已删除当前会话的所有音频文件');
    } catch (error) {
        console.error('删除音频文件失败:', error);
    }
    
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
            
            // 检查是否需要播放完成音频
            if (data.current_step === 100 && !hasPlayedCompletionAudio) {
                playCompletionAudio();
            }
            
            // 不再需要处理音频片段，因为会通过SSE推送
            // 如果初始响应中包含音频片段，仍然可以处理
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
async function newChat() {
    try {
        // 重置完成音频播放标记
        hasPlayedCompletionAudio = false;
        
        // 如果有当前聊天，先结束它
        if (currentChatId) {
            // 删除当前会话的所有音频文件
            try {
                await fetch('/api/delete_played_segments', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        chatId: currentChatId,
                        segmentIds: [-1]  // -1表示删除所有片段
                    })
                });
                console.log('已删除当前会话的所有音频文件');
            } catch (error) {
                console.error('删除音频文件失败:', error);
            }
            
            fetch(`/end_session/${currentChatId}`, { method: 'POST' })
            .catch(error => console.error('结束会话出错:', error));
            
            // 关闭当前音频流
            closeAudioStream();
            
            // 清空音频播放器
            audioPlayer.clear();
        }
        
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
        
        // 连接到新的音频流
        connectToAudioStream(currentChatId);
        
        // 更新侧边栏
        updateChatList();
        
        // 保存到本地存储
        saveChatHistory();
        
        // 滚动到底部
        document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
        
        // 如果是移动端，自动隐藏侧边栏
        if (window.innerWidth <= 768) {
            closeSidebar();
        }
        
        // 更新聊天历史列表
        updateChatList();
    } catch (error) {
        console.error('创建新聊天出错:', error);
    }
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
        // 如果有当前聊天，先结束它
        if (currentChatId && currentChatId !== chatId) {
            // 删除当前会话的所有音频文件
            try {
                await fetch('/api/delete_played_segments', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        chatId: currentChatId,
                        segmentIds: [-1]  // -1表示删除所有片段
                    })
                });
                console.log('已删除当前会话的所有音频文件');
            } catch (error) {
                console.error('删除音频文件失败:', error);
            }
            
            fetch(`/end_session/${currentChatId}`, { method: 'POST' })
            .catch(error => console.error('结束会话出错:', error));
            
            // 关闭当前音频流
            closeAudioStream();
            
            // 清空音频播放器
            audioPlayer.clear();
        }
        
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
            
            // 如果是移动端，自动隐藏侧边栏
            if (window.innerWidth <= 768) {
                closeSidebar();
            }
            
            // 连接到新的音频流
            connectToAudioStream(chatId);
            
            // 确保新会话开始时没有旧的音频文件
            try {
                await fetch('/api/delete_played_segments', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        chatId: chatId,
                        segmentIds: [-1]  // -1表示删除所有片段
                    })
                });
                console.log('已清理新会话的旧音频文件');
            } catch (error) {
                console.error('清理音频文件失败:', error);
            }
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
    
    // 如果有当前聊天ID，连接到音频流
    if (currentChatId) {
        connectToAudioStream(currentChatId);
    }
});

// 在页面关闭时关闭音频流
window.addEventListener('beforeunload', () => {
    closeAudioStream();
    
    if (currentChatId) {
        // 使用同步请求确保在页面关闭前发送
        navigator.sendBeacon(`/end_session/${currentChatId}`);
    }
});

// 检测是否为移动设备
function isMobileDevice() {
    return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
}

// 移动端音频播放辅助函数
function playAudioOnMobile(audioElement, onSuccess, onError) {
    console.log('使用移动端音频播放辅助函数');
    
    // 确保音频元素已经准备好
    if (audioElement.readyState === 0) {
        audioElement.load();
    }
    
    // 添加一次性点击事件处理器来触发播放
    const playHandler = function() {
        console.log('用户交互触发音频播放');
        
        // 移除事件监听器
        document.removeEventListener('click', playHandler);
        
        // 尝试播放
        const playPromise = audioElement.play();
        
        if (playPromise !== undefined) {
            playPromise.then(() => {
                console.log('移动端音频播放成功');
                if (onSuccess) onSuccess();
            }).catch(error => {
                console.error('移动端音频播放失败:', error);
                if (onError) onError(error);
            });
        }
    };
    
    // 如果已经有用户交互，直接尝试播放
    const playPromise = audioElement.play();
    
    if (playPromise !== undefined) {
        playPromise.then(() => {
            console.log('直接播放成功');
            if (onSuccess) onSuccess();
        }).catch(error => {
            console.error('直接播放失败，等待用户交互:', error);
            // 需要用户交互，添加点击事件
            document.addEventListener('click', playHandler);
            
            // 提示用户需要交互
            alert('请点击屏幕任意位置开始播放音频');
        });
    }
}

// 播放最后一条AI消息
async function playLastMessage() {
    try {
        // 获取所有消息元素
        const messages = document.querySelectorAll('.message');
        if (messages.length === 0) return;
        
        // 找到最后一条AI消息
        let lastAIMessage = null;
        for (let i = messages.length - 1; i >= 0; i--) {
            if (!messages[i].classList.contains('user')) {
                lastAIMessage = messages[i];
                break;
            }
        }
        
        if (!lastAIMessage) {
            console.log('没有找到AI消息');
            audioPlayer._showErrorToast('没有找到可播放的消息');
            return;
        }
        
        // 获取消息内容
        const messageContent = lastAIMessage.querySelector('.message-content').textContent.trim();
        if (!messageContent) {
            console.log('消息内容为空');
            audioPlayer._showErrorToast('消息内容为空，无法播放');
            return;
        }
        
        // 显示加载状态
        const ttsBtn = document.getElementById('tts-btn');
        const originalContent = ttsBtn.innerHTML;
        ttsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
        ttsBtn.disabled = true;
        
        // 清空当前音频队列并删除所有相关的音频文件
        audioPlayer.clear();
        
        // 在播放新音频前，确保删除当前会话的所有音频文件
        try {
            await fetch('/api/delete_played_segments', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    chatId: currentChatId,
                    segmentIds: [-1]  // -1表示删除所有片段
                })
            });
            console.log('已删除当前会话的所有音频文件');
        } catch (error) {
            console.error('删除音频文件失败:', error);
            // 继续执行，不阻止播放尝试
        }
        
        // 设置全局超时，确保按钮状态最终会恢复
        const globalTimeout = setTimeout(() => {
            console.warn('TTS操作超时，恢复按钮状态');
            ttsBtn.innerHTML = originalContent;
            ttsBtn.disabled = false;
            audioPlayer._showErrorToast('语音生成超时，请重试');
        }, 15000); // 15秒超时
        
        // 尝试播放函数，支持重试
        const tryPlayAudio = async (retryCount = 0) => {
            try {
                // 调用TTS API
                const response = await fetch('/api/tts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        text: messageContent,
                        chatId: currentChatId
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    // 获取或创建音频元素
                    let audio;
                    if (isMobileDevice()) {
                        // 在移动设备上使用已有的audio元素
                        audio = document.getElementById('tts-audio');
                    } else {
                        // 在桌面设备上创建新的音频元素
                        audio = new Audio();
                    }
                    
                    // 设置加载超时
                    const loadTimeout = setTimeout(() => {
                        console.warn('音频加载超时');
                        
                        if (retryCount < 1) {
                            // 尝试重试
                            console.log('音频加载超时，尝试重试');
                            audioPlayer._showErrorToast('音频加载超时，正在重试...');
                            clearTimeout(loadTimeout);
                            
                            // 重试
                            tryPlayAudio(retryCount + 1);
                        } else {
                            // 已达到最大重试次数
                            clearTimeout(globalTimeout);
                            ttsBtn.innerHTML = originalContent;
                            ttsBtn.disabled = false;
                            
                            // 显示错误提示
                            audioPlayer._showErrorToast('音频加载超时，已跳过');
                            
                            // 尝试删除音频文件
                            fetch('/api/delete_played_segments', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    chatId: currentChatId,
                                    segmentIds: [-1]
                                })
                            }).catch(e => console.error('删除音频文件失败:', e));
                        }
                    }, 8000); // 8秒加载超时
                    
                    // 显示播放状态
                    ttsBtn.innerHTML = '<i class="fas fa-play"></i> 播放中...';
                    
                    // 添加所有可能的事件处理
                    audio.onloadeddata = () => {
                        console.log('音频数据已加载');
                        clearTimeout(loadTimeout);
                        
                        if (isMobileDevice()) {
                            // 使用移动端辅助函数播放
                            playAudioOnMobile(audio, 
                                // 成功回调
                                () => {
                                    console.log('移动端音频播放成功');
                                },
                                // 失败回调
                                (error) => {
                                    console.error('移动端音频播放失败:', error);
                                    
                                    if (retryCount < 1) {
                                        // 尝试重试
                                        console.log('移动端音频播放失败，尝试重试');
                                        audioPlayer._showErrorToast('音频播放失败，正在重试...');
                                        
                                        // 重试
                                        tryPlayAudio(retryCount + 1);
                                    } else {
                                        // 已达到最大重试次数
                                        clearTimeout(globalTimeout);
                                        ttsBtn.innerHTML = originalContent;
                                        ttsBtn.disabled = false;
                                        audioPlayer._showErrorToast('移动端音频播放失败，已跳过');
                                    }
                                }
                            );
                        } else {
                            // 桌面端直接播放
                            const playPromise = audio.play();
                            
                            if (playPromise !== undefined) {
                                playPromise.then(() => {
                                    console.log('音频开始播放');
                                }).catch(error => {
                                    console.error('播放音频失败:', error);
                                    
                                    if (retryCount < 1) {
                                        // 尝试重试
                                        console.log('音频播放失败，尝试重试');
                                        audioPlayer._showErrorToast('音频播放失败，正在重试...');
                                        
                                        // 重试
                                        tryPlayAudio(retryCount + 1);
                                    } else {
                                        // 已达到最大重试次数
                                        clearTimeout(globalTimeout);
                                        ttsBtn.innerHTML = originalContent;
                                        ttsBtn.disabled = false;
                                        audioPlayer._showErrorToast('播放音频失败，已跳过');
                                    }
                                });
                            }
                        }
                    };
                    
                    audio.oncanplay = () => {
                        console.log('音频可以播放');
                    };
                    
                    audio.onplay = () => {
                        console.log('音频播放开始');
                        ttsBtn.innerHTML = '<i class="fas fa-volume-up"></i> 播放中...';
                    };
                    
                    audio.onended = () => {
                        console.log('音频播放完成');
                        // 播放结束后恢复按钮状态
                        clearTimeout(globalTimeout);
                        ttsBtn.innerHTML = originalContent;
                        ttsBtn.disabled = false;
                        
                        // 播放结束后删除音频文件
                        fetch('/api/delete_played_segments', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                chatId: currentChatId,
                                segmentIds: [-1]  // -1表示删除所有片段
                            })
                        }).catch(error => {
                            console.error('删除音频文件失败:', error);
                        });
                    };
                    
                    audio.onerror = (error) => {
                        console.error('音频加载错误:', error);
                        clearTimeout(loadTimeout);
                        
                        if (retryCount < 1) {
                            // 尝试重试
                            console.log('音频加载错误，尝试重试');
                            audioPlayer._showErrorToast('音频加载失败，正在重试...');
                            
                            // 重试
                            tryPlayAudio(retryCount + 1);
                        } else {
                            // 已达到最大重试次数
                            clearTimeout(globalTimeout);
                            ttsBtn.innerHTML = originalContent;
                            ttsBtn.disabled = false;
                            
                            // 显示错误提示
                            audioPlayer._showErrorToast('音频加载失败，已跳过');
                        }
                    };
                    
                    audio.onabort = () => {
                        console.log('音频播放被中止');
                        clearTimeout(loadTimeout);
                        clearTimeout(globalTimeout);
                        ttsBtn.innerHTML = originalContent;
                        ttsBtn.disabled = false;
                        audioPlayer._showErrorToast('音频播放被中止');
                    };
                    
                    audio.onstalled = () => {
                        console.log('音频播放停滞');
                        audioPlayer._showErrorToast('音频播放停滞，尝试恢复中...');
                    };
                    
                    // 添加时间更新事件，确认音频正在播放
                    let playbackStarted = false;
                    audio.ontimeupdate = () => {
                        if (!playbackStarted) {
                            console.log('音频播放进行中:', audio.currentTime);
                            playbackStarted = true;
                        }
                    };
                    
                    // 设置音频源并添加时间戳防止缓存
                    audio.src = data.audio_url + '?t=' + new Date().getTime();
                    
                    // 预加载音频
                    audio.load();
                } else {
                    console.error('TTS API错误:', data.error);
                    
                    if (retryCount < 1) {
                        // 尝试重试
                        console.log('TTS API错误，尝试重试');
                        audioPlayer._showErrorToast('生成语音失败，正在重试...');
                        
                        // 重试
                        tryPlayAudio(retryCount + 1);
                    } else {
                        // 已达到最大重试次数
                        clearTimeout(globalTimeout);
                        audioPlayer._showErrorToast('生成语音失败，已跳过');
                        ttsBtn.innerHTML = originalContent;
                        ttsBtn.disabled = false;
                    }
                }
            } catch (error) {
                console.error('播放音频出错:', error);
                
                if (retryCount < 1) {
                    // 尝试重试
                    console.log('播放音频出错，尝试重试');
                    audioPlayer._showErrorToast('播放失败，正在重试...');
                    
                    // 重试
                    tryPlayAudio(retryCount + 1);
                } else {
                    // 已达到最大重试次数
                    clearTimeout(globalTimeout);
                    audioPlayer._showErrorToast('播放失败，已跳过');
                    ttsBtn.innerHTML = originalContent;
                    ttsBtn.disabled = false;
                }
            }
        };
        
        // 开始第一次尝试
        await tryPlayAudio(0);
        
    } catch (error) {
        console.error('播放最后一条消息出错:', error);
        audioPlayer._showErrorToast('播放失败，请重试');
        
        // 恢复按钮状态
        const ttsBtn = document.getElementById('tts-btn');
        ttsBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
        ttsBtn.disabled = false;
    }
} 