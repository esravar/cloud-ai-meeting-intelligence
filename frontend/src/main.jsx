import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, API_BASE_URL, friendlyError } from './api'
import './style.css'

const words = {
  tr: { dashboard: 'Genel Bakış', meetings: 'Toplantılar', upload: 'Dosya Yükle', jobs: 'İşlemler', ask: 'AI Soru-Cevap', agent: 'Agent Sohbetleri', settings: 'Ayarlar', logout: 'Çıkış Yap', login: 'Giriş Yap', register: 'Hesap Oluştur', email: 'E-posta', password: 'Parola', title: 'Başlık', refresh: 'Yenile', loading: 'Yükleniyor…', empty: 'Henüz kayıt yok.', submit: 'Gönder', source: 'Kaynaklar', all: 'Tüm toplantılar', view: 'Görüntüle', delete: 'Sil', edit: 'Düzenle', reindex: 'Yeniden indeksle', next: 'Sonraki', previous: 'Önceki', retry: 'Tekrar dene' },
  en: { dashboard: 'Overview', meetings: 'Meetings', upload: 'Upload File', jobs: 'Jobs', ask: 'Ask AI', agent: 'Agent Chats', settings: 'Settings', logout: 'Log Out', login: 'Log In', register: 'Register', email: 'Email', password: 'Password', title: 'Title', refresh: 'Refresh', loading: 'Loading…', empty: 'No records yet.', submit: 'Send', source: 'Sources', all: 'All meetings', view: 'View', delete: 'Delete', edit: 'Edit', reindex: 'Reindex', next: 'Next', previous: 'Previous', retry: 'Retry' },
}
const nav = ['dashboard', 'meetings', 'upload', 'jobs', 'ask', 'agent', 'settings']
const readRoute = () => window.location.hash.replace(/^#\/?/, '').split('?')[0] || 'dashboard'
const dateText = value => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('mi_token') || '')
  const [user, setUser] = useState(null)
  const [language, setLanguage] = useState(() => localStorage.getItem('mi_language') || 'tr')
  const [route, setRoute] = useState(readRoute)
  const [message, setMessage] = useState('')
  const [health, setHealth] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const t = words[language]

  useEffect(() => { const handler = () => { setRoute(readRoute()); setMobileOpen(false) }; window.addEventListener('hashchange', handler); return () => window.removeEventListener('hashchange', handler) }, [])
  useEffect(() => { const handler = () => logout(); window.addEventListener('mi:session-expired', handler); return () => window.removeEventListener('mi:session-expired', handler) }, [])
  useEffect(() => { localStorage.setItem('mi_language', language); document.documentElement.lang = language }, [language])
  useEffect(() => {
    const controller = new AbortController()
    api('/health', { signal: controller.signal }).then(() => setHealth(true)).catch(() => setHealth(false))
    return () => controller.abort()
  }, [])
  useEffect(() => {
    if (!token) { setUser(null); return }
    let active = true
    api('/auth/me', { token }).then(data => { if (active) setUser(data) }).catch(error => {
      if (active && error.status === 401) logout()
    })
    return () => { active = false }
  }, [token])
  function logout() { sessionStorage.removeItem('mi_token'); setToken(''); setUser(null); window.location.hash = 'login' }
  function show(text) { setMessage(text); window.setTimeout(() => setMessage(''), 6000) }
  function go(path) { window.location.hash = path }

  if (!token) return <Auth t={t} language={language} setLanguage={setLanguage} onLogin={value => { sessionStorage.setItem('mi_token', value); setToken(value); go('dashboard') }} />
  const common = { token, t, language, go, show }
  let content
  if (route === 'meetings') content = <Meetings {...common} />
  else if (route.startsWith('meeting/')) content = <MeetingDetail {...common} id={route.slice(8)} />
  else if (route === 'upload') content = <Upload {...common} />
  else if (route === 'jobs') content = <Jobs {...common} />
  else if (route.startsWith('job/')) content = <JobDetail {...common} id={route.slice(4)} />
  else if (route === 'ask') content = <Ask {...common} />
  else if (route === 'agent' || route.startsWith('agent/')) content = <Agent {...common} route={route} />
  else if (route === 'settings') content = <Settings {...common} user={user} health={health} setLanguage={setLanguage} />
  else content = <Dashboard {...common} />
  return <div className="app-shell">
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <a className="brand" href="#dashboard"><span className="brand-icon">▤</span><span>Meeting Intelligence<small>Enterprise AI</small></span></a>
      <div className={`connection ${health ? 'ok' : ''}`}><span className="dot" /> FastAPI <b>{health ? (language === 'tr' ? 'Bağlı' : 'Connected') : (language === 'tr' ? 'Bağlantı yok' : 'Offline')}</b></div>
      <nav aria-label="Main navigation">{nav.map(item => <a key={item} className={route === item || route.startsWith(item === 'meetings' ? 'meeting/' : item === 'jobs' ? 'job/' : '___') ? 'active' : ''} href={`#${item}`}>{t[item]}</a>)}</nav>
      <div className="sidebar-bottom"><div className="user-box">{user?.email || t.loading}</div><button className="text-danger" onClick={logout}>{t.logout}</button></div>
    </aside>
    <div className="main-area"><header className="topbar"><button className="mobile-menu" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Menu">☰</button><div className="breadcrumb">Workspace / <strong>{t[route.split('/')[0]] || t.dashboard}</strong></div><div className="top-actions"><button className="lang" onClick={() => setLanguage(language === 'tr' ? 'en' : 'tr')}>{language.toUpperCase()} ⇄</button><button className="primary small" onClick={() => go('upload')}>＋ {t.upload}</button></div></header><main className="content">{content}</main></div>
    {message && <div className="toast" role="status">{message}</div>}
  </div>
}

