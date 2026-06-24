import { Lightbulb, AlertOctagon, AlertTriangle, Info, Cpu, FileText } from 'lucide-react'
import clsx from 'clsx'
import { SectionTitle, Badge } from './ui'

const SEVERITY = {
  high: { tone: 'bad', icon: AlertOctagon, label: '高' },
  medium: { tone: 'warn', icon: AlertTriangle, label: '中' },
  low: { tone: 'info', icon: Info, label: '低' },
}

const ROOT_CAUSE_TONE = {
  分发问题: 'bad',
  答案问题: 'warn',
  数据问题: 'info',
  需人工: 'brand',
}

export default function AdvicePanel({ advice }) {
  if (!advice?.items?.length) {
    return (
      <div>
        <SectionTitle>优化建议</SectionTitle>
        <div className="card p-6 text-sm text-slate-400">
          暂无明显需优化的点(各意图样本量不足或指标均健康)。
        </div>
      </div>
    )
  }
  const fromModel = advice.source === 'model'
  return (
    <div>
      <div className="flex items-center justify-between">
        <SectionTitle hint="基于业务洞察聚合指标自动生成,按严重度排序">优化建议</SectionTitle>
        <Badge tone={fromModel ? 'good' : 'slate'}>
          {fromModel ? <Cpu size={11} className="mr-1 inline" /> : <FileText size={11} className="mr-1 inline" />}
          {fromModel ? '大模型生成' : '规则生成'}
        </Badge>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {advice.items.map((a, i) => {
          const sev = SEVERITY[a.severity] || SEVERITY.low
          const SevIcon = sev.icon
          return (
            <div
              key={i}
              className={clsx(
                'card animate-fade-up p-4',
                a.severity === 'high' && 'border-bad-500/30',
              )}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-start gap-3">
                <div className={clsx(
                  'mt-0.5 rounded-lg p-2',
                  a.severity === 'high' ? 'bg-bad-500/15' : a.severity === 'medium' ? 'bg-warn-500/15' : 'bg-info-400/15',
                )}>
                  <SevIcon size={16} className={clsx(
                    a.severity === 'high' ? 'text-bad-400' : a.severity === 'medium' ? 'text-warn-400' : 'text-info-400',
                  )} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-100">{a.scope}</span>
                    <Badge tone={sev.tone}>{sev.label}优先级</Badge>
                    {a.root_cause && <Badge tone={ROOT_CAUSE_TONE[a.root_cause] || 'slate'}>{a.root_cause}</Badge>}
                  </div>
                  <div className="mt-1.5 text-sm text-slate-300">{a.problem}</div>
                  <div className="mt-2 flex gap-2 rounded-lg bg-ink-800/50 px-3 py-2">
                    <Lightbulb size={14} className="mt-0.5 shrink-0 text-brand-400" />
                    <span className="text-xs leading-relaxed text-slate-300">{a.suggestion}</span>
                  </div>
                  {a.evidence && (
                    <div className="mt-1.5 text-[11px] text-slate-500">依据:{a.evidence}</div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
