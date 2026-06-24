import { useMemo, useState, useEffect } from 'react'
import { AlertTriangle, ChevronRight, Filter, Search, ChevronLeft } from 'lucide-react'
import clsx from 'clsx'
import { Badge, YesNo, SectionTitle } from './ui'
import DetailDrawer from './DetailDrawer'

const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'disagree', label: '不一致' },
  { key: 'review', label: '需复核' },
]
const PAGE_SIZE = 50

export default function RowsTable({ rows }) {
  const [filter, setFilter] = useState('all')
  const [active, setActive] = useState(null)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    let r = rows
    if (filter === 'disagree') r = r.filter((x) => x.is_disagreement)
    else if (filter === 'review') r = r.filter((x) => x.judge?.needs_human_review)
    if (query.trim()) {
      const q = query.trim()
      r = r.filter((x) => x.question?.includes(q) || x.j_intent?.includes(q) || x.session?.includes(q))
    }
    return r
  }, [rows, filter, query])

  // 切换筛选/搜索时回到第一页
  useEffect(() => { setPage(0) }, [filter, query])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div>
      <div className="flex items-center justify-between">
        <SectionTitle hint="点击任意行查看完整上下文、答案与 Judge 判断">逐条评测明细</SectionTitle>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-lg border border-line bg-ink-850 px-2.5 py-1.5">
            <Search size={13} className="text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜问题/分类/会话"
              className="w-36 bg-transparent text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border border-line bg-ink-850 p-1">
            <Filter size={14} className="ml-1.5 text-slate-500" />
          {FILTERS.map((f) => {
            const count =
              f.key === 'all' ? rows.length
              : f.key === 'disagree' ? rows.filter((r) => r.is_disagreement).length
              : rows.filter((r) => r.judge?.needs_human_review).length
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={clsx(
                  'rounded-md px-3 py-1 text-xs font-medium transition',
                  filter === f.key ? 'bg-brand-600 text-white' : 'text-slate-400 hover:text-slate-200',
                )}
              >
                {f.label}
                <span className="ml-1 tabular-nums opacity-70">{count}</span>
              </button>
            )
          })}
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-slate-500">
              <th className="px-4 py-3 font-medium">会话 / 轮次</th>
              <th className="px-4 py-3 font-medium">客户问题</th>
              <th className="px-4 py-3 font-medium">Judge 业务分类</th>
              <th className="px-4 py-3 font-medium">分发 (判/金)</th>
              <th className="px-4 py-3 font-medium">解决 (判/金)</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {paged.map((r) => (
              <tr
                key={r.row_index}
                onClick={() => setActive(r)}
                className={clsx(
                  'cursor-pointer border-b border-line/50 transition hover:bg-ink-800/50',
                  r.is_disagreement && 'bg-bad-500/[0.04]',
                )}
              >
                <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">
                  <span className="font-mono text-slate-300">{r.session}</span>
                  <span className="ml-1.5 rounded bg-ink-700 px-1.5 py-0.5">第{r.turn}轮</span>
                </td>
                <td className="max-w-xs px-4 py-3">
                  <div className="truncate text-slate-200">{r.question}</div>
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  <Badge tone="brand">{r.j_intent || '—'}</Badge>
                </td>
                <td className="px-4 py-3">
                  <PredGold pred={r.j_dispatch} gold={r.gold?.dispatch} disagree={r.disagree_dispatch} />
                </td>
                <td className="px-4 py-3">
                  <PredGold pred={r.j_resolved} gold={r.gold?.resolved} disagree={r.disagree_resolved} />
                </td>
                <td className="px-2 py-3 text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    {r.judge?.needs_human_review && <AlertTriangle size={14} className="text-warn-400" />}
                    <ChevronRight size={16} className="text-slate-600" />
                  </div>
                </td>
              </tr>
            ))}
            {!filtered.length && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-500">无符合条件的记录</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 分页:3万行不全渲染,每页 50 条 */}
      {filtered.length > PAGE_SIZE && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
          <span>
            共 <span className="tabular-nums text-slate-200">{filtered.length}</span> 条,
            第 {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} 条
          </span>
          <div className="flex items-center gap-1">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="flex items-center gap-1 rounded-md border border-line bg-ink-850 px-2.5 py-1 transition hover:text-slate-200 disabled:opacity-40"
            >
              <ChevronLeft size={13} />上一页
            </button>
            <span className="px-2 tabular-nums">{page + 1} / {pageCount}</span>
            <button
              disabled={page >= pageCount - 1}
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              className="flex items-center gap-1 rounded-md border border-line bg-ink-850 px-2.5 py-1 transition hover:text-slate-200 disabled:opacity-40"
            >
              下一页<ChevronRight size={13} />
            </button>
          </div>
        </div>
      )}

      <DetailDrawer row={active} onClose={() => setActive(null)} />
    </div>
  )
}

// 判定 vs 金标 并排展示,不一致时高亮
function PredGold({ pred, gold, disagree }) {
  return (
    <div className={clsx('inline-flex items-center gap-1.5 rounded-md px-1', disagree && 'ring-1 ring-bad-500/40')}>
      <YesNo value={pred} />
      <span className="text-slate-600">/</span>
      {gold === '是' || gold === '否'
        ? <span className={clsx('text-xs', gold === '是' ? 'text-good-400' : 'text-bad-400')}>{gold}</span>
        : <span className="text-xs text-slate-600">—</span>}
    </div>
  )
}
