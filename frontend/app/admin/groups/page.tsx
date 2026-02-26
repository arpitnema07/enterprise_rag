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

    if (loading) return <div className="flex items-center justify-center py-20 bg-zinc-900/20 rounded-2xl border border-zinc-800/50"><Loader2 className="w-8 h-8 animate-spin text-blue-500/60" /></div>;

    return (
        <div className="animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-8">
                <h1 className="text-2xl font-bold bg-gradient-to-br from-zinc-100 to-zinc-500 bg-clip-text text-transparent">Groups</h1>
                <button onClick={() => setShowCreate(!showCreate)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-xl text-sm font-medium text-white shadow-sm shadow-blue-900/20 transition-all hover:scale-[1.02]">
                    <Plus className="w-[18px] h-[18px]" /> New Group
                </button>
            </div>

            {/* Create group form */}
            {showCreate && (
                <div className="bg-zinc-900/80 backdrop-blur-md border border-zinc-700/50 rounded-2xl p-5 mb-8 shadow-lg shadow-black/10 animate-in slide-in-from-top-4 duration-300">
                    <h3 className="text-sm font-semibold text-zinc-300 mb-3">Create New Document Group</h3>
                    <div className="flex flex-col sm:flex-row items-center gap-3">
                        <input value={newGroupName} onChange={e => setNewGroupName(e.target.value)}
                            placeholder="Engineering Dept..." className="flex-1 w-full bg-zinc-950/50 border border-zinc-700/50 rounded-xl px-4 py-2.5 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all" />
                        <select value={newGroupPrompt} onChange={e => setNewGroupPrompt(e.target.value)}
                            className="w-full sm:w-auto bg-zinc-950/50 border border-zinc-700/50 rounded-xl px-4 py-2.5 text-sm text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition-all">
                            <option value="technical">Technical</option>
                            <option value="compliance">Compliance</option>
                            <option value="general">General</option>
                        </select>
                        <div className="flex w-full sm:w-auto gap-2">
                            <button onClick={handleCreateGroup} className="flex-1 sm:flex-none px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-sm font-medium text-white transition-all shadow-sm shadow-emerald-900/20">Create</button>
                            <button onClick={() => setShowCreate(false)} className="p-2.5 hover:bg-zinc-800 rounded-xl text-zinc-400 border border-transparent hover:border-zinc-700/50 transition-all"><X className="w-5 h-5" /></button>
                        </div>
                    </div>
                </div>
            )}

            {/* Groups list */}
            {groups.length === 0 ? (
                <div className="text-center py-20 bg-zinc-900/20 rounded-2xl border border-zinc-800/50 flex flex-col items-center justify-center">
                    <div className="bg-zinc-800/50 p-6 rounded-full mb-4">
                        <FolderOpen className="w-10 h-10 text-zinc-600" />
                    </div>
                    <p className="text-zinc-400 font-medium">No groups found. Create one to organize documents.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {groups.map(group => (
                        <div key={group.id} className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-800/60 rounded-2xl overflow-hidden shadow-sm hover:border-zinc-700/50 transition-all group/card flex flex-col">
                            <button onClick={() => toggleGroup(group.id)}
                                className="w-full flex flex-col items-start p-5 text-left hover:bg-zinc-800/30 transition-colors">
                                <div className="flex items-center gap-3 mb-3 w-full">
                                    <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400 border border-amber-500/20">
                                        <FolderOpen className="w-5 h-5" />
                                    </div>
                                    <span className="font-semibold text-zinc-200 text-lg flex-1 truncate">{group.name}</span>
                                </div>
                                <div className="flex items-center justify-between w-full">
                                    <span className="text-[10px] font-medium uppercase tracking-wider px-2.5 py-1 rounded-full bg-zinc-950 border border-zinc-800/80 text-zinc-500">{group.prompt_type}</span>
                                    <span className="text-[11px] text-zinc-500 font-mono">
                                        {new Date(group.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                    </span>
                                </div>
                            </button>

                            {expandedGroup === group.id && (
                                <div className="border-t border-zinc-800/60 bg-zinc-950/30 p-4 flex-1 animate-in slide-in-from-top-2 duration-200">
                                    <div className="flex items-center gap-2 mb-4">
                                        <input value={assignEmail} onChange={e => setAssignEmail(e.target.value)}
                                            placeholder="User email..." className="flex-1 min-w-0 bg-zinc-900 border border-zinc-700/50 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500/50" />
                                        <button onClick={() => handleAssignUser(group.id)}
                                            className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700/50 rounded-lg text-xs font-medium text-zinc-200 transition-colors">
                                            <UserPlus className="w-3.5 h-3.5 text-blue-400" /> Add
                                        </button>
                                    </div>

                                    <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2 flex items-center gap-1.5"><Users size={12} /> Members</h4>

                                    {(groupUsers[group.id] || []).length === 0 ? (
                                        <p className="text-xs text-zinc-600 italic bg-zinc-900/50 p-2 rounded-lg border border-zinc-800/50">No users assigned.</p>
                                    ) : (
                                        <div className="space-y-1.5 max-h-[150px] overflow-y-auto custom-scrollbar pr-1">
                                            {(groupUsers[group.id] || []).map(u => (
                                                <div key={u.id} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-zinc-900 border border-zinc-800/50 hover:border-zinc-700/50 transition-colors group/item">
                                                    <span className="text-xs text-zinc-300 font-medium truncate pr-2">{u.email}</span>
                                                    <button onClick={() => handleRemoveUser(group.id, u.id)} className="p-1 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors opacity-0 group-hover/item:opacity-100" title="Remove User">
                                                        <X className="w-3.5 h-3.5" />
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
            )}
        </div>
    );
}
