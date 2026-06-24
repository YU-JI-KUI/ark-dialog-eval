import { SectionTitle, metricTone } from './ui'
import clsx from 'clsx'

// 单个二值金标的指标卡:κ / 准确率 / 宏F1 + 混淆矩阵 + 分类别 P/R/F1
function MetricCard({ m }) {
  const tone = metricTone(m.kappa)
  const toneText = {
    good: 'text-good-400', brand: 'text-brand-400', warn: 'text-warn-400', bad: 'text-bad-400',
  }[tone]
  const toneBorder = {
    good: 'border-good-500/30', brand: 'border-brand-500/30',
    warn: 'border-warn-500/30', bad: 'border-bad-500/30',
  }[tone]
  const cm = m.confusion_matrix // [[真是→预是,真是→预否],[真否→预是,真否→预否]]

  return (
    <div className={clsx('card animate-fade-up overflow-hidden border p-5', toneBorder)}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-medium text-slate-200">{m.name}</div>
          <div className="mt-0.5 text-xs text-slate-500">有效金标样本 n = {m.n}</div>
        </div>
        <div className="text-right">
          <div className={clsx('text-3xl font-bold tabular-nums', toneText)}>{m.kappa.toFixed(3)}</div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Cohen's κ</div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-ink-800/60 p-3">
          <div className="text-xs text-slate-500">准确率</div>
          <div className="mt-0.5 text-xl font-semibold tabular-nums text-slate-100">
            {(m.accuracy * 100).toFixed(1)}%
          </div>
        </div>
        <div className="rounded-lg bg-ink-800/60 p-3">
          <div className="text-xs text-slate-500">宏平均 F1</div>
          <div className="mt-0.5 text-xl font-semibold tabular-nums text-slate-100">
            {m.macro_f1.toFixed(3)}
          </div>
        </div>
      </div>

      {/* 混淆矩阵 */}
      <div className="mt-4">
        <div className="mb-1.5 text-xs text-slate-500">混淆矩阵</div>
        <div className="grid grid-cols-[auto_1fr_1fr] gap-1 text-center text-xs">
          <div></div>
          <div className="text-slate-500">预测·是</div>
          <div className="text-slate-500">预测·否</div>
          <ConfRowLabel>真·是</ConfRowLabel>
          <ConfCell v={cm[0][0]} diag /><ConfCell v={cm[0][1]} />
          <ConfRowLabel>真·否</ConfRowLabel>
          <ConfCell v={cm[1][0]} /><ConfCell v={cm[1][1]} diag />
        </div>
      </div>

      {/* 分类别 P/R/F1 */}
      <div className="mt-4 space-y-1.5">
        {Object.entries(m.per_label).map(([lab, s]) => (
          <div key={lab} className="flex items-center gap-2 text-xs">
            <span className="w-8 shrink-0 text-slate-400">{lab}</span>
            <MiniBar label="P" v={s.precision} />
            <MiniBar label="R" v={s.recall} />
            <MiniBar label="F1" v={s.f1} />
          </div>
        ))}
      </div>
    </div>
  )
}

function ConfRowLabel({ children }) {
  return <div className="flex items-center justify-end pr-1 text-slate-500">{children}</div>
}
function ConfCell({ v, diag }) {
  return (
    <div className={clsx(
      'rounded-md py-2 font-semibold tabular-nums',
      diag ? 'bg-brand-500/20 text-brand-300' : v > 0 ? 'bg-bad-500/15 text-bad-300' : 'bg-ink-800/60 text-slate-600',
    )}>
      {v}
    </div>
  )
}
function MiniBar({ label, v }) {
  return (
    <div className="flex flex-1 items-center gap-1">
      <span className="w-4 text-slate-600">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
        <div className="h-full rounded-full bg-brand-500/70" style={{ width: `${v * 100}%` }} />
      </div>
      <span className="w-9 text-right tabular-nums text-slate-400">{v.toFixed(2)}</span>
    </div>
  )
}

export default function MetricsPanel({ metrics }) {
  if (!metrics?.length) {
    return (
      <div className="card p-6 text-sm text-slate-400">
        当前数据没有可用的二值人工金标,无法计算校准指标。
      </div>
    )
  }
  return (
    <div>
      <SectionTitle hint="对人工金标算 准/召/F1 + 混淆矩阵 + Cohen's κ;κ≥0.6 视为可信">
        校准指标
      </SectionTitle>
      <div className="grid gap-4 lg:grid-cols-3">
        {metrics.map((m) => <MetricCard key={m.name} m={m} />)}
      </div>
    </div>
  )
}