function Auth({ t, language, setLanguage, onLogin }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function submit(event) {
    event.preventDefault(); setError(''); setNotice('')
    if (mode === 'register' && password !== confirm) { setError(language === 'tr' ? 'Parolalar eşleşmiyor.' : 'Passwords do not match.'); return }
    setBusy(true)
    try {
      if (mode === 'register') { await api('/auth/register', { method: 'POST', body: { email, password } }); setMode('login'); setNotice(language === 'tr' ? 'Hesabınız oluşturuldu. Giriş yapın.' : 'Account created. Please log in.') }
      else { const result = await api('/auth/login', { method: 'POST', body: { email, password } }); onLogin(result.access_token) }
    } catch (err) { setError(friendlyError(err, language)) } finally { setBusy(false) }
  }
  return <div className="auth-page"><div className="auth-card"><div className="auth-head"><div className="brand"><span className="brand-icon">▤</span>Meeting Intelligence</div><button className="lang" onClick={() => setLanguage(language === 'tr' ? 'en' : 'tr')}>{language.toUpperCase()} ⇄</button></div><h1>{mode === 'login' ? t.login : t.register}</h1><p>{language === 'tr' ? 'Toplantı bilgilerinizle güvenli çalışma alanınıza erişin.' : 'Access your secure meeting knowledge workspace.'}</p><form onSubmit={submit}><label>{t.email}<input type="email" required value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" /></label><label>{t.password}<input type="password" required minLength={mode === 'register' ? 12 : undefined} value={password} onChange={e => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>{mode === 'register' && <label>{language === 'tr' ? 'Parola tekrar' : 'Confirm password'}<input type="password" required value={confirm} onChange={e => setConfirm(e.target.value)} /></label>}{error && <div className="alert error">{error}</div>}{notice && <div className="alert success">{notice}</div>}<button className="primary wide" disabled={busy}>{busy ? t.loading : mode === 'login' ? t.login : t.register}</button></form><button className="link-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? t.register : t.login}</button></div></div>
}

function useApiData(path, token, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null })
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setState(previous => ({ ...previous, loading: true, error: null }))
    api(path, { token, signal: controller.signal }).then(data => setState({ loading: false, data, error: null })).catch(error => { if (error.name !== 'AbortError') setState({ loading: false, data: null, error }) })
    return () => controller.abort()
  }, [path, token, version, ...deps])
  return { ...state, refresh: () => setVersion(value => value + 1) }
}
function State({ loading, error, refresh, t, language, empty }) { if (loading) return <div className="state">{t.loading}</div>; if (error) return <div className="alert error">{friendlyError(error, language)} <button onClick={refresh}>{t.retry}</button></div>; if (empty) return <div className="state">{empty === true ? t.empty : empty}</div>; return null }
function PageTitle({ eyebrow, title, description, action }) { return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div> }
function Status({ value }) { return <span className={`status status-${value}`}>{value}</span> }
function Pager({ page, total, setPage, t }) { return <div className="pager"><button disabled={page === 0} onClick={() => setPage(page - 1)}>{t.previous}</button><span>{page + 1} / {Math.max(1, Math.ceil(total / 20))}</span><button disabled={(page + 1) * 20 >= total} onClick={() => setPage(page + 1)}>{t.next}</button></div> }

