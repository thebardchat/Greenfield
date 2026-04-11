import { useEffect, useState } from 'react';
import { facilitiesApi } from '../lib/api';
import type { Facility } from '../types';

export default function Facilities() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    facilitiesApi
      .list()
      .then(setFacilities)
      .catch((err) => console.error('Failed to load facilities:', err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        Loading facilities...
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-800">Facilities</h2>
        <span className="text-sm text-slate-500">
          {facilities.length} facilit{facilities.length !== 1 ? 'ies' : 'y'}
        </span>
      </div>
      {facilities.length === 0 ? (
        <div className="px-5 py-12 text-center text-slate-500 text-sm">
          No facilities found.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  City / State
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  NPI
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Phone
                </th>
                <th className="text-left px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {facilities.map((facility) => (
                <tr
                  key={facility.id}
                  className="hover:bg-slate-50 transition-colors"
                >
                  <td className="px-5 py-3 font-medium text-slate-800">
                    {facility.name}
                  </td>
                  <td className="px-5 py-3 text-slate-600 capitalize">
                    {facility.facility_type?.replace('_', ' ') || '-'}
                  </td>
                  <td className="px-5 py-3 text-slate-600">
                    {[facility.city, facility.state]
                      .filter(Boolean)
                      .join(', ') || '-'}
                  </td>
                  <td className="px-5 py-3 font-mono text-slate-600">
                    {facility.npi || '-'}
                  </td>
                  <td className="px-5 py-3 text-slate-600">
                    {facility.phone || '-'}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block text-xs px-2.5 py-1 rounded-full font-medium ${
                        facility.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {facility.is_active ? 'Active' : 'Inactive'}
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
