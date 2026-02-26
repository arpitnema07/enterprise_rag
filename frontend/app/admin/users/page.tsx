'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { Shield, ShieldOff, Trash2, Loader2, UserPlus } from 'lucide-react';

interface User {
    id: number;
    email: string;
    is_admin: boolean;
    is_active: boolean;
    created_at: string;
}

export default function UsersPage() {
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchUsers = () => {
        api.get('/admin/users').then(r => setUsers(r.data)).catch(console.error).finally(() => setLoading(false));
    };

    useEffect(() => { fetchUsers(); }, []);

    const handleToggleAdmin = async (userId: number) => {
        await api.put(`/admin/users/${userId}/toggle-admin`);
        fetchUsers();
    };

    const handleDelete = async (userId: number) => {
        if (!confirm('Delete this user? This cannot be undone.')) return;
        try {
            await api.delete(`/admin/users/${userId}`);
            fetchUsers();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to delete user');
        }
    };

    if (loading) return <div className="flex items-center justify-center py-20 bg-zinc-900/20 rounded-2xl border border-zinc-800/50"><Loader2 className="w-8 h-8 animate-spin text-blue-500/60" /></div>;

    return (
        <div className="animate-in fade-in duration-500">
            <h1 className="text-2xl font-bold bg-gradient-to-br from-zinc-100 to-zinc-500 bg-clip-text text-transparent mb-6">Users</h1>

            <div className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-800/60 rounded-2xl overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-zinc-800/60 bg-zinc-900 text-zinc-500 text-[10px] font-semibold uppercase tracking-wider">
                                <th className="text-left px-5 py-4">Email</th>
                                <th className="text-left px-5 py-4">Role</th>
                                <th className="text-left px-5 py-4">Joined</th>
                                <th className="text-right px-5 py-4">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-800/40">
                            {users.map(user => (
                                <tr key={user.id} className="hover:bg-zinc-800/30 transition-colors group">
                                    <td className="px-5 py-4 text-zinc-200 font-medium">{user.email}</td>
                                    <td className="px-5 py-4">
                                        {user.is_admin ? (
                                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border bg-zinc-950/50 border-blue-500/20 text-blue-400">
                                                <Shield className="w-3.5 h-3.5" /> Admin
                                            </span>
                                        ) : (
                                            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border bg-zinc-950/50 border-zinc-700/50 text-zinc-400">
                                                User
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-5 py-4 text-zinc-500 text-xs font-mono">
                                        {new Date(user.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                    </td>
                                    <td className="px-5 py-4 text-right">
                                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button onClick={() => handleToggleAdmin(user.id)}
                                                className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-blue-400 transition-colors" title={user.is_admin ? 'Remove admin role' : 'Make admin'}>
                                                {user.is_admin ? <ShieldOff className="w-[18px] h-[18px]" /> : <Shield className="w-[18px] h-[18px]" />}
                                            </button>
                                            <button onClick={() => handleDelete(user.id)}
                                                className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-red-400 transition-colors" title="Delete User">
                                                <Trash2 className="w-[18px] h-[18px]" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
