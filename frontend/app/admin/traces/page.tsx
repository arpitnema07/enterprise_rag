'use client';

import { useState, useEffect, useRef } from 'react';
import api from '@/lib/api';
import { Activity, Filter, RefreshCw, Loader2, ChevronDown, ChevronRight } from 'lucide-react';

interface TraceEvent {
    event_id: string;
    event_type: string;
    level: string;
    trace_id: string;
    message: string;
    timestamp: string;
    user_id?: number;
    user_email?: string;
    data?: any;
}

const LEVEL_COLORS: Record<string, string> = {
    info: 'text-blue-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    debug: 'text-gray-500',
};

const TYPE_COLORS: Record<string, string> = {
    request: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    response: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    retrieval: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    generation: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    error: 'bg-red-500/10 text-red-400 border-red-500/20',
    system: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
};

export default function TracesPage() {
    const [events, setEvents] = useState<TraceEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [liveEvents, setLiveEvents] = useState<TraceEvent[]>([]);
    const [isLive, setIsLive] = useState(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [filterType, setFilterType] = useState('');
    const [filterLevel, setFilterLevel] = useState('');
    const wsRef = useRef<WebSocket | null>(null);

    // Fetch historical events
    const fetchEvents = () => {
        setLoading(true);
        let url = '/admin/traces?limit=100';
        if (filterType) url += `&event_type=${filterType}`;
        if (filterLevel) url += `&level=${filterLevel}`;
        api.get(url).then(r => setEvents(r.data.events || r.data || [])).catch(console.error).finally(() => setLoading(false));
    };

    useEffect(() => { fetchEvents(); }, [filterType, filterLevel]);

    // WebSocket for live events
    const toggleLive = () => {
        if (isLive) {
            wsRef.current?.close();
            wsRef.current = null;
            setIsLive(false);
            return;
        }

        const host = process.env.NEXT_PUBLIC_WS_HOST || window.location.hostname;
        const ws = new WebSocket(`ws://${host}:8000/ws/logs`);
        ws.onmessage = (ev) => {
            try {
                const data = JSON.parse(ev.data);
                setLiveEvents(prev => [data, ...prev].slice(0, 200));
            } catch { }
        };
        ws.onopen = () => setIsLive(true);
        ws.onclose = () => setIsLive(false);
        wsRef.current = ws;
    };

    useEffect(() => { return () => wsRef.current?.close(); }, []);

    const allEvents = isLive ? [...liveEvents, ...events] : events;

    return (
        <div className="animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-8">
                <h1 className="text-2xl font-bold bg-gradient-to-br from-zinc-100 to-zinc-500 bg-clip-text text-transparent">Traces & Events</h1>
                <div className="flex items-center gap-3">
                    <button onClick={toggleLive}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all shadow-sm
              ${isLive ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20' : 'bg-zinc-800 text-zinc-300 border-zinc-700/50 hover:border-zinc-600 hover:bg-zinc-700'}`}
                    >
                        <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-zinc-500'}`} />
                        {isLive ? 'Live Stream Active' : 'Go Live'}
                    </button>
                    <button onClick={fetchEvents} className="p-2 rounded-xl bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700/50 text-zinc-400 hover:text-zinc-200 transition-all" title="Refresh Events">
                        <RefreshCw className="w-[18px] h-[18px]" />
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="flex bg-zinc-900/40 p-3 rounded-2xl border border-zinc-800/50 gap-3 mb-6 items-center">
                <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider pl-2 hidden sm:block">Filter Logs</span>
                <select value={filterType} onChange={e => setFilterType(e.target.value)}
                    className="bg-zinc-800/80 border border-zinc-700/50 rounded-lg px-4 py-2 text-sm text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition-all">
                    <option value="">All Types</option>
                    <option value="request">Request</option>
                    <option value="response">Response</option>
                    <option value="retrieval">Retrieval</option>
                    <option value="generation">Generation</option>
                    <option value="error">Error</option>
                    <option value="system">System</option>
                </select>
                <select value={filterLevel} onChange={e => setFilterLevel(e.target.value)}
                    className="bg-zinc-800/80 border border-zinc-700/50 rounded-lg px-4 py-2 text-sm text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer transition-all">
                    <option value="">All Levels</option>
                    <option value="info">Info</option>
                    <option value="warning">Warning</option>
                    <option value="error">Error</option>
                    <option value="debug">Debug</option>
                </select>
            </div>

            {/* Events list */}
            {loading ? (
                <div className="flex items-center justify-center py-20 bg-zinc-900/20 rounded-2xl border border-zinc-800/50"><Loader2 className="w-8 h-8 animate-spin text-blue-500/60" /></div>
            ) : allEvents.length === 0 ? (
                <div className="text-center py-24 bg-zinc-900/20 rounded-2xl border border-zinc-800/50 flex flex-col items-center justify-center">
                    <div className="bg-zinc-800/50 p-6 rounded-full mb-4">
                        <Activity className="w-10 h-10 text-zinc-600" />
                    </div>
                    <p className="text-zinc-400 font-medium">No system events or traces found.</p>
                </div>
            ) : (
                <div className="space-y-1.5 bg-zinc-900/30 rounded-2xl p-2 border border-zinc-800/40">
                    {allEvents.map((ev, idx) => {
                        const key = ev.event_id || `${ev.trace_id}-${idx}`;
                        const isExpanded = expandedId === key;
                        return (
                            <div key={key} className="bg-zinc-900 border border-zinc-800/50 rounded-xl overflow-hidden hover:border-zinc-700/50 transition-colors">
                                <button
                                    onClick={() => setExpandedId(isExpanded ? null : key)}
                                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-800/40 text-left text-sm transition-colors"
                                >
                                    {isExpanded ? <ChevronDown className="w-4 h-4 text-zinc-500 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-zinc-500 flex-shrink-0" />}
                                    <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${TYPE_COLORS[ev.event_type] || TYPE_COLORS.system}`}>
                                        {ev.event_type}
                                    </span>
                                    <span className={`text-xs font-semibold uppercase tracking-wider ${LEVEL_COLORS[ev.level] || 'text-zinc-500'}`}>{ev.level}</span>
                                    <span className="flex-1 text-zinc-300 truncate font-mono text-[13px]">{ev.message}</span>
                                    <span className="text-xs text-zinc-500 font-mono tracking-tighter flex-shrink-0 bg-zinc-950/50 px-2 py-1 rounded-md border border-zinc-800/50">
                                        {new Date(ev.timestamp).toLocaleTimeString(undefined, { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 })}
                                    </span>
                                </button>
                                {isExpanded && (
                                    <div className="border-t border-zinc-800/50 bg-zinc-950/40 px-5 py-4 text-sm animate-in slide-in-from-top-1 duration-200">
                                        <div className="flex flex-col sm:flex-row gap-4 sm:gap-8 mb-4">
                                            <span className="text-zinc-500 flex items-center gap-2">
                                                <span className="text-[10px] uppercase tracking-wider font-semibold">Trace ID:</span>
                                                <span className="text-xs text-zinc-300 font-mono bg-zinc-900 px-2 py-1 rounded border border-zinc-800">{ev.trace_id || '—'}</span>
                                            </span>
                                            <span className="text-zinc-500 flex items-center gap-2">
                                                <span className="text-[10px] uppercase tracking-wider font-semibold">User:</span>
                                                <span className="text-xs text-zinc-300 font-medium bg-zinc-900 px-2 py-1 rounded border border-zinc-800">{ev.user_email || ev.user_id || 'System'}</span>
                                            </span>
                                        </div>
                                        {ev.data && (
                                            <div className="relative">
                                                <div className="absolute top-0 left-0 text-[10px] font-bold text-zinc-600 uppercase tracking-widest px-3 py-1 bg-zinc-900 border-b border-r border-zinc-800/80 rounded-br-lg rounded-tl-lg z-10">Data Payload</div>
                                                <pre className="mt-1 bg-zinc-950/80 border border-zinc-800/50 rounded-xl p-4 pt-8 overflow-x-auto text-zinc-400 font-mono text-xs shadow-inner custom-scrollbar">
                                                    {typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data, null, 2)}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
