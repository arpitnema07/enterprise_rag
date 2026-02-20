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
        let url = '/traces?limit=100';
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
        const ws = new WebSocket(`ws://${host}:8000/ws/events`);
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
        <div>
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-xl font-bold text-gray-100">Traces & Events</h1>
                <div className="flex items-center gap-3">
                    <button onClick={toggleLive}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-colors
              ${isLive ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-600'}`}
                    >
                        <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
                        {isLive ? 'Live' : 'Go Live'}
                    </button>
                    <button onClick={fetchEvents} className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400" title="Refresh">
                        <RefreshCw className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="flex gap-3 mb-4">
                <select value={filterType} onChange={e => setFilterType(e.target.value)}
                    className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300">
                    <option value="">All types</option>
                    <option value="request">Request</option>
                    <option value="response">Response</option>
                    <option value="retrieval">Retrieval</option>
                    <option value="generation">Generation</option>
                    <option value="error">Error</option>
                    <option value="system">System</option>
                </select>
                <select value={filterLevel} onChange={e => setFilterLevel(e.target.value)}
                    className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300">
                    <option value="">All levels</option>
                    <option value="info">Info</option>
                    <option value="warning">Warning</option>
                    <option value="error">Error</option>
                    <option value="debug">Debug</option>
                </select>
            </div>

            {/* Events list */}
            {loading ? (
                <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>
            ) : allEvents.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                    <Activity className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p>No events found.</p>
                </div>
            ) : (
                <div className="space-y-1">
                    {allEvents.map((ev, idx) => {
                        const key = ev.event_id || `${ev.trace_id}-${idx}`;
                        const isExpanded = expandedId === key;
                        return (
                            <div key={key} className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                                <button
                                    onClick={() => setExpandedId(isExpanded ? null : key)}
                                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800/50 text-left text-sm"
                                >
                                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />}
                                    <span className={`text-xs px-2 py-0.5 rounded-full border ${TYPE_COLORS[ev.event_type] || TYPE_COLORS.system}`}>
                                        {ev.event_type}
                                    </span>
                                    <span className={`text-xs ${LEVEL_COLORS[ev.level] || 'text-gray-400'}`}>{ev.level}</span>
                                    <span className="flex-1 text-gray-300 truncate">{ev.message}</span>
                                    <span className="text-xs text-gray-600 flex-shrink-0">
                                        {new Date(ev.timestamp).toLocaleTimeString()}
                                    </span>
                                </button>
                                {isExpanded && (
                                    <div className="border-t border-gray-800 px-4 py-3 text-xs space-y-1.5">
                                        <div className="flex gap-8">
                                            <span className="text-gray-500">Trace: <span className="text-gray-400 font-mono">{ev.trace_id || '—'}</span></span>
                                            <span className="text-gray-500">User: <span className="text-gray-400">{ev.user_email || ev.user_id || '—'}</span></span>
                                        </div>
                                        {ev.data && (
                                            <pre className="mt-2 bg-gray-950 rounded-lg p-3 overflow-x-auto text-gray-400 text-xs">
                                                {typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data, null, 2)}
                                            </pre>
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
