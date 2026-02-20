'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { FileText, Users, FolderOpen, Database, HardDrive, Clock, AlertTriangle, Loader2 } from 'lucide-react';

interface Stats {
    documents: number;
    total_chunks: number;
    users: number;
    groups: number;
    queue: { pending: number; processing: number; failed: number };
    storage: { total_objects?: number; total_size_mb?: number };
}

function StatCard({ icon: Icon, label, value, sub, color }: {
    icon: any; label: string; value: string | number; sub?: string; color: string;
}) {
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
                <div className={`p-2 rounded-lg ${color}`}>
                    <Icon className="w-4 h-4" />
                </div>
                <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
            </div>
            <p className="text-2xl font-bold text-gray-100">{value}</p>
            {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
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
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
            </div>
        );
    }

    if (!stats) return <p className="text-gray-500">Failed to load stats.</p>;

    return (
        <div>
            <h1 className="text-xl font-bold text-gray-100 mb-6">Dashboard</h1>

            {/* Main stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                <StatCard icon={FileText} label="Documents" value={stats.documents} color="bg-blue-500/10 text-blue-400" />
                <StatCard icon={Database} label="Chunks" value={stats.total_chunks.toLocaleString()} color="bg-purple-500/10 text-purple-400" />
                <StatCard icon={Users} label="Users" value={stats.users} color="bg-emerald-500/10 text-emerald-400" />
                <StatCard icon={FolderOpen} label="Groups" value={stats.groups} color="bg-amber-500/10 text-amber-400" />
            </div>

            {/* Processing Queue */}
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Processing Queue</h2>
            <div className="grid grid-cols-3 gap-4 mb-8">
                <StatCard icon={Clock} label="Pending" value={stats.queue.pending} color="bg-yellow-500/10 text-yellow-400" />
                <StatCard icon={Loader2} label="Processing" value={stats.queue.processing} color="bg-blue-500/10 text-blue-400" />
                <StatCard icon={AlertTriangle} label="Failed" value={stats.queue.failed} color="bg-red-500/10 text-red-400" />
            </div>

            {/* Storage */}
            {stats.storage && stats.storage.total_objects !== undefined && (
                <>
                    <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Storage (MinIO)</h2>
                    <div className="grid grid-cols-2 gap-4">
                        <StatCard icon={HardDrive} label="Objects" value={stats.storage.total_objects || 0} color="bg-teal-500/10 text-teal-400" />
                        <StatCard
                            icon={HardDrive} label="Size"
                            value={`${(stats.storage.total_size_mb || 0).toFixed(1)} MB`}
                            color="bg-teal-500/10 text-teal-400"
                        />
                    </div>
                </>
            )}
        </div>
    );
}
