import { useEffect, useState } from 'react';
import { credentialsApi } from '../lib/api';
import { credentialStatusColors, formatStatus, formatDate } from '../lib/statusColors';
import type { Credential } from '../types';

export default function Credentials() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    credentialsApi
      .list()
      .then(setCredentials)
      .catch((err) => console.error('Failed to load credentials:', err))
      .finally(() => setLoading(false));
  }, []);

  const getRowHighlight = (cred: Credential): string => {
    if (cred.status === 'expired') return 'bg-red-50';
    if (cred.status === 'expiring_soon') return 'bg-yellow-50';
    return '';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        Loading credentials...
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-800">
          Provider Credentials
        </h2>
        <span className="text-sm text-slate-500">
          {credentials.length} credential{credentials.length !== 1 ? 's' : ''}
        </span>
      </div>
      {credentials.length === 0 ? (
        <div className="px-5 py-12 text-center text-slate-500 text-sm">
          No credentials found.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Provider
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Credential #
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Issuing Authority
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Expiry Date
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {credentials.map((cred) => (
                <tr
                  key={cred.id}
                  className={`hover:bg-slate-50 transition-colors ${getRowHighlight(cred)}`}
                >
                  <td className="px-5 py-3 font-medium text-slate-800">
                    {cred.provider_name}
                  </td>
                  <td className="px-5 py-3 text-slate-600 capitalize">
                    {cred.credential_type?.replace('_', ' ') || '-'}
                  </td>
                  <td className="px-5 py-3 font-mono text-slate-600">
                    {cred.credential_number || '-'}
                  </td>
                  <td className="px-5 py-3 text-slate-600">
                    {cred.issuing_authority || '-'}
                  </td>
                  <td className="px-5 py-3 text-slate-600">
                    {formatDate(cred.expiry_date)}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block text-xs px-2.5 py-1 rounded-full font-medium ${
                        credentialStatusColors[cred.status] ||
                        'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {formatStatus(cred.status)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
