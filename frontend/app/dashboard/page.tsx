'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '@/lib/api';
import { Send, FileText, Plus, Settings, Upload, X, RefreshCw, CheckCircle, AlertCircle, Loader2, MessageSquare, Trash2, Edit3, PanelLeftClose, PanelLeft, Cpu, Cloud } from 'lucide-react';

interface User {
    email: string;
    is_admin: boolean;
}

interface Group {
    id: number;
    name: string;
}

type FileStatus = 'pending' | 'uploading' | 'processing' | 'done' | 'failed';

interface UploadFile {
    id: string;
    file: File;
    status: FileStatus;
    progress: number;
    error?: string;
}

interface Source {
    page_number: number;
    group_id: number;
    file_path?: string;
    filename?: string;
    text_snippet: string;
    full_text: string;
}

interface Message {
    role: string;
    content: string;
    sources?: Source[];
    intent?: string; // Intent classified by agentic router
}

interface Conversation {
    id: number;
    title: string;
    group_id: number | null;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message: string | null;
}

interface ModelInfo {
    name: string;
    provider: string;
    label: string;
    size?: string;
    description?: string;
}

// Custom Markdown components for proper table styling
const MarkdownComponents = {
    table: ({ children }: { children?: React.ReactNode }) => (
        <div className="overflow-x-auto my-4">
            <table className="min-w-full border-collapse border border-gray-600 text-sm">
                {children}
            </table>
        </div>
    ),
    thead: ({ children }: { children?: React.ReactNode }) => (
        <thead className="bg-gray-700">{children}</thead>
    ),
    tbody: ({ children }: { children?: React.ReactNode }) => (
        <tbody className="divide-y divide-gray-600">{children}</tbody>
    ),
    tr: ({ children }: { children?: React.ReactNode }) => (
        <tr className="border-b border-gray-600">{children}</tr>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
        <th className="px-4 py-2 text-left font-semibold text-gray-200 border border-gray-600">
            {children}
        </th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
        <td className="px-4 py-2 text-gray-300 border border-gray-600">{children}</td>
    ),
    code: ({ className, children }: { className?: string; children?: React.ReactNode }) => {
        const isInline = !className;
        if (isInline) {
            return (
                <code className="bg-gray-700 text-blue-300 px-1.5 py-0.5 rounded text-sm font-mono">
                    {children}
                </code>
            );
        }
        return (
            <code className={`${className} block bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm`}>
                {children}
            </code>
        );
    },
    pre: ({ children }: { children?: React.ReactNode }) => (
        <pre className="bg-gray-900 rounded-lg overflow-x-auto my-4">{children}</pre>
    ),
    ul: ({ children }: { children?: React.ReactNode }) => (
        <ul className="list-disc list-inside my-2 space-y-1 text-gray-300">{children}</ul>
    ),
    ol: ({ children }: { children?: React.ReactNode }) => (
        <ol className="list-decimal list-inside my-2 space-y-1 text-gray-300">{children}</ol>
    ),
    li: ({ children }: { children?: React.ReactNode }) => (
        <li className="text-gray-300">{children}</li>
    ),
    h1: ({ children }: { children?: React.ReactNode }) => (
        <h1 className="text-2xl font-bold text-white mt-4 mb-2">{children}</h1>
    ),
    h2: ({ children }: { children?: React.ReactNode }) => (
        <h2 className="text-xl font-bold text-white mt-4 mb-2">{children}</h2>
    ),
    h3: ({ children }: { children?: React.ReactNode }) => (
        <h3 className="text-lg font-semibold text-white mt-3 mb-1">{children}</h3>
    ),
    p: ({ children }: { children?: React.ReactNode }) => (
        <p className="text-gray-300 leading-relaxed my-2">{children}</p>
    ),
    a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
        <a href={href} className="text-blue-400 hover:text-blue-300 underline" target="_blank" rel="noopener noreferrer">
            {children}
        </a>
    ),
    blockquote: ({ children }: { children?: React.ReactNode }) => (
        <blockquote className="border-l-4 border-blue-500 pl-4 my-4 text-gray-400 italic">
            {children}
        </blockquote>
    ),
    strong: ({ children }: { children?: React.ReactNode }) => (
        <strong className="font-semibold text-white">{children}</strong>
    ),
    em: ({ children }: { children?: React.ReactNode }) => (
        <em className="italic text-gray-300">{children}</em>
    ),
};

