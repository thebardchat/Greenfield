import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { claimsApi } from '../lib/api';
import {
  claimStatusColors,
  validTransitions,
  formatStatus,
  formatCurrency,
  formatDate,
} from '../lib/statusColors';
import type { Claim, ClaimStatus } from '../types';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';

export default function ClaimDetail() {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    claimsApi
      .get(id)
      .then(setClaim)
      .catch((err) => {
        console.error('Failed to load claim:', err);
        setError('Failed to load claim details.');
      })
      .finally(() => setLoading(false));
  }, [id]);

  const handleTransition = async (newStatus: ClaimStatus) => {
    if (!id || !claim) return;
    setTransitioning(true);
    setError('');
    try {
      const updated = await claimsApi.transition(id, newStatus);
      setClaim(updated);
    } catch (err) {
      console.error('Transition failed:', err);
      setError('Failed to transition claim status.');
    } finally {
      setTransitioning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        Loading claim details...
      </div>
    );
  }

  if (error && !claim) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-4">{error}</p>
        <Link to="/claims" className="text-blue-600 hover:text-blue-700">
          Back to Claims
        </Link>
      </div>
    );
  }

  if (!claim) return null;

  const nextStates = validTransitions[claim.status] || [];

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to="/claims"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeftIcon className="w-4 h-4" />
        Back to Claims
      </Link>

      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-800">
              Claim {claim.claim_number}
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              Created {formatDate(claim.created_at)} | Last updated{' '}
              {formatDate(claim.updated_at)}
            </p>
          </div>
          <span
            className={`inline-block text-sm px-3 py-1.5 rounded-full font-semibold ${
              claimStatusColors[claim.status] || 'bg-gray-100 text-gray-700'
            }`}
          >
            {formatStatus(claim.status)}
          </span>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
            {error}
          </div>
        )}

        {/* Status transition buttons */}
        {nextStates.length > 0 && (
          <div className="mb-6 pb-6 border-b border-slate-200">
            <div className="text-sm font-medium text-slate-600 mb-2">
              Transition to:
            </div>
            <div className="flex flex-wrap gap-2">
              {nextStates.map((status) => (
                <button
                  key={status}
                  onClick={() => handleTransition(status)}
                  disabled={transitioning}
                  className={`text-sm px-4 py-2 rounded-lg font-medium transition-colors border disabled:opacity-50 ${
                    status === 'void'
                      ? 'border-red-300 text-red-700 hover:bg-red-50'
                      : status === 'denied'
                        ? 'border-red-300 text-red-700 hover:bg-red-50'
                        : 'border-slate-300 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {formatStatus(status)}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Claim details grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4">
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Patient
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {claim.patient
                ? `${claim.patient.first_name} ${claim.patient.last_name}`
                : '-'}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Facility
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {claim.facility?.name || '-'}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Date of Service
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {formatDate(claim.date_of_service)}
              {claim.date_of_service_end &&
                ` - ${formatDate(claim.date_of_service_end)}`}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Total Charges
            </div>
            <div className="text-sm text-slate-800 mt-1 font-semibold">
              {formatCurrency(claim.total_charges)}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Total Allowed
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {formatCurrency(claim.total_allowed)}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Total Paid
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {formatCurrency(claim.total_paid)}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Primary ICD
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {claim.primary_icd_code || '-'}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Assigned Coder
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {claim.assigned_coder?.full_name || '-'}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Assigned Biller
            </div>
            <div className="text-sm text-slate-800 mt-1">
              {claim.assigned_biller?.full_name || '-'}
            </div>
          </div>
        </div>

        {claim.notes && (
          <div className="mt-6 pt-4 border-t border-slate-200">
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
              Notes
            </div>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">
              {claim.notes}
            </p>
          </div>
        )}
      </div>

      {/* Claim Lines */}
      {claim.claim_lines && claim.claim_lines.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200">
            <h3 className="text-base font-semibold text-slate-800">
              Claim Lines
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    #
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    CPT Code
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Description
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    ICD Codes
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Units
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Charge
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Allowed
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Paid
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {claim.claim_lines.map((line) => (
                  <tr key={line.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 text-slate-500">
                      {line.line_number}
                    </td>
                    <td className="px-5 py-3 font-mono text-slate-800">
                      {line.cpt_code || '-'}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {line.cpt_description || '-'}
                    </td>
                    <td className="px-5 py-3 font-mono text-slate-700">
                      {line.icd_codes?.length > 0
                        ? line.icd_codes.join(', ')
                        : '-'}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-700 tabular-nums">
                      {line.units}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-700 tabular-nums">
                      {formatCurrency(line.charge_amount)}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-700 tabular-nums">
                      {formatCurrency(line.allowed_amount)}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-700 tabular-nums">
                      {formatCurrency(line.paid_amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
