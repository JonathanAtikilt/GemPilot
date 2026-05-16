"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

type StepStatus = "Ready" | "Running" | "Waiting" | "Pending" | "Complete";
type RuleSourceType = "url" | "file";

type AgentStep = {
  phase: string;
  title: string;
  detail: string;
  status: StepStatus;
};

const defaultIdea = "Build a healthcare referral coordination agent that helps clinics prevent failed referrals.";

const baseSteps: AgentStep[] = [
  { phase: "Observe", title: "Receive messy idea", detail: "Capture the user idea and one rules source: either a URL or uploaded file.", status: "Ready" },
  { phase: "Retrieve", title: "Read rule source", detail: "RAG agent retrieves hackathon rules, judging criteria, NVIDIA docs, or one uploaded file.", status: "Pending" },
  { phase: "Reason", title: "Scope the MVP", detail: "Nemotron turns the broad idea into a realistic hackathon build plan.", status: "Pending" },
  { phase: "Act", title: "Create repo and generate files", detail: "OpenClaw coordinates GitHub setup, code generation, commits, and build logs.", status: "Pending" },
  { phase: "Verify", title: "Check generated project", detail: "Agent detects blockers, verifies routes, and confirms the demo path works.", status: "Pending" },
  { phase: "Remember", title: "Store build decisions", detail: "RAG and memory store useful choices, blockers, fixes, and final project state.", status: "Pending" },
  { phase: "Report", title: "Generate demo package", detail: "Agent creates the README, demo script, pitch, limitations, and next steps.", status: "Pending" },
];

