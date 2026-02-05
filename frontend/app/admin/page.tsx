'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { LogOut, Trash2, Users, FileText, FolderOpen, Shield, ShieldOff, UserPlus, ArrowLeft, X, Zap, RefreshCw } from 'lucide-react';

interface User {
    id: number;
    email: string;
    is_admin: boolean;
    is_active: boolean;
    created_at: string;
}

interface Group {
    id: number;
    name: string;
}

interface Document {
    id: number;
    filename: string;
    file_path: string;
    group_id: number;
    upload_date: string;
}

type Tab = 'groups' | 'users' | 'documents';

export default function AdminPage() {
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [activeTab, setActiveTab] = useState<Tab>('groups');
    const [groups, setGroups] = useState<Group[]>([]);
    const [users, setUsers] = useState<User[]>([]);
    const [documents, setDocuments] = useState<Document[]>([]);
    const [expandedGroup, setExpandedGroup] = useState<number | null>(null);
    const [groupDocs, setGroupDocs] = useState<Record<number, Document[]>>({});
    const [groupUsers, setGroupUsers] = useState<Record<number, User[]>>({});
    const [assignModal, setAssignModal] = useState<{ groupId: number; groupName: string } | null>(null);
    const [assignEmail, setAssignEmail] = useState('');
    const [isReindexing, setIsReindexing] = useState(false);
    const router = useRouter();

    useEffect(() => {
        const fetchData = async () => {
            try {
                const userRes = await api.get('/auth/me');
                if (!userRes.data.is_admin) {
                    router.push('/dashboard');
                    return;
                }
                setCurrentUser(userRes.data);

                const [groupsRes, usersRes, docsRes] = await Promise.all([
                    api.get('/groups'),
                    api.get('/admin/users'),
                    api.get('/admin/documents')
                ]);
                setGroups(groupsRes.data);
                setUsers(usersRes.data);
                setDocuments(docsRes.data);
            } catch (err) {
                console.error(err);
                router.push('/login');
            }
        };
        fetchData();
    }, [router]);

    const handleLogout = () => {
        localStorage.removeItem('token');
        router.push('/login');
    };

    const handleReindex = async () => {
        // First, get stats
        try {
            const statsRes = await api.post('/admin/reindex');
            const count = statsRes.data.documents_to_reindex || 0;

            if (!confirm(`This will clear all embeddings and re-process ${count} documents. This may take several minutes. Continue?`)) {
                return;
            }

            setIsReindexing(true);
            const res = await api.post('/admin/reindex?confirm=true');
            alert(`Re-indexing complete!\nProcessed: ${res.data.processed}\nFailed: ${res.data.failed}`);
        } catch (err: any) {
            console.error(err);
            alert(err.response?.data?.detail || 'Re-indexing failed');
        } finally {
            setIsReindexing(false);
        }
    };

    const toggleGroup = async (groupId: number) => {
        if (expandedGroup === groupId) {
            setExpandedGroup(null);
            return;
        }
        setExpandedGroup(groupId);
        try {
            const [docsRes, usersRes] = await Promise.all([
                api.get(`/admin/groups/${groupId}/documents`),
                api.get(`/admin/groups/${groupId}/users`)
            ]);
            setGroupDocs(prev => ({ ...prev, [groupId]: docsRes.data }));
            setGroupUsers(prev => ({ ...prev, [groupId]: usersRes.data }));
        } catch (err) {
            console.error(err);
        }
    };

    const handleDeleteDocument = async (docId: number) => {
        if (!confirm('Delete this document?')) return;
        try {
            await api.delete(`/admin/documents/${docId}`);
            setDocuments(prev => prev.filter(d => d.id !== docId));
            // Also remove from groupDocs
            Object.keys(groupDocs).forEach(gid => {
                setGroupDocs(prev => ({
                    ...prev,
                    [Number(gid)]: prev[Number(gid)]?.filter(d => d.id !== docId) || []
                }));
            });
        } catch (err) {
            console.error(err);
            alert('Failed to delete document');
        }
    };

    const handleDeleteUser = async (userId: number) => {
        if (!confirm('Delete this user?')) return;
        try {
            await api.delete(`/admin/users/${userId}`);
            setUsers(prev => prev.filter(u => u.id !== userId));
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to delete user');
        }
    };

    const handleToggleAdmin = async (userId: number) => {
        try {
            await api.put(`/admin/users/${userId}/toggle-admin`);
            setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_admin: !u.is_admin } : u));
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to toggle admin');
        }
    };

    const handleRemoveUserFromGroup = async (groupId: number, userId: number) => {
        if (!confirm('Remove user from group?')) return;
        try {
            await api.delete(`/admin/groups/${groupId}/users/${userId}`);
            setGroupUsers(prev => ({
                ...prev,
                [groupId]: prev[groupId]?.filter(u => u.id !== userId) || []
            }));
        } catch (err) {
            console.error(err);
            alert('Failed to remove user');
        }
    };

    const handleAssignUser = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!assignModal || !assignEmail.trim()) return;
        try {
            await api.post(`/admin/groups/${assignModal.groupId}/assign-user?user_email=${encodeURIComponent(assignEmail)}`);
            setAssignEmail('');
            setAssignModal(null);
            // Refresh group users
            const usersRes = await api.get(`/admin/groups/${assignModal.groupId}/users`);
            setGroupUsers(prev => ({ ...prev, [assignModal.groupId]: usersRes.data }));
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to assign user');
        }
    };

    const getGroupName = (groupId: number) => groups.find(g => g.id === groupId)?.name || `Group ${groupId}`;

    const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
        { key: 'groups', label: 'Groups', icon: <FolderOpen size={18} /> },
        { key: 'users', label: 'Users', icon: <Users size={18} /> },
        { key: 'documents', label: 'Documents', icon: <FileText size={18} /> },
    ];

    return (
        <div className="flex flex-col min-h-screen bg-gray-100">
            {/* Header */}
            <header className="bg-white shadow-sm px-6 py-4 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <button onClick={() => router.push('/dashboard')} className="text-gray-500 hover:text-gray-700">
                        <ArrowLeft size={20} />
                    </button>
                    <h1 className="text-xl font-bold text-gray-800">Admin Panel</h1>
                </div>
                <div className="flex items-center gap-4">
                    <button
                        onClick={handleReindex}
                        disabled={isReindexing}
                        className="flex items-center gap-2 px-3 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors text-sm disabled:opacity-50"
                        title="Clear and rebuild all embeddings"
                    >
                        <RefreshCw size={16} className={isReindexing ? 'animate-spin' : ''} />
                        {isReindexing ? 'Re-indexing...' : 'Re-Index All'}
                    </button>
                    <button
                        onClick={() => router.push('/admin/traces')}
                        className="flex items-center gap-2 px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm"
                    >
                        <Zap size={16} /> Traces
                    </button>
                    <button
                        onClick={() => router.push('/admin/logs')}
                        className="flex items-center gap-2 px-3 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-sm"
                    >
                        <Zap size={16} /> Live Logs
                    </button>
                    <span className="text-gray-600">{currentUser?.email}</span>
                    <button onClick={handleLogout} className="p-2 text-gray-500 hover:text-red-600">
                        <LogOut size={20} />
                    </button>
                </div>
            </header>

            {/* Tabs */}
            <div className="bg-white border-b border-gray-200">
                <div className="max-w-6xl mx-auto px-6">
                    <nav className="flex gap-1">
                        {tabs.map(tab => (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className={`flex items-center gap-2 px-4 py-3 border-b-2 font-medium text-sm transition-colors ${activeTab === tab.key
                                    ? 'border-blue-600 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                {tab.icon} {tab.label}
                            </button>
                        ))}
                    </nav>
                </div>
            </div>

            {/* Content */}
            <main className="flex-1 p-6 max-w-6xl mx-auto w-full">
                {/* GROUPS TAB */}
                {activeTab === 'groups' && (
                    <div className="space-y-4">
                        {groups.length === 0 ? (
                            <p className="text-gray-500">No groups yet.</p>
                        ) : (
                            groups.map(group => (
                                <div key={group.id} className="bg-white rounded-lg shadow-sm border border-gray-200">
                                    <button
                                        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50"
                                        onClick={() => toggleGroup(group.id)}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="font-semibold text-gray-800">{group.name}</span>
                                            <span className={`px-2 py-0.5 text-xs rounded-full ${group.prompt_type === 'technical' ? 'bg-blue-100 text-blue-700' :
                                                    group.prompt_type === 'compliance' ? 'bg-green-100 text-green-700' :
                                                        'bg-gray-100 text-gray-700'
                                                }`}>
                                                {group.prompt_type || 'technical'}
                                            </span>
                                        </div>
                                        <span className="text-xs text-gray-400">ID: {group.id}</span>
                                    </button>

                                    {expandedGroup === group.id && (
                                        <div className="px-4 pb-4 border-t border-gray-100 grid grid-cols-2 gap-6">
                                            {/* Documents */}
                                            <div className="mt-4">
                                                <h4 className="text-sm font-semibold text-gray-500 uppercase flex items-center gap-2 mb-2">
                                                    <FileText size={16} /> Documents ({groupDocs[group.id]?.length || 0})
                                                </h4>
                                                {groupDocs[group.id]?.length === 0 ? (
                                                    <p className="text-gray-400 text-sm">No documents.</p>
                                                ) : (
                                                    <ul className="space-y-2">
                                                        {groupDocs[group.id]?.map(doc => (
                                                            <li key={doc.id} className="flex items-center justify-between text-sm text-gray-700 bg-gray-50 p-2 rounded">
                                                                <span className="truncate max-w-xs">{doc.filename}</span>
                                                                <button onClick={() => handleDeleteDocument(doc.id)} className="text-red-500 hover:text-red-700">
                                                                    <Trash2 size={14} />
                                                                </button>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                )}
                                            </div>

                                            {/* Users */}
                                            <div className="mt-4">
                                                <h4 className="text-sm font-semibold text-gray-500 uppercase flex items-center gap-2 mb-2">
                                                    <Users size={16} /> Members ({groupUsers[group.id]?.length || 0})
                                                </h4>
                                                {groupUsers[group.id]?.length === 0 ? (
                                                    <p className="text-gray-400 text-sm">No users assigned.</p>
                                                ) : (
                                                    <ul className="space-y-2">
                                                        {groupUsers[group.id]?.map(u => (
                                                            <li key={u.id} className="flex items-center justify-between text-sm text-gray-700 bg-gray-50 p-2 rounded">
                                                                <span>{u.email}</span>
                                                                <button onClick={() => handleRemoveUserFromGroup(group.id, u.id)} className="text-red-500 hover:text-red-700">
                                                                    <X size={14} />
                                                                </button>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                )}
                                                <button
                                                    onClick={() => setAssignModal({ groupId: group.id, groupName: group.name })}
                                                    className="mt-2 flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm"
                                                >
                                                    <UserPlus size={14} /> Add User
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                )}

                {/* USERS TAB */}
                {activeTab === 'users' && (
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                        <table className="w-full">
                            <thead className="bg-gray-50 border-b border-gray-200">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Email</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Admin</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Status</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {users.map(u => (
                                    <tr key={u.id} className="hover:bg-gray-50">
                                        <td className="px-4 py-3 text-sm text-gray-800">{u.email}</td>
                                        <td className="px-4 py-3">
                                            {u.is_admin ? (
                                                <span className="inline-flex items-center gap-1 text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
                                                    <Shield size={12} /> Admin
                                                </span>
                                            ) : (
                                                <span className="text-xs text-gray-400">User</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`text-xs px-2 py-1 rounded-full ${u.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                                {u.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right space-x-2">
                                            <button
                                                onClick={() => handleToggleAdmin(u.id)}
                                                className="text-gray-500 hover:text-blue-600"
                                                title={u.is_admin ? 'Remove Admin' : 'Make Admin'}
                                            >
                                                {u.is_admin ? <ShieldOff size={16} /> : <Shield size={16} />}
                                            </button>
                                            <button
                                                onClick={() => handleDeleteUser(u.id)}
                                                className="text-gray-500 hover:text-red-600"
                                                title="Delete User"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* DOCUMENTS TAB */}
                {activeTab === 'documents' && (
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                        <table className="w-full">
                            <thead className="bg-gray-50 border-b border-gray-200">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Filename</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Group</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Uploaded</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {documents.map(doc => (
                                    <tr key={doc.id} className="hover:bg-gray-50">
                                        <td className="px-4 py-3 text-sm text-gray-800 max-w-xs truncate">{doc.filename}</td>
                                        <td className="px-4 py-3 text-sm text-gray-600">{getGroupName(doc.group_id)}</td>
                                        <td className="px-4 py-3 text-sm text-gray-500">{new Date(doc.upload_date).toLocaleDateString()}</td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                onClick={() => handleDeleteDocument(doc.id)}
                                                className="text-gray-500 hover:text-red-600"
                                                title="Delete Document"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </main>

            {/* Assign User Modal */}
            {assignModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
                        <h3 className="text-lg font-semibold text-gray-800 mb-2">Add User to {assignModal.groupName}</h3>
                        <form onSubmit={handleAssignUser}>
                            <input
                                type="email"
                                value={assignEmail}
                                onChange={(e) => setAssignEmail(e.target.value)}
                                placeholder="User Email"
                                className="w-full p-2 border border-gray-300 rounded-md mb-4 text-black"
                                autoFocus
                            />
                            <div className="flex justify-end gap-2">
                                <button
                                    type="button"
                                    onClick={() => { setAssignModal(null); setAssignEmail(''); }}
                                    className="px-4 py-2 text-gray-600 hover:text-gray-800"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                                >
                                    Add
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
