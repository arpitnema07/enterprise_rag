'use client';

import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';
import { Upload, Trash2, RefreshCw, CheckCircle, XCircle, Clock, Loader2, FileText } from 'lucide-react';

interface Document {
    id: number;
    filename: string;
    group_id: number;
    upload_date: string;
    processing_status: string;
    processing_error: string | null;
    chunk_count: number | null;
    object_key: string | null;
}

interface Group {
    id: number;
    name: string;
}

const STATUS_STYLES: Record<string, { icon: any; color: string; label: string }> = {
    done: { icon: CheckCircle, color: 'text-emerald-400', label: 'Done' },
    pending: { icon: Clock, color: 'text-yellow-400', label: 'Pending' },
    processing: { icon: Loader2, color: 'text-blue-400', label: 'Processing' },
    failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
};

export default function DocumentsPage() {
    const [docs, setDocs] = useState<Document[]>([]);
    const [groups, setGroups] = useState<Group[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [selectedGroup, setSelectedGroup] = useState<number | ''>('');
    const [filterStatus, setFilterStatus] = useState<string>('');
    const [dragOver, setDragOver] = useState(false);
    const [retryAfterMs, setRetryAfterMs] = useState(0);

    const fetchDocs = useCallback(() => {
        let url = '/admin/documents';
        const params = new URLSearchParams();
        if (selectedGroup) params.append('group_id', String(selectedGroup));
        if (filterStatus) params.append('status', filterStatus);
        if (params.toString()) url += `?${params}`;
        api.get(url).then(r => {
            setDocs(r.data.documents);
            setRetryAfterMs(r.data.retry_after_ms || 0);
        }).catch(console.error).finally(() => setLoading(false));
    }, [selectedGroup, filterStatus]);

    useEffect(() => {
        api.get('/groups').then(r => setGroups(r.data)).catch(() => { });
        fetchDocs();
    }, [fetchDocs]);

    // Smart polling: use server-provided retry_after_ms
    useEffect(() => {
        if (retryAfterMs <= 0) return;
        const timer = setTimeout(fetchDocs, retryAfterMs);
        return () => clearTimeout(timer);
    }, [retryAfterMs, fetchDocs]);

    const handleUpload = async (files: FileList, groupId: number) => {
        setUploading(true);
        for (const file of Array.from(files)) {
            const formData = new FormData();
            formData.append('file', file);
            try {
                await api.post(`/documents/upload?group_id=${groupId}`, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
            } catch (err: any) {
                alert(`Upload failed for ${file.name}: ${err.response?.data?.detail || err.message}`);
            }
        }
        setUploading(false);
        fetchDocs();
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        if (!selectedGroup) { alert('Select a group first'); return; }
        if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files, Number(selectedGroup));
    };

    const handleDelete = async (docId: number) => {
        if (!confirm('Delete this document? This will also remove its chunks from the vector DB.')) return;
        await api.delete(`/admin/documents/${docId}`);
        fetchDocs();
    };

    const handleRetry = async (docId: number) => {
        try {
            await api.post(`/admin/documents/${docId}/retry`);
            fetchDocs();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Retry failed');
        }
    };

    const getGroupName = (id: number) => groups.find(g => g.id === id)?.name || `Group ${id}`;

    return (
        <div className="animate-in fade-in duration-500">
            <h1 className="text-2xl font-bold bg-gradient-to-br from-zinc-100 to-zinc-500 bg-clip-text text-transparent mb-6">Documents</h1>

            {/* Upload zone */}
            <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-2xl p-8 mb-8 text-center transition-all duration-300
          ${dragOver ? 'border-blue-500 bg-blue-500/5 scale-[1.01]' : 'border-zinc-700 bg-zinc-900/30 hover:bg-zinc-900/50 hover:border-zinc-600'}`}
            >
                <div className={`mx-auto w-16 h-16 rounded-full flex items-center justify-center mb-4 transition-colors ${dragOver ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-800 text-zinc-500'}`}>
                    <Upload className="w-8 h-8" />
                </div>
                <p className="text-sm font-medium text-zinc-400 mb-6">Drag & drop files here, or click to browse</p>
                <div className="flex items-center justify-center gap-3 max-w-sm mx-auto">
                    <select
                        value={selectedGroup}
                        onChange={e => setSelectedGroup(Number(e.target.value) || '')}
                        className="flex-1 bg-zinc-800/80 border border-zinc-700/50 rounded-xl px-4 py-2.5 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all cursor-pointer"
                    >
                        <option value="">Select group...</option>
                        {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                    </select>
                    <label className={`px-5 py-2.5 rounded-xl text-sm font-semibold cursor-pointer transition-all shadow-sm flex items-center gap-2
            ${selectedGroup ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/20 hover:scale-[1.02]' : 'bg-zinc-800/50 border border-zinc-700 text-zinc-500 cursor-not-allowed opacity-70'}`}>
                        {uploading ? <Loader2 size={16} className="animate-spin" /> : null}
                        {uploading ? 'Uploading...' : 'Choose Files'}
                        <input
                            type="file" multiple accept=".pdf,.pptx,.ppt" className="hidden"
                            disabled={!selectedGroup || uploading}
                            onChange={e => e.target.files && handleUpload(e.target.files, Number(selectedGroup))}
                        />
                    </label>
                </div>
            </div>

            {/* Filters */}
            <div className="flex bg-zinc-900/40 p-3 rounded-2xl border border-zinc-800/50 gap-3 mb-6 items-center">
                <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider pl-2 hidden sm:block">Filter Results</span>
                <select
                    value={filterStatus}
                    onChange={e => setFilterStatus(e.target.value)}
                    className="bg-zinc-800/80 border border-zinc-700/50 rounded-lg px-4 py-2 text-sm text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition-all min-w-[150px]"
                >
                    <option value="">All statuses</option>
                    <option value="done">Done</option>
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="failed">Failed</option>
                </select>
                <button
                    onClick={fetchDocs}
                    className="p-2.5 ml-auto rounded-lg bg-zinc-800/50 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-700/30 hover:border-zinc-600 transition-all"
                    title="Refresh List"
                >
                    <RefreshCw className="w-4 h-4" />
                </button>
            </div>

            {/* Document table */}
            {loading ? (
                <div className="flex items-center justify-center py-20 bg-zinc-900/20 rounded-2xl border border-zinc-800/50"><Loader2 className="w-8 h-8 animate-spin text-blue-500/60" /></div>
            ) : docs.length === 0 ? (
                <div className="text-center py-24 bg-zinc-900/20 rounded-2xl border border-zinc-800/50 flex flex-col items-center justify-center">
                    <div className="bg-zinc-800/50 p-6 rounded-full mb-4">
                        <FileText className="w-10 h-10 text-zinc-600" />
                    </div>
                    <p className="text-zinc-400 font-medium">No documents found matching the criteria.</p>
                </div>
            ) : (
                <div className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-800/60 rounded-2xl overflow-hidden shadow-sm">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-zinc-800/60 bg-zinc-900 text-zinc-500 text-[10px] font-semibold uppercase tracking-wider">
                                    <th className="text-left px-5 py-4">Filename</th>
                                    <th className="text-left px-5 py-4">Group</th>
                                    <th className="text-left px-5 py-4">Status</th>
                                    <th className="text-left px-5 py-4">Chunks</th>
                                    <th className="text-left px-5 py-4">Uploaded</th>
                                    <th className="text-right px-5 py-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-800/40">
                                {docs.map(doc => {
                                    const st = STATUS_STYLES[doc.processing_status] || STATUS_STYLES.done;
                                    const StIcon = st.icon;
                                    return (
                                        <tr key={doc.id} className="hover:bg-zinc-800/30 transition-colors group">
                                            <td className="px-5 py-4 text-zinc-200 font-medium break-all max-w-[200px]">{doc.filename}</td>
                                            <td className="px-5 py-4 text-zinc-400">{getGroupName(doc.group_id)}</td>
                                            <td className="px-5 py-4">
                                                <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-zinc-950/50 ${doc.processing_status === 'done' ? 'border-emerald-500/20 text-emerald-400' : doc.processing_status === 'failed' ? 'border-red-500/20 text-red-400' : doc.processing_status === 'processing' ? 'border-blue-500/20 text-blue-400' : 'border-yellow-500/20 text-yellow-400'}`}>
                                                    <StIcon className={`w-3.5 h-3.5 ${doc.processing_status === 'processing' ? 'animate-spin' : ''}`} />
                                                    {st.label}
                                                </div>
                                                {doc.processing_error && (
                                                    <p className="text-[10px] text-red-400/80 mt-2 truncate max-w-[200px] bg-red-400/10 px-2 py-1 rounded-md" title={doc.processing_error}>
                                                        {doc.processing_error}
                                                    </p>
                                                )}
                                            </td>
                                            <td className="px-5 py-4 text-zinc-400">
                                                {doc.chunk_count !== null ? (
                                                    <span className="inline-flex items-center justify-center bg-zinc-800/80 px-2.5 py-1 rounded-md text-xs font-mono">{doc.chunk_count}</span>
                                                ) : <span className="text-zinc-600">—</span>}
                                            </td>
                                            <td className="px-5 py-4 text-zinc-500 text-xs font-mono">
                                                {doc.upload_date ? new Date(doc.upload_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                                            </td>
                                            <td className="px-5 py-4 text-right">
                                                <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    {doc.processing_status === 'failed' && (
                                                        <button onClick={() => handleRetry(doc.id)}
                                                            className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-amber-400 transition-colors" title="Retry Processing">
                                                            <RefreshCw className="w-[18px] h-[18px]" />
                                                        </button>
                                                    )}
                                                    <button onClick={() => handleDelete(doc.id)}
                                                        className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-red-400 transition-colors" title="Delete Document & Chunks">
                                                        <Trash2 className="w-[18px] h-[18px]" />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}