function Dashboard({ token, t, language, go }) {
  const meetings = useApiData('/meetings?limit=5&offset=0', token)
  const jobs = useApiData('/jobs?limit=5&offset=0', token)
  const jobItems = jobs.data?.items || []
  return <><PageTitle eyebrow="MEETING INTELLIGENCE" title={language === 'tr' ? 'Genel Bakış' : 'Overview'} description={language === 'tr' ? 'Toplantılarınız ve son işleme görevleri tek yerde.' : 'Your meetings and recent processing jobs in one place.'} action={<button className="primary" onClick={() => go('upload')}>＋ {t.upload}</button>} /><div className="stats"><div className="stat"><small>{t.meetings}</small><strong>{meetings.data?.total ?? '—'}</strong></div><div className="stat"><small>{language === 'tr' ? 'İşleniyor' : 'Processing'}</small><strong>{jobs.data ? jobItems.filter(x => ['queued', 'processing'].includes(x.status)).length : '—'}</strong></div><div className="stat"><small>{language === 'tr' ? 'Tamamlandı' : 'Completed'}</small><strong>{jobs.data ? jobItems.filter(x => x.status === 'completed').length : '—'}</strong></div><div className="stat"><small>{language === 'tr' ? 'Başarısız' : 'Failed'}</small><strong>{jobs.data ? jobItems.filter(x => x.status === 'failed').length : '—'}</strong></div></div><div className="grid two"><section className="panel"><div className="panel-heading"><h2>{language === 'tr' ? 'Son Toplantılar' : 'Recent Meetings'}</h2><button onClick={() => go('meetings')}>{language === 'tr' ? 'Tümünü Gör' : 'See all'} →</button></div><State {...meetings} t={t} language={language} empty={!meetings.data?.items?.length && (language === 'tr' ? 'Henüz toplantı yok. İlk PDF veya ses kaydınızı yükleyin.' : 'No meetings yet. Upload your first file.')} />{meetings.data?.items?.map(item => <div className="list-row" key={item.id}><div><b>{item.title}</b><small>{item.source_type.toUpperCase()} · {item.chunk_count} chunks · {dateText(item.created_at)}</small></div><button onClick={() => go(`meeting/${item.id}`)}>{t.view}</button></div>)}</section><section className="panel"><div className="panel-heading"><h2>{language === 'tr' ? 'Son İşlemler' : 'Recent Jobs'}</h2><button onClick={() => go('jobs')}>{language === 'tr' ? 'Tümünü Gör' : 'See all'} →</button></div><State {...jobs} t={t} language={language} empty={!jobItems.length} />{jobItems.map(item => <div className="list-row" key={item.id}><div><b>{item.title}</b><small>{item.original_filename} · {dateText(item.created_at)}</small></div><Status value={item.status} /><button onClick={() => go(`job/${item.id}`)}>{t.view}</button></div>)}</section></div><div className="quick-actions"><button onClick={() => go('upload')}>＋ {t.upload}</button><button onClick={() => go('ask')}>✦ {t.ask}</button><button onClick={() => go('agent')}>◈ {t.agent}</button></div></>
}

function Meetings({ token, t, language, go, show }) {
  const [page, setPage] = useState(0), [query, setQuery] = useState(''), [filter, setFilter] = useState('all')
  const list = useApiData(`/meetings?limit=20&offset=${page * 20}`, token)
  const items = (list.data?.items || []).filter(item => (filter === 'all' || item.source_type === filter) && item.title.toLowerCase().includes(query.toLowerCase()))
  return <><PageTitle eyebrow="KNOWLEDGE BASE" title={t.meetings} description={language === 'tr' ? 'Kaydedilen ve indekslenen toplantılar.' : 'Stored and indexed meetings.'} action={<button className="primary" onClick={() => go('upload')}>＋ {t.upload}</button>} /><section className="panel"><div className="filters"><input placeholder={language === 'tr' ? 'Bu sayfada ara…' : 'Search this page…'} value={query} onChange={e => setQuery(e.target.value)} /><select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">{t.all}</option><option value="text">Text</option><option value="pdf">PDF</option><option value="audio">Audio</option></select><button onClick={list.refresh}>{t.refresh}</button></div><State {...list} t={t} language={language} empty={!items.length} />{items.map(item => <div className="list-row" key={item.id}><div><b>{item.title}</b><small>{item.source_name || item.source_type} · {item.chunk_count} chunks · {dateText(item.created_at)}</small></div><button onClick={() => go(`meeting/${item.id}`)}>{t.view}</button><button onClick={() => go(`ask?meeting=${item.id}`)}>{t.ask}</button></div>)}<Pager page={page} total={list.data?.total || 0} setPage={setPage} t={t} /></section></>
}

