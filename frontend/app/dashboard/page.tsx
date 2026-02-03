'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '@/lib/api';
import { LogOut, Send, FileText, Plus, Settings, Upload, X, RefreshCw, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

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
}

// Custom Markdown components for proper table styling
const MarkdownComponents = {
    table: ({ children }: { children: React.ReactNode }) => (
        <div className="overflow-x-auto my-4">
            <table className="min-w-full border-collapse border border-gray-600 text-sm">
                {children}
            </table>
        </div>
    ),
    thead: ({ children }: { children: React.ReactNode }) => (
        <thead className="bg-gray-700">{children}</thead>
    ),
    tbody: ({ children }: { children: React.ReactNode }) => (
        <tbody className="divide-y divide-gray-600">{children}</tbody>
    ),
    tr: ({ children }: { children: React.ReactNode }) => (
        <tr className="border-b border-gray-600">{children}</tr>
    ),
    th: ({ children }: { children: React.ReactNode }) => (
        <th className="px-4 py-2 text-left font-semibold text-gray-200 border border-gray-600">
            {children}
        </th>
    ),
    td: ({ children }: { children: React.ReactNode }) => (
        <td className="px-4 py-2 text-gray-300 border border-gray-600">{children}</td>
    ),
    code: ({ className, children }: { className?: string; children: React.ReactNode }) => {
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
    pre: ({ children }: { children: React.ReactNode }) => (
        <pre className="bg-gray-900 rounded-lg overflow-x-auto my-4">{children}</pre>
    ),
    ul: ({ children }: { children: React.ReactNode }) => (
        <ul className="list-disc list-inside my-2 space-y-1 text-gray-300">{children}</ul>
    ),
    ol: ({ children }: { children: React.ReactNode }) => (
        <ol className="list-decimal list-inside my-2 space-y-1 text-gray-300">{children}</ol>
    ),
    li: ({ children }: { children: React.ReactNode }) => (
        <li className="text-gray-300">{children}</li>
    ),
    h1: ({ children }: { children: React.ReactNode }) => (
        <h1 className="text-2xl font-bold text-white mt-4 mb-2">{children}</h1>
    ),
    h2: ({ children }: { children: React.ReactNode }) => (
        <h2 className="text-xl font-bold text-white mt-4 mb-2">{children}</h2>
    ),
    h3: ({ children }: { children: React.ReactNode }) => (
        <h3 className="text-lg font-semibold text-white mt-3 mb-1">{children}</h3>
    ),
    p: ({ children }: { children: React.ReactNode }) => (
        <p className="text-gray-300 leading-relaxed my-2">{children}</p>
    ),
    a: ({ href, children }: { href?: string; children: React.ReactNode }) => (
        <a href={href} className="text-blue-400 hover:text-blue-300 underline" target="_blank" rel="noopener noreferrer">
            {children}
        </a>
    ),
    blockquote: ({ children }: { children: React.ReactNode }) => (
        <blockquote className="border-l-4 border-blue-500 pl-4 my-4 text-gray-400 italic">
            {children}
        </blockquote>
    ),
    strong: ({ children }: { children: React.ReactNode }) => (
        <strong className="font-semibold text-white">{children}</strong>
    ),
    em: ({ children }: { children: React.ReactNode }) => (
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
    }, [router]);

    const handleLogout = () => {
        localStorage.removeItem('token');
        router.push('/login');
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
            const res = await api.post('/documents/query', {
                query: userMessage.content,
                group_id: selectedGroupId
            });

            const botMessage: Message = {
                role: 'bot',
                content: res.data.answer,
                sources: res.data.sources
            };
            setMessages((prev) => [...prev, botMessage]);
        } catch (err) {
            console.error(err);
            setMessages((prev) => [...prev, { role: 'bot', content: 'Error processing query.' }]);
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
        <div className="flex flex-col h-screen bg-gray-900">
            {/* Header */}
            <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <h1 className="text-xl font-semibold text-white">Vehicle RAG System</h1>
                    {isAdmin && <span className="bg-blue-600 text-blue-100 text-xs px-2 py-1 rounded-full">Admin</span>}
                </div>
                <div className="flex items-center gap-4">
                    {isAdmin && (
                        <button
                            onClick={() => router.push('/admin')}
                            className="p-2 text-gray-400 hover:text-blue-400 transition-colors"
                            title="Admin Panel"
                        >
                            <Settings size={20} />
                        </button>
                    )}
                    <span className="text-gray-300">{user?.email}</span>
                    <button onClick={handleLogout} className="p-2 text-gray-400 hover:text-red-400 transition-colors">
                        <LogOut size={20} />
                    </button>
                </div>
            </header>

            <main className="flex-1 flex overflow-hidden">
                {/* Sidebar - Only for Admin */}
                {isAdmin && (
                    <aside className="w-96 bg-gray-800 border-r border-gray-700 p-6 flex flex-col gap-6 overflow-y-auto">
                        {/* Group Selection */}
                        <div>
                            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">Select Group/Vehicle</h3>
                            <div className="flex gap-2 mb-2">
                                <select
                                    className="flex-1 p-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                                    className="p-2 bg-gray-700 hover:bg-gray-600 rounded-md text-gray-300 transition-colors"
                                    title="Create New Group"
                                >
                                    <Plus size={20} />
                                </button>
                            </div>

                            {isCreatingGroup && (
                                <form onSubmit={handleCreateGroup} className="mt-2 p-3 bg-gray-700 rounded-md border border-gray-600">
                                    <input
                                        type="text"
                                        value={newGroupName}
                                        onChange={(e) => setNewGroupName(e.target.value)}
                                        placeholder="New Group Name"
                                        className="w-full p-2 mb-2 text-sm bg-gray-600 border border-gray-500 rounded-md text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500"
                                        autoFocus
                                    />
                                    <div className="flex justify-end gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setIsCreatingGroup(false)}
                                            className="px-2 py-1 text-xs text-gray-400 hover:text-gray-200"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            className="px-2 py-1 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700"
                                        >
                                            Create
                                        </button>
                                    </div>
                                </form>
                            )}
                        </div>

                        {/* Document Upload */}
                        <div>
                            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">Upload Documents</h3>

                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf"
                                multiple
                                onChange={handleFilesSelected}
                                className="hidden"
                                id="file-upload"
                            />
                            <label
                                htmlFor="file-upload"
                                className={`flex items-center justify-center gap-2 p-4 border-2 border-dashed border-gray-600 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-gray-700/50 transition-colors ${!selectedGroupId ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                <Upload size={20} className="text-gray-400" />
                                <span className="text-sm text-gray-400">Click to select PDFs</span>
                            </label>

                            {uploadQueue.length > 0 && (
                                <div className="mt-4 space-y-2">
                                    <div className="flex justify-between items-center">
                                        <span className="text-xs text-gray-400">{uploadQueue.length} file(s)</span>
                                        {hasCompletedUploads && (
                                            <button onClick={handleClearCompleted} className="text-xs text-gray-500 hover:text-gray-300">
                                                Clear completed
                                            </button>
                                        )}
                                    </div>

                                    <div className="max-h-64 overflow-y-auto space-y-2">
                                        {uploadQueue.map(f => (
                                            <div key={f.id} className="bg-gray-700 rounded-md p-2 border border-gray-600">
                                                <div className="flex items-center justify-between gap-2">
                                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                                        {getStatusIcon(f.status)}
                                                        <span className="text-xs text-gray-300 truncate">{f.file.name}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-xs text-gray-500">{getStatusText(f.status)}</span>
                                                        {f.status === 'failed' && (
                                                            <button onClick={() => handleRetry(f.id)} className="p-1 text-blue-400 hover:text-blue-300">
                                                                <RefreshCw size={12} />
                                                            </button>
                                                        )}
                                                        {(f.status === 'pending' || f.status === 'failed' || f.status === 'done') && (
                                                            <button onClick={() => handleRemoveFromQueue(f.id)} className="p-1 text-gray-500 hover:text-red-400">
                                                                <X size={12} />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>

                                                {(f.status === 'uploading' || f.status === 'processing') && (
                                                    <div className="mt-2 h-1.5 bg-gray-600 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full transition-all duration-300 ${f.status === 'processing' ? 'bg-yellow-500' : 'bg-blue-500'}`}
                                                            style={{ width: `${f.progress}%` }}
                                                        />
                                                    </div>
                                                )}

                                                {f.error && (
                                                    <p className="mt-1 text-xs text-red-400">{f.error}</p>
                                                )}
                                            </div>
                                        ))}
                                    </div>

                                    {hasPendingUploads && (
                                        <button
                                            onClick={handleUploadAll}
                                            disabled={!selectedGroupId}
                                            className="w-full mt-2 flex items-center justify-center gap-2 bg-blue-600 text-white p-2 rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                                        >
                                            <Upload size={16} /> Upload All ({uploadQueue.filter(f => f.status === 'pending').length})
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    </aside>
                )}

                {/* Chat Area */}
                <section className="flex-1 flex flex-col bg-gray-900">
                    {!isAdmin && hasMultipleGroups && (
                        <div className="p-4 bg-gray-800 border-b border-gray-700">
                            <label className="text-sm text-gray-400 mr-2">Query from:</label>
                            <select
                                className="p-2 bg-gray-700 border border-gray-600 rounded-md text-white"
                                value={selectedGroupId || ''}
                                onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                            >
                                {groups.map(g => (
                                    <option key={g.id} value={g.id}>{g.name}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div className="flex-1 overflow-y-auto p-6 space-y-6">
                        {messages.length === 0 && !isQuerying && (
                            <div className="text-center text-gray-500 mt-20">
                                <FileText size={48} className="mx-auto mb-4 opacity-50" />
                                <p>
                                    {groups.length === 0
                                        ? "You are not assigned to any group yet. Please contact an admin."
                                        : "Start asking questions about the vehicle documents."}
                                </p>
                            </div>
                        )}

                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-3xl p-4 rounded-lg ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-800 border border-gray-700 text-gray-200'}`}>
                                    {msg.role === 'user' ? (
                                        <p className="whitespace-pre-wrap">{msg.content}</p>
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
                                        <div className="mt-4 pt-4 border-t border-gray-600 text-xs">
                                            <p className="font-semibold text-gray-400 mb-2">Sources (click to view):</p>
                                            <div className="flex flex-wrap gap-2">
                                                {msg.sources.map((src, i) => (
                                                    <button
                                                        key={i}
                                                        onClick={() => setSelectedSource(src)}
                                                        className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 hover:text-white transition-colors"
                                                    >
                                                        📄 {src.filename || `Page ${src.page_number}`}
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
                            <div className="flex justify-start">
                                <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 flex items-center gap-2">
                                    <Loader2 size={16} className="animate-spin text-blue-400" />
                                    <span className="text-gray-400 text-sm">Thinking...</span>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input Area */}
                    <div className="p-4 bg-gray-800 border-t border-gray-700">
                        <form onSubmit={handleSearch} className="flex gap-4 max-w-4xl mx-auto">
                            <input
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder={groups.length === 0 ? "No group assigned..." : "Ask a question about the vehicle documents..."}
                                disabled={groups.length === 0 || isQuerying}
                                className="flex-1 p-3 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white placeholder-gray-400 disabled:bg-gray-800 disabled:text-gray-500"
                            />
                            <button
                                type="submit"
                                disabled={!query.trim() || !selectedGroupId || groups.length === 0 || isQuerying}
                                className="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
                            >
                                {isQuerying ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
                            </button>
                        </form>
                    </div>
                </section>
            </main>

            {/* Source Citation Modal */}
            {selectedSource && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col border border-gray-700">
                        <div className="flex items-center justify-between p-4 border-b border-gray-700">
                            <div>
                                <h3 className="font-semibold text-white">{selectedSource.filename || 'Source Citation'}</h3>
                                <p className="text-sm text-gray-400">Page {selectedSource.page_number}</p>
                            </div>
                            <button onClick={() => setSelectedSource(null)} className="text-gray-400 hover:text-white transition-colors">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4">
                            <div className="bg-gray-900 rounded-lg p-4 text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                                {selectedSource.full_text}
                            </div>
                        </div>
                        <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
                            {selectedSource.file_path && <p>File: {selectedSource.file_path}</p>}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
