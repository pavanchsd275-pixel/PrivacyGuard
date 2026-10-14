import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const api = axios.create({ baseURL: API_BASE })
const TIERS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
const TIER_COLORS = { CRITICAL: '#f36f74', HIGH: '#f6a65b', MEDIUM: '#e6c66b', LOW: '#57c9a5' }
const PROFILE_OPTIONS = {
  bank: {
    label: 'Banking & finance', icon: '▤', note: 'Account, card and customer details',
    types: ['PERSON', 'EMAIL', 'PHONE_IN', 'ADDRESS', 'LOCATION', 'PAN_ID', 'AADHAAR_ID', 'PASSWORD', 'USERNAME', 'ACCOUNT_NUM', 'CREDIT_CARD', 'CVV', 'DATE_OF_BIRTH', 'ID_NUMBER', 'CUSTOM_PII'],
  },
  resume: {
    label: 'Resume & hiring', icon: '▧', note: 'Keep career context, protect personal identifiers',
    types: ['EMAIL', 'PHONE_IN', 'ADDRESS', 'PAN_ID', 'AADHAAR_ID', 'PASSWORD', 'ACCOUNT_NUM', 'CREDIT_CARD', 'CVV', 'ID_NUMBER', 'CUSTOM_PII'],
  },
  medical: {
    label: 'Medical record', icon: '✚', note: 'Patient identity, contact and location details',
    types: ['PERSON', 'EMAIL', 'PHONE_IN', 'ADDRESS', 'LOCATION', 'PAN_ID', 'AADHAAR_ID', 'PASSWORD', 'USERNAME', 'ACCOUNT_NUM', 'CREDIT_CARD', 'CVV', 'DATE_OF_BIRTH', 'ID_NUMBER', 'CUSTOM_PII'],
  },
  legal: {
    label: 'Legal document', icon: '§', note: 'Parties, contact details and account identifiers',
    types: ['PERSON', 'EMAIL', 'PHONE_IN', 'ADDRESS', 'LOCATION', 'ORGANIZATION', 'PAN_ID', 'AADHAAR_ID', 'PASSWORD', 'USERNAME', 'ACCOUNT_NUM', 'CREDIT_CARD', 'CVV', 'DATE_OF_BIRTH', 'ID_NUMBER', 'CUSTOM_PII'],
  },
  general: {
    label: 'General document', icon: '▤', note: 'A balanced personal-data baseline',
    types: ['PERSON', 'EMAIL', 'PHONE_IN', 'ADDRESS', 'PAN_ID', 'AADHAAR_ID', 'PASSWORD', 'USERNAME', 'ACCOUNT_NUM', 'CREDIT_CARD', 'CVV', 'DATE_OF_BIRTH', 'ID_NUMBER', 'CUSTOM_PII'],
  },
}
const CATEGORY_GROUPS = [
  { title: 'Identity', types: [['PERSON', 'Person names'], ['USERNAME', 'Usernames'], ['DATE_OF_BIRTH', 'Date of birth'], ['ID_NUMBER', 'Identity numbers']] },
  { title: 'Contact & location', types: [['EMAIL', 'Email addresses'], ['PHONE_IN', 'Phone numbers'], ['ADDRESS', 'Street addresses'], ['LOCATION', 'Cities and locations']] },
  { title: 'Financial', types: [['ACCOUNT_NUM', 'Bank account numbers'], ['CREDIT_CARD', 'Payment card numbers'], ['CVV', 'Card security codes (CVV/CVC)'], ['PAN_ID', 'PAN numbers'], ['AADHAAR_ID', 'Aadhaar numbers']] },
  { title: 'Access & custom', types: [['PASSWORD', 'Passwords'], ['CUSTOM_PII', 'My manual sensitive terms']] },
  { title: 'Context', types: [['ORGANIZATION', 'Organizations']] },
]
const PROFILE_CATEGORY_GROUPS = {
  bank: [
    { title: 'Customer identity', types: [['PERSON', 'Account holder names'], ['USERNAME', 'Online banking usernames'], ['DATE_OF_BIRTH', 'Dates of birth'], ['ID_NUMBER', 'Identity numbers']] },
    { title: 'Contact & address', types: [['EMAIL', 'Email addresses'], ['PHONE_IN', 'Phone numbers'], ['ADDRESS', 'Street addresses'], ['LOCATION', 'Cities and locations']] },
    { title: 'Financial identifiers', types: [['ACCOUNT_NUM', 'Bank account numbers'], ['CREDIT_CARD', 'Payment card numbers'], ['CVV', 'Card security codes (CVV/CVC)'], ['PAN_ID', 'PAN numbers'], ['AADHAAR_ID', 'Aadhaar numbers']] },
    { title: 'Access & custom', types: [['PASSWORD', 'Passwords'], ['CUSTOM_PII', 'My manual sensitive terms']] },
  ],
  resume: [
    { title: 'Candidate identity', types: [['PERSON', 'Candidate and reference names'], ['USERNAME', 'Usernames'], ['DATE_OF_BIRTH', 'Dates of birth'], ['ID_NUMBER', 'Identity numbers']] },
    { title: 'Contact details', types: [['EMAIL', 'Email addresses'], ['PHONE_IN', 'Phone numbers'], ['ADDRESS', 'Street addresses'], ['LOCATION', 'Locations']] },
    { title: 'Financial & official IDs', types: [['PAN_ID', 'PAN numbers'], ['AADHAAR_ID', 'Aadhaar numbers'], ['ACCOUNT_NUM', 'Bank account numbers'], ['CREDIT_CARD', 'Payment card numbers'], ['CVV', 'Card security codes (CVV/CVC)']] },
    { title: 'Custom protection', types: [['PASSWORD', 'Passwords'], ['CUSTOM_PII', 'My manual sensitive terms']] },
  ],
  medical: [
    { title: 'Patient identity', types: [['PERSON', 'Patient and relative names'], ['DATE_OF_BIRTH', 'Dates of birth'], ['ID_NUMBER', 'Patient / identity numbers']] },
    { title: 'Contact & location', types: [['EMAIL', 'Email addresses'], ['PHONE_IN', 'Phone numbers'], ['ADDRESS', 'Street addresses'], ['LOCATION', 'Cities and locations']] },
    { title: 'Billing identifiers', types: [['ACCOUNT_NUM', 'Account numbers'], ['CREDIT_CARD', 'Payment card numbers'], ['CVV', 'Card security codes (CVV/CVC)'], ['PAN_ID', 'PAN numbers'], ['AADHAAR_ID', 'Aadhaar numbers']] },
    { title: 'Access & custom', types: [['USERNAME', 'Usernames'], ['PASSWORD', 'Passwords'], ['CUSTOM_PII', 'My manual sensitive terms']] },
  ],
  legal: [
    { title: 'Parties & organizations', types: [['PERSON', 'Party and witness names'], ['ORGANIZATION', 'Organizations'], ['ID_NUMBER', 'Identity numbers'], ['DATE_OF_BIRTH', 'Dates of birth']] },
    { title: 'Contact & location', types: [['EMAIL', 'Email addresses'], ['PHONE_IN', 'Phone numbers'], ['ADDRESS', 'Street addresses'], ['LOCATION', 'Cities and locations']] },
    { title: 'Financial identifiers', types: [['ACCOUNT_NUM', 'Account numbers'], ['CREDIT_CARD', 'Payment card numbers'], ['CVV', 'Card security codes (CVV/CVC)'], ['PAN_ID', 'PAN numbers'], ['AADHAAR_ID', 'Aadhaar numbers']] },
    { title: 'Access & custom', types: [['USERNAME', 'Usernames'], ['PASSWORD', 'Passwords'], ['CUSTOM_PII', 'My manual sensitive terms']] },
  ],
  general: CATEGORY_GROUPS,
}
const tokenConfig = (token) => ({ headers: { Authorization: `Bearer ${token}` } })