function MeetingDetail({ id, token, t, language, go, show }) {
  const item = useApiData(`/meetings/${id}`, token)
  const [title, setTitle] = useState(''), [transcript, setTranscript] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => { if (item.data) setTitle(item.data.title) }, [item.data])
  async function action(kind) {
    if (kind === 'delete' && !window.confirm(language === 'tr' ? 'Bu toplantı silinsin mi?' : 'Delete this meeting?')) return
    setBusy(true)
    try {
      if (kind === 'delete') { await api(`/meetings/${id}`, { method: 'DELETE', token }); go('meetings'); return }
      if (kind === 'save') await api(`/meetings/${id}`, { method: 'PATCH', token, body: { title, ...(transcript.trim() ? { transcript } : {}) } })
      if (kind === 'reindex') await api(`/meetings/${id}/reindex`, { method: 'POST', token })
      item.refresh(); show(language === 'tr' ? 'İşlem tamamlandı.' : 'Done.')
    } catch (error) { show(friendlyError(error, language)) } finally { setBusy(false) }
  }
  return <><PageTitle eyebrow="MEETING" title={item.data?.title || t.loading} action={<button onClick={() => go('meetings')}>← {t.meetings}</button>} /><State {...item} t={t} language={language} />{item.data && <div className="grid two"><section className="panel"><h2>{language === 'tr' ? 'Toplantı Bilgileri' : 'Meeting Details'}</h2><dl className="details"><dt>ID</dt><dd>{item.data.id}</dd><dt>{language === 'tr' ? 'Kaynak' : 'Source'}</dt><dd>{item.data.source_name || item.data.source_type}</dd><dt>Chunks</dt><dd>{item.data.chunk_count}</dd><dt>Embedding</dt><dd>{item.data.embedding_model}</dd><dt>{language === 'tr' ? 'Oluşturuldu' : 'Created'}</dt><dd>{dateText(item.data.created_at)}</dd></dl><div className="actions"><button className="primary" onClick={() => go(`ask?meeting=${id}`)}>{t.ask}</button><button onClick={() => go(`agent?meeting=${id}`)}>{t.agent}</button></div></section><section className="panel"><h2>{t.edit}</h2><label>{t.title}<input value={title} onChange={e => setTitle(e.target.value)} minLength={3} maxLength={300} /></label><label>{language === 'tr' ? 'Yeni transcript (isteğe bağlı)' : 'New transcript (optional)'}<textarea value={transcript} onChange={e => setTranscript(e.target.value)} minLength={20} placeholder={language === 'tr' ? 'Mevcut transcript API tarafından gösterilmez.' : 'Current transcript is not exposed by the API.'} /></label><div className="actions"><button disabled={busy || title.length < 3} onClick={() => action('save')}>{language === 'tr' ? 'Kaydet' : 'Save'}</button><button disabled={busy} onClick={() => action('reindex')}>{t.reindex}</button><button className="text-danger" disabled={busy} onClick={() => action('delete')}>{t.delete}</button></div></section></div>}</>
}