export default function DashboardPage() {
    const [user, setUser] = useState<User | null>(null);
    const [groups, setGroups] = useState<Group[]>([]);
    const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
    const [query, setQuery] = useState('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [isQuerying, setIsQuerying] = useState(false);
    const [uploadQueue, setUploadQueue] = useState<UploadFile[]>([]);
    const [newGroupName, setNewGroupName] = useState('');
    const [isCreatingGroup, setIsCreatingGroup] = useState(false);
    const [selectedSource, setSelectedSource] = useState<Source | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const router = useRouter();

    // Chat history state
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [editingConversationId, setEditingConversationId] = useState<number | null>(null);
    const [editingTitle, setEditingTitle] = useState('');
    const [loadingConversations, setLoadingConversations] = useState(false);

    // Model selector state
    const [ollamaModels, setOllamaModels] = useState<ModelInfo[]>([]);
    const [cloudModels, setCloudModels] = useState<ModelInfo[]>([]);
    const [selectedModel, setSelectedModel] = useState<{ provider: string; name: string }>(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('selected_llm_model');
            if (saved) return JSON.parse(saved);
        }
        return { provider: '', name: '' }; // empty = server default
    });

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isQuerying]);

    const fetchUserAndGroups = async () => {
        try {
            const userRes = await api.get('/auth/me');
            setUser(userRes.data);

            const groupsRes = await api.get('/groups');
            setGroups(groupsRes.data);

            if (groupsRes.data.length > 0 && !selectedGroupId) {
                setSelectedGroupId(groupsRes.data[0].id);
            }
        } catch (err) {
            console.error(err);
            router.push('/login');
        }
    };

    useEffect(() => {
        fetchUserAndGroups();
        fetchModels();
    }, [router]);

    // Fetch available LLM models
    const fetchModels = async () => {
        try {
            const res = await api.get('/models');
            setOllamaModels(res.data.ollama || []);
            setCloudModels(res.data.cloud || []);
        } catch (err) {
            console.error('Failed to fetch models', err);
        }
    };

    const handleModelChange = (value: string) => {
        if (value === 'default') {
            const model = { provider: '', name: '' };
            setSelectedModel(model);
            localStorage.setItem('selected_llm_model', JSON.stringify(model));
        } else {
            const [provider, ...nameParts] = value.split(':');
            const model = { provider, name: nameParts.join(':') };
            setSelectedModel(model);
            localStorage.setItem('selected_llm_model', JSON.stringify(model));
        }
    };

    // Fetch conversations on load
    const fetchConversations = useCallback(async () => {
        setLoadingConversations(true);
        try {
            const res = await api.get('/conversations');
            setConversations(res.data);
        } catch (err) {
            console.error('Failed to load conversations', err);
        } finally {
            setLoadingConversations(false);
        }
    }, []);

    useEffect(() => {
        fetchConversations();
    }, [fetchConversations]);

    // Load a specific conversation
    const loadConversation = async (conversationId: number) => {
        try {
            const res = await api.get(`/conversations/${conversationId}`);
            const conv = res.data;
            setCurrentConversationId(conversationId);
            if (conv.group_id) {
                setSelectedGroupId(conv.group_id);
            }
            // Transform messages to local format
            const loadedMessages: Message[] = conv.messages.map((msg: any) => ({
                role: msg.role === 'assistant' ? 'bot' : msg.role,
                content: msg.content,
                sources: msg.sources || [],
                intent: msg.intent,
            }));
            setMessages(loadedMessages);
            // Clear session storage to use conversation_id instead
            sessionStorage.removeItem('chat_session_id');
        } catch (err) {
            console.error('Failed to load conversation', err);
        }
    };

    // Start a new chat
    const startNewChat = () => {
        setCurrentConversationId(null);
        setMessages([]);
        sessionStorage.removeItem('chat_session_id');
    };

    // Delete a conversation
    const handleDeleteConversation = async (conversationId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Delete this conversation?')) return;
        try {
            await api.delete(`/conversations/${conversationId}`);
            setConversations(prev => prev.filter(c => c.id !== conversationId));
            if (currentConversationId === conversationId) {
                startNewChat();
            }
        } catch (err) {
            console.error('Failed to delete conversation', err);
        }
    };

    // Rename a conversation
    const handleUpdateTitle = async (conversationId: number) => {
        if (!editingTitle.trim()) {
            setEditingConversationId(null);
            return;
        }
        try {
            await api.put(`/conversations/${conversationId}`, { title: editingTitle });
            setConversations(prev => prev.map(c =>
                c.id === conversationId ? { ...c, title: editingTitle } : c
            ));
            setEditingConversationId(null);
            setEditingTitle('');
        } catch (err) {
            console.error('Failed to update conversation title', err);
        }
    };



    const handleCreateGroup = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newGroupName.trim()) return;
        try {
            await api.post('/groups/', { name: newGroupName });
            setNewGroupName('');
            setIsCreatingGroup(false);
            fetchUserAndGroups();
        } catch (err) {
            console.error("Failed to create group", err);
            alert("Failed to create group. Only Admins can create groups.");
        }
    };

    const handleFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files) return;

        const newFiles: UploadFile[] = Array.from(files).map(file => ({
            id: `${file.name}-${Date.now()}-${Math.random()}`,
            file,
            status: 'pending' as FileStatus,
            progress: 0,
        }));

        setUploadQueue(prev => [...prev, ...newFiles]);

        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const uploadFile = async (uploadFile: UploadFile) => {
        if (!selectedGroupId) return;

        setUploadQueue(prev => prev.map(f =>
            f.id === uploadFile.id ? { ...f, status: 'uploading' as FileStatus, progress: 0 } : f
        ));

        const formData = new FormData();
        formData.append('file', uploadFile.file);

        try {
            await api.post(`/documents/upload?group_id=${selectedGroupId}`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (progressEvent) => {
                    const percent = progressEvent.total
                        ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
                        : 0;
                    setUploadQueue(prev => prev.map(f =>
                        f.id === uploadFile.id ? { ...f, progress: percent } : f
                    ));
                }
            });

            setUploadQueue(prev => prev.map(f =>
                f.id === uploadFile.id ? { ...f, status: 'processing' as FileStatus, progress: 100 } : f
            ));

            await new Promise(resolve => setTimeout(resolve, 500));

            setUploadQueue(prev => prev.map(f =>
                f.id === uploadFile.id ? { ...f, status: 'done' as FileStatus } : f
            ));
        } catch (err: any) {
            setUploadQueue(prev => prev.map(f =>
                f.id === uploadFile.id ? {
                    ...f,
                    status: 'failed' as FileStatus,
                    error: err.response?.data?.detail || 'Upload failed'
                } : f
            ));
        }
    };

    const handleUploadAll = async () => {
        const pendingFiles = uploadQueue.filter(f => f.status === 'pending');
        for (const file of pendingFiles) {
            await uploadFile(file);
        }
    };

    const handleRetry = (fileId: string) => {
        const file = uploadQueue.find(f => f.id === fileId);
        if (file) {
            setUploadQueue(prev => prev.map(f =>
                f.id === fileId ? { ...f, status: 'pending' as FileStatus, progress: 0, error: undefined } : f
            ));
            uploadFile(file);
        }
    };

    const handleRemoveFromQueue = (fileId: string) => {
        setUploadQueue(prev => prev.filter(f => f.id !== fileId));
    };

    const handleClearCompleted = () => {
        setUploadQueue(prev => prev.filter(f => f.status !== 'done'));
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim() || isQuerying) return;

        const userMessage: Message = { role: 'user', content: query };
        setMessages((prev) => [...prev, userMessage]);
        setQuery('');
        setIsQuerying(true);

        try {
            const token = localStorage.getItem('token');
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

            // Add initial empty bot message
            const botMessageId = Date.now().toString();
            setMessages(prev => [
                ...prev,
                { role: 'bot', content: '', id: botMessageId }
            ]);

            const response = await fetch(`${apiUrl}/documents/chat-stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify({
                    message: userMessage.content,
                    group_id: selectedGroupId,
                    conversation_id: currentConversationId || undefined,
                    session_id: sessionStorage.getItem('chat_session_id') || undefined,
                    model_provider: selectedModel.provider || undefined,
                    model_name: selectedModel.name || undefined,
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let accumulatedContent = '';
            let buffer = '';

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        break;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const dataStr = line.slice(6).trim();
                            if (!dataStr || dataStr === '[DONE]') continue;

                            try {
                                const data = JSON.parse(dataStr);

                                if (data.type === 'chunk') {
                                    accumulatedContent += data.content;
                                    setMessages(prev => {
                                        const newMsgs = [...prev];
                                        const lastMsgIdx = newMsgs.length - 1;
                                        if (newMsgs[lastMsgIdx].role === 'bot') {
                                            newMsgs[lastMsgIdx] = {
                                                ...newMsgs[lastMsgIdx],
                                                content: accumulatedContent
                                            };
                                        }
                                        return newMsgs;
                                    });
                                } else if (data.type === 'end') {
                                    // Finalize message with sources and metadata
                                    setMessages(prev => {
                                        const newMsgs = [...prev];
                                        const lastMsgIdx = newMsgs.length - 1;
                                        if (newMsgs[lastMsgIdx].role === 'bot') {
                                            newMsgs[lastMsgIdx] = {
                                                ...newMsgs[lastMsgIdx],
                                                sources: data.sources || [],
                                                intent: data.intent || 'unknown'
                                            };
                                        }
                                        return newMsgs;
                                    });

                                    if (data.session_id) {
                                        sessionStorage.setItem('chat_session_id', data.session_id);
                                    }
                                    if (data.conversation_id && !currentConversationId) {
                                        setCurrentConversationId(data.conversation_id);
                                        fetchConversations();
                                    }
                                }
                            } catch (e) {
                                console.error('Error parsing SSE data:', e, dataStr);
                            }
                        }
                    }
                }
            }
        } catch (err) {
            console.error('Chat error:', err);
            setMessages(prev => [...prev, { role: 'bot', content: 'An error occurred while communicating with the server.' }]);
        } finally {
            setIsQuerying(false);
        }
    };

    const isAdmin = user?.is_admin;
    const hasMultipleGroups = groups.length > 1;
    const hasPendingUploads = uploadQueue.some(f => f.status === 'pending');
    const hasCompletedUploads = uploadQueue.some(f => f.status === 'done');

    const getStatusIcon = (status: FileStatus) => {
        switch (status) {
            case 'pending': return <div className="w-4 h-4 rounded-full bg-gray-500" />;
            case 'uploading': return <Loader2 size={16} className="text-blue-400 animate-spin" />;
            case 'processing': return <Loader2 size={16} className="text-yellow-400 animate-spin" />;
            case 'done': return <CheckCircle size={16} className="text-green-400" />;
            case 'failed': return <AlertCircle size={16} className="text-red-400" />;
        }
    };

    const getStatusText = (status: FileStatus) => {
        switch (status) {
            case 'pending': return 'Waiting...';
            case 'uploading': return 'Uploading...';
            case 'processing': return 'Embedding...';
            case 'done': return 'Complete';
            case 'failed': return 'Failed';
        }
    };

    return (
        <div className="flex flex-col h-screen bg-zinc-950 text-zinc-300">
            {/* Header */}
            <header className="fixed top-0 w-full z-10 bg-zinc-900/80 backdrop-blur-xl border-b border-zinc-800/50 px-6 py-4 flex justify-between items-center shadow-sm">
                <div className="flex items-center gap-2">
                    <h1 className="text-xl font-semibold bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">Vehicle RAG System</h1>
                    {isAdmin && <span className="bg-blue-500/10 text-blue-400 border border-blue-500/20 text-xs px-2 py-1 rounded-full">Admin</span>}
                </div>
                <div className="flex items-center gap-4">
                    {isAdmin && (
                        <button
                            onClick={() => router.push('/admin')}
                            className="p-2 text-zinc-400 hover:text-blue-400 hover:bg-zinc-800/50 rounded-lg transition-all"
                            title="Admin Panel"
                        >
                            <Settings size={20} />
                        </button>
                    )}
                    <span className="text-zinc-400 text-sm">{user?.email}</span>
                </div>
            </header>

            <main className="flex-1 flex overflow-hidden pt-[73px]">
                {/* Chat History Sidebar - Collapsible */}
                <aside className={`bg-zinc-900/60 backdrop-blur-md border-r border-zinc-800/50 flex flex-col transition-all duration-300 relative ${sidebarOpen ? 'w-64' : 'w-12'} shrink-0 z-0`}>
                    {/* Sidebar Toggle */}
                    <div className="p-3 border-b border-zinc-800/50 flex items-center justify-between">
                        {sidebarOpen && <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Chat History</span>}
                        <button
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                            className="p-1.5 text-zinc-500 rounded-md hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
                            title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
                        >
                            {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
                        </button>
                    </div>

                    {sidebarOpen && (
                        <>
                            {/* New Chat Button */}
                            <div className="p-3">
                                <button
                                    onClick={startNewChat}
                                    className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/50 hover:border-zinc-600 rounded-xl transition-all shadow-sm"
                                >
                                    <Plus size={16} />
                                    <span className="text-sm font-medium">New Chat</span>
                                </button>
                            </div>

                            {/* Conversation List */}
                            <div className="flex-1 overflow-y-auto px-2 space-y-1 mt-2">
                                {loadingConversations ? (
                                    <div className="flex items-center justify-center py-8">
                                        <Loader2 size={18} className="animate-spin text-zinc-500" />
                                    </div>
                                ) : conversations.length === 0 ? (
                                    <p className="text-center text-zinc-500 text-xs py-8">No conversations yet</p>
                                ) : (
                                    <div className="space-y-0.5 pb-4">
                                        {conversations.map(conv => (
                                            <div
                                                key={conv.id}
                                                onClick={() => loadConversation(conv.id)}
                                                className={`group flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 ${currentConversationId === conv.id
                                                    ? 'bg-zinc-800/80 text-zinc-100 shadow-sm border border-zinc-700/50'
                                                    : 'text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200 border border-transparent'
                                                    }`}
                                            >
                                                <MessageSquare size={14} className={currentConversationId === conv.id ? 'text-blue-400' : 'text-zinc-500 group-hover:text-zinc-400'} />
                                                {editingConversationId === conv.id ? (
                                                    <input
                                                        type="text"
                                                        value={editingTitle}
                                                        onChange={(e) => setEditingTitle(e.target.value)}
                                                        onBlur={() => handleUpdateTitle(conv.id)}
                                                        onKeyDown={(e) => {
                                                            if (e.key === 'Enter') handleUpdateTitle(conv.id);
                                                            if (e.key === 'Escape') setEditingConversationId(null);
                                                        }}
                                                        onClick={(e) => e.stopPropagation()}
                                                        autoFocus
                                                        className="flex-1 bg-zinc-950 text-zinc-100 text-sm px-2 py-1 rounded-md border border-zinc-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                                    />
                                                ) : (
                                                    <span className="flex-1 text-sm truncate font-medium">{conv.title}</span>
                                                )}
                                                {/* Actions - show on hover */}
                                                <div className="hidden group-hover:flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setEditingConversationId(conv.id);
                                                            setEditingTitle(conv.title);
                                                        }}
                                                        className="p-1.5 text-zinc-400 hover:text-blue-400 hover:bg-zinc-700/50 rounded-md transition-all"
                                                        title="Rename"
                                                    >
                                                        <Edit3 size={12} />
                                                    </button>
                                                    <button
                                                        onClick={(e) => handleDeleteConversation(conv.id, e)}
                                                        className="p-1.5 text-zinc-400 hover:text-red-400 hover:bg-zinc-700/50 rounded-md transition-all"
                                                        title="Delete"
                                                    >
                                                        <Trash2 size={12} />
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </aside>

                {/* Admin Sidebar - Only for Admin */}
                {isAdmin && (
                    <aside className="w-96 bg-zinc-900/60 backdrop-blur-md border-r border-zinc-800/50 p-6 flex flex-col gap-6 overflow-y-auto">
                        {/* Group Selection */}
                        <div>
                            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Select Group/Vehicle</h3>
                            <div className="flex gap-2 mb-2">
                                <select
                                    className="flex-1 p-2.5 bg-zinc-800 border border-zinc-700/50 rounded-lg text-zinc-200 focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-sm"
                                    value={selectedGroupId || ''}
                                    onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                                >
                                    {groups.length === 0 && <option value="">No groups available</option>}
                                    {groups.map(g => (
                                        <option key={g.id} value={g.id}>{g.name}</option>
                                    ))}
                                </select>
                                <button
                                    onClick={() => setIsCreatingGroup(!isCreatingGroup)}
                                    className="p-2.5 bg-zinc-800 border border-zinc-700/50 hover:bg-zinc-700 hover:border-zinc-600 rounded-lg text-zinc-300 transition-all"
                                    title="Create New Group"
                                >
                                    <Plus size={18} />
                                </button>
                            </div>

                            {isCreatingGroup && (
                                <form onSubmit={handleCreateGroup} className="mt-3 p-4 bg-zinc-800/80 rounded-xl border border-zinc-700/50 shadow-sm">
                                    <input
                                        type="text"
                                        value={newGroupName}
                                        onChange={(e) => setNewGroupName(e.target.value)}
                                        placeholder="New Group Name"
                                        className="w-full p-2 mb-3 text-sm bg-zinc-950 border border-zinc-700 rounded-lg text-zinc-100 placeholder-zinc-500 focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                                        autoFocus
                                    />
                                    <div className="flex justify-end gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setIsCreatingGroup(false)}
                                            className="px-3 py-1.5 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            className="px-3 py-1.5 text-xs font-medium bg-blue-600/90 text-white rounded-lg hover:bg-blue-600 shadow-sm shadow-blue-900/20 transition-all"
                                        >
                                            Create
                                        </button>
                                    </div>
                                </form>
                            )}
                        </div>

                        {/* Document Upload */}
                        <div>
                            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Upload Documents</h3>

                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf,.ppt,.pptx"
                                multiple
                                onChange={handleFilesSelected}
                                className="hidden"
                                id="file-upload"
                            />
                            <label
                                htmlFor="file-upload"
                                className={`flex items-center justify-center gap-3 p-6 border-2 border-dashed border-zinc-700 rounded-xl cursor-pointer hover:border-blue-500/50 hover:bg-zinc-800/50 bg-zinc-800/20 transition-all ${!selectedGroupId ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                <Upload size={22} className="text-zinc-400" />
                                <span className="text-sm font-medium text-zinc-400">Select PDFs or Presentations</span>
                            </label>

                            {uploadQueue.length > 0 && (
                                <div className="mt-5 space-y-3">
                                    <div className="flex justify-between items-center px-1">
                                        <span className="text-xs font-medium text-zinc-500">{uploadQueue.length} file(s) in queue</span>
                                        {hasCompletedUploads && (
                                            <button onClick={handleClearCompleted} className="text-xs font-medium text-blue-400 hover:text-blue-300 transition-colors">
                                                Clear completed
                                            </button>
                                        )}
                                    </div>

                                    <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
                                        {uploadQueue.map(f => (
                                            <div key={f.id} className="bg-zinc-800/80 rounded-xl p-3 border border-zinc-700/50 shadow-sm group">
                                                <div className="flex items-center justify-between gap-3">
                                                    <div className="flex items-center gap-2.5 flex-1 min-w-0">
                                                        {getStatusIcon(f.status)}
                                                        <span className="text-xs font-medium text-zinc-300 truncate">{f.file.name}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">{getStatusText(f.status)}</span>
                                                        {f.status === 'failed' && (
                                                            <button onClick={() => handleRetry(f.id)} className="p-1 text-blue-400 hover:text-blue-300 transition-colors opacity-0 group-hover:opacity-100">
                                                                <RefreshCw size={12} />
                                                            </button>
                                                        )}
                                                        {(f.status === 'pending' || f.status === 'failed' || f.status === 'done') && (
                                                            <button onClick={() => handleRemoveFromQueue(f.id)} className="p-1 text-zinc-500 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100">
                                                                <X size={12} />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>

                                                {(f.status === 'uploading' || f.status === 'processing') && (
                                                    <div className="mt-3 h-1.5 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
                                                        <div
                                                            className={`h-full transition-all duration-300 rounded-full ${f.status === 'processing' ? 'bg-yellow-500/80' : 'bg-blue-500/80'}`}
                                                            style={{ width: `${f.progress}%` }}
                                                        />
                                                    </div>
                                                )}

                                                {f.error && (
                                                    <p className="mt-2 text-[11px] text-red-400/90 font-medium bg-red-400/10 p-1.5 rounded-lg border border-red-400/20">{f.error}</p>
                                                )}
                                            </div>
                                        ))}
                                    </div>

                                    {hasPendingUploads && (
                                        <button
                                            onClick={handleUploadAll}
                                            disabled={!selectedGroupId}
                                            className="w-full mt-2 flex items-center justify-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 font-semibold p-2.5 rounded-xl disabled:opacity-50 transition-all shadow-sm"
                                        >
                                            <Upload size={16} className="text-zinc-600" /> Start Upload ({uploadQueue.filter(f => f.status === 'pending').length})
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    </aside>
                )}

                {/* Chat Area */}
                <section className="flex-1 flex flex-col bg-transparent relative z-0">
                    {!isAdmin && hasMultipleGroups && (
                        <div className="p-3 bg-zinc-900/60 backdrop-blur-sm border-b border-zinc-800/50 flex items-center justify-center">
                            <label className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mr-3">Query from</label>
                            <select
                                className="p-1.5 bg-zinc-800 border border-zinc-700 rounded-md text-zinc-200 text-sm focus:ring-1 focus:ring-blue-500/50"
                                value={selectedGroupId || ''}
                                onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                            >
                                {groups.map(g => (
                                    <option key={g.id} value={g.id}>{g.name}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 scroll-smooth">
                        {messages.length === 0 && !isQuerying && (
                            <div className="text-center text-zinc-500 mt-32 flex flex-col items-center">
                                <div className="bg-zinc-800/50 p-6 rounded-3xl border border-zinc-700/50 shadow-sm mb-6">
                                    <FileText size={48} className="text-zinc-600" />
                                </div>
                                <h2 className="text-lg font-medium text-zinc-300 mb-2">Welcome to RAG AI</h2>
                                <p className="text-sm">
                                    {groups.length === 0
                                        ? "You are not assigned to any group yet. Please contact an admin."
                                        : "Start asking questions about the vehicle documents."}
                                </p>
                            </div>
                        )}

                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                                <div className={`relative max-w-3xl p-5 rounded-2xl ${msg.role === 'user'
                                    ? 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-900/20 rounded-br-sm'
                                    : 'bg-zinc-800/40 backdrop-blur-sm border border-zinc-700/50 text-zinc-200 shadow-sm rounded-bl-sm'
                                    }`}>

                                    {msg.role === 'user' ? (
                                        <p className="whitespace-pre-wrap leading-relaxed text-sm">{msg.content}</p>
                                    ) : (
                                        <div className="markdown-content">
                                            <ReactMarkdown
                                                remarkPlugins={[remarkGfm]}
                                                components={MarkdownComponents}
                                            >
                                                {msg.content}
                                            </ReactMarkdown>
                                        </div>
                                    )}

                                    {msg.sources && msg.sources.length > 0 && (
                                        <div className="mt-5 pt-4 border-t border-zinc-700/50">
                                            <p className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider mb-3">Sources</p>
                                            <div className="flex flex-wrap gap-2">
                                                {msg.sources.map((src, i) => (
                                                    <button
                                                        key={i}
                                                        onClick={() => setSelectedSource(src)}
                                                        className="px-3 py-1.5 bg-zinc-900/60 border border-zinc-700 hover:border-zinc-500 hover:bg-zinc-800 rounded-full text-xs text-zinc-400 hover:text-zinc-200 transition-all shadow-sm flex items-center gap-1.5 group"
                                                    >
                                                        <FileText size={12} className="text-zinc-500 group-hover:text-zinc-400" />
                                                        <span className="truncate max-w-[150px]">{src.filename || `Page ${src.page_number}`}</span>
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}

                        {/* Typing Indicator */}
                        {isQuerying && (
                            <div className="flex justify-start animate-in fade-in duration-300">
                                <div className="bg-zinc-800/40 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-4 flex items-center gap-3 rounded-bl-sm">
                                    <div className="flex gap-1.5">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce"></div>
                                    </div>
                                    <span className="text-zinc-500 text-sm font-medium">Thinking...</span>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} className="h-4" />
                    </div>

                    {/* Input Area - Floating Pill Design */}
                    <div className="p-4 md:p-6 bg-gradient-to-t from-zinc-950 via-zinc-950/90 to-transparent pb-6">
                        <div className="max-w-4xl mx-auto rounded-2xl bg-zinc-900/80 backdrop-blur-xl border border-zinc-700/50 shadow-xl overflow-hidden shadow-black/20">

                            {/* Model Selector Bar */}
                            <div className="flex items-center gap-2 px-4 py-2 bg-zinc-800/30 border-b border-zinc-700/50">
                                <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                                    {selectedModel.provider === 'nvidia' ? (
                                        <Cloud size={13} className="text-emerald-400" />
                                    ) : (
                                        <Cpu size={13} className="text-blue-400" />
                                    )}
                                    <span>Model</span>
                                </div>
                                <select
                                    value={selectedModel.provider && selectedModel.name ? `${selectedModel.provider}:${selectedModel.name}` : 'default'}
                                    onChange={(e) => handleModelChange(e.target.value)}
                                    className="max-w-[200px] text-xs bg-transparent text-zinc-300 font-medium focus:outline-none cursor-pointer hover:text-white transition-colors border-none p-0 focus:ring-0"
                                >
                                    <option value="default" className="bg-zinc-900 text-zinc-100">Server Default</option>
                                    {ollamaModels.length > 0 && (
                                        <optgroup label="⚡ Local (Ollama)" className="bg-zinc-900 text-zinc-500 font-semibold">
                                            {ollamaModels.map(m => (
                                                <option key={m.name} value={`ollama:${m.name}`} className="text-zinc-100 font-medium">
                                                    {m.label} ({m.size})
                                                </option>
                                            ))}
                                        </optgroup>
                                    )}
                                    {cloudModels.length > 0 && (
                                        <optgroup label="☁️ Cloud (NVIDIA)" className="bg-zinc-900 text-zinc-500 font-semibold">
                                            {cloudModels.map(m => (
                                                <option key={m.name} value={`nvidia:${m.name}`} className="text-zinc-100 font-medium">
                                                    {m.label}
                                                </option>
                                            ))}
                                        </optgroup>
                                    )}
                                </select>
                            </div>

                            <form onSubmit={handleSearch} className="flex gap-3 p-2 pl-4">
                                <input
                                    type="text"
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    placeholder={groups.length === 0 ? "No group assigned..." : "Ask a question about the vehicle documents..."}
                                    disabled={groups.length === 0 || isQuerying}
                                    className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 text-zinc-100 placeholder-zinc-500 disabled:text-zinc-600 font-medium text-[15px] pt-1"
                                />
                                <button
                                    type="submit"
                                    disabled={!query.trim() || !selectedGroupId || groups.length === 0 || isQuerying}
                                    className="bg-zinc-800 text-white p-3 rounded-xl hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-all shadow-sm group border border-zinc-700/50"
                                >
                                    {isQuerying ? <Loader2 size={18} className="animate-spin text-blue-400" /> : <Send size={18} className="text-blue-400 group-hover:scale-110 transition-transform" />}
                                </button>
                            </form>
                        </div>
                    </div>
                </section>
            </main>

            {/* Source Citation Modal */}
            {selectedSource && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[100] p-4 animate-in fade-in duration-200">
                    <div className="bg-zinc-900 rounded-2xl shadow-2xl shadow-black max-w-2xl w-full max-h-[80vh] flex flex-col border border-zinc-700/60 overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="flex items-center justify-between p-5 border-b border-zinc-800 bg-zinc-900/50">
                            <div>
                                <h3 className="font-semibold text-zinc-100">{selectedSource.filename || 'Source Citation'}</h3>
                                <p className="text-xs font-medium text-zinc-500 mt-0.5">Page {selectedSource.page_number}</p>
                            </div>
                            <button onClick={() => setSelectedSource(null)} className="p-2 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 rounded-full transition-all">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-6 bg-zinc-950/50">
                            <div className="bg-zinc-900/80 rounded-xl p-5 text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap border border-zinc-800 shadow-inner font-serif">
                                {selectedSource.full_text}
                            </div>
                        </div>
                        <div className="p-4 border-t border-zinc-800 bg-zinc-900/80 text-[11px] font-mono text-zinc-600 truncate">
                            {selectedSource.file_path && <p>Path: {selectedSource.file_path}</p>}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
