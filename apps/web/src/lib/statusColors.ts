import type { ClaimStatus } from '../types';

export const claimStatusColors: Record<ClaimStatus, string> = {
  submitted: 'bg-gray-100 text-gray-700',
  ocr_processing: 'bg-yellow-100 text-yellow-700',
  ocr_failed: 'bg-red-100 text-red-700',
  ready_for_review: 'bg-blue-100 text-blue-700',
  in_progress: 'bg-indigo-100 text-indigo-700',
  coded: 'bg-purple-100 text-purple-700',
  billed: 'bg-cyan-100 text-cyan-700',
  paid: 'bg-green-100 text-green-700',
  denied: 'bg-red-100 text-red-700',
  appealed: 'bg-orange-100 text-orange-700',
  void: 'bg-gray-100 text-gray-500',
};

export const ticketStatusColors: Record<string, string> = {
  open: 'bg-blue-100 text-blue-700',
  in_progress: 'bg-indigo-100 text-indigo-700',
  waiting: 'bg-yellow-100 text-yellow-700',
  resolved: 'bg-green-100 text-green-700',
  closed: 'bg-gray-100 text-gray-500',
};

export const ticketTypeColors: Record<string, string> = {
  coding_query: 'bg-purple-100 text-purple-700',
  missing_info: 'bg-orange-100 text-orange-700',
  denial_review: 'bg-red-100 text-red-700',
  credentialing: 'bg-cyan-100 text-cyan-700',
  general: 'bg-gray-100 text-gray-700',
};

export const priorityColors: Record<string, string> = {
  low: 'text-slate-500',
  medium: 'text-blue-600',
  high: 'text-orange-600 font-semibold',
  urgent: 'text-red-600 font-bold',
};

export const credentialStatusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  expiring_soon: 'bg-yellow-100 text-yellow-700',
  expired: 'bg-red-100 text-red-700',
  pending: 'bg-blue-100 text-blue-700',
  revoked: 'bg-gray-100 text-gray-500',
};

// Valid transitions for each claim status
export const validTransitions: Record<ClaimStatus, ClaimStatus[]> = {
  submitted: ['ocr_processing', 'void'],
  ocr_processing: ['ready_for_review', 'ocr_failed'],
  ocr_failed: ['submitted', 'ready_for_review', 'void'],
  ready_for_review: ['in_progress', 'void'],
  in_progress: ['coded', 'ready_for_review', 'void'],
  coded: ['billed', 'in_progress', 'void'],
  billed: ['paid', 'denied', 'void'],
  paid: [],
  denied: ['appealed', 'void'],
  appealed: ['billed', 'denied', 'void'],
  void: [],
};

export function formatStatus(status: string): string {
  return status
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function formatCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}
