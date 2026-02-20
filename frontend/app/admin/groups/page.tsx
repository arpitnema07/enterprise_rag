'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { FolderOpen, Users, Trash2, UserPlus, X, Loader2, Plus } from 'lucide-react';

interface Group {
    id: number;
    name: string;
    prompt_type: string;
    created_at: string;
}

interface User {
    id: number;
    email: string;
    is_admin: boolean;
}

export default function GroupsPage() {
    const [groups, setGroups] = useState<Group[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedGroup, setExpandedGroup] = useState<number | null>(null);
    const [groupUsers, setGroupUsers] = useState<Record<number, User[]>>({});
    const [assignEmail, setAssignEmail] = useState('');
    const [newGroupName, setNewGroupName] = useState('');
    const [newGroupPrompt, setNewGroupPrompt] = useState('technical');
    const [showCreate, setShowCreate] = useState(false);

    const fetchGroups = () => {
        api.get('/groups').then(r => setGroups(r.data)).catch(console.error).finally(() => setLoading(false));
    };

    useEffect(() => { fetchGroups(); }, []);

    const toggleGroup = async (groupId: number) => {
        if (expandedGroup === groupId) { setExpandedGroup(null); return; }
        setExpandedGroup(groupId);
        if (!groupUsers[groupId]) {
            const res = await api.get(`/admin/groups/${groupId}/users`);
            setGroupUsers(prev => ({ ...prev, [groupId]: res.data }));
        }
    };

    const handleAssignUser = async (groupId: number) => {
        if (!assignEmail.trim()) return;
        try {
            await api.post(`/admin/groups/${groupId}/assign-user?user_email=${assignEmail}`);
            setAssignEmail('');
            const res = await api.get(`/admin/groups/${groupId}/users`);
            setGroupUsers(prev => ({ ...prev, [groupId]: res.data }));
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed');
        }
    };

    const handleRemoveUser = async (groupId: number, userId: number) => {
        await api.delete(`/admin/groups/${groupId}/users/${userId}`);
        const res = await api.get(`/admin/groups/${groupId}/users`);
        setGroupUsers(prev => ({ ...prev, [groupId]: res.data }));
    };

    const handleCreateGroup = async () => {
        if (!newGroupName.trim()) return;
        try {
            await api.post('/groups', { name: newGroupName, prompt_type: newGroupPrompt });
            setNewGroupName('');
            setShowCreate(false);
            fetchGroups();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed');
        }
    };

    if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>;

    return (
        <div>
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-xl font-bold text-gray-100">Groups</h1>
                <button onClick={() => setShowCreate(!showCreate)}
                    className="flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm text-white">
                    <Plus className="w-4 h-4" /> New Group
                </button>
            </div>

            {/* Create group form */}
            {showCreate && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
                    <div className="flex items-center gap-3">
                        <input value={newGroupName} onChange={e => setNewGroupName(e.target.value)}
                            placeholder="Group name..." className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200" />
                        <select value={newGroupPrompt} onChange={e => setNewGroupPrompt(e.target.value)}
                            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300">
                            <option value="technical">Technical</option>
                            <option value="compliance">Compliance</option>
                            <option value="general">General</option>
                        </select>
                        <button onClick={handleCreateGroup} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm text-white">Create</button>
                        <button onClick={() => setShowCreate(false)} className="p-2 hover:bg-gray-800 rounded-lg text-gray-400"><X className="w-4 h-4" /></button>
                    </div>
                </div>
            )}

            {/* Groups list */}
            <div className="space-y-3">
                {groups.map(group => (
                    <div key={group.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                        <button onClick={() => toggleGroup(group.id)}
                            className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800/50 text-left">
                            <div className="flex items-center gap-3">
                                <FolderOpen className="w-4 h-4 text-amber-400" />
                                <span className="font-medium text-gray-200">{group.name}</span>
                                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400">{group.prompt_type}</span>
                            </div>
                            <span className="text-xs text-gray-500">
                                {new Date(group.created_at).toLocaleDateString()}
                            </span>
                        </button>

                        {expandedGroup === group.id && (
                            <div className="border-t border-gray-800 px-4 py-3">
                                <div className="flex items-center gap-2 mb-3">
                                    <input value={assignEmail} onChange={e => setAssignEmail(e.target.value)}
                                        placeholder="user@email.com" className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-200" />
                                    <button onClick={() => handleAssignUser(group.id)}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm text-white">
                                        <UserPlus className="w-3.5 h-3.5" /> Add
                                    </button>
                                </div>
                                {(groupUsers[group.id] || []).length === 0 ? (
                                    <p className="text-xs text-gray-500">No members yet.</p>
                                ) : (
                                    <div className="space-y-1">
                                        {(groupUsers[group.id] || []).map(u => (
                                            <div key={u.id} className="flex items-center justify-between py-1 px-2 rounded hover:bg-gray-800/50">
                                                <span className="text-sm text-gray-300">{u.email}</span>
                                                <button onClick={() => handleRemoveUser(group.id, u.id)} className="p-1 text-red-400 hover:bg-gray-700 rounded">
                                                    <X className="w-3 h-3" />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