const demoSources = [
  "Hackathon judging criteria URL",
  "OpenClaw or Nemotron documentation URL",
  "Uploaded README, PDF, TXT, or Markdown file",
];

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    Ready: "border-slate-200 bg-slate-50 text-slate-600",
    Running: "border-cyan-200 bg-cyan-50 text-cyan-700",
    Waiting: "border-amber-200 bg-amber-50 text-amber-700",
    Pending: "border-slate-200 bg-slate-50 text-slate-600",
    Complete: "border-emerald-200 bg-emerald-50 text-emerald-700",
    Failed: "border-rose-200 bg-rose-50 text-rose-700",
  };

  return (
    <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${styles[status] ?? styles.Pending}`}>
      {status}
    </span>
  );
}

export default function Home() {
  const [idea, setIdea] = useState(defaultIdea);
  const [ruleSourceType, setRuleSourceType] = useState<RuleSourceType>("url");
  const [rulesUrl, setRulesUrl] = useState("https://developer.nvidia.com/");
  const [rulesFile, setRulesFile] = useState<File | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [submitState, setSubmitState] = useState<"idle" | "sending" | "sent" | "mocked" | "error">("idle");
  const [message, setMessage] = useState("Ready to send an idea and one rule source to the orchestrator.");

  const payloadPreview = useMemo(
    () => ({
      title: idea.split(".")[0] || "Untitled MVP idea",
      idea,
      rule_source_type: ruleSourceType,
      rules_url: ruleSourceType === "url" ? rulesUrl.trim() || null : null,
      rules_file: ruleSourceType === "file" && rulesFile
        ? {
            name: rulesFile.name,
            type: rulesFile.type || "unknown",
            size: rulesFile.size,
          }
        : null,
      source: "mvpilot_frontend",
    }),
    [idea, ruleSourceType, rulesFile, rulesUrl],
  );

  const steps = baseSteps.map((step, index) => {
    if (submitState === "idle") return step;
    if (index === 0) return { ...step, status: "Complete" as StepStatus };
    if (index === 1) return { ...step, status: "Running" as StepStatus };
    return step;
  });

  function handleSourceTypeChange(nextType: RuleSourceType) {
    setRuleSourceType(nextType);
    setSubmitState("idle");
    setTaskId(null);
    setMessage("Ready to send an idea and one rule source to the orchestrator.");
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setRulesFile(event.target.files?.[0] ?? null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (ruleSourceType === "url" && !rulesUrl.trim()) {
      setSubmitState("error");
      setMessage("Add a rules URL before starting the run.");
      return;
    }

    if (ruleSourceType === "file" && !rulesFile) {
      setSubmitState("error");
      setMessage("Upload one rules file before starting the run.");
      return;
    }

    setSubmitState("sending");
    setMessage("Sending idea and rule source to Person 1's agent endpoint...");

    const apiBaseUrl = process.env.NEXT_PUBLIC_AGENT_API_URL;

    if (!apiBaseUrl) {
      const mockTaskId = `mock-${Date.now()}`;
      setTaskId(mockTaskId);
      setSubmitState("mocked");
      setMessage("No backend URL is configured yet, so the UI created a mock task. Add NEXT_PUBLIC_AGENT_API_URL when Person 1's FastAPI service is ready.");
      return;
    }

    const formData = new FormData();
    formData.append("title", payloadPreview.title);
    formData.append("idea", idea);
    formData.append("rule_source_type", ruleSourceType);
    formData.append("source", "mvpilot_frontend");

    if (ruleSourceType === "url") {
      formData.append("rules_url", rulesUrl.trim());
    }

    if (ruleSourceType === "file" && rulesFile) {
      formData.append("rules_file", rulesFile);
    }

    try {
      const response = await fetch(`${apiBaseUrl}/agent/run`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Agent returned ${response.status}`);
      }

      const data = await response.json();
      setTaskId(data.task_id ?? data.id ?? "sent-without-task-id");
      setSubmitState("sent");
      setMessage("Idea sent to the orchestrator. Next step: subscribe to task updates from Supabase or poll GET /agent/tasks/{task_id}.");
    } catch (error) {
      setSubmitState("error");
      setMessage(error instanceof Error ? error.message : "Could not reach the agent endpoint.");
    }
  }

  return (
    <main className="min-h-screen bg-[#f6f7f9] text-slate-950">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 py-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">MVPilot Mission Control</p>
            <h1 className="mt-2 text-3xl font-bold tracking-normal text-slate-950 lg:text-4xl">
              Turn a messy hackathon idea into a working MVP
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
              Enter an idea, then attach exactly one rule source: a URL or a file. The frontend packages that request for the OpenClaw + Nemotron orchestrator, then shows the autonomous build workflow as it creates the repo, scopes the MVP, logs progress, fixes blockers, and prepares the demo.
            </p>
          </div>
          <div className="w-full rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:w-[360px]">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Agent Handoff</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">POST /agent/run</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">This page is ready to send one rule source once Person 1 provides the FastAPI backend URL.</p>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[0.95fr_1.25fr]">
          <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">Idea Intake</h2>
                <p className="mt-1 text-sm text-slate-600">This is the information you send to the agent brain.</p>
              </div>
              <StatusPill status={submitState === "sending" ? "Running" : submitState === "error" ? "Failed" : taskId ? "Complete" : "Ready"} />
            </div>

            <label className="mt-5 block text-sm font-semibold text-slate-800" htmlFor="idea">Messy project idea</label>
            <textarea id="idea" value={idea} onChange={(event) => setIdea(event.target.value)} rows={4} className="mt-2 w-full resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100" />

            <fieldset className="mt-4">
              <legend className="block text-sm font-semibold text-slate-800">Rules source</legend>
              <div className="mt-2 grid grid-cols-2 gap-2 rounded-md border border-slate-200 bg-slate-50 p-1">
                <button type="button" onClick={() => handleSourceTypeChange("url")} className={`rounded px-3 py-2 text-sm font-semibold transition ${ruleSourceType === "url" ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-white"}`}>URL</button>
                <button type="button" onClick={() => handleSourceTypeChange("file")} className={`rounded px-3 py-2 text-sm font-semibold transition ${ruleSourceType === "file" ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-white"}`}>File</button>
              </div>
            </fieldset>

            {ruleSourceType === "url" ? (
              <>
                <label className="mt-4 block text-sm font-semibold text-slate-800" htmlFor="rules-url">Rules URL</label>
                <input id="rules-url" type="url" value={rulesUrl} onChange={(event) => setRulesUrl(event.target.value)} placeholder="https://example.com/hackathon-rules" className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100" />
              </>
            ) : (
              <>
                <label className="mt-4 block text-sm font-semibold text-slate-800" htmlFor="rules-file">Rules file</label>
                <input id="rules-file" type="file" accept=".pdf,.md,.txt,.doc,.docx,.json,.csv" onChange={handleFileChange} className="mt-2 w-full rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-sm text-slate-700 file:mr-4 file:rounded-md file:border-0 file:bg-slate-950 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" />
                {rulesFile && (
                  <div className="mt-3 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700">
                    {rulesFile.name} <span className="text-slate-400">({Math.ceil(rulesFile.size / 1024)} KB)</span>
                  </div>
                )}
              </>
            )}

            <p className="mt-2 text-xs leading-5 text-slate-500">Choose URL or file. Free-text rules are disabled so the agent retrieves from source material.</p>

            <button type="submit" disabled={submitState === "sending"} className="mt-5 w-full rounded-md bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
              {submitState === "sending" ? "Sending to Agent..." : "Start MVPilot Run"}
            </button>

            <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-600">{message}</p>
          </form>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">Autonomous Workflow</h2>
                <p className="mt-1 text-sm text-slate-600">Mapped from the repo docs: idea input, RAG, scoping, repo creation, commits, fixes, and final pitch.</p>
              </div>
              <StatusPill status={taskId ? "Running" : "Ready"} />
            </div>

            <div className="mt-5 grid gap-3">
              {steps.map((step, index) => (
                <div key={step.phase} className="grid gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-[42px_110px_1fr_auto] sm:items-start">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-950 text-sm font-bold text-white">{index + 1}</div>
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
        </section>

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">Request Payload</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Sent To Person 1</h2>
            <pre className="mt-3 max-h-72 overflow-auto rounded-md bg-slate-950 p-3 text-xs leading-5 text-slate-100">{JSON.stringify(payloadPreview, null, 2)}</pre>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">RAG Inputs</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Allowed Rule Sources</h2>
            <div className="mt-3 grid gap-2">
              {demoSources.map((source) => (
                <div key={source} className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700">{source}</div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold uppercase tracking-wide text-cyan-700">Integration Contract</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">What You Need From Person 1</h2>
            <div className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
              <p>Backend URL for NEXT_PUBLIC_AGENT_API_URL.</p>
              <p>POST /agent/run accepts multipart form data with title, idea, rule_source_type, either rules_url or rules_file, and source.</p>
              <p>Response returns task_id so the UI can display live progress.</p>
              <p>Later: GET /agent/tasks/{"{task_id}"} or Supabase Realtime for updates.</p>
            </div>
            {taskId && <p className="mt-4 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-semibold text-cyan-700">Task ID: {taskId}</p>}
          </div>
        </section>
      </div>
    </main>
  );
}
