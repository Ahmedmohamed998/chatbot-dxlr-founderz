import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { 
  MessageSquare, Send, Bot, User, UserCog, Search, 
  Phone, Clock, MoreVertical, Sparkles, Loader2, Wifi, WifiOff,
  Pencil, Check, X, UserCheck, Paperclip, FileText, Download, ZoomIn, Volume2, Mic, Square, Trash2
} from 'lucide-react';
import { Switch } from '../components/ui/switch';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const ChatSkeleton = () => (
  <div className="space-y-3 p-4">
    {[...Array(5)].map((_, i) => (
      <div key={i} className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full skeleton" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-1/3 skeleton rounded" />
          <div className="h-3 w-2/3 skeleton rounded" />
        </div>
      </div>
    ))}
  </div>
);

const MessageSkeleton = () => (
  <div className="space-y-4 p-4">
    {[...Array(6)].map((_, i) => (
      <div key={i} className={`flex ${i % 2 === 0 ? 'justify-start' : 'justify-end'}`}>
        <div className={`h-12 ${i % 2 === 0 ? 'w-2/3' : 'w-1/2'} skeleton rounded-lg`} />
      </div>
    ))}
  </div>
);

// Avatar with initials when name is saved
const ContactAvatar = ({ name, phone }) => {
  const hasName = name && name !== phone;
  const initials = hasName
    ? name.trim().split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : null;
  return (
    <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 border ${
      hasName
        ? 'bg-[#00E599]/10 border-[#00E599]/30 text-[#00E599] font-semibold text-sm'
        : 'bg-[#111] border-white/10'
    }`}>
      {hasName ? initials : <Phone className="w-4 h-4 text-zinc-400" />}
    </div>
  );
};

const Inbox = () => {
  const { api } = useAuth();
  const { success, error, info } = useToast();
  
  const [chats, setChats] = useState([]);
  const [selectedChat, setSelectedChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isTogglingAI, setIsTogglingAI] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [totalChats, setTotalChats] = useState(0);
  const chatListRef = useRef(null);
  const loadMoreRef = useRef(null);

  // Contact name editing state
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [isSavingName, setIsSavingName] = useState(false);
  const nameInputRef = useRef(null);
  // Unread tracking (session ids that have unread messages)
  const [unreadSessions, setUnreadSessions] = useState(new Set());
  const [lightboxImage, setLightboxImage] = useState(null);

  // Audio Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerIntervalRef = useRef(null);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const wsRef = useRef(null);
  const selectedChatRef = useRef(null);
  
  useEffect(() => { selectedChatRef.current = selectedChat; }, [selectedChat]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchChats = useCallback(async (page = 1, append = false) => {
    if (page === 1) setIsLoadingChats(true);
    else setIsLoadingMore(true);
    try {
      const response = await api.get(`/chats?page=${page}&limit=50`);
      const { chats: newChats, has_more, total } = response.data;
      setChats(prev => append ? [...prev, ...newChats] : newChats);
      setHasMore(has_more);
      setTotalChats(total);
      setCurrentPage(page);
    } catch (err) {
      console.error('Failed to fetch chats:', err);
    } finally {
      setIsLoadingChats(false);
      setIsLoadingMore(false);
    }
  }, [api]);

  const fetchMoreChats = useCallback(() => {
    if (!isLoadingMore && hasMore) {
      fetchChats(currentPage + 1, true);
    }
  }, [fetchChats, currentPage, hasMore, isLoadingMore]);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) fetchMoreChats(); },
      { threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [fetchMoreChats]);

  const fetchMessages = useCallback(async (phone) => {
    setIsLoadingMessages(true);
    try {
      const response = await api.get(`/chats/${phone}/messages`);
      setMessages(response.data);
    } catch (err) {
      console.error('Failed to fetch messages:', err);
      error('Failed to load messages');
    } finally {
      setIsLoadingMessages(false);
    }
  }, [api, error]);

  useEffect(() => { fetchChats(); }, [fetchChats]);
  
  // WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      const wsUrl = BACKEND_URL.replace(/^http/, 'ws') + '/api/ws';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onopen = () => { setWsConnected(true); info('Real-time updates connected'); };
      
      ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'new_message') {
            const msgData = data.data;
            const currentChat = selectedChatRef.current;
            const isCurrentChat = currentChat && currentChat.contact?.phone_number === msgData.phone_number;

            // Smart update: move chat to top + update last_message without refetching
            setChats(prev => {
              const idx = prev.findIndex(c => c.contact?.phone_number === msgData.phone_number);
              const newLastMsg = {
                id: msgData.id, session_id: msgData.session_id,
                direction: msgData.direction, sender_type: msgData.sender_type,
                text: msgData.text, status: 'sent', created_at: msgData.created_at,
                media_url: msgData.media_url, media_type: msgData.media_type
              };
              if (idx === -1) {
                // New contact not in list yet — do a background refresh without touching scroll
                fetchChats(1, false);
                return prev;
              }
              const updated = { ...prev[idx], last_message: newLastMsg };
              return [updated, ...prev.filter((_, i) => i !== idx)];
            });

            // Mark as unread if not the currently open chat
            if (!isCurrentChat) {
              setUnreadSessions(prev => new Set([...prev, msgData.session_id]));
            }

            // Append message to open chat
            if (isCurrentChat) {
              setMessages(prev => {
                if (prev.some(m => m.id === msgData.id)) return prev;
                return [...prev, {
                  id: msgData.id, session_id: msgData.session_id,
                  direction: msgData.direction, sender_type: msgData.sender_type,
                  text: msgData.text, status: 'sent', created_at: msgData.created_at,
                  media_url: msgData.media_url, media_type: msgData.media_type
                }];
              });
            }
          }
        } catch (e) { console.error('WS parse error:', e); }
      };
      
      ws.onclose = () => { setWsConnected(false); setTimeout(connectWebSocket, 3000); };
      ws.onerror = (err) => { console.error('WS error:', err); ws.close(); };
      
      const heartbeat = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 30000);
      
      return () => { clearInterval(heartbeat); ws.close(); };
    };
    const cleanup = connectWebSocket();
    return cleanup;
  }, [fetchChats, info]);

  useEffect(() => {
    if (selectedChat) fetchMessages(selectedChat.contact.phone_number);
  }, [selectedChat, fetchMessages]);

  useEffect(() => { scrollToBottom(); }, [messages]);

  // Focus name input when editing starts
  useEffect(() => {
    if (isEditingName) {
      setTimeout(() => nameInputRef.current?.focus(), 50);
    }
  }, [isEditingName]);

  const handleSelectChat = (chat) => {
    setSelectedChat(chat);
    setMessages([]);
    setIsEditingName(false);
    // Mark as read
    setUnreadSessions(prev => {
      const next = new Set(prev);
      next.delete(chat.id);
      return next;
    });
    inputRef.current?.focus();
  };

  const uploadFile = async (file) => {
    if (!file || !selectedChat || isSending) return;
    
    // Check file size limit (e.g. 16MB Meta limit for most media)
    if (file.size > 16 * 1024 * 1024) {
      error('File is too large (max 16MB)');
      return;
    }

    setIsSending(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      await api.post(`/chats/${selectedChat.contact.phone_number}/send-media`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      success('Media sent');
    } catch (err) {
      error('Failed to send media');
    } finally {
      setIsSending(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSendMedia = async (e) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  // Voice Recording Functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Microphone access denied or error:', err);
      error('Microphone access denied');
    }
  };

  const stopRecordingAndSend = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.onstop = async () => {
        const mimeType = mediaRecorderRef.current.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        const extension = mimeType.includes('mp4') ? 'mp4' : mimeType.includes('webm') ? 'webm' : 'ogg';
        const audioFile = new File([audioBlob], `voice_note_${Date.now()}.${extension}`, { type: mimeType });
        await uploadFile(audioFile);
        
        // Cleanup stream
        mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      clearInterval(timerIntervalRef.current);
      setRecordingTime(0);
    }
  };

  const cancelRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.onstop = () => {
        // Cleanup stream without saving
        mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      };
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      clearInterval(timerIntervalRef.current);
      setRecordingTime(0);
      audioChunksRef.current = [];
    }
  };

  const formatRecordingTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedChat || isSending) return;
    setIsSending(true);
    try {
      await api.post(`/chats/${selectedChat.contact.phone_number}/send`, { text: newMessage.trim() });
      setNewMessage('');
      success('Message sent');
    } catch (err) {
      error('Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  const handleToggleAI = async () => {
    if (!selectedChat || isTogglingAI) return;
    setIsTogglingAI(true);
    try {
      const newPausedState = !selectedChat.is_bot_paused;
      await api.put(`/chats/${selectedChat.contact.phone_number}/toggle-ai`, { is_paused: newPausedState });
      setSelectedChat(prev => ({ ...prev, is_bot_paused: newPausedState }));
      success(newPausedState ? 'AI Bot paused' : 'AI Bot resumed');
      await fetchChats();
    } catch (err) {
      error('Failed to toggle AI');
    } finally {
      setIsTogglingAI(false);
    }
  };

  const handleStartEditName = () => {
    const currentName = selectedChat?.contact?.name;
    const phone = selectedChat?.contact?.phone_number;
    // If name is the phone number (no custom name yet), start with empty
    setNameInput(currentName && currentName !== phone ? currentName : '');
    setIsEditingName(true);
  };

  const handleSaveName = async () => {
    if (!nameInput.trim() || !selectedChat) return;
    setIsSavingName(true);
    try {
      const phone = selectedChat.contact.phone_number;
      await api.put(`/contacts/${phone}/name`, { name: nameInput.trim() });
      
      // Update selectedChat state
      const updatedContact = { ...selectedChat.contact, name: nameInput.trim() };
      setSelectedChat(prev => ({ ...prev, contact: updatedContact }));
      
      // Update in chats list too
      setChats(prev => prev.map(c =>
        c.id === selectedChat.id
          ? { ...c, contact: { ...c.contact, name: nameInput.trim() } }
          : c
      ));
      
      setIsEditingName(false);
      success(`Contact saved as "${nameInput.trim()}"`);
    } catch (err) {
      error(err.response?.data?.detail || 'Failed to save contact');
    } finally {
      setIsSavingName(false);
    }
  };

  const handleCancelEdit = () => {
    setIsEditingName(false);
    setNameInput('');
  };

  const filteredChats = chats.filter((chat) => {
    const q = searchQuery.toLowerCase();
    return (
      chat.contact?.phone_number?.toLowerCase().includes(q) ||
      chat.contact?.name?.toLowerCase().includes(q) ||
      chat.last_message?.text?.toLowerCase().includes(q)
    );
  });

  const formatTime = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return date.toLocaleDateString('en-US', { weekday: 'short' });
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getBubbleIcon = (senderType) => {
    if (senderType === 'CUSTOMER') return <User className="w-3 h-3" />;
    if (senderType === 'BOT') return <Bot className="w-3 h-3" />;
    if (senderType === 'ADMIN') return <UserCog className="w-3 h-3" />;
    return null;
  };

  const getBubbleClass = (senderType) => {
    if (senderType === 'CUSTOMER') return 'bubble-customer';
    if (senderType === 'BOT') return 'bubble-bot';
    if (senderType === 'ADMIN') return 'bubble-admin';
    return 'bubble-customer';
  };

  const contactHasCustomName = (chat) => {
    return chat?.contact?.name && chat.contact.name !== chat.contact.phone_number;
  };

  return (
    <>
      <div className="h-screen flex" data-testid="inbox-page">
        {/* Chat List Panel */}
      <div className="w-[350px] border-r border-white/5 flex flex-col bg-[#0A0A0A]">
        {/* Header */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-white/5">
          <div className="flex items-center">
            <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'Cabinet Grotesk' }}>Inbox</h1>
            <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-[#00E599]/10 text-[#00E599] rounded-full">
              {totalChats || chats.length}
            </span>
          </div>
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${
              wsConnected ? 'bg-[#00E599]/10 text-[#00E599]' : 'bg-amber-500/10 text-amber-400'
            }`}
            title={wsConnected ? 'Real-time updates active' : 'Reconnecting...'}
            data-testid="ws-status-indicator"
          >
            {wsConnected ? <><Wifi className="w-3 h-3" /><span>Live</span></> : <><WifiOff className="w-3 h-3" /><span>Connecting</span></>}
          </div>
        </div>

        {/* Search */}
        <div className="p-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name or number..."
              data-testid="chat-search-input"
              className="w-full pl-10 pr-4 py-2.5 bg-[#111] border border-white/5 rounded-lg text-sm focus:border-[#00E599] focus:ring-1 focus:ring-[#00E599]"
            />
          </div>
        </div>

        {/* Chat List */}
        <div className="flex-1 overflow-y-auto">
          {isLoadingChats ? (
            <ChatSkeleton />
          ) : filteredChats.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <MessageSquare className="w-12 h-12 text-zinc-700 mb-3" />
              <p className="text-zinc-500">No conversations yet</p>
              <p className="text-xs text-zinc-600 mt-1">Messages will appear here when customers contact you</p>
            </div>
          ) : (
            <div className="divide-y divide-white/5">
              {filteredChats.map((chat) => (
                <button
                  key={chat.id}
                  onClick={() => handleSelectChat(chat)}
                  data-testid={`contact-item-${chat.contact?.phone_number}`}
                  className={`w-full px-4 py-3 flex items-start gap-3 hover:bg-white/5 transition-colors text-left ${
                    selectedChat?.id === chat.id ? 'bg-white/5 border-l-2 border-[#00E599]' : 'border-l-2 border-transparent'
                  }`}
                >
                  <ContactAvatar name={chat.contact?.name} phone={chat.contact?.phone_number} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className={`font-medium truncate ${unreadSessions.has(chat.id) ? 'text-white' : 'text-zinc-300'}`}>
                          {contactHasCustomName(chat) ? chat.contact.name : chat.contact?.phone_number}
                        </span>
                        {contactHasCustomName(chat) && (
                          <UserCheck className="w-3 h-3 text-[#00E599] flex-shrink-0" />
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
                        {unreadSessions.has(chat.id) && (
                          <span className="w-2 h-2 rounded-full bg-[#00E599] flex-shrink-0" />
                        )}
                        {chat.last_message && (
                          <span className="text-xs text-zinc-500">
                            {formatTime(chat.last_message.created_at)}
                          </span>
                        )}
                      </div>
                    </div>
                    {contactHasCustomName(chat) && (
                      <p className="text-xs text-zinc-600 font-mono mb-0.5">{chat.contact.phone_number}</p>
                    )}
                    <div className="flex items-center gap-2">
                      {chat.last_message ? (
                        <>
                          {getBubbleIcon(chat.last_message.sender_type)}
                          <p className="text-sm text-zinc-400 truncate">{chat.last_message.text}</p>
                        </>
                      ) : (
                        <p className="text-sm text-zinc-500 italic">No messages</p>
                      )}
                    </div>
                    {!chat.is_bot_paused && (
                      <div className="flex items-center gap-1 mt-1">
                        <Sparkles className="w-3 h-3 text-[#00D4FF]" />
                        <span className="text-xs text-[#00D4FF]">AI Active</span>
                      </div>
                    )}
                  </div>
                </button>
              ))}
              {/* Infinite scroll sentinel */}
              {hasMore && (
                <div ref={loadMoreRef} className="py-4 flex items-center justify-center">
                  {isLoadingMore ? (
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Loading more...
                    </div>
                  ) : (
                    <button
                      onClick={fetchMoreChats}
                      className="text-xs text-zinc-500 hover:text-[#00E599] transition-colors px-3 py-1.5 rounded-lg hover:bg-white/5"
                    >
                      Load more ({totalChats - chats.length} remaining)
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Message Panel */}
      <div className="flex-1 flex flex-col bg-[#0A0A0A]">
        {selectedChat ? (
          <>
            {/* Chat Header */}
            <div className="h-16 px-6 flex items-center justify-between border-b border-white/5 bg-black/60 backdrop-blur-xl sticky top-0 z-10">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <ContactAvatar name={selectedChat.contact?.name} phone={selectedChat.contact?.phone_number} />
                <div className="min-w-0 flex-1">
                  {isEditingName ? (
                    <div className="flex items-center gap-2">
                      <input
                        ref={nameInputRef}
                        type="text"
                        value={nameInput}
                        onChange={e => setNameInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') handleSaveName(); if (e.key === 'Escape') handleCancelEdit(); }}
                        placeholder="Enter contact name..."
                        className="flex-1 px-2 py-1 bg-[#111] border border-[#00E599]/50 rounded-lg text-sm focus:outline-none focus:border-[#00E599] text-white min-w-0"
                        maxLength={100}
                      />
                      <button
                        onClick={handleSaveName}
                        disabled={!nameInput.trim() || isSavingName}
                        className="p-1.5 bg-[#00E599] text-black rounded-lg hover:bg-[#00CC88] transition-colors disabled:opacity-50 flex-shrink-0"
                        title="Save name"
                      >
                        {isSavingName ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        className="p-1.5 bg-white/10 text-zinc-400 rounded-lg hover:bg-white/20 transition-colors flex-shrink-0"
                        title="Cancel"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 group">
                      <div className="min-w-0">
                        <h2 className="font-semibold truncate">
                          {contactHasCustomName(selectedChat) ? selectedChat.contact.name : selectedChat.contact?.phone_number}
                        </h2>
                        {contactHasCustomName(selectedChat) && (
                          <p className="text-xs text-zinc-500 font-mono">{selectedChat.contact?.phone_number}</p>
                        )}
                      </div>
                      <button
                        onClick={handleStartEditName}
                        className="p-1 rounded-lg text-zinc-600 hover:text-[#00E599] hover:bg-[#00E599]/10 transition-all opacity-0 group-hover:opacity-100 flex-shrink-0"
                        title={contactHasCustomName(selectedChat) ? 'Edit contact name' : 'Save contact name'}
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      {!contactHasCustomName(selectedChat) && (
                        <button
                          onClick={handleStartEditName}
                          className="flex items-center gap-1.5 px-2 py-1 text-xs bg-[#00E599]/10 text-[#00E599] border border-[#00E599]/20 rounded-full hover:bg-[#00E599]/20 transition-all flex-shrink-0"
                        >
                          <UserCheck className="w-3 h-3" />
                          Save Contact
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4 flex-shrink-0">
                {/* AI Toggle */}
                <div className="flex items-center gap-3 px-4 py-2 bg-[#111] rounded-lg border border-white/5">
                  <div className="flex items-center gap-2">
                    <Bot className={`w-4 h-4 ${selectedChat.is_bot_paused ? 'text-zinc-500' : 'text-[#00D4FF]'}`} />
                    <span className="text-sm font-medium">
                      {selectedChat.is_bot_paused ? 'AI Paused' : 'AI Active'}
                    </span>
                  </div>
                  <Switch
                    data-testid="ai-toggle-switch"
                    checked={!selectedChat.is_bot_paused}
                    onCheckedChange={handleToggleAI}
                    disabled={isTogglingAI}
                  />
                </div>
                <button className="p-2 hover:bg-white/5 rounded-lg transition-colors">
                  <MoreVertical className="w-5 h-5 text-zinc-400" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6">
              {isLoadingMessages ? (
                <MessageSkeleton />
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <MessageSquare className="w-16 h-16 text-zinc-700 mb-4" />
                  <p className="text-zinc-500">No messages in this conversation</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      data-testid={`message-${message.id}`}
                      className={`flex ${message.direction === 'INBOUND' ? 'justify-start' : 'justify-end'}`}
                    >
                      <div className={`max-w-[75%] px-4 py-3 rounded-xl ${getBubbleClass(message.sender_type)}`}>
                        <div className="flex items-center gap-2 mb-1">
                          {getBubbleIcon(message.sender_type)}
                          <span className="text-xs opacity-70 font-medium">
                            {message.sender_type === 'CUSTOMER'
                              ? (contactHasCustomName(selectedChat) ? selectedChat.contact.name : 'Customer')
                              : message.sender_type === 'BOT' ? 'AI Bot' : 'Admin'}
                          </span>
                          <span className="text-xs opacity-50">{formatTime(message.created_at)}</span>
                        </div>
                        
                        {/* Media Rendering */}
                        {message.media_url && (
                          <div className="mb-2 mt-1">
                            {message.media_type === 'image' && (
                              <div
                                className="relative group cursor-zoom-in rounded-xl overflow-hidden border border-white/10 bg-black/30"
                                onClick={() => setLightboxImage(`${BACKEND_URL}${message.media_url}`)}
                              >
                                <img
                                  src={`${BACKEND_URL}${message.media_url}`}
                                  alt="Attached"
                                  className="max-w-full h-auto max-h-64 object-cover w-full block"
                                />
                                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center">
                                  <ZoomIn className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-lg" />
                                </div>
                              </div>
                            )}
                            {message.media_type === 'audio' && (
                              <div className="flex items-center gap-3 px-3 py-2 bg-black/30 rounded-xl border border-white/10 min-w-[220px]">
                                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#00E599]/10 border border-[#00E599]/30 flex items-center justify-center">
                                  <Mic className="w-4 h-4 text-[#00E599]" />
                                </div>
                                <audio
                                  controls
                                  src={`${BACKEND_URL}${message.media_url}`}
                                  className="flex-1 h-8"
                                  style={{ minWidth: 0 }}
                                />
                              </div>
                            )}
                            {message.media_type === 'video' && (
                              <div className="rounded-xl overflow-hidden border border-white/10 bg-black/30">
                                <video controls src={`${BACKEND_URL}${message.media_url}`} className="max-w-full h-auto max-h-72 w-full" />
                              </div>
                            )}
                            {message.media_type === 'document' && (
                              <a href={`${BACKEND_URL}${message.media_url}`} target="_blank" rel="noreferrer"
                                className="flex items-center gap-3 px-3 py-2.5 bg-black/30 rounded-xl border border-white/10 hover:border-blue-400/30 hover:bg-blue-400/5 transition-all">
                                <FileText className="w-8 h-8 text-blue-400 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium text-blue-400 truncate">Document</p>
                                  <p className="text-xs text-zinc-500">Tap to open</p>
                                </div>
                                <Download className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                              </a>
                            )}
                          </div>
                        )}

                        {message.text && (
                          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{message.text}</p>
                        )}
                        
                        {message.status && message.direction === 'OUTBOUND' && (
                          <div className="flex items-center justify-end gap-1 mt-1">
                            <Clock className="w-3 h-3 opacity-50" />
                            <span className="text-xs opacity-50 capitalize">{message.status}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Message Input */}
            <div className="p-4 border-t border-white/5 bg-black/40 backdrop-blur-xl">
              {isRecording ? (
                <div className="flex items-center gap-4 bg-[#111] border border-[#ff4444]/30 rounded-xl px-4 py-2">
                  <div className="flex items-center gap-2 text-[#ff4444] flex-1">
                    <div className="w-2.5 h-2.5 rounded-full bg-[#ff4444] animate-pulse" />
                    <span className="font-medium font-mono text-lg">{formatRecordingTime(recordingTime)}</span>
                  </div>
                  
                  <button
                    onClick={cancelRecording}
                    className="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors flex items-center gap-2"
                    title="Cancel recording"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                  
                  <button
                    onClick={stopRecordingAndSend}
                    className="px-4 py-2 bg-[#00E599] hover:bg-[#00CC88] text-black font-medium rounded-lg flex items-center gap-2 transition-colors"
                  >
                    <Send className="w-4 h-4" />
                    Send
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSendMessage} className="flex items-center gap-2">
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    className="hidden" 
                    onChange={handleSendMedia}
                    accept="image/*,audio/*,video/*,.pdf,.doc,.docx"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isSending}
                    className="p-3 text-zinc-400 hover:text-[#00E599] hover:bg-[#00E599]/10 rounded-xl transition-all disabled:opacity-50"
                    title="Attach file"
                  >
                    <Paperclip className="w-5 h-5" />
                  </button>
                  <input
                    ref={inputRef}
                    type="text"
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    placeholder="Type your message..."
                    data-testid="message-input"
                    className="flex-1 px-4 py-3 bg-[#111] border border-white/5 rounded-xl focus:border-[#00E599] focus:ring-1 focus:ring-[#00E599]"
                    disabled={isSending}
                  />
                  {newMessage.trim() ? (
                    <button
                      type="submit"
                      data-testid="send-message-button"
                      disabled={isSending}
                      className="p-3 bg-[#00E599] hover:bg-[#00CC88] text-black rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={startRecording}
                      disabled={isSending}
                      className="p-3 bg-[#111] border border-white/5 text-[#00E599] hover:bg-[#00E599]/10 rounded-xl transition-all disabled:opacity-50"
                      title="Record Voice Note"
                    >
                      <Mic className="w-5 h-5" />
                    </button>
                  )}
                </form>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <div className="w-20 h-20 rounded-2xl bg-[#111] border border-white/5 flex items-center justify-center mb-6">
              <MessageSquare className="w-10 h-10 text-zinc-600" />
            </div>
            <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk' }}>
              Select a conversation
            </h2>
            <p className="text-zinc-500 max-w-md">
              Choose a chat from the list to view messages and respond to customers
            </p>
          </div>
        )}
      </div>
    </div>

    {/* Lightbox */}
    {lightboxImage && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm"
        onClick={() => setLightboxImage(null)}
      >
        <button
          onClick={() => setLightboxImage(null)}
          className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full transition-colors"
        >
          <X className="w-6 h-6 text-white" />
        </button>
        <img
          src={lightboxImage}
          alt="Full size"
          className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        />
      </div>
    )}
    </>
  );
};

export default Inbox;