function Upload({ token, t, language, go }) {
  const [mode, setMode] = useState('pdf'), [file, setFile] = useState(null), [title, setTitle] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const maxBytes = 25 * 1024 * 1024
  async function submit(event) {
    event.preventDefault(); setError('')
    if (!file) return setError(language === 'tr' ? 'Dosya seçin.' : 'Choose a file.')
    if (file.size > maxBytes) return setError(language === 'tr' ? 'Dosya 25 MB sınırını aşıyor.' : 'File exceeds 25 MB limit.')
    const body = new FormData(); body.append('file', file); body.append('title', title)
    setBusy(true)
    try { const job = await api(`/uploads/${mode}`, { method: 'POST', token, body }); go(`job/${job.id}`) } catch (err) { setError(friendlyError(err, language)) } finally { setBusy(false) }
  }
  function chooseMode(value) { setMode(value); setFile(null); setError('') }
  return <><PageTitle eyebrow="INGESTION" title={t.upload} description={language === 'tr' ? 'PDF veya ses kaydını yükle; işleme arka planda devam eder.' : 'Upload a PDF or recording; processing continues in the background.'} /><section className="panel narrow"><div className="tabs"><button className={mode === 'pdf' ? 'selected' : ''} onClick={() => chooseMode('pdf')}>PDF</button><button className={mode === 'audio' ? 'selected' : ''} onClick={() => chooseMode('audio')}>{language === 'tr' ? 'Ses Kaydı' : 'Audio'}</button></div><form onSubmit={submit}><label>{t.title}<input value={title} onChange={e => setTitle(e.target.value)} minLength={3} maxLength={300} required /></label><label className="dropzone">{file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB` : (language === 'tr' ? 'Dosya seçin veya buraya sürükleyin' : 'Choose or drop a file here')}<input type="file" accept={mode === 'pdf' ? '.pdf,application/pdf' : '.mp3,.wav,.m4a,.ogg,.webm,.mp4'} onChange={e => setFile(e.target.files?.[0] || null)} onDrop={e => { e.preventDefault(); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]) }} onDragOver={e => e.preventDefault()} /></label>{file && <button type="button" onClick={() => setFile(null)}>{language === 'tr' ? 'Dosyayı kaldır' : 'Remove file'}</button>}<p className="hint">{mode === 'pdf' ? (language === 'tr' ? 'Metin tabanlı PDF desteklenir. Taranmış PDF için OCR gerekir.' : 'Text-based PDFs are supported. Scanned PDFs require OCR.') : 'MP3, WAV, M4A, OGG, WEBM, MP4'} · 25 MB</p>{error && <div className="alert error">{error}</div>}<button className="primary" disabled={busy || !file || title.trim().length < 3}>{busy ? t.loading : t.upload}</button></form></section></>
}

function Jobs({ token, t, language, go }) {
  const [page, setPage] = useState(0), [status, setStatus] = useState('all')
  const list = useApiData(`/jobs?limit=20&offset=${page * 20}`, token)
  const items = (list.data?.items || []).filter(item => status === 'all' || item.status === status)
  return <><PageTitle eyebrow="BACKGROUND WORK" title={t.jobs} description={language === 'tr' ? 'Dosya işleme görevlerinin durumunu takip edin.' : 'Track background file processing.'} action={<button onClick={list.refresh}>{t.refresh}</button>} /><section className="panel"><div className="filters"><select value={status} onChange={e => setStatus(e.target.value)}><option value="all">{language === 'tr' ? 'Tüm durumlar' : 'All statuses'}</option>{['queued', 'processing', 'completed', 'failed'].map(x => <option key={x}>{x}</option>)}</select></div><State {...list} t={t} language={language} empty={!items.length} />{items.map(item => <div className="list-row" key={item.id}><div><b>{item.title}</b><small>{item.original_filename} · {item.kind.toUpperCase()} · {dateText(item.created_at)}</small>{item.error && <small className="text-danger">{item.error}</small>}</div><Status value={item.status} /><button onClick={() => go(`job/${item.id}`)}>{t.view}</button></div>)}<Pager page={page} total={list.data?.total || 0} setPage={setPage} t={t} /></section></>
}

function JobDetail({ id, token, t, language, go }) {
  const job = useApiData(`/jobs/${id}`, token)
  useEffect(() => { if (!['queued', 'processing'].includes(job.data?.status)) return; const timer = window.setInterval(job.refresh, 2000); return () => window.clearInterval(timer) }, [job.data?.status])
  return <><PageTitle eyebrow="UPLOAD JOB" title={job.data?.title || t.loading} action={<button onClick={job.refresh}>{t.refresh}</button>} /><State {...job} t={t} language={language} />{job.data && <section className="panel narrow"><div className="list-row"><strong>{job.data.original_filename}</strong><Status value={job.data.status} /></div><dl className="details"><dt>Job ID</dt><dd>{job.data.id}</dd><dt>{language === 'tr' ? 'Tür' : 'Type'}</dt><dd>{job.data.kind}</dd><dt>{language === 'tr' ? 'Güncellendi' : 'Updated'}</dt><dd>{dateText(job.data.updated_at)}</dd></dl>{job.data.status === 'failed' && <div className="alert error">{job.data.error || 'Processing failed.'}</div>}{job.data.status === 'completed' && job.data.meeting_id && <div className="actions"><button className="primary" onClick={() => go(`meeting/${job.data.meeting_id}`)}>{t.view}</button><button onClick={() => go(`ask?meeting=${job.data.meeting_id}`)}>{t.ask}</button><button onClick={() => go(`agent?meeting=${job.data.meeting_id}`)}>{t.agent}</button></div>}{job.data.status === 'failed' && <button onClick={() => go('upload')}>{t.retry}</button>}</section>}</>
}

function CitationList({ citations, go, t }) { if (!citations?.length) return null; return <div className="citations"><h3>{t.source}</h3>{citations.map(item => <div className="citation" key={`${item.index}-${item.chunk_id}`}><div><strong>[{item.index}] {item.meeting_title}</strong><span>{Math.round(item.score * 100)}% · chunk {item.chunk_index}</span></div><p>{item.excerpt}</p><button onClick={() => go(`meeting/${item.meeting_id}`)}>{t.view} →</button></div>)}</div> }
function MeetingSelect({ token, t, value, setValue }) { const list = useApiData('/meetings?limit=100&offset=0', token); return <select value={value} onChange={e => setValue(e.target.value)}><option value="">{t.all}</option>{list.data?.items?.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select> }

function Ask({ token, t, language, go }) {
  const initial = new URLSearchParams((window.location.hash.split('?')[1] || '')).get('meeting') || ''
  const [meeting, setMeeting] = useState(initial), [question, setQuestion] = useState(''), [topK, setTopK] = useState(5), [answer, setAnswer] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  async function submit(event) { event.preventDefault(); setBusy(true); setError(''); setAnswer(null); try { setAnswer(await api('/questions', { method: 'POST', token, body: { question, meeting_id: meeting || null, top_k: Number(topK) } })) } catch (err) { setError(friendlyError(err, language)) } finally { setBusy(false) } }
  return <><PageTitle eyebrow="SEMANTIC SEARCH & RAG" title={t.ask} description={language === 'tr' ? 'Toplantılarınız hakkında kaynaklı cevaplar alın.' : 'Get cited answers about your meetings.'} /><div className="grid two"><section className="panel"><h2>{language === 'tr' ? 'Sorgu Parametreleri' : 'Query Parameters'}</h2><form onSubmit={submit}><label>{language === 'tr' ? 'Hedef toplantı' : 'Target meeting'}<MeetingSelect token={token} t={t} value={meeting} setValue={setMeeting} /></label><label>{language === 'tr' ? 'Sorunuz' : 'Your question'}<textarea value={question} onChange={e => setQuestion(e.target.value)} minLength={5} maxLength={2000} required placeholder={language === 'tr' ? 'Toplantıda hangi kararlar alındı?' : 'What decisions were made?'} /></label><label>Retrieval depth: {topK}<input type="range" min="1" max="20" value={topK} onChange={e => setTopK(e.target.value)} /></label><button className="primary" disabled={busy || question.trim().length < 5}>{busy ? t.loading : (language === 'tr' ? 'Soruyu Yanıtla' : 'Answer Query')}</button></form></section><section className="panel"><h2>{language === 'tr' ? 'Üretilen Yanıt' : 'Generated Answer'}</h2>{error && <div className="alert error">{error}<button onClick={submit}>{t.retry}</button></div>}{!answer && !busy && !error && <div className="state">{language === 'tr' ? 'Yanıt burada görüntülenecek.' : 'Your answer will appear here.'}</div>}{busy && <div className="state">{t.loading}</div>}{answer && <><p className="answer-text">{answer.answer}</p><small>{answer.model}</small><CitationList citations={answer.citations} go={go} t={t} /></>}</section></div></>
}

function Agent({ token, t, language, go, route }) {
  const initialMeeting = new URLSearchParams((window.location.hash.split('?')[1] || '')).get('meeting') || ''
  const threadId = route.startsWith('agent/') ? route.slice(6).split('?')[0] : ''
  const [meeting, setMeeting] = useState(initialMeeting), [title, setTitle] = useState(''), [draft, setDraft] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [last, setLast] = useState(null)
  const thread = useApiData(threadId ? `/agent/threads/${threadId}` : '/health', token)
  const saved = JSON.parse(sessionStorage.getItem('mi_threads') || '[]')
  async function create(event) { event.preventDefault(); setBusy(true); setError(''); try { const result = await api('/agent/threads', { method: 'POST', token, body: { title, meeting_id: meeting || null } }); sessionStorage.setItem('mi_threads', JSON.stringify([{ id: result.id, title: result.title }, ...saved.filter(x => x.id !== result.id)])); go(`agent/${result.id}`) } catch (err) { setError(friendlyError(err, language)) } finally { setBusy(false) } }
  async function send(event) { event.preventDefault(); if (!draft.trim()) return; setBusy(true); setError(''); try { const result = await api(`/agent/threads/${threadId}/messages`, { method: 'POST', token, body: { message: draft } }); setDraft(''); setLast(result); thread.refresh() } catch (err) { setError(friendlyError(err, language)) } finally { setBusy(false) } }
  return <><PageTitle eyebrow="STATEFUL AGENT" title={t.agent} description={language === 'tr' ? 'Toplantı bağlamını koruyan takip soruları sorun.' : 'Ask follow-up questions with persistent context.'} action={threadId && <button onClick={() => go('agent')}>＋ {language === 'tr' ? 'Yeni Sohbet' : 'New Chat'}</button>} /><div className="grid agent-grid"><section className="panel"><h2>{language === 'tr' ? 'Sohbetler' : 'Chats'}</h2>{saved.length ? saved.map(item => <button className="thread-link" key={item.id} onClick={() => go(`agent/${item.id}`)}>{item.title}</button>) : <div className="state">{language === 'tr' ? 'Bu oturumda henüz sohbet yok.' : 'No chats in this browser session.'}</div>}<p className="hint">{language === 'tr' ? 'Eski bir thread ID varsa adres çubuğunda #agent/ID ile açabilirsiniz.' : 'Existing threads can be opened with #agent/ID.'}</p></section><section className="panel"><h2>{threadId ? thread.data?.title || t.loading : (language === 'tr' ? 'Yeni Agent Sohbeti' : 'New Agent Chat')}</h2>{!threadId ? <form onSubmit={create}><label>{t.title}<input required minLength={3} maxLength={300} value={title} onChange={e => setTitle(e.target.value)} /></label><label>{language === 'tr' ? 'Toplantı kapsamı' : 'Meeting scope'}<MeetingSelect token={token} t={t} value={meeting} setValue={setMeeting} /></label>{error && <div className="alert error">{error}</div>}<button className="primary" disabled={busy || title.trim().length < 3}>{language === 'tr' ? 'Sohbeti Başlat' : 'Start Chat'}</button></form> : <><State {...thread} t={t} language={language} />{thread.data && <><div className="chat-history">{thread.data.turns.length === 0 && <div className="state">{language === 'tr' ? 'İlk sorunuzu yazın.' : 'Write your first question.'}</div>}{thread.data.turns.map(turn => <div key={turn.id} className={`chat-turn ${turn.role}`}><div>{turn.content}</div><small>{dateText(turn.created_at)} · {turn.state}</small></div>)}</div>{last && <><CitationList citations={last.citations} go={go} t={t} /><details><summary>{language === 'tr' ? 'Teknik detaylar' : 'Technical details'}</summary>Trace: {last.trace_id || '—'} · {last.input_tokens}/{last.output_tokens} tokens · ${last.estimated_cost_usd}</details></>}<form className="chat-form" onSubmit={send}><input value={draft} minLength={3} maxLength={2000} onChange={e => setDraft(e.target.value)} placeholder={language === 'tr' ? 'Toplantı hakkında sorun…' : 'Ask about your meetings…'} /><button className="primary" disabled={busy || draft.trim().length < 3}>{busy ? t.loading : t.submit}</button></form>{error && <div className="alert error">{error}<button onClick={send}>{t.retry}</button></div>}</>}</>}</section></div></>
}

function Settings({ t, language, user, health, setLanguage }) { return <><PageTitle eyebrow="PREFERENCES" title={t.settings} /><section className="panel narrow"><dl className="details"><dt>{t.email}</dt><dd>{user?.email || '—'}</dd><dt>FastAPI</dt><dd>{health ? 'Connected' : 'Offline'}</dd><dt>API URL</dt><dd>{API_BASE_URL}</dd></dl><label>{language === 'tr' ? 'Dil' : 'Language'}<select value={language} onChange={e => setLanguage(e.target.value)}><option value="tr">Türkçe</option><option value="en">English</option></select></label></section></> }

createRoot(document.getElementById('root')).render(<App />)
