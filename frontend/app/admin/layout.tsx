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
        <div className="flex h-screen bg-gray-950 text-gray-100">
            {/* Sidebar */}
            <aside className={`flex flex-col border-r border-gray-800 bg-gray-900 transition-all duration-200 ${collapsed ? 'w-16' : 'w-56'}`}>
                {/* Header */}
                <div className="flex items-center justify-between px-4 h-14 border-b border-gray-800">
                    {!collapsed && <span className="font-bold text-sm tracking-wider text-indigo-400">VECVRAG</span>}
                    <button onClick={() => setCollapsed(!collapsed)} className="p-1 rounded hover:bg-gray-800 text-gray-400">
                        {collapsed ? <Menu className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                    </button>
                </div>

                {/* Nav */}
                <nav className="flex-1 py-3 space-y-0.5 px-2">
                    {NAV_ITEMS.map(item => (
                        <Link key={item.href} href={item.href}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${isActive(item.href)
                                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30'
                                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800 border border-transparent'
                                }`}
                        >
                            <item.icon className="w-4 h-4 flex-shrink-0" />
                            {!collapsed && <span>{item.label}</span>}
                        </Link>
                    ))}
                </nav>

                {/* Service health bar */}
                <div className={`px-3 py-3 border-t border-gray-800 ${collapsed ? 'px-2' : ''}`}>
                    {!collapsed && <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">Services</p>}
                    <div className={`flex ${collapsed ? 'flex-col gap-1.5 items-center' : 'flex-wrap gap-x-3 gap-y-1'}`}>
                        {['postgres', 'redis', 'qdrant', 'minio', 'clickhouse', 'ollama'].map(svc => (
                            <div key={svc} className="flex items-center gap-1" title={svc}>
                                <ServiceDot name={svc} />
                                {!collapsed && <span className="text-[10px] text-gray-500 capitalize">{svc}</span>}
                            </div>
                        ))}
                    </div>
                </div>

                {/* User + Logout */}
                <div className="px-3 py-3 border-t border-gray-800">
                    {!collapsed && user && (
                        <p className="text-[10px] text-gray-500 truncate mb-2">{user.email}</p>
                    )}
                    <button onClick={handleLogout}
                        className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 transition-colors w-full"
                    >
                        <LogOut className="w-4 h-4" />
                        {!collapsed && <span>Logout</span>}
                    </button>
                </div>
            </aside>

            {/* Main content */}
            <main className="flex-1 overflow-y-auto bg-gray-950">
                <div className="p-6 max-w-7xl mx-auto">
                    {children}
                </div>
            </main>
        </div>
    );
}
