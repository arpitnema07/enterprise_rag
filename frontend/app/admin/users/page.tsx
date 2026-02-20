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

    if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>;

    return (
        <div>
            <h1 className="text-xl font-bold text-gray-100 mb-6">Users</h1>

            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                            <th className="text-left px-4 py-3">Email</th>
                            <th className="text-left px-4 py-3">Role</th>
                            <th className="text-left px-4 py-3">Joined</th>
                            <th className="text-right px-4 py-3">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => (
                            <tr key={user.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                                <td className="px-4 py-3 text-gray-200">{user.email}</td>
                                <td className="px-4 py-3">
                                    {user.is_admin ? (
                                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                                            <Shield className="w-3 h-3" /> Admin
                                        </span>
                                    ) : (
                                        <span className="text-xs text-gray-500">User</span>
                                    )}
                                </td>
                                <td className="px-4 py-3 text-gray-500 text-xs">
                                    {new Date(user.created_at).toLocaleDateString()}
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <div className="flex items-center justify-end gap-1">
                                        <button onClick={() => handleToggleAdmin(user.id)}
                                            className="p-1.5 rounded hover:bg-gray-700 text-gray-400" title={user.is_admin ? 'Remove admin' : 'Make admin'}>
                                            {user.is_admin ? <ShieldOff className="w-3.5 h-3.5" /> : <Shield className="w-3.5 h-3.5" />}
                                        </button>
                                        <button onClick={() => handleDelete(user.id)}
                                            className="p-1.5 rounded hover:bg-gray-700 text-red-400" title="Delete">
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
