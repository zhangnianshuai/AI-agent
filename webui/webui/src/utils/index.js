const TOKEN_KEY = 'auth_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * Safe JSON parse — protects Snowflake IDs (64-bit integers) from precision loss.
 * JS Number can only represent integers up to 2^53-1 safely.
 * Snowflake IDs can be 16+ digits, exceeding this limit.
 * This function wraps raw integers with 16+ digits in quotes so they parse as strings.
 */
export function safeJsonParse(text) {
  if (typeof text !== 'string') return text
  // Match JSON integer values (not inside strings) that are 16+ digits
  // Pattern: :<whitespace><16+digits> followed by , } ] or whitespace/end
  const safe = text.replace(/(:\s*)(\d{16,})(\s*[,}\]])/g, '$1"$2"$3')
  return JSON.parse(safe)
}

export function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

function fmtYuan(val) {
  if (val >= 10000) {
    const w = val / 10000
    return w % 1 === 0 ? `${w.toFixed(0)}万` : `${w.toFixed(1)}万`
  }
  return `${val}元`
}

export function formatSalary(min, max) {
  if (min && max) return `${fmtYuan(min)}-${fmtYuan(max)}`
  if (min) return `${fmtYuan(min)}起`
  if (max) return `最高${fmtYuan(max)}`
  return '薪资面议'
}

/** Split skills string into array (handles comma, Chinese comma, semicolon, spaces) */
export function splitSkills(skills) {
  if (!skills) return []
  if (Array.isArray(skills)) return skills.filter(Boolean)
  if (typeof skills !== 'string') return []
  return skills
    .split(/[,，;；\s]+/)
    .map(s => s.trim())
    .filter(Boolean)
}
