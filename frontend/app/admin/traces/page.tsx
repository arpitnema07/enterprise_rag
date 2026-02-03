'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import {
    ArrowLeft, RefreshCw, Search, ChevronDown, ChevronRight,
    Clock, Zap, Hash, CheckCircle, XCircle, Trash2, Filter
} from 'lucide-react';

interface Trace {
    trace_id: string;
    timestamp: string;
    user_id: number | null;
    user_email: string | null;
    query: string;
    response: string;
    chunks: ChunkInfo[];
    latency: {
        retrieval_ms: number;
        generation_ms: number;
        total_ms: number;
    };
    tokens: {
        prompt: number;
        completion: number;
        total: number;
    };
    status: 'success' | 'error';
    error: string | null;
}

interface ChunkInfo {
    text: string;
    score: number;
    page_number: number;
    file_path: string;
    group_id: number;
}

export default function TracesPage() {
    const [traces, setTraces] = useState<Trace[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [expandedTrace, setExpandedTrace] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('');
    const [autoRefresh, setAutoRefresh] = useState(false);
    const [offset, setOffset] = useState(0);
    const limit = 25;
    const router = useRouter();

    const fetchTraces = useCallback(async () => {
        try {
            const params = new URLSearchParams({
                limit: String(limit),
                offset: String(offset),
            });
            if (searchQuery) params.append('search', searchQuery);
            if (statusFilter) params.append('status', statusFilter);

            const res = await api.get(`/admin/traces?${params}`);
            setTraces(res.data.traces);
            setTotal(res.data.total);
        } catch (err: any) {
            if (err.response?.status === 403) {
                router.push('/dashboard');
            }
            console.error('Failed to fetch traces', err);
        } finally {
            setLoading(false);
        }
    }, [offset, searchQuery, statusFilter, router]);

    useEffect(() => {
        fetchTraces();
    }, [fetchTraces]);

    useEffect(() => {
        if (autoRefresh) {
            const interval = setInterval(fetchTraces, 5000);
            return () => clearInterval(interval);
        }
    }, [autoRefresh, fetchTraces]);

    const handleClearTraces = async () => {
        if (!confirm('Archive all traces? This will move them to a timestamped file.')) return;
        try {
            await api.delete('/admin/traces?confirm=true');
            fetchTraces();
        } catch (err) {
            console.error('Failed to clear traces', err);
        }
    };

    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${Math.round(ms)}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    };

    const formatDate = (iso: string) => {
        const d = new Date(iso);
        return d.toLocaleString();
    };

    const getStatusColor = (status: string) => {
        return status === 'success'
            ? 'bg-green-500/20 text-green-400 border-green-500/30'
            : 'bg-red-500/20 text-red-400 border-red-500/30';
    };

    return (
        <div className="min-h-screen bg-gray-900 text-gray-100">
            {/* Header */}
            <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
                <div className="max-w-7xl mx-auto flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => router.push('/admin')}
                            className="text-gray-400 hover:text-white transition-colors"
                        >
                            <ArrowLeft size={20} />
                        </button>
                        <h1 className="text-xl font-bold">Trace Monitor</h1>
                        <span className="text-xs bg-blue-600 px-2 py-1 rounded-full">
                            {total} traces
                        </span>
                    </div>
                    <div className="flex items-center gap-3">
                        <label className="flex items-center gap-2 text-sm text-gray-400">
                            <input
                                type="checkbox"
                                checked={autoRefresh}
                                onChange={(e) => setAutoRefresh(e.target.checked)}
                                className="rounded bg-gray-700 border-gray-600"
                            />
                            Auto-refresh
                        </label>
                        <button
                            onClick={fetchTraces}
                            className="p-2 text-gray-400 hover:text-white transition-colors"
                            title="Refresh"
                        >
                            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                        </button>
                        <button
                            onClick={handleClearTraces}
                            className="p-2 text-gray-400 hover:text-red-400 transition-colors"
                            title="Archive All"
                        >
                            <Trash2 size={18} />
                        </button>
                    </div>
                </div>
            </header>

            {/* Filters */}
            <div className="bg-gray-800/50 border-b border-gray-700 px-6 py-3">
                <div className="max-w-7xl mx-auto flex gap-4 items-center">
                    <div className="relative flex-1 max-w-md">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                        <input
                            type="text"
                            placeholder="Search queries..."
                            value={searchQuery}
                            onChange={(e) => { setSearchQuery(e.target.value); setOffset(0); }}
                            className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <Filter size={16} className="text-gray-500" />
                        <select
                            value={statusFilter}
                            onChange={(e) => { setStatusFilter(e.target.value); setOffset(0); }}
                            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white"
                        >
                            <option value="">All Status</option>
                            <option value="success">Success</option>
                            <option value="error">Error</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* Traces Table */}
            <main className="max-w-7xl mx-auto p-6">
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <RefreshCw className="animate-spin text-blue-500" size={32} />
                    </div>
                ) : traces.length === 0 ? (
                    <div className="text-center py-20 text-gray-500">
                        <Zap size={48} className="mx-auto mb-4 opacity-50" />
                        <p>No traces recorded yet. Make some queries to see them here.</p>
                    </div>
                ) : (
                    <div className="space-y-2">
                        {traces.map((trace) => (
                            <div key={trace.trace_id} className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                                {/* Trace Row */}
                                <button
                                    onClick={() => setExpandedTrace(
                                        expandedTrace === trace.trace_id ? null : trace.trace_id
                                    )}
                                    className="w-full px-4 py-3 flex items-center gap-4 hover:bg-gray-750 transition-colors text-left"
                                >
                                    <div className="text-gray-500">
                                        {expandedTrace === trace.trace_id
                                            ? <ChevronDown size={18} />
                                            : <ChevronRight size={18} />}
                                    </div>

                                    <div className={`px-2 py-1 rounded border text-xs font-medium ${getStatusColor(trace.status)}`}>
                                        {trace.status === 'success'
                                            ? <CheckCircle size={12} className="inline mr-1" />
                                            : <XCircle size={12} className="inline mr-1" />}
                                        {trace.status}
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-white truncate">{trace.query}</p>
                                        <p className="text-xs text-gray-500">{formatDate(trace.timestamp)}</p>
                                    </div>

                                    <div className="flex items-center gap-4 text-xs text-gray-400">
                                        <div className="flex items-center gap-1" title="Total Latency">
                                            <Clock size={14} />
                                            {formatDuration(trace.latency.total_ms)}
                                        </div>
                                        <div className="flex items-center gap-1" title="Tokens">
                                            <Hash size={14} />
                                            {trace.tokens.total}
                                        </div>
                                        <div title="Chunks Retrieved" className="text-gray-500">
                                            {trace.chunks.length} chunks
                                        </div>
                                    </div>
                                </button>

                                {/* Expanded Details */}
                                {expandedTrace === trace.trace_id && (
                                    <div className="border-t border-gray-700 bg-gray-900/50">
                                        {/* Latency Breakdown */}
                                        <div className="px-4 py-3 border-b border-gray-700">
                                            <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">Latency Breakdown</h4>
                                            <div className="flex gap-6 text-sm">
                                                <div>
                                                    <span className="text-gray-500">Retrieval:</span>
                                                    <span className="ml-2 text-blue-400">{formatDuration(trace.latency.retrieval_ms)}</span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Generation:</span>
                                                    <span className="ml-2 text-purple-400">{formatDuration(trace.latency.generation_ms)}</span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Total:</span>
                                                    <span className="ml-2 text-green-400">{formatDuration(trace.latency.total_ms)}</span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Query & Response */}
                                        <div className="px-4 py-3 border-b border-gray-700 grid grid-cols-2 gap-4">
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">Query</h4>
                                                <p className="text-sm text-gray-300 bg-gray-800 p-3 rounded-lg">{trace.query}</p>
                                            </div>
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">Response</h4>
                                                <p className="text-sm text-gray-300 bg-gray-800 p-3 rounded-lg max-h-40 overflow-y-auto">{trace.response}</p>
                                            </div>
                                        </div>

                                        {/* Retrieved Chunks */}
                                        <div className="px-4 py-3">
                                            <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                                                Retrieved Chunks ({trace.chunks.length})
                                            </h4>
                                            <div className="space-y-2 max-h-60 overflow-y-auto">
                                                {trace.chunks.map((chunk, i) => (
                                                    <div key={i} className="bg-gray-800 p-3 rounded-lg border border-gray-700">
                                                        <div className="flex justify-between items-start mb-2">
                                                            <span className="text-xs text-gray-500">
                                                                Score: <span className="text-yellow-400">{chunk.score?.toFixed(4) || 'N/A'}</span>
                                                            </span>
                                                            <span className="text-xs text-gray-500">
                                                                Page {chunk.page_number}
                                                            </span>
                                                        </div>
                                                        <p className="text-xs text-gray-400 leading-relaxed">{chunk.text}</p>
                                                        <p className="text-xs text-gray-600 mt-2 truncate">{chunk.file_path}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Error if present */}
                                        {trace.error && (
                                            <div className="px-4 py-3 bg-red-900/20 border-t border-red-700/50">
                                                <h4 className="text-xs font-semibold text-red-400 uppercase mb-1">Error</h4>
                                                <p className="text-sm text-red-300">{trace.error}</p>
                                            </div>
                                        )}

                                        {/* Metadata */}
                                        <div className="px-4 py-3 bg-gray-800/50 text-xs text-gray-500 flex gap-6">
                                            <span>Trace ID: {trace.trace_id}</span>
                                            {trace.user_email && <span>User: {trace.user_email}</span>}
                                            <span>Prompt tokens: {trace.tokens.prompt}</span>
                                            <span>Completion tokens: {trace.tokens.completion}</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}

                        {/* Pagination */}
                        <div className="flex justify-between items-center pt-4">
                            <span className="text-sm text-gray-500">
                                Showing {offset + 1} - {Math.min(offset + traces.length, total)} of {total}
                            </span>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setOffset(Math.max(0, offset - limit))}
                                    disabled={offset === 0}
                                    className="px-4 py-2 bg-gray-700 rounded-lg text-sm disabled:opacity-50 hover:bg-gray-600 transition-colors"
                                >
                                    Previous
                                </button>
                                <button
                                    onClick={() => setOffset(offset + limit)}
                                    disabled={offset + limit >= total}
                                    className="px-4 py-2 bg-gray-700 rounded-lg text-sm disabled:opacity-50 hover:bg-gray-600 transition-colors"
                                >
                                    Next
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
