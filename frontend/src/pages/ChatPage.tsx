import React, { useState, useEffect, useRef } from 'react';
import { useAppStore } from '../store/useAppStore';
import { ChatService } from '../services/api';
import { ChatMessage, ChatResponse } from '../types';
import { MessageItem } from '../components/chat/MessageItem';
import { ChatComposer } from '../components/chat/ChatComposer';
import { Sparkles, MessageSquare } from 'lucide-react';

export const ChatPage: React.FC = () => {
  const { activeThreadId, setActiveThreadId, fetchThreads, setQueriesRemaining, setGuestLimitModalOpen } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isSubmittingRef = useRef(false);

  const processingSteps = [
    'Analyzing prompt & identifying company tickers...',
    'Fetching live stock quotes & technical valuation metrics...',
    'Aggregating financial news & market sentiment...',
    'Searching filing repository & annual report chunks...',
    'Synthesizing multi-agent intelligence response...',
  ];

  // Cycle through agent processing steps when loading
  useEffect(() => {
    let interval: any;
    if (isLoading) {
      setProcessingStep(0);
      interval = setInterval(() => {
        setProcessingStep((prev) => (prev < processingSteps.length - 1 ? prev + 1 : prev));
      }, 2200);
    }
    return () => clearInterval(interval);
  }, [isLoading]);

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
  }, [messages, isLoading, processingStep]);

  const handleSend = async (question: string) => {
    isSubmittingRef.current = true;
    setIsLoading(true);
    setProcessingStep(0);

    // Optimistically append user message
    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res: ChatResponse = await ChatService.sendQuery({
        question,
        chat_id: activeThreadId || undefined,
      });

      if (res.queries_remaining !== undefined) {
        setQueriesRemaining(res.queries_remaining);
      }

      const tempAssistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: res.answer,
        images: res.images,
        sources: res.sources,
        agents_used: res.agents_used,
        symbols_queried: res.symbols_queried,
        context_truncated: res.context_truncated,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, tempAssistantMsg]);

      if (!activeThreadId && res.chat_id) {
        setActiveThreadId(res.chat_id);
        await fetchThreads();
      }
    } catch (err: any) {
      console.error('Chat error:', err);
      const errorMessage =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'An error occurred while connecting to the backend.';

      if (err?.response?.status === 403) {
        setGuestLimitModalOpen(true);
      }

      const errorAssistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `⚠️ **Query Execution Error**\n\n${errorMessage}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorAssistantMsg]);
    } finally {
      setIsLoading(false);
      setTimeout(() => {
        isSubmittingRef.current = false;
      }, 500);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#060E0A] overflow-hidden font-sans min-w-0">
      {/* Scrollable Message List Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-w-0">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4 max-w-md mx-auto">
            <div className="w-12 h-12 rounded-full bg-[#14251B] border border-hairline text-accent flex items-center justify-center">
              <Sparkles className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h1 className="text-xl font-medium text-cream tracking-tight">AI Financial Intelligence</h1>
              <p className="text-xs text-cream-muted leading-relaxed">
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
            />
          ))
        )}

        {/* Live Processing Indicator Banner */}
        {isLoading && (
          <div className="py-3 px-4 my-2 bg-[#0D1912] border border-hairline rounded-xl max-w-4xl mx-auto transition-all">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-accent" />
                <span className="text-xs font-medium text-cream">FinnAI Multi-Agent System Processing...</span>
              </div>
              <span className="text-[10px] text-cream-muted font-mono tabular-nums bg-[#14251B] px-2.5 py-0.5 rounded border border-hairline">
                Step {processingStep + 1} of {processingSteps.length}
              </span>
            </div>
            <div className="flex items-center space-x-3 py-1">
              <div className="w-2 h-2 rounded-full bg-accent flex-shrink-0 animate-pulse" />
              <span className="text-xs text-cream font-normal">{processingSteps[processingStep]}</span>
            </div>
            {/* Solid Progress Bar */}
            <div className="w-full bg-[#14251B] h-1.5 rounded-full mt-2.5 overflow-hidden">
              <div
                className="bg-accent h-full transition-all duration-500 rounded-full"
                style={{ width: `${((processingStep + 1) / processingSteps.length) * 100}%` }}
              />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Composer Input Bar */}
      <ChatComposer onSend={handleSend} isLoading={isLoading} />
    </div>
  );
};
