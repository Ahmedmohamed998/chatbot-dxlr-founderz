import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { 
  MessageSquare, Send, Bot, User, UserCog, Search, 
  Phone, Clock, MoreVertical, Sparkles, Loader2, Wifi, WifiOff 
} from 'lucide-react';
import { Switch } from '../components/ui/switch';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Skeleton Loader Component
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

const Inbox = () => {
  const { api } = useAuth();
  const { success, error, info } = useToast();
  
  const [chats, setChats] = useState([]);
  const [selectedChat, setSelectedChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isTogglingAI, setIsTogglingAI] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const wsRef = useRef(null);
  const selectedChatRef = useRef(null);
  
  // Keep selectedChatRef in sync with selectedChat
  useEffect(() => {
    selectedChatRef.current = selectedChat;
  }, [selectedChat]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchChats = useCallback(async () => {
    try {
      const response = await api.get('/chats');
      setChats(response.data);
    } catch (err) {
      console.error('Failed to fetch chats:', err);
    } finally {
      setIsLoadingChats(false);
    }
  }, [api]);

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

  useEffect(() => {
    fetchChats();
    // Initial fetch only - WebSocket handles real-time updates
  }, [fetchChats]);
  
  // WebSocket connection for real-time updates
  useEffect(() => {
    const connectWebSocket = () => {
      // Convert http(s) to ws(s)
      const wsUrl = BACKEND_URL.replace(/^http/, 'ws') + '/api/ws';
      console.log('Connecting to WebSocket:', wsUrl);
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
        info('Real-time updates connected');
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message received:', data);
          
          if (data.type === 'new_message') {
            const msgData = data.data;
            
            // Update chats list (refresh to get latest)
            fetchChats();
            
            // If this message belongs to the currently selected chat, add it
            const currentChat = selectedChatRef.current;
            if (currentChat && currentChat.contact?.phone_number === msgData.phone_number) {
              setMessages(prev => {
                // Check if message already exists
                const exists = prev.some(m => m.id === msgData.id);
                if (exists) return prev;
                
                return [...prev, {
                  id: msgData.id,
                  session_id: msgData.session_id,
                  direction: msgData.direction,
                  sender_type: msgData.sender_type,
                  text: msgData.text,
                  status: 'sent',
                  created_at: msgData.created_at
                }];
              });
            }
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
      };
      
      // Heartbeat every 30 seconds
      const heartbeat = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000);
      
      return () => {
        clearInterval(heartbeat);
        ws.close();
      };
    };
    
    const cleanup = connectWebSocket();
    return cleanup;
  }, [fetchChats, info]);

  useEffect(() => {
    if (selectedChat) {
      fetchMessages(selectedChat.contact.phone_number);
      // No polling needed - WebSocket handles real-time updates
    }
  }, [selectedChat, fetchMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSelectChat = (chat) => {
    setSelectedChat(chat);
    setMessages([]);
    inputRef.current?.focus();
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedChat || isSending) return;

    setIsSending(true);
    try {
      await api.post(`/chats/${selectedChat.contact.phone_number}/send`, {
        text: newMessage.trim(),
      });
      setNewMessage('');
      success('Message sent');
      // No need to fetch - WebSocket will push the update
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
      await api.put(`/chats/${selectedChat.contact.phone_number}/toggle-ai`, {
        is_paused: newPausedState,
      });
      setSelectedChat((prev) => ({ ...prev, is_bot_paused: newPausedState }));
      success(newPausedState ? 'AI Bot paused' : 'AI Bot resumed');
      await fetchChats();
    } catch (err) {
      error('Failed to toggle AI');
    } finally {
      setIsTogglingAI(false);
    }
  };

  const filteredChats = chats.filter((chat) => {
    const searchLower = searchQuery.toLowerCase();
    return (
      chat.contact?.phone_number?.toLowerCase().includes(searchLower) ||
      chat.contact?.name?.toLowerCase().includes(searchLower) ||
      chat.last_message?.text?.toLowerCase().includes(searchLower)
    );
  });

  const formatTime = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return date.toLocaleDateString('en-US', { weekday: 'short' });
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getBubbleIcon = (senderType) => {
    switch (senderType) {
      case 'CUSTOMER':
        return <User className="w-3 h-3" />;
      case 'BOT':
        return <Bot className="w-3 h-3" />;
      case 'ADMIN':
        return <UserCog className="w-3 h-3" />;
      default:
        return null;
    }
  };

  const getBubbleClass = (senderType) => {
    switch (senderType) {
      case 'CUSTOMER':
        return 'bubble-customer';
      case 'BOT':
        return 'bubble-bot';
      case 'ADMIN':
        return 'bubble-admin';
      default:
        return 'bubble-customer';
    }
  };

  return (
    <div className="h-screen flex" data-testid="inbox-page">
      {/* Chat List Panel */}
      <div className="w-[350px] border-r border-white/5 flex flex-col bg-[#0A0A0A]">
        {/* Header */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-white/5">
          <div className="flex items-center">
            <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'Cabinet Grotesk' }}>
              Inbox
            </h1>
            <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-[#00E599]/10 text-[#00E599] rounded-full">
              {chats.length}
            </span>
          </div>
          {/* WebSocket Status Indicator */}
          <div 
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${
              wsConnected 
                ? 'bg-[#00E599]/10 text-[#00E599]' 
                : 'bg-amber-500/10 text-amber-400'
            }`}
            title={wsConnected ? 'Real-time updates active' : 'Reconnecting...'}
            data-testid="ws-status-indicator"
          >
            {wsConnected ? (
              <>
                <Wifi className="w-3 h-3" />
                <span>Live</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3 h-3" />
                <span>Connecting</span>
              </>
            )}
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
              placeholder="Search conversations..."
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
              <p className="text-xs text-zinc-600 mt-1">
                Messages will appear here when customers contact you
              </p>
            </div>
          ) : (
            <div className="divide-y divide-white/5">
              {filteredChats.map((chat) => (
                <button
                  key={chat.id}
                  onClick={() => handleSelectChat(chat)}
                  data-testid={`contact-item-${chat.contact?.phone_number}`}
                  className={`w-full px-4 py-3 flex items-start gap-3 hover:bg-white/5 transition-colors text-left ${
                    selectedChat?.id === chat.id ? 'bg-white/5' : ''
                  }`}
                >
                  {/* Avatar */}
                  <div className="w-10 h-10 rounded-full bg-[#111] border border-white/10 flex items-center justify-center flex-shrink-0">
                    <Phone className="w-4 h-4 text-zinc-400" />
                  </div>
                  
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium truncate">
                        {chat.contact?.name || chat.contact?.phone_number}
                      </span>
                      {chat.last_message && (
                        <span className="text-xs text-zinc-500 ml-2 flex-shrink-0">
                          {formatTime(chat.last_message.created_at)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {chat.last_message ? (
                        <>
                          {getBubbleIcon(chat.last_message.sender_type)}
                          <p className="text-sm text-zinc-400 truncate">
                            {chat.last_message.text}
                          </p>
                        </>
                      ) : (
                        <p className="text-sm text-zinc-500 italic">No messages</p>
                      )}
                    </div>
                    {/* AI Status indicator */}
                    {!chat.is_bot_paused && (
                      <div className="flex items-center gap-1 mt-1">
                        <Sparkles className="w-3 h-3 text-[#00D4FF]" />
                        <span className="text-xs text-[#00D4FF]">AI Active</span>
                      </div>
                    )}
                  </div>
                </button>
              ))}
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
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#111] border border-white/10 flex items-center justify-center">
                  <Phone className="w-4 h-4 text-zinc-400" />
                </div>
                <div>
                  <h2 className="font-semibold">
                    {selectedChat.contact?.name || selectedChat.contact?.phone_number}
                  </h2>
                  <p className="text-xs text-zinc-500 font-mono">
                    {selectedChat.contact?.phone_number}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4">
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
                      className={`flex ${
                        message.direction === 'INBOUND' ? 'justify-start' : 'justify-end'
                      }`}
                    >
                      <div
                        className={`max-w-[75%] px-4 py-3 rounded-xl ${getBubbleClass(
                          message.sender_type
                        )}`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          {getBubbleIcon(message.sender_type)}
                          <span className="text-xs opacity-70 font-medium">
                            {message.sender_type === 'CUSTOMER'
                              ? 'Customer'
                              : message.sender_type === 'BOT'
                              ? 'AI Bot'
                              : 'Admin'}
                          </span>
                          <span className="text-xs opacity-50">
                            {formatTime(message.created_at)}
                          </span>
                        </div>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">
                          {message.text}
                        </p>
                        {message.status && message.direction === 'OUTBOUND' && (
                          <div className="flex items-center justify-end gap-1 mt-1">
                            <Clock className="w-3 h-3 opacity-50" />
                            <span className="text-xs opacity-50 capitalize">
                              {message.status}
                            </span>
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
              <form onSubmit={handleSendMessage} className="flex items-center gap-3">
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
                <button
                  type="submit"
                  data-testid="send-message-button"
                  disabled={!newMessage.trim() || isSending}
                  className="p-3 bg-[#00E599] hover:bg-[#00CC88] text-black rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </form>
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
  );
};

export default Inbox;
