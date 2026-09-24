export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

export async function api(path, { method = 'GET', body, token, signal } = {}) {
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined && !(body instanceof FormData)) headers['Content-Type'] = 'application/json'
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(0, 'API bağlantısı kurulamadı. Adresi ve CORS ayarını kontrol edin.')
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    if (response.status === 401 && token) window.dispatchEvent(new Event('mi:session-expired'))
    throw new ApiError(response.status, payload.detail || `HTTP ${response.status}`)
  }
  if (response.status === 204) return null
  return response.json()
}

export function friendlyError(error, language = 'tr') {
  if (error?.status === 429) return language === 'tr' ? 'AI sağlayıcısı şu anda yoğun. Biraz sonra tekrar deneyin.' : 'The AI provider is rate-limited. Please retry later.'
  if (error?.status === 502) return language === 'tr' ? 'AI sağlayıcısı yanıt veremedi. Sorunuz korunuyor; tekrar deneyin.' : 'The AI provider could not answer. Please retry.'
  if (error?.status === 503) return language === 'tr' ? 'Servis geçici olarak kullanılamıyor.' : 'The service is temporarily unavailable.'
  if (error?.status === 404) return language === 'tr' ? 'Kayıt bulunamadı.' : 'Record not found.'
  if (Array.isArray(error?.detail)) return error.detail.map(item => `${item.loc?.at(-1) || 'Alan'}: ${item.msg}`).join(' · ')
  return error?.message || (language === 'tr' ? 'Beklenmeyen bir hata oluştu.' : 'An unexpected error occurred.')
}
