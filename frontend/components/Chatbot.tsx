'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Bot, Send, User, X, MessageSquare, Minimize2, Maximize2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';

const MODEL_MAP: Record<string, string> = {
  'llama-3.3-70b': 'llama-3.3-70b-versatile',
  'llama-3.1-70b': 'llama-3.1-70b-versatile',
  'llama-3.1-8b': 'llama-3.1-8b-instant',
  'llama-3.2-3b': 'llama-3.2-3b-preview',
  'mixtral-8x7b': 'mixtral-8x7b-32768',
  'gemma2-9b': 'gemma2-9b-it',
};

function mapModel(userModel: string): string {
  for (const [key, value] of Object.entries(MODEL_MAP)) {
    if (userModel.includes(key)) return value;
  }
  return 'llama-3.3-70b-versatile';
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Hello! I am your AI assistant. How can I help you with the FaceSnap system today?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isOpen, isMinimized]);

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    const updatedMessages = [...messages, { role: 'user' as const, content: userMessage }];
    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      // Server-side proxy keeps the provider key out of the browser bundle.
      const chatMessages = updatedMessages.map(m => ({ role: m.role, content: m.content.slice(0, 2000) })).slice(-20);
      const modelName = mapModel('');

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: chatMessages, model: modelName }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || `Chat error (${response.status})`);
      }

      const data = await response.json();
      const reply = data.reply || 'Sorry, I could not process that.';
      setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
    } catch (error: any) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, { role: 'assistant', content: error.message || 'An error occurred. Please try again.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {!isOpen && (
        <motion.button
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          whileHover={{ scale: 1.1, rotate: 10 }}
          whileTap={{ scale: 0.9 }}
          transition={{ type: 'spring', bounce: 0.5 }}
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 w-16 h-16 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-full shadow-[0_0_30px_-5px_rgba(79,70,229,0.5)] flex items-center justify-center z-50 hover:from-indigo-700 hover:to-blue-700 transition-colors border-4 border-white"
        >
          <MessageSquare className="w-7 h-7" />
        </motion.button>
      )}

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.95, transformOrigin: 'bottom right' }}
            animate={{ opacity: 1, y: 0, scale: 1, height: isMinimized ? 'auto' : '550px' }}
            exit={{ opacity: 0, y: 30, scale: 0.95 }}
            transition={{ type: 'spring', bounce: 0.4 }}
            className="fixed bottom-6 right-6 w-[350px] sm:w-[400px] bg-white rounded-[2rem] shadow-2xl shadow-slate-200/50 border border-slate-100 z-50 flex flex-col overflow-hidden"
          >
            <div className="bg-slate-900 text-white p-5 flex items-center justify-between relative overflow-hidden">
              <div className="absolute top-[-50%] right-[-20%] w-[60%] h-[150%] rounded-full bg-indigo-500/30 blur-[30px] pointer-events-none" />
              <div className="flex items-center gap-4 relative z-10">
                <div className="w-10 h-10 bg-indigo-500/20 border border-indigo-500/30 rounded-xl flex items-center justify-center shadow-inner">
                  <Bot className="w-6 h-6 text-indigo-300" />
                </div>
                <div>
                  <h3 className="font-bold text-base tracking-wide">FaceSnap Assistant</h3>
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.6)]" />
                    <p className="text-xs text-slate-300 font-medium">Online</p>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 relative z-10">
                <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }} onClick={() => setIsMinimized(!isMinimized)} className="p-2 hover:bg-white/10 rounded-xl transition-colors text-slate-300 hover:text-white">
                  {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
                </motion.button>
                <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }} onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/10 rounded-xl transition-colors text-slate-300 hover:text-white">
                  <X className="w-4 h-4" />
                </motion.button>
              </div>
            </div>

            {!isMinimized && (
              <>
                <div className="flex-1 p-5 overflow-y-auto bg-slate-50/50 flex flex-col gap-5">
                  {messages.map((msg, idx) => (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', bounce: 0.4 }} key={idx} className={`flex gap-3 max-w-[85%] ${msg.role === 'user' ? 'self-end flex-row-reverse' : 'self-start'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm ${msg.role === 'user' ? 'bg-indigo-100 text-indigo-600' : 'bg-white border border-slate-200 text-indigo-600'}`}>
                        {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                      </div>
                      <div className={`p-4 rounded-2xl text-sm shadow-sm ${msg.role === 'user' ? 'bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-tr-sm' : 'bg-white border border-slate-100 text-slate-700 rounded-tl-sm'}`}>
                        <div className="markdown-body prose prose-sm max-w-none">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                  {isLoading && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3 max-w-[85%] self-start">
                      <div className="w-8 h-8 rounded-full bg-white border border-slate-200 text-indigo-600 flex items-center justify-center flex-shrink-0 shadow-sm">
                        <Bot className="w-4 h-4" />
                      </div>
                      <div className="p-4 rounded-2xl bg-white border border-slate-100 rounded-tl-sm flex items-center gap-1.5 shadow-sm">
                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </motion.div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <div className="p-4 bg-white border-t border-slate-100">
                  <form onSubmit={handleSend} className="flex items-center gap-3">
                    <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your message..." className="flex-1 px-5 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all text-slate-700 placeholder:text-slate-400" />
                    <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} type="submit" disabled={!input.trim() || isLoading} className="p-3.5 bg-indigo-600 text-white rounded-2xl hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-indigo-600/20">
                      <Send className="w-5 h-5" />
                    </motion.button>
                  </form>
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
