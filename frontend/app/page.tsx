const agentSteps = [
  { phase: "Observe", title: "Checkout latency alert received", detail: "Latency has stayed above 2 seconds for 15 minutes.", status: "Complete" },
  { phase: "Retrieve", title: "Runbook matched", detail: "Found checkout incident response steps from the knowledge base.", status: "Complete" },
  { phase: "Reason", title: "Likely payment API timeout", detail: "Nemotron compared logs, runbook guidance, and prior memory.", status: "Complete" },
  { phase: "Act", title: "Draft Slack and ticket update", detail: "Medium-risk action paused for human approval.", status: "Waiting" },
  { phase: "Verify", title: "Confirm update after approval", detail: "Agent will read back the posted message and ticket state.", status: "Pending" },
  { phase: "Remember", title: "Store incident outcome", detail: "Root cause and resolution will be saved for future runs.", status: "Pending" },
  { phase: "Report", title: "Generate final incident summary", detail: "Final report includes sources, tools, action, and verification.", status: "Pending" },
];

const toolCalls = [
  { name: "Runbook Search", result: "Checkout latency runbook", status: "Verified" },
  { name: "Memory Lookup", result: "Similar payment timeout from last week", status: "Verified" },
  { name: "Log Search", result: "Spike in payment_provider_timeout", status: "Verified" },
  { name: "Slack Update", result: "Awaiting approval", status: "Blocked" },
];

const reportItems = [
  "Trigger: checkout latency exceeded the incident threshold.",
  "Evidence: runbook guidance, prior memory, and live log search agree on payment API timeout.",
  "Action: request approval to notify engineering and update the incident ticket.",
  "Verification: after approval, confirm the Slack message and ticket update exist.",
];

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    Complete: "border-emerald-200 bg-emerald-50 text-emerald-700",
    Waiting: "border-amber-200 bg-amber-50 text-amber-700",
    Pending: "border-slate-200 bg-slate-50 text-slate-600",
    Verified: "border-cyan-200 bg-cyan-50 text-cyan-700",
    Blocked: "border-rose-200 bg-rose-50 text-rose-700",
  };

  return (
    <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${styles[status] ?? styles.Pending}`}>
      {status}
    </span>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f6f7f9] text-slate-950">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 py-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">MVPilot Mission Control</p>
            <h1 className="mt-2 text-3xl font-bold tracking-normal text-slate-950 lg:text-4xl">
              Autonomous Incident Response Agent
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
              A live dashboard for judges to watch the agent observe an enterprise event, retrieve context, reason, act with approval, verify the result, remember the outcome, and report what happened.
            </p>
          </div>
          <div className="w-full rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:w-[360px]">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Current Trigger</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">Checkout latency incident</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">Checkout latency is above 2 seconds for 15 minutes.</p>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">Agent Timeline</h2>
                <p className="mt-1 text-sm text-slate-600">The required enterprise loop is visible as the agent runs.</p>
              </div>
              <StatusPill status="Waiting" />
            </div>

            <div className="mt-5 grid gap-3">
              {agentSteps.map((step, index) => (
                <div key={step.phase} className="grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-[42px_110px_1fr_auto] sm:items-start">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-950 text-sm font-bold text-white">
                    {index + 1}
                  </div>
                  <p className="text-sm font-semibold text-cyan-700">{step.phase}</p>
                  <div>
                    <p className="font-semibold text-slate-950">{step.title}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-600">{step.detail}</p>
                  </div>
                  <StatusPill status={step.status} />
                </div>
              ))}
            </div>
          </div>

          <aside className="flex flex-col gap-6">
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">Approval Gate</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                The agent wants to send a Slack update and mark the ticket as investigating. This is a medium-risk action, so it pauses for human approval.
              </p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <button className="rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">
                  Approve Action
                </button>
                <button className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
                  Reject
                </button>
              </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">Tool Activity</h2>
              <div className="mt-4 grid gap-3">
                {toolCalls.map((tool) => (
                  <div key={tool.name} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-950">{tool.name}</p>
                      <StatusPill status={tool.status} />
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{tool.result}</p>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </section>

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">RAG Source</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Checkout Runbook</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              If payment provider timeouts rise, notify engineering, update the incident ticket, and monitor checkout recovery for 10 minutes.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">Persistent Memory</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Similar Prior Incident</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Last week, checkout latency was caused by payment API timeout. Slack notification and ticket update reduced triage time.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">Final Report</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Ready After Verification</h2>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
              {reportItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </main>
  );
}
