import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { claimsApi, facilitiesApi } from '../lib/api';
import {
  claimStatusColors,
  formatStatus,
  formatCurrency,
  formatDate,
} from '../lib/statusColors';
import type { Claim, Facility, ClaimStatus } from '../types';

const allStatuses: ClaimStatus[] = [
  'submitted',
  'ocr_processing',
  'ocr_failed',
  'ready_for_review',
  'in_progress',
  'coded',
  'billed',
  'paid',
  'denied',
  'appealed',
  'void',
];

export default function Claims() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [facilityFilter, setFacilityFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    facilitiesApi.list().then(setFacilities).catch(console.error);
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const params: Record<string, string> = {};
        if (statusFilter) params.status = statusFilter;
        if (facilityFilter) params.facility_id = facilityFilter;
        const data = await claimsApi.list(params);
        setClaims(data);
      } catch (err) {
        console.error('Failed to load claims:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [statusFilter, facilityFilter]);

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
            {allStatuses.map((s) => (
              <option key={s} value={s}>
                {formatStatus(s)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600">
            Facility:
          </label>
          <select
            value={facilityFilter}
            onChange={(e) => setFacilityFilter(e.target.value)}
            className="text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">All Facilities</option>
            {facilities.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </div>
        <div className="ml-auto text-sm text-slate-500">
          {claims.length} claim{claims.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Claims table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="px-5 py-12 text-center text-slate-500 text-sm">
            Loading claims...
          </div>
        ) : claims.length === 0 ? (
          <div className="px-5 py-12 text-center text-slate-500 text-sm">
            No claims found matching your filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Claim #
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Patient
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Facility
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Charges
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Assigned To
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    DOS
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {claims.map((claim) => (
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
                    <td className="px-5 py-3 text-slate-700">
                      {claim.facility?.name || '-'}
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
                    <td className="px-5 py-3 text-slate-700">
                      {claim.assigned_coder?.full_name ||
                        claim.assigned_biller?.full_name ||
                        '-'}
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
