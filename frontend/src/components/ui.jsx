import clsx from 'clsx'

// 顶部统计卡
export function StatCard({ label, value, sub, tone = 'brand', icon: Icon }) {
  const tones = {
    brand: 'text-brand-400',
    good: 'text-good-400',
    warn: 'text-warn-400',
    bad: 'text-bad-400',
    info: 'text-info-400',
  }
  return (
    <div className="card p-5 animate-fade-up">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-400">{label}</span>
        {Icon && <Icon size={18} className={tones[tone]} />}
      </div>
      <div className={clsx('mt-2 text-3xl font-semibold tabular-nums', tones[tone])}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

// 是/否/状态徽章
export function Badge({ children, tone = 'slate' }) {
  const tones = {
    slate: 'bg-ink-700 text-slate-300 border-line',
    good: 'bg-good-500/15 text-good-400 border-good-500/30',
    warn: 'bg-warn-500/15 text-warn-400 border-warn-500/30',
    bad: 'bg-bad-500/15 text-bad-400 border-bad-500/30',
    brand: 'bg-brand-500/15 text-brand-400 border-brand-500/30',
    info: 'bg-info-400/15 text-info-400 border-info-400/30',
  }
  return (
    <span className={clsx('inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium', tones[tone])}>
      {children}
    </span>
  )
}

// 是/否 -> 带色徽章
export function YesNo({ value, goodWhenYes = true }) {
  if (value !== '是' && value !== '否') return <span className="text-slate-600">—</span>
  const isYes = value === '是'
  const positive = goodWhenYes ? isYes : !isYes
  return <Badge tone={positive ? 'good' : 'bad'}>{value}</Badge>
}

// 进度条
export function ProgressBar({ pct, tone = 'brand' }) {
  const bg = { brand: 'bg-brand-500', good: 'bg-good-500', warn: 'bg-warn-500' }[tone]
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-ink-700">
      <div className={clsx('h-full rounded-full transition-all duration-500', bg)} style={{ width: `${pct}%` }} />
    </div>
  )
}

// 段落标题
export function SectionTitle({ children, hint }) {
  return (
    <div className="mb-4 flex items-baseline gap-3">
      <h2 className="text-lg font-semibold text-slate-100">{children}</h2>
      {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </div>
  )
}

// 指标好坏的颜色映射(κ / F1 阈值)
export function metricTone(v) {
  if (v >= 0.8) return 'good'
  if (v >= 0.6) return 'brand'
  if (v >= 0.4) return 'warn'
  return 'bad'
}
