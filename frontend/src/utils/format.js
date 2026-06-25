// 全局时间格式约定:前端所有展示时间统一用 yyyy-MM-dd HH:mm:ss。
// 数据库存的是时间戳数字(后端 time.time() 为秒级);这里兼容秒/毫秒。

const pad = (n) => String(n).padStart(2, '0')

/**
 * 时间戳 → "yyyy-MM-dd HH:mm:ss"。
 * 入参可为秒级或毫秒级数字,也兼容可被 Date 解析的字符串;无效值返回 '—'。
 */
export function formatTime(ts) {
  if (ts === null || ts === undefined || ts === '') return '—'
  let ms
  if (typeof ts === 'number') {
    // 小于 1e12 视为秒级(2001 年的毫秒数已超 1e12),换算成毫秒
    ms = ts < 1e12 ? ts * 1000 : ts
  } else {
    ms = new Date(ts).getTime()
  }
  const d = new Date(ms)
  if (Number.isNaN(d.getTime())) return '—'
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  )
}
