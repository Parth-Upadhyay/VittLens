import React, { useState, useEffect, useRef } from 'react';
import { useAppStore } from '../store/useAppStore';
import { ChatService } from '../services/api';
import { ChatMessage, ChatResponse } from '../types';
import { MessageItem } from '../components/chat/MessageItem';
import { ChatComposer } from '../components/chat/ChatComposer';
import { Sparkles, MessageSquare } from 'lucide-react';
import { LoadingSpinner } from '../components/common/LoadingSpinner';

export const ChatPage: React.FC = () => {
  const { activeThreadId, setActiveThreadId, fetchThreads, setQueriesRemaining, setGuestLimitModalOpen } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isSubmittingRef = useRef(false);

  // Load messages when activeThreadId changes (e.g. from sidebar selection)
  useEffect(() => {
    // Prevent double state update when activeThreadId is assigned during an active prompt submission
    if (isSubmittingRef.current) return;

    if (activeThreadId) {
      ChatService.getThreadMessages(activeThreadId)
        .then((data: ChatMessage[]) => setMessages(data))
        .catch((e: any) => console.error('Failed to load thread messages:', e));
    } else {
      setMessages([]);
    }
  }, [activeThreadId]);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async (question: string) => {
    isSubmittingRef.current = true;
    setIsLoading(true);

    // Optimistically append user message
    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    // Create a temporary assistant message that will stream
    const tempAssistantId = Date.now() + 1;
    let currentContent = '';
    
    setMessages((prev) => [
      ...prev,
      {
        id: tempAssistantId,
        role: 'assistant',
        content: '',
        status_logs: [],
        is_generating: true,
        created_at: new Date().toISOString(),
      },
    ]);

    await ChatService.sendQueryStream(
      { question, chat_id: activeThreadId || undefined },
      (event) => {
        setIsLoading(false); // Hide the main spinner once stream begins
        if (event.type === 'token') {
           currentContent += event.content;
           setMessages((prev) => prev.map(m => m.id === tempAssistantId ? { ...m, content: currentContent } : m));
        } else if (event.type === 'error') {
           currentContent += `\n\n⚠️ **Error:** ${event.content}`;
           setMessages((prev) => prev.map(m => m.id === tempAssistantId ? { ...m, content: currentContent } : m));
        } else if (event.type === 'status' || event.type === 'agent_start' || event.type === 'agent_complete') {
           if (event.message) {
             setMessages((prev) => prev.map(m => m.id === tempAssistantId ? { 
               ...m, 
               status_logs: [...(m.status_logs || []), event.message]
             } : m));
           }
        } else if (event.type === 'done') {
           setMessages((prev) => prev.map(m => m.id === tempAssistantId ? { 
             ...m, 
             sources: event.sources, 
             images: event.images, 
             symbols_queried: event.symbols_queried,
             agents_used: event.agents_used,
             is_generating: false
           } : m));
        } else if (event.type === 'queries_remaining') {
           setQueriesRemaining(event.content);
        } else if (event.type === 'chat_id' && !activeThreadId) {
           setActiveThreadId(event.content);
           fetchThreads();
        }
      },
      () => {
        setIsLoading(false);
        setTimeout(() => { isSubmittingRef.current = false; }, 500);
      },
      (err: any) => {
        console.error('Chat error:', err);
        const errorMessage = err.message || 'An error occurred while connecting to the backend.';
        
        if (err.message && err.message.includes('403')) {
          setGuestLimitModalOpen(true);
        }
        
        const errorAssistantMsg: ChatMessage = {
          id: Date.now() + 2,
          role: 'assistant',
          content: `⚠️ **Query Execution Error**\n\n${errorMessage}`,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev.filter(m => m.id !== tempAssistantId), errorAssistantMsg]);
        setIsLoading(false);
        setTimeout(() => { isSubmittingRef.current = false; }, 500);
      }
    );

  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-primary overflow-hidden font-sans min-w-0">
      {/* Scrollable Message List Container */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 min-w-0 animate-page-in">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-5 max-w-lg mx-auto">
            <div className="w-16 h-16 rounded-2xl bg-accent-light border border-accent/20 text-accent flex items-center justify-center shadow-sm">
              <Sparkles className="w-8 h-8" />
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-heading font-semibold text-tx-primary tracking-tight">AI Financial Intelligence</h1>
              <p className="text-sm text-tx-secondary leading-relaxed">
                Ask multi-symbol financial questions, compare ratios, explore recent news, or search SEC filings.
              </p>
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <MessageItem
              key={m.id}
              role={m.role}
              content={m.content}
              images={m.images}
              sources={m.sources}
              agents_used={m.agents_used}
              symbols_queried={m.symbols_queried}
              context_truncated={m.context_truncated}
              status_logs={m.status_logs}
              is_generating={m.is_generating}
            />
          ))
        )}

        {/* Simple Loading Indicator */}
        {isLoading && (
          <div className="flex justify-start my-4 ml-6 sm:ml-12">
            <LoadingSpinner message="Thinking..." className="p-4" />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Composer Input Bar */}
      <ChatComposer onSend={handleSend} isLoading={isLoading} />
    </div>
  );
};
