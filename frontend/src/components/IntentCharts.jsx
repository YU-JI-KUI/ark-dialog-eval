import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { SectionTitle } from './ui'

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <div className="rounded-lg border border-line bg-ink-900/95 px-3 py-2 text-xs shadow-xl">
      <div className="font-medium text-slate-200">{p.payload.name}</div>
      <div className="text-slate-400">数量:<span className="tabular-nums text-brand-400">{p.value}</span></div>
    </div>
  )
}

export default function IntentCharts({ dist }) {
  const byIntent = dist?.by_intent ?? []
  if (!byIntent.length) return null

  return (
    <div>
      <SectionTitle hint="Judge 给出的业务分类分布,用于针对性优化某类业务">
        业务分类分布
      </SectionTitle>
      <div className="card p-5">
        <ResponsiveContainer width="100%" height={Math.max(260, byIntent.length * 28)}>
          <BarChart data={byIntent} layout="vertical" margin={{ left: 12, right: 16 }}>
            <XAxis type="number" stroke="#64748b" fontSize={11} allowDecimals={false} />
            <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={11} width={140} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(99,102,241,0.08)' }} />
            <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
              {byIntent.map((_, i) => (
                <Cell key={i} fill="url(#barGrad)" />
              ))}
            </Bar>
            <defs>
              <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#4f46e5" />
                <stop offset="100%" stopColor="#818cf8" />
              </linearGradient>
            </defs>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
