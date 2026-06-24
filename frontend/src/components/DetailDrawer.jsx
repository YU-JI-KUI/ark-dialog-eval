import { useEffect } from 'react'
import { X, MessageSquare, Bot, Scale, ShieldCheck } from 'lucide-react'
import { Badge, YesNo } from './ui'
import clsx from 'clsx'

export default function DetailDrawer({ row, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!row) return null
  const j = row.judge || {}

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-2xl flex-col border-l border-line bg-ink-900 shadow-2xl animate-fade-up">
        {/* 头部 */}
        <div className="flex items-start justify-between border-b border-line px-6 py-4">
          <div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="font-mono text-slate-400">会话 {row.session}</span>
              <span className="rounded bg-ink-700 px-1.5 py-0.5">第 {row.turn} 轮</span>
              <Badge tone="brand">{row.j_intent}</Badge>
              {row.is_disagreement && <Badge tone="bad">与金标不一致</Badge>}
            </div>
            <h3 className="mt-2 text-lg font-semibold text-slate-100">{row.question}</h3>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-ink-700 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {/* 多轮上下文:用户问 + AI 答(AI 答用于判断指代上一轮的问题) */}
          {row.context?.length > 0 && (
            <Block icon={MessageSquare} title="会话上下文（前文）">
              <div className="space-y-2">
                {row.context.map((c, i) => (
                  <div key={i} className="rounded-lg bg-ink-800/60 px-3 py-2 text-sm">
                    <div className="text-slate-300">
                      <span className="mr-2 text-xs text-slate-500">第{c.turn ?? i + 1}轮 · 用户</span>
                      {c.user ?? c}
                    </div>
                    {c.ai && (
                      <div className="mt-1 border-l-2 border-brand-500/30 pl-2 text-xs text-slate-400">
                        <span className="mr-1.5 text-slate-500">AI答</span>{c.ai}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Block>
          )}

          {/* AI 回答原文(不解析,交给 LLM 读) */}
          <Block icon={Bot} title="AI 回答（原始内容）">
            <pre className="whitespace-pre-wrap rounded-lg bg-ink-800/60 px-3 py-2.5 text-sm leading-relaxed text-slate-300">
              {row.answer_text || '（空）'}
            </pre>
            {row.next_user_turn && (
              <div className="mt-2 rounded-lg border border-warn-500/20 bg-warn-500/[0.06] px-3 py-2 text-xs text-warn-400">
                ⤷ 用户下一轮:{row.next_user_turn}
              </div>
            )}
          </Block>

          {/* Judge 判断 */}
          <Block icon={Scale} title="Judge 判断">
            <div className="grid grid-cols-2 gap-2.5">
              <JField label="业务分类" value={j.business_type} />
              <JField label="分发场景" value={row.dispatch_scene} highlight />
              <JFieldBool label="该不该本BU接(AI判)" value={j.should_dispatch_to_bu} />
              <JFieldBool label="答案相关" value={j.answer_relevant} />
              <JFieldBool label="答案完整" value={j.answer_complete} />
              <JField label="是否解决" value={j.answer_resolved} highlight />
              <JFieldBool label="需人工复核" value={j.needs_human_review} warnTrue />
            </div>
            {j.dispatch_reason && (
              <div className="mt-3 rounded-lg bg-ink-800/60 px-3 py-2 text-xs text-slate-400">
                <span className="text-slate-500">分发理由:</span> {j.dispatch_reason}
              </div>
            )}
            {j.review_reason && (
              <div className="mt-2 rounded-lg bg-ink-800/60 px-3 py-2 text-xs text-slate-400">
                <span className="text-slate-500">复核原因:</span> {j.review_reason}
              </div>
            )}
          </Block>

          {/* 金标对比 */}
          <Block icon={ShieldCheck} title="人工金标对比">
            <div className="grid grid-cols-2 gap-3">
              <GoldCompare label="分发是否正确" pred={row.j_dispatch} gold={row.gold?.dispatch} />
              <GoldCompare label="答案是否解决" pred={row.j_resolved} gold={row.gold?.resolved} />
            </div>
            {row.gold?.unresolved_reason && (
              <div className="mt-3 text-xs text-slate-400">
                <span className="text-slate-500">人工标注·未解决原因:</span> {row.gold.unresolved_reason}
              </div>
            )}
            {row.gold?.qtype && (
              <div className="mt-1 text-xs text-slate-400">
                <span className="text-slate-500">人工标注·问题类型:</span> {row.gold.qtype}
              </div>
            )}
          </Block>
        </div>
      </aside>
    </>
  )
}

function Block({ icon: Icon, title, badge, children }) {
  return (
    <section>
      <div className="mb-2 flex items-center gap-2">
        <Icon size={15} className="text-brand-400" />
        <h4 className="text-sm font-medium text-slate-200">{title}</h4>
        {badge && <Badge tone="info">{badge}</Badge>}
      </div>
      {children}
    </section>
  )
}
function JField({ label, value, highlight }) {
  return (
    <div className="rounded-lg bg-ink-800/40 px-3 py-2">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className={clsx('mt-0.5 text-sm', highlight ? 'font-semibold text-brand-400' : 'text-slate-200')}>
        {value ?? '—'}
      </div>
    </div>
  )
}
function JFieldBool({ label, value, warnTrue }) {
  const tone = value === null || value === undefined ? 'slate' : value ? (warnTrue ? 'warn' : 'good') : 'slate'
  const text = value === true ? '是' : value === false ? '否' : '—'
  return (
    <div className="flex items-center justify-between rounded-lg bg-ink-800/40 px-3 py-2">
      <span className="text-[11px] text-slate-500">{label}</span>
      <Badge tone={tone}>{text}</Badge>
    </div>
  )
}
function GoldCompare({ label, pred, gold }) {
  const disagree = (gold === '是' || gold === '否') && pred !== gold
  return (
    <div className={clsx('rounded-lg border bg-ink-800/40 p-3', disagree ? 'border-bad-500/40' : 'border-line')}>
      <div className="mb-2 text-xs text-slate-400">{label}</div>
      <div className="flex items-center justify-between text-xs">
        <div className="flex flex-col items-center gap-1">
          <span className="text-slate-500">Judge</span>
          <YesNo value={pred} />
        </div>
        <span className={clsx('text-lg', disagree ? 'text-bad-400' : 'text-good-400')}>
          {disagree ? '≠' : '='}
        </span>
        <div className="flex flex-col items-center gap-1">
          <span className="text-slate-500">金标</span>
          <YesNo value={gold} />
        </div>
      </div>
    </div>
  )
}
