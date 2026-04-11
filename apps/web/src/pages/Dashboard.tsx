import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { claimsApi, ticketsApi, credentialsApi } from '../lib/api';
import {
  claimStatusColors,
  formatStatus,
  formatCurrency,
  formatDate,
} from '../lib/statusColors';
import type { Claim, Ticket } from '../types';
import {
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  TicketIcon,
  IdentificationIcon,
} from '@heroicons/react/24/outline';

interface DashboardStats {
  totalClaims: number;
  readyForReview: number;
  inProgress: number;
  denied: number;
  expiringCredentials: number;
  pendingTickets: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    totalClaims: 0,
    readyForReview: 0,
    inProgress: 0,
    denied: 0,
    expiringCredentials: 0,
    pendingTickets: 0,
  });
  const [recentClaims, setRecentClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [allClaims, tickets, expiringCreds] = await Promise.all([
          claimsApi.list(),
          ticketsApi.list(),
          credentialsApi.expiring(90),
        ]);

        const statusCounts = allClaims.reduce(
          (acc: Record<string, number>, c: Claim) => {
            acc[c.status] = (acc[c.status] || 0) + 1;
            return acc;
          },
          {}
        );

        const openTickets = tickets.filter(
          (t: Ticket) => t.status === 'open' || t.status === 'in_progress'
        );

        setStats({
          totalClaims: allClaims.length,
          readyForReview: statusCounts['ready_for_review'] || 0,
          inProgress: statusCounts['in_progress'] || 0,
          denied: statusCounts['denied'] || 0,
          expiringCredentials: expiringCreds.length,
          pendingTickets: openTickets.length,
        });

        const sorted = [...allClaims].sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setRecentClaims(sorted.slice(0, 10));
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        Loading dashboard...
      </div>
    );
  }

  const statCards = [
    {
      label: 'Total Claims',
      value: stats.totalClaims,
      icon: DocumentTextIcon,
      color: 'bg-blue-50 text-blue-600',
    },
    {
      label: 'Ready for Review',
      value: stats.readyForReview,
      icon: ClockIcon,
      color: 'bg-indigo-50 text-indigo-600',
    },
    {
      label: 'In Progress',
      value: stats.inProgress,
      icon: CheckCircleIcon,
      color: 'bg-purple-50 text-purple-600',
    },
    {
      label: 'Denied',
      value: stats.denied,
      icon: ExclamationTriangleIcon,
      color: 'bg-red-50 text-red-600',
    },
    {
      label: 'Expiring Credentials',
      value: stats.expiringCredentials,
      icon: IdentificationIcon,
      color: 'bg-yellow-50 text-yellow-600',
    },
    {
      label: 'Open Tickets',
      value: stats.pendingTickets,
      icon: TicketIcon,
      color: 'bg-green-50 text-green-600',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4"
          >
            <div className={`p-3 rounded-lg ${card.color}`}>
              <card.icon className="w-6 h-6" />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-800">
                {card.value}
              </div>
              <div className="text-sm text-slate-500">{card.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Claims */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-800">
            Recent Claims
          </h2>
          <Link
            to="/claims"
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            View all
          </Link>
        </div>
        {recentClaims.length === 0 ? (
          <div className="px-5 py-8 text-center text-slate-500 text-sm">
            No claims found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Claim #
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Patient
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Charges
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentClaims.map((claim) => (
                  <tr
                    key={claim.id}
                    className="hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-5 py-3">
                      <Link
                        to={`/claims/${claim.id}`}
                        className="text-blue-600 hover:text-blue-700 font-medium"
                      >
                        {claim.claim_number}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {claim.patient
                        ? `${claim.patient.last_name}, ${claim.patient.first_name}`
                        : '-'}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-block text-xs px-2.5 py-1 rounded-full font-medium ${
                          claimStatusColors[claim.status] ||
                          'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {formatStatus(claim.status)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right text-slate-700 tabular-nums">
                      {formatCurrency(claim.total_charges)}
                    </td>
                    <td className="px-5 py-3 text-slate-500">
                      {formatDate(claim.date_of_service)}
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
