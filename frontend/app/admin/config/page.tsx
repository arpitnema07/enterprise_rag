'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import {
    CheckCircle, XCircle, Loader2, RefreshCw, Zap, Database,
    HardDrive, Server, AlertTriangle, Save, Settings
} from 'lucide-react';

interface HealthStatus {
    [key: string]: { status: string;[key: string]: any };
}

interface LLMConfig {
    provider: string;
    model: string;
    endpoint: string;
    ollama_model: string;
    nvidia_model: string;
    ollama_base_url: string;
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
    const [llm, setLlm] = useState<LLMConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [reindexing, setReindexing] = useState(false);
    const [reindexResult, setReindexResult] = useState<any>(null);

    // Editable LLM config
    const [editProvider, setEditProvider] = useState('');
    const [editOllamaModel, setEditOllamaModel] = useState('');
    const [editNvidiaModel, setEditNvidiaModel] = useState('');
    const [saving, setSaving] = useState(false);
    const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);

    const fetchHealth = () => {
        setLoading(true);
        Promise.all([
            api.get('/admin/service-health'),
            api.get('/admin/llm-status'),
        ])
            .then(([h, l]) => {
                setHealth(h.data);
                setLlm(l.data);
                setEditProvider(l.data.provider);
                setEditOllamaModel(l.data.ollama_model);
                setEditNvidiaModel(l.data.nvidia_model);
            })
            .catch(console.error)
            .finally(() => setLoading(false));
    };

    useEffect(() => { fetchHealth(); }, []);

    const handleSaveConfig = async () => {
        setSaving(true);
        setSaveMsg(null);
        try {
            const res = await api.put('/admin/llm-config', {
                provider: editProvider,
                ollama_model: editOllamaModel,
                nvidia_model: editNvidiaModel,
            });
            setLlm(res.data);
            setSaveMsg({ ok: true, text: `Switched to ${res.data.provider} — ${res.data.model}` });
        } catch (err: any) {
            setSaveMsg({ ok: false, text: err.response?.data?.detail || 'Failed to update config' });
        }
        setSaving(false);
    };

    const hasChanges = llm && (
        editProvider !== llm.provider ||
        editOllamaModel !== llm.ollama_model ||
        editNvidiaModel !== llm.nvidia_model
    );

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

            {/* LLM Provider Settings */}
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                <Settings className="w-3.5 h-3.5 inline mr-1.5" />
                LLM Provider
            </h2>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6 space-y-4">
                {/* Provider Toggle */}
                <div>
                    <label className="block text-xs text-gray-500 mb-2">Active Provider</label>
                    <div className="flex gap-2">
                        {['ollama', 'nvidia'].map(p => (
                            <button
                                key={p}
                                onClick={() => setEditProvider(p)}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${editProvider === p
                                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                                    }`}
                            >
                                {p === 'ollama' ? '🦙 Ollama (Local)' : '⚡ NVIDIA (Cloud)'}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Model Inputs */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs text-gray-500 mb-1.5">Ollama Model</label>
                        <input
                            type="text"
                            value={editOllamaModel}
                            onChange={e => setEditOllamaModel(e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
                            placeholder="e.g. gemma3:4b"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-gray-500 mb-1.5">NVIDIA Model</label>
                        <input
                            type="text"
                            value={editNvidiaModel}
                            onChange={e => setEditNvidiaModel(e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
                            placeholder="e.g. moonshotai/kimi-k2-instruct"
                        />
                    </div>
                </div>

                {/* Active Config Display */}
                <div className="flex items-center gap-3 bg-gray-800/50 rounded-lg px-3 py-2">
                    <Zap className="w-4 h-4 text-amber-400 shrink-0" />
                    <div className="text-xs">
                        <span className="text-gray-500">Active: </span>
                        <span className="text-gray-300 font-medium">{llm?.provider}</span>
                        <span className="text-gray-600 mx-1">→</span>
                        <span className="text-gray-400">{llm?.model}</span>
                    </div>
                </div>

                {/* Save */}
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleSaveConfig}
                        disabled={!hasChanges || saving}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm text-white disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 transition-all"
                    >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                    {saveMsg && (
                        <span className={`text-xs ${saveMsg.ok ? 'text-emerald-400' : 'text-red-400'}`}>
                            {saveMsg.text}
                        </span>
                    )}
                </div>

                <p className="text-xs text-gray-600">
                    Changes take effect immediately. Vision OCR and embeddings always use Ollama regardless of this setting.
                    Restarting the server resets to .env defaults.
                </p>
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
