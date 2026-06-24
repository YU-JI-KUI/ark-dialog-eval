import { Loader2 } from 'lucide-react'
import { ProgressBar } from './ui'

const STAGE_LABEL = {
  loading: '读取与解析 Excel',
  loaded: '样本构造完成',
  judging: 'LLM Judge 评测中',
  advising: '生成优化建议中',
  done: '完成',
}

export default function RunProgress({ task }) {
  const stage = STAGE_LABEL[task.stage] || '准备中'
  return (
    <div className="mx-auto max-w-xl">
      <div className="card p-8 text-center animate-fade-up">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/10">
          <Loader2 size={26} className="animate-spin text-brand-400" />
        </div>
        <div className="mt-4 text-lg font-medium text-slate-100">正在评测</div>
        <div className="mt-1 text-sm text-slate-500">{task.filename}</div>

        <div className="mt-6">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-slate-400">{stage}</span>
            <span className="tabular-nums text-brand-400">{task.progress_pct}%</span>
          </div>
          <ProgressBar pct={task.progress_pct} />
          {task.progress_total > 0 && (
            <div className="mt-2 text-xs text-slate-500">
              {task.progress_done} / {task.progress_total} 条样本
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
