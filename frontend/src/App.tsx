import BackendStatus from './components/BackendStatus'

/**
 * N0 shell only: proves the design-system tokens bootstrap and the SPA can
 * reach the FastAPI backend. No product pages yet (10 routes come later
 * milestones); Sidebar layout follows the mockup language (navy sidebar +
 * light content surface) at a minimal level — no polish in N0.
 */
export default function App() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 bg-[var(--factora-navy)] p-5 text-slate-200">
        <h1 className="text-lg font-semibold tracking-tight text-white">
          Factora <span className="text-blue-400">/</span> Factory OS
        </h1>
        <p className="mt-1 text-[11px] text-slate-400">Autonomous factory operating system</p>

        <nav className="mt-6 space-y-1 text-[13px] text-slate-400">
          <p className="px-2 py-1">Scaffold — routes arrive in later milestones</p>
        </nav>

        <div className="mt-8">
          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-[10px] font-medium text-amber-300">
            N0 scaffold — 0 / 10 pages
          </span>
        </div>
      </aside>

      <main className="flex-1 p-6">
        <div className="mx-auto max-w-3xl space-y-5">
          <BackendStatus />
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800">Milestone status</h2>
            <p className="mt-2 text-xs leading-relaxed text-slate-600">
              Fresh neatHack scaffold. Design tokens from docs/design/mockups are bootstrapped in
              src/index.css; the digital twin, agents, and product pages do not exist yet.
            </p>
          </section>
        </div>
      </main>
    </div>
  )
}
