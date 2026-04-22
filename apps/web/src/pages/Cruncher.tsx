import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  SparklesIcon,
  PaperAirplaneIcon,
  XMarkIcon,
  ExclamationTriangleIcon,
  TicketIcon,
  MagnifyingGlassIcon,
  FlagIcon,
  DocumentMagnifyingGlassIcon,
  ClipboardDocumentCheckIcon,
} from '@heroicons/react/24/outline';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type MessageRole = 'user' | 'assistant' | 'system';

interface ToolEvent {
  type: 'flag' | 'ticket' | 'search' | 'fetch' | 'analyze';
  label: string;
}

interface Message {
  id: string;
  role: MessageRole;
  content: string;
  toolEvents?: ToolEvent[];
  timestamp: Date;
}

interface AnalyzeResult {
  claim_id: string;
  flags: { reason: string; priority: number; ticket_created: boolean }[];
  analysis: string;
  tickets_created: number;
  model_used: string;
}

interface DenialResult {
  claim_id: string;
  root_cause: string;
  disputable: boolean | null;
  dispute_likelihood: string;
  appeal_strategy: string;
  appeal_steps: string[];
  appeal_letter_language: string;
  documentation_needed: string[];
  timely_filing_deadline: string | null;
}

// ---------------------------------------------------------------------------
// Tool event label helpers
// ---------------------------------------------------------------------------

const TOOL_LABELS: Record<string, { icon: React.FC<{ className?: string }>; label: string; type: ToolEvent['type'] }> = {
  get_claim: { icon: DocumentMagnifyingGlassIcon, label: 'Fetching claim data', type: 'fetch' },
  get_claim_lines: { icon: DocumentMagnifyingGlassIcon, label: 'Loading service lines', type: 'fetch' },
  get_patient_claim_history: { icon: MagnifyingGlassIcon, label: 'Checking patient history', type: 'search' },
  get_claim_documents: { icon: DocumentMagnifyingGlassIcon, label: 'Loading documents', type: 'fetch' },
  flag_claim: { icon: FlagIcon, label: 'Flagging claim', type: 'flag' },
  create_ticket: { icon: TicketIcon, label: 'Creating work ticket', type: 'ticket' },
  search_similar_claims: { icon: MagnifyingGlassIcon, label: 'Searching similar claims', type: 'search' },
};

const toolBadgeColors: Record<ToolEvent['type'], string> = {
  flag: 'bg-red-50 text-red-700 border-red-200',
  ticket: 'bg-blue-50 text-blue-700 border-blue-200',
  search: 'bg-purple-50 text-purple-700 border-purple-200',
  fetch: 'bg-slate-50 text-slate-600 border-slate-200',
  analyze: 'bg-amber-50 text-amber-700 border-amber-200',
};

// ---------------------------------------------------------------------------
// Parse SSE stream and detect tool-call indicators from text
// ---------------------------------------------------------------------------

