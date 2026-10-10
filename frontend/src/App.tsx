import { Link, Route, Routes, useLocation } from 'react-router'

import BackendStatus from './components/BackendStatus'
import FactoryStatus from './components/FactoryStatus'
import CommandCenter from './routes/CommandCenter'
import TwinPage from './routes/TwinPage'

const LIVE_ITEMS = [
  { to: '/', label: 'Command Center' },
  { to: '/twin', label: 'Factory Twin', accent: true },
  { to: '/factory', label: 'Factory World' },
]

const UPCOMING = ['Machines', 'Predictive', 'Agent Activity', 'Work Orders', 'Parts', 'OEE', 'Planner']

export default function App() {
  const location = useLocation()
  const onTwin = location.pathname === '/twin'

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-52 shrink-0 flex-col justify-between bg-[var(--factora-navy)] px-4 py-5 text-slate-300">
        <div>
          <Link to="/" className="block">
            <h1 className="text-lg font-semibold tracking-tight text-white">
              Factora <span className="text-blue-400">/</span> Factory OS
            </h1>
          </Link>
          <p className="mt-1 text-[10px] text-slate-400">Autonomous factory · neatHack build</p>

          <nav className="mt-6 space-y-0.5">
            {LIVE_ITEMS.map((item) => {
              const active = location.pathname === item.to
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`block rounded-md px-3 py-1.5 text-[13px] transition ${
                    active
                      ? item.accent
                        ? 'bg-blue-500/20 font-medium text-blue-300'
                        : 'bg-white/10 font-medium text-white'
                      : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                  }`}
                >
                  {item.label}
                  {item.accent && <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-amber-400 align-middle" />}
                </Link>
              )
            })}
          </nav>

          <p className="mt-5 px-3 text-[9px] font-semibold uppercase tracking-widest text-slate-500">
            Later milestones
          </p>
          <div className="mt-1 space-y-0.5">
            {UPCOMING.map((item) => (
              <span key={item} className="block cursor-default rounded-md px-3 py-1 text-[11px] text-slate-600">
                {item}
              </span>
            ))}
          </div>
        </div>

        <span className="mx-3 rounded-full border border-slate-600 px-2.5 py-1 text-center text-[9px] font-medium uppercase tracking-wider text-slate-400">
          {onTwin ? 'Twin · live sim' : '3 / 10 pages'}
        </span>
      </aside>

      <main className={`flex-1 ${onTwin ? 'flex h-screen flex-col p-4' : 'p-6'}`}>
        {onTwin ? (
          <Routes>
            <Route path="/twin" element={<TwinPage />} />
          </Routes>
        ) : (
          <div className="mx-auto max-w-6xl">
            <Routes>
              <Route path="/" element={<CommandCenter />} />
              <Route
                path="/factory"
                element={
                  <div className="space-y-5">
                    <div>
                      <h1 className="text-lg font-semibold tracking-tight text-slate-800">Factory World</h1>
                      <p className="text-xs text-slate-500">Direct FactoryWorld health + snapshot panels</p>
                    </div>
                    <FactoryStatus />
                    <BackendStatus />
                  </div>
                }
              />
              <Route path="*" element={<CommandCenter />} />
            </Routes>
          </div>
        )}
      </main>
    </div>
  )
}
