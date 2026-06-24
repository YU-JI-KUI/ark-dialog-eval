import {
  Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { SectionTitle } from './ui'

const PIE_COLORS = ['#6366f1', '#38bdf8', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#f472b6']

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
  const byGroup = dist?.by_group ?? []
  if (!byIntent.length) return null

  return (
    <div>
      <SectionTitle hint="Judge 给出的意图分布,用于针对性优化某类意图(意图细分类暂作信息项)">
        意图分布
      </SectionTitle>
      <div className="grid gap-4 lg:grid-cols-5">
        {/* 意图柱状图 */}
        <div className="card p-5 lg:col-span-3">
          <div className="mb-3 text-sm text-slate-300">按叶子意图</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byIntent} layout="vertical" margin={{ left: 12, right: 16 }}>
              <XAxis type="number" stroke="#64748b" fontSize={11} allowDecimals={false} />
              <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={11} width={92} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(99,102,241,0.08)' }} />
              <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
                {byIntent.map((_, i) => (
                  <Cell key={i} fill={`url(#barGrad)`} />
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

        {/* 业务大类饼图 */}
        <div className="card p-5 lg:col-span-2">
          <div className="mb-3 text-sm text-slate-300">按业务大类</div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={byGroup} dataKey="count" nameKey="name"
                cx="50%" cy="50%" innerRadius={48} outerRadius={88} paddingAngle={2}
              >
                {byGroup.map((_, i) => (
                  <Cell key={i} stroke="#0f1420" strokeWidth={2} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
            {byGroup.map((g, i) => (
              <div key={g.name} className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                {g.name}
                <span className="tabular-nums text-slate-500">{g.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
