import { useRef, useState } from 'react'
import { UploadCloud, FileSpreadsheet, ShieldCheck, TrendingUp, Building2 } from 'lucide-react'
import clsx from 'clsx'

// 评测流水线(上传什么评什么,不过滤;答案原文进 LLM,不代码解析)
const PIPELINE = [
  ['会话重组', '按会话ID分组、按轮次排序拼上下文'],
  ['LLM Judge', 'BU分发 + 答案解决度 + 业务分类(答案原文进上下文)'],
  ['漏斗聚合', 'BU分发准确率 + 端到端解决率(按业务分类切片)'],
  ['优化建议', '基于聚合指标给针对性改进方向'],
  ['校准对齐', '有人工金标时算 准召F1 + κ + 混淆矩阵'],
  ['置信路由', '高置信自动结案,难例进人工复核'],
]

export default function Uploader({ onUpload, onSample, busy, bus = [] }) {
  const inputRef = useRef(null)
  const [drag, setDrag] = useState(false)
  const [bu, setBu] = useState(bus[0]?.code || 'securities')

  const pick = (file) => file && onUpload(file, bu)
  const curBu = bus.find((b) => b.code === bu)

  return (
    <div className="mx-auto max-w-4xl">
      {/* BU 选择器:决定用哪套业务分类体系评测 */}
      {bus.length > 0 && (
        <div className="mb-5">
          <div className="mb-2 flex items-center gap-2 text-sm text-slate-400">
            <Building2 size={15} className="text-brand-400" />
            选择 BU
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {bus.map((b) => (
              <button
                key={b.code}
                onClick={() => setBu(b.code)}
                className={clsx(
                  'flex items-start gap-3 rounded-xl border px-4 py-3 text-left transition',
                  bu === b.code
                    ? 'border-brand-500 bg-brand-500/10'
                    : 'border-line bg-ink-850/60 hover:border-brand-500/40',
                )}
              >
                <div className={clsx(
                  'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold',
                  bu === b.code ? 'bg-brand-500 text-white' : 'bg-ink-700 text-slate-400',
                )}>
                  {b.name[0]}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-100">{b.name}</span>
                    <span className="text-xs text-slate-500">{b.intent_count} 个业务分类</span>
                  </div>
                  <div className="mt-0.5 truncate text-xs text-slate-500">{b.description}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 上传区 */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]) }}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          'card group relative flex cursor-pointer flex-col items-center justify-center px-8 py-14 text-center transition',
          drag ? 'border-brand-500 bg-brand-500/5' : 'hover:border-brand-500/50',
          busy && 'pointer-events-none opacity-60',
        )}
      >
        <div className="rounded-2xl bg-brand-500/10 p-4 transition group-hover:scale-105">
          <UploadCloud size={32} className="text-brand-400" />
        </div>
        <div className="mt-4 text-lg font-medium text-slate-100">拖入或点击上传对话日志 Excel</div>
        <div className="mt-1.5 text-sm text-slate-500">
          支持 .xlsx / .xls,需包含日志导出列 + 运营人工标注列(A–BF)
        </div>
        <input
          ref={inputRef} type="file" accept=".xlsx,.xls" hidden
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </div>

      {/* 用样例数据:校准(有金标) / 生产(无金标,大数据) 两种场景 */}
      <div className="mt-4">
        <div className="mb-3 flex items-center gap-3">
          <div className="h-px flex-1 bg-line" />
          <span className="text-xs text-slate-500">
            没有数据?试试{curBu ? `「${curBu.name}」` : ''}内置样例
          </span>
          <div className="h-px flex-1 bg-line" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            onClick={() => onSample(bu, 'calib')}
            disabled={busy}
            className="group flex items-start gap-3 rounded-xl border border-info-400/30 bg-info-400/[0.06] px-4 py-3 text-left transition hover:bg-info-400/[0.12] disabled:opacity-50"
          >
            <ShieldCheck size={18} className="mt-0.5 shrink-0 text-info-400" />
            <div>
              <div className="text-sm font-medium text-slate-100">校准样例(有人工金标)</div>
              <div className="mt-0.5 text-xs text-slate-500">算 κ/F1 验证 Judge 可信度</div>
            </div>
          </button>
          <button
            onClick={() => onSample(bu, 'prod')}
            disabled={busy}
            className="group flex items-start gap-3 rounded-xl border border-good-500/30 bg-good-500/[0.06] px-4 py-3 text-left transition hover:bg-good-500/[0.12] disabled:opacity-50"
          >
            <TrendingUp size={18} className="mt-0.5 shrink-0 text-good-400" />
            <div>
              <div className="text-sm font-medium text-slate-100">生产样例(3000行无标注)</div>
              <div className="mt-0.5 text-xs text-slate-500">直接出业务洞察 + 优化建议</div>
            </div>
          </button>
        </div>
      </div>

      {/* 流水线示意 */}
      <div className="mt-10">
        <div className="mb-3 flex items-center gap-2 text-sm text-slate-400">
          <FileSpreadsheet size={15} className="text-brand-400" />
          评测流水线
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PIPELINE.map(([title, desc], i) => (
            <div key={title} className="card flex items-start gap-3 p-4 animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-500/15 text-xs font-semibold text-brand-400">
                {i + 1}
              </div>
              <div>
                <div className="text-sm font-medium text-slate-200">{title}</div>
                <div className="mt-0.5 text-xs leading-relaxed text-slate-500">{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
