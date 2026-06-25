import { useEffect, useState } from 'react'
import { X, History, Building2, FileSpreadsheet, Clock, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { Badge } from './ui'
import { api } from '../api/client'
import { formatTime } from '../utils/format'

// 历史评测记录:从 SQLite 拉所有任务,点击加载该次结果
export default function HistoryPanel({ open, onClose, onSelect }) {
  const [tasks, setTasks] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!open) return
    setTasks(null)
    setError(null)
    api.listTasks().then(setTasks).catch((e) => setError(e?.message || '加载失败'))
  }, [open])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const done = (tasks || []).filter((t) => t.status === 'done')

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-line bg-ink-900 shadow-2xl animate-fade-up">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div className="flex items-center gap-2">
            <History size={18} className="text-brand-400" />
            <h3 className="text-base font-semibold text-slate-100">历史评测记录</h3>
            {tasks && <Badge tone="slate">{done.length}</Badge>}
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-ink-700 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-2 overflow-y-auto px-4 py-4">
          {tasks === null && !error && (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
              <Loader2 size={16} className="animate-spin" />加载中…
            </div>
          )}
          {error && <div className="py-16 text-center text-sm text-bad-400">{error}</div>}
          {tasks && !done.length && !error && (
            <div className="py-16 text-center text-sm text-slate-500">暂无已完成的评测记录</div>
          )}
          {done.map((t) => (
            <button
              key={t.task_id}
              onClick={() => onSelect(t.task_id)}
              className="flex w-full flex-col gap-1.5 rounded-xl border border-line bg-ink-850/60 px-4 py-3 text-left transition hover:border-brand-500/40 hover:bg-ink-800"
            >
              <div className="flex items-center gap-2">
                <FileSpreadsheet size={14} className="shrink-0 text-slate-400" />
                <span className="truncate text-sm font-medium text-slate-100">{t.filename}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <Building2 size={12} />{t.bu_name}
                </span>
                <Badge tone={t.mode === 'calibration' ? 'info' : 'good'}>
                  {t.mode === 'calibration' ? '校准' : '生产'}
                </Badge>
                <span className="inline-flex items-center gap-1">
                  <Clock size={12} />{formatTime(t.finished_at || t.created_at)}
                </span>
              </div>
            </button>
          ))}
        </div>
      </aside>
    </>
  )
}
