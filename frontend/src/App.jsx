import { useEffect, useRef, useState } from 'react'
import {
  Activity, Database, Download, RotateCcw, AlertTriangle, CheckCircle2, Cpu,
  ShieldCheck, TrendingUp, Building2,
} from 'lucide-react'
import clsx from 'clsx'
import { api } from './api/client'
import { StatCard } from './components/ui'
import Uploader from './components/Uploader'
import RunProgress from './components/RunProgress'
import MetricsPanel from './components/MetricsPanel'
import IntentCharts from './components/IntentCharts'
import RowsTable from './components/RowsTable'
import InsightsPanel from './components/InsightsPanel'
import AdvicePanel from './components/AdvicePanel'

export default function App() {
  const [config, setConfig] = useState(null)
  const [bus, setBus] = useState([])
  const [view, setView] = useState('upload') // upload | running | result
  const [task, setTask] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [resumable, setResumable] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    api.getConfig().then(setConfig).catch(() => {})
    api.getBus().then(setBus).catch(() => {})
    return () => clearInterval(pollRef.current)
  }, [])

  const startPolling = (taskId) => {
    setView('running')
    setError(null)
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const t = await api.getTask(taskId)
        setTask(t)
        if (t.status === 'done') {
          clearInterval(pollRef.current)
          const r = await api.getResult(taskId)
          setResult(r)
          setView('result')
        } else if (t.status === 'failed') {
          clearInterval(pollRef.current)
          setError(t.error || '评测失败')
          if (t.can_resume) setResumable(taskId)
          setView('upload')
        }
      } catch (e) {
        clearInterval(pollRef.current)
        setError(e?.message || '轮询失败')
        setView('upload')
      }
    }, 600)
  }

  const handleUpload = async (file, bu = 'securities') => {
    try {
      setError(null)
      const t = await api.upload(file, bu)
      setTask(t)
      startPolling(t.task_id)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const handleSample = async (bu = 'securities', kind = 'calib') => {
    try {
      const t = await api.runSample(bu, kind)
      setTask(t)
      startPolling(t.task_id)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const handleResume = async () => {
    if (!resumable) return
    try {
      setError(null)
      const t = await api.resume(resumable)
      setResumable(null)
      setTask(t)
      startPolling(resumable)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const reset = () => {
    setView('upload'); setResult(null); setTask(null); setError(null); setResumable(null)
  }

  return (
    <div className="min-h-full">
      <NavBar config={config} onReset={reset} showReset={view === 'result'} />

      <main className="mx-auto max-w-7xl px-6 py-8">
        {error && (
          <div className="mx-auto mb-6 flex max-w-4xl items-center justify-between rounded-xl border border-bad-500/30 bg-bad-500/10 px-4 py-3 text-sm text-bad-300">
            <span><AlertTriangle size={15} className="mr-1.5 inline" />{error}</span>
            {resumable && (
              <button
                onClick={handleResume}
                className="ml-4 shrink-0 rounded-lg bg-bad-500/20 px-3 py-1.5 text-xs font-medium text-bad-200 transition hover:bg-bad-500/30"
              >
                断点续跑
              </button>
            )}
          </div>
        )}

        {view === 'upload' && <Uploader onUpload={handleUpload} onSample={handleSample} busy={false} bus={bus} />}
        {view === 'running' && task && <RunProgress task={task} />}
        {view === 'result' && result && <ResultView result={result} task={task} />}
      </main>
    </div>
  )
}

function NavBar({ config, onReset, showReset }) {
  const active = config?.active_backend
  const isMock = active === 'mock'
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink-950/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-info-400">
            <Activity size={18} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-100">Ark 快捷服务评估平台</div>
            <div className="text-[11px] text-slate-500">多 BU · LLM-as-a-Judge 自动化评测流水线</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 rounded-lg border border-line bg-ink-850 px-3 py-1.5 text-xs">
            <Cpu size={13} className={isMock ? 'text-warn-400' : 'text-good-400'} />
            <span className="text-slate-400">Judge 后端</span>
            <span className={isMock ? 'font-medium text-warn-400' : 'font-medium text-good-400'}>
              {isMock ? 'Mock 规则桩' : '平安大模型'}
            </span>
          </div>
          {showReset && (
            <button
              onClick={onReset}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-brand-500"
            >
              <RotateCcw size={13} />新评测
            </button>
          )}
        </div>
      </div>
    </header>
  )
}

function ModeBadge({ mode }) {
  const isCalib = mode === 'calibration'
  return (
    <div className={clsx(
      'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium',
      isCalib ? 'border-info-400/30 bg-info-400/10 text-info-400' : 'border-good-500/30 bg-good-500/10 text-good-400',
    )}>
      {isCalib ? <ShieldCheck size={13} /> : <TrendingUp size={13} />}
      {isCalib ? '校准模式 · 有人工金标,可算可信度' : '生产模式 · 无标注,直接出洞察'}
    </div>
  )
}

function ResultView({ result, task }) {
  const s = result.summary
  const f = result.filter_stats
  const isCalib = result.mode === 'calibration'
  const pct = (v) => `${Math.round((v || 0) * 100)}%`
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-300">
          <Building2 size={13} />{result.bu_name} BU
        </div>
        <ModeBadge mode={result.mode} />
      </div>

      {/* 概览统计:BU 分发准确率 + 端到端解决率(漏斗口径) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="评测样本" value={s.total_samples} sub={`日志共 ${f.total} 条`} tone="brand" icon={Database} />
        <StatCard label="BU 分发准确率" value={pct(s.dispatch_accuracy)} sub={`该承接/拒识判对占比`} tone="info" icon={TrendingUp} />
        <StatCard label="端到端解决率" value={pct(s.end_to_end_resolved_rate ?? s.resolved_rate)} sub="仅分发到本BU的问题" tone="good" icon={CheckCircle2} />
        {isCalib
          ? <StatCard label="不一致 case" value={s.disagreement_count} sub="Judge 与人工金标分歧" tone="bad" icon={AlertTriangle} />
          : <StatCard label="需人工复核" value={s.needs_review} sub="低置信 / 难例,进复核队列" tone="warn" icon={AlertTriangle} />}
      </div>

      {/* BU 分发漏斗:两类错误 */}
      {s.bu_dispatch && (
        <div className="rounded-xl border border-line bg-ink-850/60 px-5 py-3 text-sm text-slate-400">
          <TrendingUp size={14} className="mr-1.5 inline text-info-400" />
          BU 分发:对 <span className="text-good-400">{s.bu_dispatch.correct}</span> /{s.bu_dispatch.scored} 条 ·
          漏收(该承接却拒识) <span className="text-warn-400">{s.bu_dispatch.miss_should_accept_but_rejected}</span> 条 ·
          误收(该拒识却承接) <span className="text-bad-400">{s.bu_dispatch.over_should_reject_but_accepted}</span> 条
        </div>
      )}

      {/* 优化建议:你要的核心新环节,放显眼位置 */}
      <AdvicePanel advice={result.advice} />

      {/* 业务洞察 */}
      <InsightsPanel insights={result.insights} />
      <IntentCharts dist={result.intent_distribution} />

      {/* 校准模式才显示:可信度指标 + 不一致导出 */}
      {isCalib && (
        <>
          <MetricsPanel metrics={result.metrics} />
          <div className="flex items-center justify-between rounded-xl border border-line bg-ink-850/60 px-5 py-3.5">
            <div className="text-sm text-slate-400">
              共 <span className="font-medium text-slate-200">{s.disagreement_count}</span> 条不一致 case,导出后可双向复核(改 prompt / 修人工标)
            </div>
            <a
              href={api.exportUrl(task.task_id)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-ink-800 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-brand-500/50 hover:text-brand-300"
            >
              <Download size={14} />导出不一致 case (Excel)
            </a>
          </div>
        </>
      )}

      <RowsTable rows={result.rows} />
    </div>
  )
}
