import { useState } from 'react'
import clsx from 'clsx'
import { SectionTitle } from './ui'

// 比率色条:解决率/分发准确率,绿好红差
function RateBar({ value, dangerLow = true }) {
  const pct = Math.round(value * 100)
  const tone = value >= 0.8 ? 'bg-good-500' : value >= 0.6 ? 'bg-warn-500' : 'bg-bad-500'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-ink-700">
        <div className={clsx('h-full rounded-full', dangerLow ? tone : 'bg-brand-500')} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-9 text-right text-xs tabular-nums text-slate-300">{pct}%</span>
    </div>
  )
}

function SliceTable({ slices, dim }) {
  const [sortKey, setSortKey] = useState('count')
  const sorted = [...slices].sort((a, b) => {
    if (sortKey === 'count') return b.count - a.count
    if (sortKey === 'resolved') return a.resolved_rate - b.resolved_rate // 差的在前
    return 0
  })
  const Th = ({ k, children, className }) => (
    <th
      className={clsx('cursor-pointer px-4 py-2.5 font-medium transition hover:text-slate-200', className)}
      onClick={() => setSortKey(k)}
    >
      {children}
      {sortKey === k && <span className="ml-1 text-brand-400">↓</span>}
    </th>
  )
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-slate-500">
            <th className="px-4 py-2.5 font-medium">{dim}</th>
            <Th k="count">样本量</Th>
            <th className="px-4 py-2.5 font-medium">进漏斗(分发到本BU)</th>
            <Th k="resolved">端到端解决率</Th>
            <th className="px-4 py-2.5 font-medium">需复核率</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={s.name} className="border-b border-line/50 transition hover:bg-ink-800/40">
              <td className="px-4 py-2.5">
                <span className="font-medium text-slate-200">{s.name}</span>
              </td>
              <td className="px-4 py-2.5 tabular-nums text-slate-400">{s.count}</td>
              <td className="px-4 py-2.5 tabular-nums text-slate-400">{s.in_bu_count ?? '—'}</td>
              <td className="px-4 py-2.5">
                {s.in_bu_count > 0 ? <RateBar value={s.resolved_rate} /> : <span className="text-xs text-slate-600">不在漏斗</span>}
              </td>
              <td className="px-4 py-2.5">
                <span className={clsx(
                  'text-xs tabular-nums',
                  s.needs_review_rate >= 0.4 ? 'text-warn-400' : 'text-slate-500',
                )}>
                  {Math.round(s.needs_review_rate * 100)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function InsightsPanel({ insights }) {
  const [dim, setDim] = useState('intent')
  if (!insights) return null
  const slices = dim === 'intent' ? insights.by_intent : insights.by_group
  return (
    <div>
      <div className="flex items-center justify-between">
        <SectionTitle hint="端到端解决率(仅分发到本BU的问题),点表头按差的排序,定位优化重点">
          业务洞察
        </SectionTitle>
        <div className="flex gap-1 rounded-lg border border-line bg-ink-850 p-1">
          {[['intent', '按意图'], ['group', '按业务大类']].map(([k, label]) => (
            <button
              key={k}
              onClick={() => setDim(k)}
              className={clsx(
                'rounded-md px-3 py-1 text-xs font-medium transition',
                dim === k ? 'bg-brand-600 text-white' : 'text-slate-400 hover:text-slate-200',
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <SliceTable slices={slices} dim={dim === 'intent' ? '意图' : '业务大类'} />
    </div>
  )
}