function Icon({ name, size = 18 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h8"/></>,
    text: <><path d="M4 6h16M4 12h16M4 18h10"/></>,
    chart: <><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-5 5"/></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    lock: <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('privacyguard_token') || '')
  const [user, setUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const [page, setPage] = useState('dashboard')
  const [authMode, setAuthMode] = useState('login')
  const [metrics, setMetrics] = useState(null)
  const [doc, setDoc] = useState(null)
  const [authError, setAuthError] = useState('')

  const loadMetrics = useCallback(async (activeToken) => {
    const { data } = await api.get('/metrics', tokenConfig(activeToken))
    setMetrics(data)
  }, [])

  useEffect(() => {
    if (!token) { setAuthReady(true); return }
    Promise.all([api.get('/auth/me', tokenConfig(token)), loadMetrics(token)])
      .then(([me]) => setUser(me.data))
      .catch(() => { localStorage.removeItem('privacyguard_token'); setToken(''); setUser(null) })
      .finally(() => setAuthReady(true))
  }, [])

  const onAuthenticated = async (data) => {
    localStorage.setItem('privacyguard_token', data.token)
    setToken(data.token)
    setUser(data.user)
    setAuthError('')
    setPage('dashboard')
    await loadMetrics(data.token).catch(() => {})
  }

  const signOut = async () => {
    try { await api.post('/auth/logout', {}, tokenConfig(token)) } catch {}
    localStorage.removeItem('privacyguard_token')
    setToken(''); setUser(null); setMetrics(null); setDoc(null); setPage('dashboard')
  }

  const receiveDocument = (result) => {
    setDoc(result)
    setPage('result')
    loadMetrics(token).catch(() => {})
  }

  if (!authReady) return <div className="boot-screen"><div className="brand-mark"><Icon name="shield" size={22}/></div><p>Opening your private workspace…</p></div>
  if (!user) return <LoginPage mode={authMode} setMode={setAuthMode} onAuthenticated={onAuthenticated} error={authError} setError={setAuthError}/>

  const navItems = [
    { id: 'dashboard', label: 'Overview', icon: 'grid' },
    { id: 'file', label: 'Protect a file', icon: 'file' },
    { id: 'text', label: 'Protect text', icon: 'text' },
  ]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Icon name="shield" size={20}/></div><div><strong>PrivacyGuard</strong><span>PRIVATE WORKSPACE</span></div></div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav">
          {navItems.map((item) => <button key={item.id} className={`nav-item ${page === item.id || (page === 'result' && item.id === 'file') || (page === 'chat' && item.id === 'dashboard') ? 'active' : ''}`} onClick={() => setPage(item.id)}><Icon name={item.icon}/><span>{item.label}</span>{item.id === 'file' && <span className="nav-plus">+</span>}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-badge"><span className="status-dot"/><div><b>Local processing</b><small>Your files stay on this machine</small></div></div>
          <div className="profile-row"><div className="avatar">{user.name?.[0]?.toUpperCase() || 'P'}</div><div className="profile-copy"><b>{user.name}</b><small>{user.email}</small></div><button title="Sign out" className="icon-button" onClick={signOut}><Icon name="logout" size={16}/></button></div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <b>{page === 'dashboard' ? 'Overview' : page === 'file' ? 'Protect a file' : page === 'text' ? 'Protect text' : page === 'chat' ? 'Document Q&A' : 'Protection report'}</b></div><div className="topbar-right"><span className="secure-pill"><Icon name="lock" size={13}/> ENCRYPTED SESSION</span><div className="avatar avatar-small">{user.name?.[0]?.toUpperCase() || 'P'}</div></div></header>
        <div className="content-wrap">
          {page === 'dashboard' && <DashboardPage user={user} metrics={metrics} onRefresh={() => loadMetrics(token)} onNavigate={setPage}/>}
          {page === 'file' && <ProtectPage token={token} onDone={receiveDocument}/>}
          {page === 'text' && <TextPage token={token} onDone={receiveDocument}/>}
          {page === 'result' && doc && <ResultPage doc={doc} token={token} onBack={() => setPage('dashboard')} onChat={() => setPage('chat')}/>}
          {page === 'chat' && doc && <ChatPage doc={doc} token={token} onBack={() => setPage('result')}/>}
        </div>
        <footer className="app-footer"><span>PrivacyGuard <i>·</i> Policy-driven PII protection</span><span>Review every protected copy before sharing</span></footer>
      </main>
    </div>
  )
}

function LoginPage({ mode, setMode, onAuthenticated, error, setError }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const { data } = await api.post(mode === 'register' ? '/auth/register' : '/auth/login', { name, email, password })
      await onAuthenticated(data)
    } catch (err) { setError(err.response?.data?.detail || 'Could not connect to the local PrivacyGuard backend.') }
    finally { setBusy(false) }
  }
  return (
    <div className="login-shell">
      <section className="login-art">
        <div className="login-brand"><div className="brand-mark"><Icon name="shield" size={20}/></div><b>PrivacyGuard</b></div>
        <div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="art-shield"><Icon name="shield" size={58}/><span/></div>
        <div className="login-art-copy"><div className="eyebrow"><span className="status-dot"/> YOUR DOCUMENTS. YOUR RULES.</div><h1>Share with<br/><em>confidence.</em></h1><p>Protect the details that matter. Keep the context people need.</p></div>
        <div className="art-foot"><span>01&nbsp; Detect</span><span>02&nbsp; Decide</span><span>03&nbsp; Protect</span></div>
      </section>
      <section className="login-form-side">
        <div className="login-mobile-brand"><div className="brand-mark"><Icon name="shield" size={20}/></div><b>PrivacyGuard</b></div>
        <div className="auth-card"><div className="eyebrow muted-eyebrow">LOCAL · PRIVATE · POLICY-DRIVEN</div><h2>{mode === 'register' ? 'Create your workspace' : 'Welcome back'}</h2><p className="auth-subtitle">{mode === 'register' ? 'Set up your private document workspace.' : 'Sign in to continue to your private workspace.'}</p>
          <form onSubmit={submit} className="auth-form">
            {mode === 'register' && <label>Your name<input autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="How should we address you?" required maxLength={80}/></label>}
            <label>Email address<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required maxLength={254}/></label>
            <label>Password<div className="password-field"><input type={showPassword ? 'text' : 'password'} autoComplete={mode === 'register' ? 'new-password' : 'current-password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter your password'} minLength={8} required/><button type="button" className="show-password" onClick={() => setShowPassword(!showPassword)}>{showPassword ? 'Hide' : 'Show'}</button></div></label>
            {error && <div className="form-error">{error}</div>}
            <button className="button button-primary button-wide" disabled={busy}>{busy ? 'Please wait…' : mode === 'register' ? 'Create workspace' : 'Sign in'}<Icon name="arrow" size={17}/></button>
          </form>
          <p className="auth-switch">{mode === 'register' ? 'Already have a workspace?' : 'New to PrivacyGuard?'} <button onClick={() => { setError(''); setMode(mode === 'register' ? 'login' : 'register') }}>{mode === 'register' ? 'Sign in' : 'Create an account'}</button></p>
          <div className="auth-note"><Icon name="lock" size={15}/><span>Accounts and sessions are stored locally on this machine. Use a unique password.</span></div>
        </div>
        <div className="login-copyright">PRIVACYGUARD <span>·</span> PRIVATE BY DESIGN</div>
      </section>
    </div>
  )
}

function DashboardPage({ user, metrics, onRefresh, onNavigate }) {
  const risk = metrics?.risk_breakdown || { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
  const maxRisk = Math.max(1, ...Object.values(risk))
  return (
    <div className="page-stack">
      <section className="welcome-row"><div><div className="eyebrow">YOUR PERSONAL PRIVACY WORKSPACE</div><h1>Good to see you, {user.name?.split(' ')[0]}<span className="title-period">.</span></h1><p>Protect a document or text with a policy tailored to its purpose.</p></div><button className="button button-ghost" onClick={onRefresh}><span className="refresh-icon">↻</span> Refresh</button></section>
      <section className="hero-card"><div className="hero-copy"><div className="hero-kicker"><Icon name="shield" size={15}/> CONTEXT-AWARE PROTECTION</div><h2>Information should travel<br/>with the right safeguards.</h2><p>Choose who the document is for. Fine-tune the categories. Add any phrases you want protected or left visible.</p><div className="hero-actions"><button className="button button-light" onClick={() => onNavigate('file')}>Protect a file <Icon name="arrow" size={17}/></button><button className="button button-outline-light" onClick={() => onNavigate('text')}>Protect text <Icon name="text" size={16}/></button></div></div><div className="hero-art"><div className="hero-ring ring-a"/><div className="hero-ring ring-b"/><div className="hero-document"><div className="document-fold"/><span/><span/><span className="short-line"/><b><Icon name="shield" size={23}/></b></div><div className="float-chip chip-top"><span className="chip-dot mint"/>PRIVATE</div><div className="float-chip chip-bottom"><span className="chip-dot gold"/>POLICY APPLIED</div></div></section>

      <section className="metric-grid">
        <MetricCard label="Documents protected" value={metrics?.totals.documents ?? '—'} icon="file" change="Your workspace" tone="blue"/>
        <MetricCard label="Items identified" value={metrics?.totals.entities ?? '—'} icon="shield" change="Across your documents" tone="mint"/>
        <MetricCard label="Items protected" value={metrics?.totals.protected_items ?? '—'} icon="lock" change="Matched your policy" tone="gold"/>
        <MetricCard label="Manual rules" value={metrics?.totals.manual_rules ?? '—'} icon="text" change="Custom terms applied" tone="gold"/>
      </section>

      <section className="dashboard-lower">
        <div className="surface-card risk-card"><div className="section-heading"><div><span className="eyebrow">YOUR WORKSPACE</span><h3>Risk overview</h3></div><span className="mini-icon"><Icon name="chart" size={16}/></span></div><p className="section-note">Detected items grouped by risk level across your protected documents.</p><div className="risk-bars">{TIERS.map((tier) => <div className="risk-bar-row" key={tier}><span className="risk-label"><i style={{ background: TIER_COLORS[tier] }}/>{tier}</span><div className="risk-track"><div style={{ width: `${(risk[tier] / maxRisk) * 100}%`, background: TIER_COLORS[tier] }}/></div><b>{risk[tier] || 0}</b></div>)}</div><div className="risk-foot"><span><i className="legend-dot"/> Entity totals are estimates</span><span>Updated just now</span></div></div>
        <div className="surface-card recent-card"><div className="section-heading"><div><span className="eyebrow">ACTIVITY</span><h3>Recent protection</h3></div><button className="text-link" onClick={() => onNavigate('file')}>New <Icon name="arrow" size={14}/></button></div>{metrics?.recent_documents?.length ? <div className="recent-list">{metrics.recent_documents.map((item) => <div className="recent-item" key={item.doc_id}><div className="recent-file-icon"><Icon name="file" size={17}/></div><div className="recent-copy"><b>{item.filename}</b><small>{PROFILE_OPTIONS[item.profile]?.label || item.profile} · {item.entity_count} items</small></div><RiskPill tier={item.overall_risk}/></div>)}</div> : <div className="empty-activity"><div className="empty-icon"><Icon name="file" size={19}/></div><b>No documents yet</b><span>Your protected files will appear here.</span><button className="text-link" onClick={() => onNavigate('file')}>Protect your first document <Icon name="arrow" size={14}/></button></div>}</div>
      </section>
      <section className="tip-banner"><span className="tip-spark">✦</span><div><b>Make the policy fit the moment</b><span>A bank statement for an accountant may need a different policy than one shared publicly.</span></div><button onClick={() => onNavigate('file')}>Explore profiles <Icon name="arrow" size={15}/></button></section>
    </div>
  )
}

function MetricCard({ label, value, icon, change, tone }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon name={icon} size={18}/></div><span className="metric-label">{label}</span><div className="metric-value">{value}</div><span className="metric-change">{change}</span></div>
}

function ProtectPage({ token, onDone }) {
  const [file, setFile] = useState(null)
  const [profile, setProfile] = useState('bank')
  const [audience, setAudience] = useState('Finance team')
  const [purpose, setPurpose] = useState('Review transactions and balances')
  const [protectTypes, setProtectTypes] = useState(PROFILE_OPTIONS.bank.types)
  const [manualProtect, setManualProtect] = useState('')
  const [manualAllow, setManualAllow] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef(null)

  const chooseProfile = (next) => { setProfile(next); setProtectTypes(PROFILE_OPTIONS[next].types) }
  const toggleType = (type) => setProtectTypes((items) => items.includes(type) ? items.filter((item) => item !== type) : [...items, type])
  const setSelectedFile = (next) => { if (next) { setFile(next); setError('') } }
  const submit = async (event) => {
    event.preventDefault()
    if (!file) { setError('Choose a document first.'); return }
    setBusy(true); setError('')
    const form = new FormData()
    form.append('file', file); form.append('profile', profile); form.append('audience', audience); form.append('purpose', purpose)
    form.append('protect_types', protectTypes.join(',')); form.append('manual_protect', manualProtect); form.append('manual_allow', manualAllow)
    try { const { data } = await api.post('/process', form, tokenConfig(token)); onDone(data) }
    catch (err) { setError(err.response?.data?.detail || 'The backend could not process this document.') }
    finally { setBusy(false) }
  }

  return <div className="page-stack">
    <PageTitle eyebrow="DOCUMENT WORKFLOW" title="Protect a file" subtitle="Choose the document context, set the release policy, then review the protected copy."/>
    <form className="protection-layout" onSubmit={submit}>
      <div className="protection-main">
        <section className="surface-card form-section"><SectionHeader number="01" title="Choose a document profile" subtitle="Profiles preselect sensitive categories. You can change every selection."/><div className="profile-grid">{Object.entries(PROFILE_OPTIONS).map(([key, value]) => <button type="button" key={key} className={`profile-option ${profile === key ? 'selected' : ''}`} onClick={() => chooseProfile(key)}><span className="profile-icon">{value.icon}</span><b>{value.label}</b><small>{value.note}</small>{profile === key && <span className="selected-check">✓</span>}</button>)}</div></section>
        <section className="surface-card form-section"><SectionHeader number="02" title={`Decide what to protect · ${PROFILE_OPTIONS[profile].label}`} subtitle="Options are tailored to this document type. Checked categories will be anonymized when found."/><div className="category-groups">{PROFILE_CATEGORY_GROUPS[profile].map((group) => <div className="category-group" key={group.title}><h4>{group.title}</h4><div className="category-options">{group.types.map(([type, label]) => <label className="check-option" key={type}><input type="checkbox" checked={protectTypes.includes(type)} onChange={() => toggleType(type)}/><span className="custom-check">✓</span><span>{label}</span></label>)}</div></div>)}</div><div className="manual-grid"><label>Always protect these phrases <small>One phrase per line. Every matching occurrence is redacted.</small><textarea value={manualProtect} onChange={(e) => setManualProtect(e.target.value)} placeholder={'e.g. Client Northstar\nProject Falcon'} rows={3}/></label><label>Leave these phrases visible <small>Overrides automatic detection, except phrases listed to protect.</small><textarea value={manualAllow} onChange={(e) => setManualAllow(e.target.value)} placeholder={'e.g. Vellore Institute of Technology'} rows={3}/></label></div></section>
        <section className="surface-card form-section"><SectionHeader number="03" title="Who is this copy for?" subtitle="Recipient and purpose help you choose a policy you can explain."/><div className="field-grid"><label>Recipient<input value={audience} onChange={(e) => setAudience(e.target.value)} maxLength={100} placeholder="e.g. finance team, accountant"/></label><label>Purpose<input value={purpose} onChange={(e) => setPurpose(e.target.value)} maxLength={300} placeholder="e.g. share selected transactions"/></label></div></section>
      </div>
      <aside className="protection-aside"><div className={`drop-card ${dragging ? 'dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); setSelectedFile(e.dataTransfer.files?.[0]) }}><input ref={fileRef} hidden type="file" accept=".pdf,.docx,.txt,.csv" onChange={(e) => setSelectedFile(e.target.files?.[0])}/><div className="drop-icon"><Icon name="file" size={24}/></div><h3>{file ? file.name : 'Add your document'}</h3><p>{file ? `${(file.size / 1024).toFixed(0)} KB · ready to scan` : 'PDF, DOCX, TXT or CSV. Drop it here or browse.'}</p><button type="button" className="button button-ghost button-small" onClick={() => fileRef.current?.click()}>{file ? 'Change file' : 'Browse files'}</button></div><div className="policy-summary"><div className="summary-heading"><Icon name="shield" size={16}/> CURRENT POLICY</div><b>{PROFILE_OPTIONS[profile].label}</b><p>{protectTypes.length} categories selected · {manualProtect.split(/[\n;,]+/).filter(Boolean).length} manual phrases</p><div className="summary-rule"/><div className="summary-line"><span>Recipient</span><b>{audience || 'Not set'}</b></div><div className="summary-line"><span>Visible terms</span><b>{manualAllow.split(/[\n;,]+/).filter(Boolean).length} manual exceptions</b></div></div><div className="privacy-note"><Icon name="lock" size={15}/><span>Original file is removed after the protected copy is generated. Review the result before sharing.</span></div>{error && <div className="form-error">{error}</div>}<button className="button button-primary button-wide protect-button" disabled={busy}>{busy ? <><span className="spinner"/> Scanning and protecting…</> : <>Protect document <Icon name="arrow" size={17}/></>}</button></aside>
    </form>
  </div>
}

function TextPage({ token, onDone }) {
  const [text, setText] = useState('')
  const [profile, setProfile] = useState('general')
  const [audience, setAudience] = useState('Personal review')
  const [purpose, setPurpose] = useState('Protect pasted text')
  const [protectTypes, setProtectTypes] = useState(PROFILE_OPTIONS.general.types)
  const [manualProtect, setManualProtect] = useState('')
  const [manualAllow, setManualAllow] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const chooseProfile = (next) => { setProfile(next); setProtectTypes(PROFILE_OPTIONS[next].types) }
  const toggleType = (type) => setProtectTypes((items) => items.includes(type) ? items.filter((item) => item !== type) : [...items, type])
  const submit = async (event) => {
    event.preventDefault()
    if (!text.trim()) { setError('Paste or write some text first.'); return }
    setBusy(true); setError('')
    const payload = {
      text, profile, audience, purpose, protect_types: protectTypes,
      manual_protect: manualProtect.split(/[\n;,]+/).map((v) => v.trim()).filter(Boolean),
      manual_allow: manualAllow.split(/[\n;,]+/).map((v) => v.trim()).filter(Boolean),
    }
    try { const { data } = await api.post('/protect-text', payload, tokenConfig(token)); onDone(data) }
    catch (err) { setError(err.response?.data?.detail || 'Could not protect this text.') }
    finally { setBusy(false) }
  }
  return <div className="page-stack"><PageTitle eyebrow="QUICK PROTECTION" title="Protect text" subtitle="Write or paste a paragraph, set the sharing policy, and get a protected version instantly."/><form onSubmit={submit} className="text-workspace"><div className="text-input-column"><section className="surface-card text-editor-card"><div className="editor-heading"><div><span className="eyebrow">YOUR TEXT</span><h3>Draft or paste content</h3></div><button type="button" className="text-link" onClick={() => setText('')}>Clear</button></div><textarea className="main-textarea" maxLength={100000} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste an email, a paragraph, or any text you want to share more safely…"/><div className="editor-footer"><span><span className="status-dot"/> Processed on this machine</span><span>{text.length.toLocaleString()} / 100,000</span></div></section><div className="manual-grid"><label>Always protect these phrases<textarea value={manualProtect} onChange={(e) => setManualProtect(e.target.value)} placeholder={'One phrase per line\ne.g. patient code 4382'} rows={3}/></label><label>Leave these phrases visible<textarea value={manualAllow} onChange={(e) => setManualAllow(e.target.value)} placeholder="One phrase per line" rows={3}/></label></div></div><aside className="text-settings surface-card"><SectionHeader number="01" title="Protection policy" subtitle="Choose a preset, then fine-tune its relevant fields."/><label className="standalone-label">Document type<select value={profile} onChange={(e) => chooseProfile(e.target.value)}>{Object.entries(PROFILE_OPTIONS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label><div className="compact-categories">{PROFILE_CATEGORY_GROUPS[profile].map((group) => <details key={group.title} open={group.title.toLowerCase().includes('financial') && profile === 'bank'}><summary>{group.title}<span>{group.types.filter(([type]) => protectTypes.includes(type)).length} selected</span></summary>{group.types.map(([type, label]) => <label className="check-option" key={type}><input type="checkbox" checked={protectTypes.includes(type)} onChange={() => toggleType(type)}/><span className="custom-check">✓</span><span>{label}</span></label>)}</details>)}</div><label className="standalone-label">Who will receive it?<input value={audience} onChange={(e) => setAudience(e.target.value)} maxLength={100} placeholder="e.g. faculty reviewer"/></label><label className="standalone-label">Purpose<input value={purpose} onChange={(e) => setPurpose(e.target.value)} maxLength={300}/></label>{error && <div className="form-error">{error}</div>}<button className="button button-primary button-wide" disabled={busy || !text.trim()}>{busy ? 'Protecting…' : <>Protect this text <Icon name="arrow" size={17}/></>}</button></aside></form><div className="text-helper"><Icon name="lock" size={15}/>Your text is not saved in browser storage. Only the protected copy and basic metrics are stored for your account.</div></div>
}

function PageTitle({ eyebrow, title, subtitle }) { return <div className="page-title"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p></div> }
function SectionHeader({ number, title, subtitle }) { return <div className="form-section-heading"><span className="step-number">{number}</span><div><h3>{title}</h3><p>{subtitle}</p></div></div> }

function ResultPage({ doc, token, onBack, onChat }) {
  const [copied, setCopied] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const copy = async () => { await navigator.clipboard.writeText(doc.protected_text); setCopied(true); setTimeout(() => setCopied(false), 1800) }
  const download = async () => {
    setDownloadError('')
    try {
      const { data } = await api.get(doc.download_url, { ...tokenConfig(token), responseType: 'blob' })
      const url = URL.createObjectURL(data); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${doc.filename.replace(/\.[^.]+$/, '')}_protected.${doc.file_type || 'txt'}`; anchor.click(); URL.revokeObjectURL(url)
    } catch { setDownloadError('Download failed. Your session may have expired.') }
  }
  return <div className="page-stack"><PageTitle eyebrow="PROTECTION COMPLETE" title="Your policy report" subtitle={`Prepared for ${doc.audience || 'your chosen recipient'} · ${doc.purpose || 'Purpose not specified'}`}/><section className="result-banner"><div className="result-shield"><Icon name="shield" size={24}/></div><div><span className="eyebrow">SCAN COMPLETE · {doc.ner_backend || 'HYBRID DETECTION'}</span><h2>Protected copy is ready</h2><p>{doc.filename} · {doc.entities.length} detected items · {PROFILE_OPTIONS[doc.profile]?.label || 'Custom policy'}</p></div><RiskPill tier={doc.risk.overall_risk}/></section><section className="result-metrics"><MetricCard label="Items identified" value={doc.risk.total_entities} icon="shield" change="Regex + contextual NER" tone="mint"/><MetricCard label="Items protected" value={doc.protected_items ?? doc.risk.total_entities} icon="lock" change="Under your selected policy" tone="blue"/><MetricCard label="Manual phrases" value={doc.manual_protect_count ?? 0} icon="text" change="Added by your policy" tone="gold"/><MetricCard label="Unresolved matches" value={doc.residual_structured_pii} icon="chart" change="Protected patterns still visible" tone={doc.residual_structured_pii ? 'gold' : 'mint'}/></section><section className="surface-card result-entities"><div className="section-heading"><div><span className="eyebrow">DETECTION DETAIL</span><h3>What the guard found</h3></div><span className="detector-chip"><span className="status-dot"/>{doc.ner_backend || 'hybrid'} active</span></div>{doc.entities.length ? <div className="entity-table">{doc.entities.slice(0, 40).map((entity, index) => <div className="entity-row" key={`${entity.start}-${index}`}><span className="entity-type">{entity.entity_type.replaceAll('_', ' ')}</span><span className="entity-value">{entity.text}</span><span className="entity-source">{entity.source}</span><span className="entity-score">{Math.round(entity.confidence * 100)}%</span></div>)}</div> : <div className="empty-state">No PII items were detected. Review the text carefully before sharing.</div>}</section><section className="surface-card protected-preview"><div className="section-heading"><div><span className="eyebrow">SAFE TO REVIEW</span><h3>Protected content preview</h3></div><div className="preview-actions"><button type="button" className="button button-ghost button-small" onClick={copy}>{copied ? 'Copied!' : 'Copy text'}</button><button type="button" className="button button-primary button-small" onClick={download}>Download <Icon name="arrow" size={15}/></button></div></div><pre>{doc.protected_text}</pre>{downloadError && <div className="form-error">{downloadError}</div>}</section><div className="result-actions"><button className="button button-ghost" onClick={onBack}>← Dashboard</button><button className="button button-primary" onClick={onChat}>Ask about this document <Icon name="arrow" size={16}/></button></div></div>
}

function RiskPill({ tier = 'LOW' }) { return <span className="risk-pill" style={{ color: TIER_COLORS[tier], borderColor: `${TIER_COLORS[tier]}55`, background: `${TIER_COLORS[tier]}12` }}><i style={{ background: TIER_COLORS[tier] }}/>{tier}</span> }

function ChatPage({ doc, token, onBack }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])
  const ask = async (question) => {
    const value = question.trim(); if (!value || busy) return
    setMessages((items) => [...items, { role: 'user', text: value }]); setInput(''); setBusy(true)
    try { const { data } = await api.post('/chat', { doc_id: doc.doc_id, question: value }, tokenConfig(token)); setMessages((items) => [...items, { role: 'assistant', ...data }]) }
    catch (err) { setMessages((items) => [...items, { role: 'error', text: err.response?.data?.detail || 'Could not reach the PrivacyGuard backend.' }]) }
    finally { setBusy(false) }
  }
  return <div className="page-stack"><PageTitle eyebrow="PRIVATE DOCUMENT Q&A" title="Ask about your document" subtitle={`Answers use the protected version of ${doc.filename}.`} /><section className="surface-card chat-card"><div className="chat-topline"><div className="metric-icon mint"><Icon name="shield" size={18}/></div><div><b>Protected context only</b><span>Responses are checked before they are shown.</span></div><RiskPill tier="LOW"/></div><div className="chat-messages">{!messages.length && <div className="chat-empty"><div className="chat-empty-icon"><Icon name="text" size={22}/></div><h3>What would you like to know?</h3><p>Try a question about topics, dates, or key points. Protected values stay hidden.</p><div className="suggestions">{['Summarize the main points', 'What skills or topics are mentioned?', 'List the key dates'].map((value) => <button key={value} onClick={() => ask(value)}>{value}<Icon name="arrow" size={13}/></button>)}</div></div>}{messages.map((item, index) => item.role === 'user' ? <div className="chat-user" key={index}>{item.text}</div> : item.role === 'error' ? <div className="form-error" key={index}>{item.text}</div> : <div className="chat-answer" key={index}><p>{item.answer}</p><span className="answer-status">{item.status} · privacy check</span></div>)}{busy && <div className="chat-thinking"><span className="spinner"/> Looking through protected context…</div>}<div ref={endRef}/></div><form className="chat-input-row" onSubmit={(e) => { e.preventDefault(); ask(input) }}><input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question about this document…"/><button className="button button-primary" disabled={!input.trim() || busy}>Send <Icon name="arrow" size={15}/></button></form></section><button className="button button-ghost" onClick={onBack}>← Protection report</button></div>
}
