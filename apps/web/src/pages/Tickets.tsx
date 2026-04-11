import { useEffect, useState } from 'react';
import { ticketsApi } from '../lib/api';
import {
  ticketStatusColors,
  ticketTypeColors,
  priorityColors,
  formatStatus,
  formatDate,
} from '../lib/statusColors';
import type { Ticket } from '../types';

const ticketStatuses = ['open', 'in_progress', 'waiting', 'resolved', 'closed'];

export default function Tickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const params: Record<string, string> = {};
        if (statusFilter) params.status = statusFilter;
        const data = await ticketsApi.list(params);
        setTickets(data);
      } catch (err) {
        console.error('Failed to load tickets:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [statusFilter]);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-slate-200 px-5 py-4 flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">All Statuses</option>
            {ticketStatuses.map((s) => (
              <option key={s} value={s}>
                {formatStatus(s)}
              </option>
            ))}
          </select>
        </div>
        <div className="ml-auto text-sm text-slate-500">
          {tickets.length} ticket{tickets.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Tickets table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="px-5 py-12 text-center text-slate-500 text-sm">
            Loading tickets...
          </div>
        ) : tickets.length === 0 ? (
          <div className="px-5 py-12 text-center text-slate-500 text-sm">
            No tickets found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Title
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Priority
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Assigned To
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Due Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    className="hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-5 py-3 font-medium text-slate-800 max-w-xs truncate">
                      {ticket.title}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-block text-xs px-2.5 py-1 rounded-full font-medium ${
                          ticketTypeColors[ticket.ticket_type] ||
                          'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {formatStatus(ticket.ticket_type)}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-block text-xs px-2.5 py-1 rounded-full font-medium ${
                          ticketStatusColors[ticket.status] ||
                          'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {formatStatus(ticket.status)}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`text-sm ${
                          priorityColors[ticket.priority] || 'text-slate-600'
                        }`}
                      >
                        {formatStatus(ticket.priority)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {ticket.assigned_to?.full_name || '-'}
                    </td>
                    <td className="px-5 py-3 text-slate-500">
                      {formatDate(ticket.due_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
