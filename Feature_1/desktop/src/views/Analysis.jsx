import React, { useState, useEffect } from 'react';
import { Download, FileText, BarChart2, TrendingUp, History, Clock } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

export default function Analysis() {
  const [metrics, setMetrics] = useState({ good: 0, rework: 0, history: [], log: [] });
  const [sessionList, setSessionList] = useState([]); 
  const [reworkTime, setReworkTime] = useState(2.0); // Rework Time එක සඳහා අලුත් State එක

  // දැනට දුවන Session එකේ දත්ත ලබා ගැනීම
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch('http://localhost:8000/metrics');
        const data = await res.json();
        setMetrics(data);
      } catch (error) {
        console.error("Failed to fetch metrics for analysis:", error);
      }
    };
    
    fetchMetrics(); 
    const interval = setInterval(fetchMetrics, 2000); 
    return () => clearInterval(interval);
  }, []);

  // පරණ Sessions වල සාරාංශය ලබා ගැනීම
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const res = await fetch('http://localhost:8000/sessions');
        const data = await res.json();
        setSessionList(data);
      } catch (error) {
        console.error("Failed to fetch sessions history:", error);
      }
    };
    
    fetchSessions();
    const interval = setInterval(fetchSessions, 5000); 
    return () => clearInterval(interval);
  }, []);

  const barData = [
    { name: 'Good', value: metrics.good, color: '#168768' },
    { name: 'Rework', value: metrics.rework, color: '#BD4A67' }
  ];

  const handleDownloadCSV = () => {
    if (metrics.log.length === 0) return;
    const headers = "ID,Verdict,Timestamp\n";
    const csvData = metrics.log.map(row => `${row.id},${row.verdict},${row.timestamp}`).join("\n");
    const blob = new Blob([headers + csvData], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `live_inspection_log_${new Date().getTime()}.csv`;
    a.click();
  };

  // CSV එකටත් Delay Time එක එකතු කර ඇත
  const handleDownloadSessionsCSV = () => {
    if (sessionList.length === 0) return;
    const headers = "Session ID,Total Checked,Good,Rework,Pass Rate (%),Total Delay (Mins),Start Time,End Time\n";
    const csvData = sessionList.map(row => {
      const delay = (row.rework * reworkTime).toFixed(1);
      return `${row.session_id},${row.total},${row.good},${row.rework},${row.pass_rate},${delay},${row.start_time},${row.end_time}`;
    }).join("\n");
    
    const blob = new Blob([headers + csvData], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sessions_summary_${new Date().getTime()}.csv`;
    a.click();
  };

  return (
    <div className="max-w-[1400px] mx-auto h-full flex flex-col font-sans gap-6 pb-6 overflow-y-auto">
      
      {/* Charts Row */}
      <div className="flex gap-6 h-[300px] shrink-0">
        {/* Line Chart */}
        <div className="flex-[2] bg-surface border border-line rounded-xl p-5 shadow-sm flex flex-col">
          <h3 className="font-bold text-ink text-sm flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-accent" /> Live Inspection Trend
          </h3>
          <div className="flex-1 w-full h-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics.history} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0F2F6" vertical={false} />
                <XAxis dataKey="frame" tick={{ fontSize: 10, fill: '#8691A4' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#8691A4' }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Line type="monotone" dataKey="good" stroke="#168768" strokeWidth={3} dot={false} name="Good" />
                <Line type="monotone" dataKey="rework" stroke="#BD4A67" strokeWidth={3} dot={false} name="Rework" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar Chart */}
        <div className="flex-[1] bg-surface border border-line rounded-xl p-5 shadow-sm flex flex-col">
          <h3 className="font-bold text-ink text-sm flex items-center gap-2 mb-4">
            <BarChart2 size={16} className="text-accent" /> Live Verdict Split
          </h3>
          <div className="flex-1 w-full h-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0F2F6" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#5B6980', fontWeight: 'bold' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#8691A4' }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: '#F5F7FB' }} contentStyle={{ borderRadius: '8px', border: 'none' }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {barData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="flex gap-6 h-[350px] shrink-0">
        {/* 1. Live Inspection Log Table */}
        <div className="bg-surface border border-line rounded-xl flex-1 flex flex-col shadow-sm overflow-hidden h-full">
          <div className="px-5 py-4 border-b border-line flex justify-between items-center bg-canvas">
            <h3 className="font-bold text-ink text-sm flex items-center gap-2">
              <FileText size={16} className="text-ink-soft" /> Current Session Log
            </h3>
            <button 
              onClick={handleDownloadCSV}
              className="flex items-center gap-2 text-xs font-bold text-accent hover:text-accent/80 transition-colors bg-accent-soft px-3 py-1.5 rounded-md"
            >
              <Download size={14} /> Export Live
            </button>
          </div>
          
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-surface sticky top-0 border-b border-line shadow-sm">
                <tr>
                  <th className="py-3 px-5 text-xs font-semibold text-ink-secondary w-1/4">ID</th>
                  <th className="py-3 px-5 text-xs font-semibold text-ink-secondary w-1/4">Verdict</th>
                  <th className="py-3 px-5 text-xs font-semibold text-ink-secondary w-1/4">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {metrics.log.length > 0 ? (
                  metrics.log.map((row, index) => (
                    <tr key={index} className="border-b border-line-soft hover:bg-canvas/50 transition-colors">
                      <td className="py-2.5 px-5 text-sm font-medium text-ink">{row.id}</td>
                      <td className="py-2.5 px-5 text-sm">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${row.verdict === 'Good' ? 'bg-status-success-bg text-status-success' : 'bg-status-error-bg text-status-error'}`}>
                          {row.verdict}
                        </span>
                      </td>
                      <td className="py-2.5 px-5 text-sm text-ink-soft">{row.timestamp}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="3" className="text-center py-10 text-sm text-ink-soft">
                      No live inspection logs available yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 2. Historical Sessions Table */}
        <div className="bg-surface border border-line rounded-xl flex-[1.2] flex flex-col shadow-sm overflow-hidden h-full">
          <div className="px-5 py-4 border-b border-line flex justify-between items-center bg-canvas">
            <h3 className="font-bold text-ink text-sm flex items-center gap-2">
              <History size={16} className="text-ink-soft" /> Historical Sessions
            </h3>
            
            <div className="flex items-center gap-4">
              {/* Rework Time එක වෙනස් කරන Input එක */}
              <div className="flex items-center gap-2 bg-surface px-2 py-1 rounded-md border border-line">
                <Clock size={12} className="text-status-warning" />
                <label className="text-[10px] font-bold text-ink-secondary whitespace-nowrap">Avg Fix (Mins):</label>
                <input 
                  type="number" 
                  value={reworkTime}
                  onChange={(e) => setReworkTime(Number(e.target.value))}
                  step="0.5" 
                  className="w-14 text-xs p-1 border border-line bg-canvas rounded outline-none focus:border-accent text-ink" 
                />
              </div>

              <button 
                onClick={handleDownloadSessionsCSV}
                className="flex items-center gap-2 text-xs font-bold text-ink hover:text-ink/80 transition-colors bg-line-soft px-3 py-1.5 rounded-md border border-line"
              >
                <Download size={14} /> Export
              </button>
            </div>
          </div>
          
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-surface sticky top-0 border-b border-line shadow-sm">
                <tr>
                  <th className="py-3 px-5 text-xs font-semibold text-ink-secondary">Session ID</th>
                  <th className="py-3 px-4 text-xs font-semibold text-ink-secondary text-center">Good</th>
                  <th className="py-3 px-4 text-xs font-semibold text-ink-secondary text-center">Rework</th>
                  <th className="py-3 px-4 text-xs font-semibold text-ink-secondary text-center">Pass Rate</th>
                  {/* අලුත් Delay Column එක */}
                  <th className="py-3 px-4 text-xs font-semibold text-ink-secondary text-center">Delay (Mins)</th>
                  <th className="py-3 px-5 text-xs font-semibold text-ink-secondary">Time</th>
                </tr>
              </thead>
              <tbody>
                {sessionList.length > 0 ? (
                  sessionList.map((session, index) => (
                    <tr key={index} className="border-b border-line-soft hover:bg-canvas/50 transition-colors">
                      <td className="py-2.5 px-5 text-[11px] font-mono text-ink font-semibold">{session.session_id}</td>
                      <td className="py-2.5 px-4 text-sm text-center text-status-success font-bold">{session.good}</td>
                      <td className="py-2.5 px-4 text-sm text-center text-status-error font-bold">{session.rework}</td>
                      <td className="py-2.5 px-4 text-sm text-center font-bold">
                        <span className={session.pass_rate > 90 ? 'text-status-success' : session.pass_rate > 75 ? 'text-status-warning' : 'text-status-error'}>
                          {session.pass_rate}%
                        </span>
                      </td>
                      {/* මෙතන තමයි Rework ගාණෙන් Rework Time එක ගුණ කරලා පෙන්වන්නේ */}
                      <td className="py-2.5 px-4 text-sm text-center font-black text-status-warning">
                        {(session.rework * reworkTime).toFixed(1)}m
                      </td>
                      <td className="py-2.5 px-5 text-[10px] text-ink-soft whitespace-nowrap">
                        {session.start_time} - {session.end_time}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="text-center py-10 text-sm text-ink-soft">
                      No historical sessions found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

    </div>
  );
}