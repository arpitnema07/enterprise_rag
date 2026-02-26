'use client';

import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import api from '@/lib/api';
import {
    BarChart3, FileText, Users, FolderOpen, Activity, Settings,
    LogOut, ChevronLeft, Menu, CheckCircle, XCircle, Loader2
} from 'lucide-react';

interface ServiceStatus {
    [key: string]: { status: string;[key: string]: any };
}

const NAV_ITEMS = [
    { href: '/admin', label: 'Stats', icon: BarChart3 },
    { href: '/admin/documents', label: 'Documents', icon: FileText },
    { href: '/admin/users', label: 'Users', icon: Users },
    { href: '/admin/groups', label: 'Groups', icon: FolderOpen },
    { href: '/admin/traces', label: 'Traces', icon: Activity },
    { href: '/admin/config', label: 'Config', icon: Settings },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    const [collapsed, setCollapsed] = useState(false);
    const [user, setUser] = useState<{ email: string; is_admin: boolean } | null>(null);
    const [health, setHealth] = useState<ServiceStatus>({});

    useEffect(() => {
        // Verify admin access
        api.get('/auth/me').then(res => {
            if (!res.data.is_admin) {
                router.push('/dashboard');
            }
            setUser(res.data);
        }).catch(() => router.push('/login'));

        // Fetch service health
        api.get('/admin/service-health').then(res => setHealth(res.data)).catch(() => { });

        // Poll health every 30s
        const interval = setInterval(() => {
            api.get('/admin/service-health').then(res => setHealth(res.data)).catch(() => { });
        }, 30000);
        return () => clearInterval(interval);
    }, [router]);

    const handleLogout = () => {
        localStorage.removeItem('token');
        router.push('/login');
    };

    const isActive = (href: string) => {
        if (href === '/admin') return pathname === '/admin';
        return pathname.startsWith(href);
    };

    const ServiceDot = ({ name }: { name: string }) => {
        const svc = health[name];
        if (!svc) return <Loader2 className="w-3 h-3 animate-spin text-gray-500" />;
        return svc.status === 'ok'
            ? <CheckCircle className="w-3 h-3 text-emerald-400" />
            : <XCircle className="w-3 h-3 text-red-400" />;
    };

    return (
        <div className="flex h-screen bg-zinc-950 text-zinc-100 flex-row overflow-hidden relative z-0">
            {/* Sidebar */}
            <aside className={`flex flex-col border-r border-zinc-800/50 bg-zinc-900/60 backdrop-blur-md transition-all duration-300 z-10 ${collapsed ? 'w-16' : 'w-64'}`}>
                {/* Header */}
                <div className="flex items-center justify-between px-4 h-16 border-b border-zinc-800/50">
                    {!collapsed && (
                        <span className="font-bold text-[15px] tracking-wider bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
                            VECVRAG ADMIN
                        </span>
                    )}
                    <button onClick={() => setCollapsed(!collapsed)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors">
                        {collapsed ? <Menu className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                    </button>
                </div>

                {/* Nav */}
                <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1 custom-scrollbar">
                    {NAV_ITEMS.map(item => {
                        const active = isActive(item.href);
                        return (
                            <Link key={item.href} href={item.href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group
                                    ${active
                                        ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/50'
                                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 border border-transparent'
                                    }`}
                            >
                                <item.icon className={`w-[18px] h-[18px] flex-shrink-0 ${active ? 'text-blue-400' : 'text-zinc-500 group-hover:text-zinc-400'}`} />
                                {!collapsed && <span className="truncate">{item.label}</span>}
                            </Link>
                        );
                    })}
                </nav>

                {/* Service health bar */}
                <div className={`px-4 py-4 border-t border-zinc-800/50 ${collapsed ? 'px-2' : ''}`}>
                    {!collapsed && <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-3">System Health</p>}
                    <div className={`flex ${collapsed ? 'flex-col gap-2.5 items-center' : 'flex-wrap gap-x-3 gap-y-2'}`}>
                        {['postgres', 'redis', 'qdrant', 'minio', 'clickhouse', 'ollama'].map(svc => (
                            <div key={svc} className="flex items-center gap-1.5 bg-zinc-950/50 px-2 py-1 rounded-md border border-zinc-800/50" title={svc}>
                                <ServiceDot name={svc} />
                                {!collapsed && <span className="text-[10px] font-medium text-zinc-400 capitalize truncate">{svc}</span>}
                            </div>
                        ))}
                    </div>
                </div>

                {/* User + Logout */}
                <div className="px-4 py-4 border-t border-zinc-800/50 bg-zinc-950/20">
                    {!collapsed && user && (
                        <p className="text-[11px] font-medium text-zinc-500 truncate mb-3 px-1">{user.email}</p>
                    )}
                    <button onClick={handleLogout}
                        className={`flex items-center gap-3 text-sm font-medium text-zinc-400 hover:text-red-400 hover:bg-zinc-800/50 transition-all rounded-xl w-full ${collapsed ? 'justify-center p-2.5' : 'px-3 py-2.5'}`}
                        title="Logout"
                    >
                        <LogOut className="w-[18px] h-[18px]" />
                        {!collapsed && <span>Logout</span>}
                    </button>
                </div>
            </aside>

            {/* Main content */}
            <main className="flex-1 overflow-hidden relative">
                <div className="absolute inset-0 overflow-y-auto">
                    <div className="p-6 md:p-8 max-w-7xl mx-auto min-h-full">
                        {children}
                    </div>
                </div>
            </main>
        </div>
    );
}
