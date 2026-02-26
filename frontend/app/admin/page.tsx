'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { FileText, Users, FolderOpen, Database, HardDrive, Clock, AlertTriangle, Loader2, MessageSquare, Zap, AlertCircle, Activity } from 'lucide-react';

interface Stats {
    documents: number;
    total_chunks: number;
    users: number;
    groups: number;
    queue: { pending: number; processing: number; failed: number };
    storage: { total_objects?: number; total_size_mb?: number };
    queries_24h?: { count: number; avg_latency_ms: number; errors: number };
}

function StatCard({ icon: Icon, label, value, sub, color }: {
    icon: any; label: string; value: string | number; sub?: string; color: string;
}) {
    return (
        <div className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-800/50 rounded-2xl p-5 shadow-sm transition-all hover:bg-zinc-900/80 hover:border-zinc-700/50">
            <div className="flex items-center gap-3 mb-4">
                <div className={`p-2.5 rounded-xl ${color}`}>
                    <Icon className="w-[18px] h-[18px]" />
                </div>
                <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">{label}</span>
            </div>
            <p className="text-3xl font-bold text-zinc-100 tracking-tight">{value}</p>
            {sub && <p className="text-xs font-medium text-zinc-500 mt-2">{sub}</p>}
        </div>
    );
}

export default function StatsPage() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.get('/admin/stats')
            .then(res => setStats(res.data))
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-[60vh]">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500/80" />
            </div>
        );
    }

    if (!stats) return <p className="text-zinc-500 border border-red-500/20 bg-red-500/10 p-4 rounded-xl max-w-md my-8">Failed to load system statistics.</p>;

    return (
        <div className="space-y-10 animate-in fade-in duration-500">
            <div>
                <h1 className="text-2xl font-bold bg-gradient-to-br from-zinc-100 to-zinc-500 bg-clip-text text-transparent mb-1">System Dashboard</h1>
                <p className="text-sm text-zinc-400 mb-6">Overview of current RAG instance metrics and capacity.</p>

                {/* Main stats */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
                    <StatCard icon={FileText} label="Documents" value={stats.documents || 0} color="bg-blue-500/10 text-blue-400 border border-blue-500/20" />
                    <StatCard icon={Database} label="Chunks" value={(stats.total_chunks || 0).toLocaleString()} color="bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" />
                    <StatCard icon={Users} label="Users" value={stats.users || 0} color="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" />
                    <StatCard icon={FolderOpen} label="Groups" value={stats.groups || 0} color="bg-amber-500/10 text-amber-400 border border-amber-500/20" />
                </div>
            </div>

            {/* Processing Queue */}
            <div>
                <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <Activity size={14} className="text-zinc-600" /> Processing Queue
                </h2>
                <div className="grid grid-cols-3 gap-5">
                    <StatCard icon={Clock} label="Pending" value={stats.queue.pending} color="bg-yellow-500/10 text-yellow-400 border border-yellow-500/20" />
                    <StatCard icon={Loader2} label="Processing" value={stats.queue.processing} color="bg-blue-500/10 text-blue-400 border border-blue-500/20" />
                    <StatCard icon={AlertTriangle} label="Failed" value={stats.queue.failed} color="bg-red-500/10 text-red-400 border border-red-500/20" />
                </div>
            </div>

            {/* Query Analytics */}
            {stats.queries_24h && (
                <div>
                    <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                        <MessageSquare size={14} className="text-zinc-600" /> Query Analytics (24h)
                    </h2>
                    <div className="grid grid-cols-3 gap-5">
                        <StatCard icon={MessageSquare} label="Queries" value={stats.queries_24h.count} color="bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" />
                        <StatCard icon={Zap} label="Avg Latency" value={`${Math.round(stats.queries_24h.avg_latency_ms)} ms`} color="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" />
                        <StatCard icon={AlertCircle} label="Errors" value={stats.queries_24h.errors} color="bg-rose-500/10 text-rose-400 border border-rose-500/20" />
                    </div>
                </div>
            )}

            {/* Storage */}
            {stats.storage && stats.storage.total_objects !== undefined && (
                <div>
                    <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                        <HardDrive size={14} className="text-zinc-600" /> Storage (MinIO)
                    </h2>
                    <div className="grid grid-cols-2 gap-5 max-w-2xl">
                        <StatCard icon={HardDrive} label="Objects" value={stats.storage.total_objects || 0} color="bg-teal-500/10 text-teal-400 border border-teal-500/20" />
                        <StatCard
                            icon={HardDrive} label="Size"
                            value={`${(stats.storage.total_size_mb || 0).toFixed(1)} MB`}
                            color="bg-teal-500/10 text-teal-400 border border-teal-500/20"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
