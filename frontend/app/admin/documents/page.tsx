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

    const fetchDocs = useCallback(() => {
        let url = '/admin/documents';
        const params = new URLSearchParams();
        if (selectedGroup) params.append('group_id', String(selectedGroup));
        if (filterStatus) params.append('status', filterStatus);
        if (params.toString()) url += `?${params}`;
        api.get(url).then(r => setDocs(r.data)).catch(console.error).finally(() => setLoading(false));
    }, [selectedGroup, filterStatus]);

    useEffect(() => {
        api.get('/groups').then(r => setGroups(r.data)).catch(() => { });
        fetchDocs();
    }, [fetchDocs]);

    // Poll for pending/processing docs
    useEffect(() => {
        const hasActive = docs.some(d => d.processing_status === 'pending' || d.processing_status === 'processing');
        if (!hasActive) return;
        const interval = setInterval(fetchDocs, 3000);
        return () => clearInterval(interval);
    }, [docs, fetchDocs]);

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
        <div>
            <h1 className="text-xl font-bold text-gray-100 mb-6">Documents</h1>

            {/* Upload zone */}
            <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 mb-6 text-center transition-colors
          ${dragOver ? 'border-indigo-500 bg-indigo-500/5' : 'border-gray-700 hover:border-gray-600'}`}
            >
                <Upload className="w-8 h-8 text-gray-500 mx-auto mb-3" />
                <p className="text-sm text-gray-400 mb-3">Drag & drop files here, or click to upload</p>
                <div className="flex items-center justify-center gap-3">
                    <select
                        value={selectedGroup}
                        onChange={e => setSelectedGroup(Number(e.target.value) || '')}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
                    >
                        <option value="">Select group...</option>
                        {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                    </select>
                    <label className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors
            ${selectedGroup ? 'bg-indigo-600 hover:bg-indigo-500 text-white' : 'bg-gray-800 text-gray-500 cursor-not-allowed'}`}>
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
            <div className="flex gap-3 mb-4">
                <select
                    value={filterStatus}
                    onChange={e => setFilterStatus(e.target.value)}
                    className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300"
                >
                    <option value="">All statuses</option>
                    <option value="done">Done</option>
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="failed">Failed</option>
                </select>
                <button onClick={fetchDocs} className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400" title="Refresh">
                    <RefreshCw className="w-4 h-4" />
                </button>
            </div>

            {/* Document table */}
            {loading ? (
                <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>
            ) : docs.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                    <FileText className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p>No documents found.</p>
                </div>
            ) : (
                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                                <th className="text-left px-4 py-3">Filename</th>
                                <th className="text-left px-4 py-3">Group</th>
                                <th className="text-left px-4 py-3">Status</th>
                                <th className="text-left px-4 py-3">Chunks</th>
                                <th className="text-left px-4 py-3">Uploaded</th>
                                <th className="text-right px-4 py-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {docs.map(doc => {
                                const st = STATUS_STYLES[doc.processing_status] || STATUS_STYLES.done;
                                const StIcon = st.icon;
                                return (
                                    <tr key={doc.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                                        <td className="px-4 py-3 text-gray-200 font-medium">{doc.filename}</td>
                                        <td className="px-4 py-3 text-gray-400">{getGroupName(doc.group_id)}</td>
                                        <td className="px-4 py-3">
                                            <span className={`flex items-center gap-1.5 ${st.color}`}>
                                                <StIcon className={`w-3.5 h-3.5 ${doc.processing_status === 'processing' ? 'animate-spin' : ''}`} />
                                                {st.label}
                                            </span>
                                            {doc.processing_error && (
                                                <p className="text-xs text-red-400/70 mt-1 truncate max-w-[200px]" title={doc.processing_error}>
                                                    {doc.processing_error}
                                                </p>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 text-gray-400">{doc.chunk_count ?? '—'}</td>
                                        <td className="px-4 py-3 text-gray-500 text-xs">
                                            {doc.upload_date ? new Date(doc.upload_date).toLocaleDateString() : '—'}
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                {doc.processing_status === 'failed' && (
                                                    <button onClick={() => handleRetry(doc.id)}
                                                        className="p-1.5 rounded hover:bg-gray-700 text-amber-400" title="Retry">
                                                        <RefreshCw className="w-3.5 h-3.5" />
                                                    </button>
                                                )}
                                                <button onClick={() => handleDelete(doc.id)}
                                                    className="p-1.5 rounded hover:bg-gray-700 text-red-400" title="Delete">
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