function detectToolEvent(chunk: string): ToolEvent | null {
  for (const [key, val] of Object.entries(TOOL_LABELS)) {
    if (chunk.toLowerCase().includes(key.replace(/_/g, ' ')) ||
        chunk.toLowerCase().includes(key)) {
      return { type: val.type, label: val.label };
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Markdown-lite renderer (bold, code, lists — no heavy dep)
// ---------------------------------------------------------------------------

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith('## ')) {
      elements.push(<h3 key={i} className="text-base font-semibold text-slate-800 mt-3 mb-1">{line.slice(3)}</h3>);
    } else if (line.startsWith('# ')) {
      elements.push(<h2 key={i} className="text-lg font-bold text-slate-800 mt-3 mb-1">{line.slice(2)}</h2>);
    } else if (line.startsWith('- ') || line.startsWith('• ')) {
      elements.push(
        <li key={i} className="ml-4 list-disc text-sm">
          {renderInline(line.slice(2))}
        </li>
      );
    } else if (/^\d+\. /.test(line)) {
      elements.push(
        <li key={i} className="ml-4 list-decimal text-sm">
          {renderInline(line.replace(/^\d+\. /, ''))}
        </li>
      );
    } else if (line.trim() === '') {
      elements.push(<div key={i} className="h-2" />);
    } else {
      elements.push(<p key={i} className="text-sm leading-relaxed">{renderInline(line)}</p>);
    }
    i++;
  }
  return <>{elements}</>;
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

// ---------------------------------------------------------------------------
// Cruncher page
// ---------------------------------------------------------------------------

const API_BASE = '/api';
const getToken = () => localStorage.getItem('access_token') || '';

export default function Cruncher() {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hi — I'm Cruncher, your AI billing assistant. I can review claims, look up CPT and ICD codes, analyze denials, and help you draft appeal letters.\n\nPaste a Claim ID above to focus on a specific claim, or just ask me anything.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [claimId, setClaimId] = useState(searchParams.get('claim_id') || '');
  const action = searchParams.get('action');

  // Auto-trigger action from URL params (e.g. from ClaimDetail "Auto-flag" button)
  useEffect(() => {
    if (action === 'analyze' && claimId) {
      // Small delay so component finishes mounting
      const t = setTimeout(handleAnalyzeClaim, 300);
      return () => clearTimeout(t);
    }
    if (action === 'denial' && claimId) {
      setDenialMode(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [streaming, setStreaming] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null);
  const [denialMode, setDenialMode] = useState(false);
  const [denialReason, setDenialReason] = useState('');
  const [denialResult, setDenialResult] = useState<DenialResult | null>(null);
  const [denialLoading, setDenialLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ---------------------------------------------------------------------------
  // Send chat message (SSE streaming)
  // ---------------------------------------------------------------------------

  const send = async () => {
    const text = input.trim();
    if (!text || streaming) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    const assistantId = `a-${Date.now()}`;
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      toolEvents: [],
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInput('');
    setStreaming(true);

    try {
      const resp = await fetch(`${API_BASE}/cruncher/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          message: text,
          claim_id: claimId || null,
          include_rag: true,
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') break;
          if (data.startsWith('[ERROR]')) {
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: m.content + `\n\n⚠️ ${data.slice(8)}` }
                  : m
              )
            );
            break;
          }

          const chunk = data.replace(/\\n/g, '\n');
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== assistantId) return m;
              const toolEvent = detectToolEvent(chunk);
              return {
                ...m,
                content: m.content + chunk,
                toolEvents: toolEvent
                  ? [...(m.toolEvents || []), toolEvent]
                  : m.toolEvents,
              };
            })
          );
        }
      }
    } catch (err) {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: m.content || '⚠️ Connection error. Please try again.' }
            : m
        )
      );
    } finally {
      setStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  // ---------------------------------------------------------------------------
  // Analyze claim (auto-flag)
  // ---------------------------------------------------------------------------

  const handleAnalyzeClaim = async () => {
    if (!claimId.trim() || analyzing) return;
    setAnalyzing(true);
    setAnalyzeResult(null);
    try {
      const resp = await fetch(`${API_BASE}/cruncher/analyze-claim/${claimId.trim()}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setAnalyzeResult(data);

      // Add result as a system message
      const summary =
        data.flags.length === 0
          ? '✅ AI analysis complete — no issues detected. Claim looks clean.'
          : `⚠️ AI found ${data.flags.length} issue${data.flags.length > 1 ? 's' : ''} — ${data.tickets_created} ticket${data.tickets_created !== 1 ? 's' : ''} created.`;
      setMessages(prev => [
        ...prev,
        {
          id: `sys-${Date.now()}`,
          role: 'system',
          content: summary,
          timestamp: new Date(),
        },
      ]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: `sys-err-${Date.now()}`,
          role: 'system',
          content: '⚠️ Claim analysis failed. Check that the claim ID is valid.',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setAnalyzing(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Denial analysis
  // ---------------------------------------------------------------------------

  const handleDenialAnalysis = async () => {
    if (!claimId.trim() || !denialReason.trim() || denialLoading) return;
    setDenialLoading(true);
    setDenialResult(null);
    try {
      const resp = await fetch(`${API_BASE}/cruncher/denial-analysis/${claimId.trim()}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ denial_reason: denialReason }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setDenialResult(data);
    } catch {
      setDenialResult(null);
    } finally {
      setDenialLoading(false);
    }
  };

  const likelihoodColor: Record<string, string> = {
    high: 'text-green-600 bg-green-50',
    medium: 'text-amber-600 bg-amber-50',
    low: 'text-red-600 bg-red-50',
    unknown: 'text-slate-500 bg-slate-50',
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full max-h-[calc(100vh-9rem)] gap-4">

      {/* Top bar — claim context + actions */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col sm:flex-row gap-3 items-start sm:items-center shrink-0">
        <div className="flex items-center gap-2 text-blue-600 shrink-0">
          <SparklesIcon className="w-5 h-5" />
          <span className="font-semibold text-sm">Cruncher AI</span>
        </div>
        <div className="flex-1 flex flex-col sm:flex-row gap-2 w-full">
          <input
            type="text"
            placeholder="Claim ID (optional — focus the conversation on a specific claim)"
            value={claimId}
            onChange={e => setClaimId(e.target.value)}
            className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
          />
          <div className="flex gap-2 shrink-0">
            <button
              onClick={handleAnalyzeClaim}
              disabled={!claimId.trim() || analyzing}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ClipboardDocumentCheckIcon className="w-4 h-4" />
              {analyzing ? 'Analyzing…' : 'Analyze'}
            </button>
            <button
              onClick={() => setDenialMode(!denialMode)}
              disabled={!claimId.trim()}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                denialMode
                  ? 'bg-red-100 text-red-700 border border-red-200'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <ExclamationTriangleIcon className="w-4 h-4" />
              Denial Analysis
            </button>
          </div>
        </div>
      </div>

      {/* Denial analysis form */}
      {denialMode && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 shrink-0 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm text-red-800 flex items-center gap-2">
              <ExclamationTriangleIcon className="w-4 h-4" />
              Denial Analysis — Claim {claimId}
            </h3>
            <button onClick={() => { setDenialMode(false); setDenialResult(null); }} className="text-red-400 hover:text-red-600">
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Paste denial reason from EOB or remittance…"
              value={denialReason}
              onChange={e => setDenialReason(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleDenialAnalysis()}
              className="flex-1 text-sm border border-red-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-red-400"
            />
            <button
              onClick={handleDenialAnalysis}
              disabled={!denialReason.trim() || denialLoading}
              className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {denialLoading ? 'Analyzing…' : 'Analyze'}
            </button>
          </div>

          {denialResult && (
            <div className="bg-white rounded-lg border border-red-100 divide-y divide-red-50 text-sm">
              {/* Header */}
              <div className="p-4 flex items-start justify-between gap-4">
                <div>
                  <div className="font-semibold text-slate-800">{denialResult.root_cause}</div>
                  <div className="text-slate-500 text-xs mt-0.5">Root cause</div>
                </div>
                <div className="shrink-0 flex flex-col items-end gap-1">
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                    denialResult.disputable ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {denialResult.disputable ? 'Disputable' : 'Not disputable'}
                  </span>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                    likelihoodColor[denialResult.dispute_likelihood] || likelihoodColor.unknown
                  }`}>
                    {denialResult.dispute_likelihood} success likelihood
                  </span>
                </div>
              </div>

              {/* Appeal steps */}
              {denialResult.appeal_steps.length > 0 && (
                <div className="p-4">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Appeal Steps</div>
                  <ol className="space-y-1">
                    {denialResult.appeal_steps.map((step, i) => (
                      <li key={i} className="flex gap-2 text-slate-700">
                        <span className="font-mono text-xs text-slate-400 shrink-0 mt-0.5">{i + 1}.</span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* Documentation needed */}
              {denialResult.documentation_needed.length > 0 && (
                <div className="p-4">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Documentation Needed</div>
                  <ul className="space-y-1">
                    {denialResult.documentation_needed.map((doc, i) => (
                      <li key={i} className="flex gap-2 text-slate-700">
                        <span className="text-slate-400">•</span>
                        <span>{doc}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Letter language */}
              {denialResult.appeal_letter_language && (
                <div className="p-4">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Appeal Letter Language</div>
                  <div className="bg-slate-50 rounded-md p-3 text-slate-700 text-xs font-mono leading-relaxed whitespace-pre-wrap">
                    {denialResult.appeal_letter_language}
                  </div>
                  <button
                    onClick={() => navigator.clipboard.writeText(denialResult.appeal_letter_language)}
                    className="mt-2 text-xs text-blue-600 hover:text-blue-700"
                  >
                    Copy to clipboard
                  </button>
                </div>
              )}

              {denialResult.timely_filing_deadline && (
                <div className="p-4 text-xs text-amber-700">
                  ⏰ Timely filing deadline: {denialResult.timely_filing_deadline}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Analyze result banner */}
      {analyzeResult && analyzeResult.flags.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 shrink-0">
          <div className="flex items-center justify-between mb-3">
            <div className="font-semibold text-sm text-amber-800 flex items-center gap-2">
              <ExclamationTriangleIcon className="w-4 h-4" />
              {analyzeResult.flags.length} Issue{analyzeResult.flags.length !== 1 ? 's' : ''} Found
              {analyzeResult.tickets_created > 0 && (
                <span className="ml-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                  {analyzeResult.tickets_created} ticket{analyzeResult.tickets_created !== 1 ? 's' : ''} created
                </span>
              )}
            </div>
            <button onClick={() => setAnalyzeResult(null)} className="text-amber-400 hover:text-amber-600">
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-2">
            {analyzeResult.flags.map((flag, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className={`shrink-0 text-xs px-1.5 py-0.5 rounded font-mono font-medium ${
                  flag.priority >= 4 ? 'bg-red-100 text-red-700' :
                  flag.priority >= 3 ? 'bg-amber-100 text-amber-700' :
                  'bg-slate-100 text-slate-600'
                }`}>P{flag.priority}</span>
                <span className="text-slate-700">{flag.reason}</span>
                {flag.ticket_created && (
                  <TicketIcon className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto bg-white rounded-xl border border-slate-200 min-h-0">
        <div className="p-4 space-y-4">
          {messages.map(msg => {
            if (msg.role === 'system') {
              return (
                <div key={msg.id} className="flex justify-center">
                  <div className="text-xs bg-slate-100 text-slate-500 px-3 py-1.5 rounded-full">
                    {msg.content}
                  </div>
                </div>
              );
            }

            if (msg.role === 'user') {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
                    {msg.content}
                  </div>
                </div>
              );
            }

            // Assistant
            return (
              <div key={msg.id} className="flex gap-3 items-start">
                <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0 mt-0.5">
                  <SparklesIcon className="w-4 h-4 text-blue-600" />
                </div>
                <div className="flex-1 min-w-0">
                  {/* Tool event badges */}
                  {msg.toolEvents && msg.toolEvents.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {msg.toolEvents.map((evt, i) => {
                        const meta = Object.values(TOOL_LABELS).find(t => t.type === evt.type);
                        const Icon = meta?.icon;
                        return (
                          <span key={i} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${toolBadgeColors[evt.type]}`}>
                            {Icon && <Icon className="w-3 h-3" />}
                            {evt.label}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  <div className="bg-slate-50 rounded-2xl rounded-tl-sm px-4 py-3 text-slate-800 space-y-1">
                    {msg.content
                      ? renderMarkdown(msg.content)
                      : <span className="text-slate-400 animate-pulse">Thinking…</span>
                    }
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 flex gap-3 items-end shrink-0">
        <textarea
          ref={inputRef}
          rows={2}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          placeholder="Ask about CPT codes, review a claim, explain a denial… (Enter to send, Shift+Enter for new line)"
          className="flex-1 resize-none text-sm border-0 focus:outline-none focus:ring-0 text-slate-700 placeholder-slate-400 bg-transparent"
        />
        <button
          onClick={send}
          disabled={!input.trim() || streaming}
          className="flex items-center justify-center w-9 h-9 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
        >
          {streaming
            ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            : <PaperAirplaneIcon className="w-4 h-4" />
          }
        </button>
      </div>
    </div>
  );
}
