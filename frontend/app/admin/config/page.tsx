'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import {
    CheckCircle, XCircle, Loader2, RefreshCw, Zap, Database,
    HardDrive, Server, AlertTriangle
} from 'lucide-react';

interface HealthStatus {
    [key: string]: { status: string;[key: string]: any };
}

interface LLMStatus {
    provider: string;
    model: string;
    base_url?: string;
}

const SERVICE_ICONS: Record<string, any> = {
    postgres: Database,
    redis: Server,
    qdrant: Database,
    minio: HardDrive,
    clickhouse: Database,
    ollama: Zap,
};

export default function ConfigPage() {
    const [health, setHealth] = useState<HealthStatus>({});
    const [llm, setLlm] = useState<LLMStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [reindexing, setReindexing] = useState(false);
    const [reindexResult, setReindexResult] = useState<any>(null);

    const fetchHealth = () => {
        setLoading(true);
        Promise.all([
            api.get('/admin/service-health'),
            api.get('/admin/llm-status'),
        ])
            .then(([h, l]) => {
                setHealth(h.data);
                setLlm(l.data);
            })
            .catch(console.error)
            .finally(() => setLoading(false));
    };

    useEffect(() => { fetchHealth(); }, []);

    const handleReindex = async () => {
        if (!confirm('This will re-process all documents. Proceed?')) return;
        setReindexing(true);
        setReindexResult(null);
        try {
            const res = await api.post('/admin/reindex?confirm=true');
            setReindexResult(res.data);
        } catch (err: any) {
            setReindexResult({ error: err.response?.data?.detail || 'Reindex failed' });
        }
        setReindexing(false);
    };

    if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>;

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-xl font-bold text-gray-100">Configuration</h1>
                <button onClick={fetchHealth} className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400" title="Refresh">
                    <RefreshCw className="w-4 h-4" />
                </button>
            </div>

            {/* LLM Provider */}
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">LLM Provider</h2>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
                {llm ? (
                    <div className="flex items-center gap-4">
                        <Zap className="w-5 h-5 text-amber-400" />
                        <div>
                            <p className="text-sm font-medium text-gray-200">{llm.provider}</p>
                            <p className="text-xs text-gray-500">{llm.model}</p>
                            {llm.base_url && <p className="text-xs text-gray-600">{llm.base_url}</p>}
                        </div>
                    </div>
                ) : (
                    <p className="text-sm text-gray-500">Unable to fetch LLM status</p>
                )}
            </div>

            {/* Service Health */}
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Service Health</h2>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
                {Object.entries(health).map(([name, svc]) => {
                    const Icon = SERVICE_ICONS[name] || Server;
                    const isOk = svc.status === 'ok';
                    return (
                        <div key={name} className={`bg-gray-900 border rounded-xl p-4 ${isOk ? 'border-gray-800' : 'border-red-800/50'}`}>
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <Icon className="w-4 h-4 text-gray-500" />
                                    <span className="text-sm font-medium text-gray-200 capitalize">{name}</span>
                                </div>
                                {isOk
                                    ? <CheckCircle className="w-4 h-4 text-emerald-400" />
                                    : <XCircle className="w-4 h-4 text-red-400" />
                                }
                            </div>
                            {svc.detail && (
                                <p className="text-xs text-red-400/70 truncate">{svc.detail}</p>
                            )}
                            {svc.points !== undefined && (
                                <p className="text-xs text-gray-500">Vectors: {svc.points.toLocaleString()}</p>
                            )}
                            {svc.models !== undefined && (
                                <p className="text-xs text-gray-500">Models: {svc.models}</p>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Reindex */}
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Re-Index</h2>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-sm text-gray-300">Re-process all documents through the RAG pipeline</p>
                        <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3 text-yellow-500" />
                            This will recreate all embeddings. Search may be temporarily unavailable.
                        </p>
                    </div>
                    <button onClick={handleReindex} disabled={reindexing}
                        className="px-4 py-2 bg-red-600/80 hover:bg-red-600 rounded-lg text-sm text-white disabled:opacity-50 flex items-center gap-2">
                        {reindexing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                        {reindexing ? 'Re-indexing...' : 'Re-index All'}
                    </button>
                </div>
                {reindexResult && (
                    <div className={`mt-3 p-3 rounded-lg text-sm ${reindexResult.error ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                        {reindexResult.error
                            ? reindexResult.error
                            : `${reindexResult.message} — ${reindexResult.processed} processed, ${reindexResult.failed} failed`
                        }
                    </div>
                )}
            </div>
        </div>
    );
}
