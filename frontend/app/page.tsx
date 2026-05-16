"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

type StepStatus = "Ready" | "Running" | "Waiting" | "Pending" | "Complete";
type AdditionalSourceType = "url" | "file";

type AgentStep = {
  phase: string;
  title: string;
  detail: string;
  status: StepStatus;
};

type AdditionalSource =
  | { id: number; type: "url"; value: string }
  | { id: number; type: "file"; file: File | null };

const defaultTitle = "Healthcare Referral Coordinator";
const defaultIdea = "Build a healthcare referral coordination agent that helps clinics prevent failed referrals.";

const baseSteps: AgentStep[] = [
  { phase: "Observe", title: "Receive messy idea", detail: "Capture the user idea, GitHub connection, primary rules URL, and any extra source material.", status: "Ready" },
  { phase: "Retrieve", title: "Read source material", detail: "RAG agent retrieves hackathon rules, judging criteria, NVIDIA docs, uploaded files, and additional URLs.", status: "Pending" },
  { phase: "Reason", title: "Scope the MVP", detail: "Nemotron turns the broad idea into a realistic hackathon build plan.", status: "Pending" },
  { phase: "Act", title: "Create repo and generate files", detail: "OpenClaw coordinates GitHub setup, code generation, commits, and build logs.", status: "Pending" },
  { phase: "Verify", title: "Check generated project", detail: "Agent detects blockers, verifies routes, and confirms the demo path works.", status: "Pending" },
  { phase: "Remember", title: "Store build decisions", detail: "RAG and memory store useful choices, blockers, fixes, and final project state.", status: "Pending" },
  { phase: "Report", title: "Generate demo package", detail: "Agent creates the README, demo script, pitch, limitations, and next steps.", status: "Pending" },
];

const demoSources = [
  "Primary hackathon rules URL",
  "Additional OpenClaw or Nemotron documentation URLs",
  "Optional uploaded README, PDF, TXT, or Markdown files",
];

function readGithubAuthCode() {
  if (typeof window === "undefined") return null;

  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const state = params.get("state");
  const expectedState = window.localStorage.getItem("mvpilot_github_oauth_state");

  return code && state === expectedState ? code : null;
}

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
  const [projectTitle, setProjectTitle] = useState(defaultTitle);
  const [idea, setIdea] = useState(defaultIdea);
  const [primaryRulesUrl, setPrimaryRulesUrl] = useState("https://developer.nvidia.com/");
  const [additionalSources, setAdditionalSources] = useState<AdditionalSource[]>([]);
  const [nextSourceType, setNextSourceType] = useState<AdditionalSourceType>("url");
  const [githubAuthCode, setGithubAuthCode] = useState<string | null>(null);
  const [githubMessage, setGithubMessage] = useState("Connect GitHub so the agent can create or update a repo after backend token exchange.");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [submitState, setSubmitState] = useState<"idle" | "sending" | "sent" | "mocked" | "error">("idle");
  const [message, setMessage] = useState("Ready to send an idea and source material to the orchestrator.");

  useEffect(() => {
    Promise.resolve().then(() => {
      const code = readGithubAuthCode();

      if (code) {
        setGithubAuthCode(code);
        setGithubMessage("GitHub authorization received. Person 1's backend still needs to exchange this code for an access token.");
        window.history.replaceState({}, "", window.location.pathname);
      }
    });
  }, []);

  const payloadPreview = useMemo(
    () => ({
      title: projectTitle.trim() || "Untitled MVP idea",
      idea,
      github_connected: Boolean(githubAuthCode),
      github_auth_code: githubAuthCode ? "received_by_frontend" : null,
      primary_rules_url: primaryRulesUrl.trim() || null,
      additional_urls: additionalSources
        .filter((source): source is Extract<AdditionalSource, { type: "url" }> => source.type === "url")
        .map((source) => source.value.trim())
        .filter(Boolean),
      additional_files: additionalSources
        .filter((source): source is Extract<AdditionalSource, { type: "file" }> => source.type === "file" && Boolean(source.file))
        .map((source) => ({
          name: source.file?.name,
          type: source.file?.type || "unknown",
          size: source.file?.size,
        })),
      source: "mvpilot_frontend",
    }),
    [additionalSources, githubAuthCode, idea, primaryRulesUrl, projectTitle],
  );

  const steps = baseSteps.map((step, index) => {
    if (submitState === "idle") return step;
    if (index === 0) return { ...step, status: "Complete" as StepStatus };
    if (index === 1) return { ...step, status: "Running" as StepStatus };
    return step;
  });

  function connectGitHub() {
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID;

    if (!clientId) {
      setGithubMessage("Missing NEXT_PUBLIC_GITHUB_CLIENT_ID. Create a GitHub OAuth App, add the client ID to .env.local, then restart npm run dev.");
      return;
    }

    const state = crypto.randomUUID();
    window.localStorage.setItem("mvpilot_github_oauth_state", state);

    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: window.location.origin,
      scope: "repo read:user user:email",
      state,
    });

    window.location.href = `https://github.com/login/oauth/authorize?${params.toString()}`;
  }

  function disconnectGitHub() {
    setGithubAuthCode(null);
    setGithubMessage("GitHub disconnected for this browser session.");
  }

  function addSource() {
    setAdditionalSources((sources) => [
      ...sources,
      nextSourceType === "url"
        ? { id: Date.now(), type: "url", value: "" }
        : { id: Date.now(), type: "file", file: null },
    ]);
  }

  function removeSource(id: number) {
    setAdditionalSources((sources) => sources.filter((source) => source.id !== id));
  }

  function updateAdditionalUrl(id: number, value: string) {
    setAdditionalSources((sources) =>
      sources.map((source) => source.id === id && source.type === "url" ? { ...source, value } : source),
    );
  }

  function updateAdditionalFile(id: number, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setAdditionalSources((sources) =>
      sources.map((source) => source.id === id && source.type === "file" ? { ...source, file } : source),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!projectTitle.trim()) {
      setSubmitState("error");
      setMessage("Add a project title before starting the run.");
      return;
    }

    if (!primaryRulesUrl.trim()) {
      setSubmitState("error");
      setMessage("Add the primary rules URL before starting the run.");
      return;
    }

    setSubmitState("sending");
    setMessage("Sending idea and source material to Person 1's agent endpoint...");

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
    formData.append("primary_rules_url", primaryRulesUrl.trim());
    formData.append("source", "mvpilot_frontend");

    if (githubAuthCode) {
      formData.append("github_auth_code", githubAuthCode);
    }

    additionalSources.forEach((source) => {
      if (source.type === "url" && source.value.trim()) {
        formData.append("additional_urls", source.value.trim());
      }

      if (source.type === "file" && source.file) {
        formData.append("additional_files", source.file);
      }
    });

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
              Enter an idea, connect GitHub, and add source material. The frontend packages that request for the OpenClaw + Nemotron orchestrator, then shows the autonomous build workflow as it creates the repo, scopes the MVP, logs progress, fixes blockers, and prepares the demo.
            </p>
          </div>
          <div className="w-full rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:w-[360px]">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Agent Handoff</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">POST /agent/run</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">This page sends the idea, GitHub authorization code, primary URL, and optional sources once Person 1&apos;s FastAPI backend is running.</p>
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

            <label className="mt-5 block text-sm font-semibold text-slate-800" htmlFor="project-title">Project title</label>
            <input id="project-title" type="text" required value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} placeholder="Healthcare Referral Coordinator" className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100" />

            <label className="mt-4 block text-sm font-semibold text-slate-800" htmlFor="idea">Project idea</label>
            <textarea id="idea" value={idea} onChange={(event) => setIdea(event.target.value)} rows={4} className="mt-2 w-full resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100" />

            <section className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-800">GitHub connection</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">The backend exchanges the temporary code for an access token. No GitHub secret is stored in the browser.</p>
                </div>
                {githubAuthCode ? (
                  <button type="button" onClick={disconnectGitHub} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white">Disconnect</button>
                ) : (
                  <button type="button" onClick={connectGitHub} className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">Connect GitHub</button>
                )}
              </div>
              <div className="mt-3 flex items-start justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 py-2">
                <p className="text-sm leading-6 text-slate-600">{githubMessage}</p>
                <StatusPill status={githubAuthCode ? "Complete" : "Ready"} />
              </div>
            </section>

            <label className="mt-4 block text-sm font-semibold text-slate-800" htmlFor="primary-rules-url">Primary rules URL</label>
            <input id="primary-rules-url" type="url" required value={primaryRulesUrl} onChange={(event) => setPrimaryRulesUrl(event.target.value)} placeholder="https://example.com/hackathon-rules" className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100" />

            <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-800">Additional information</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">Add extra URLs or files only when the agent needs more context.</p>
                </div>
                <div className="flex gap-2">
                  <select value={nextSourceType} onChange={(event) => setNextSourceType(event.target.value as AdditionalSourceType)} className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100">
                    <option value="url">URL</option>
                    <option value="file">File</option>
                  </select>
                  <button type="button" onClick={addSource} className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800" aria-label="Add additional source">+</button>
                </div>
              </div>

              {additionalSources.length > 0 && (
                <div className="mt-3 grid gap-3">
                  {additionalSources.map((source) => (
                    <div key={source.id} className="rounded-md border border-slate-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-cyan-700">Additional {source.type === "url" ? "URL" : "file"}</p>
                        <button type="button" onClick={() => removeSource(source.id)} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-600 transition hover:bg-slate-100">Remove</button>
                      </div>
                      {source.type === "url" ? (
                        <input type="url" value={source.value} onChange={(event) => updateAdditionalUrl(source.id, event.target.value)} placeholder="https://example.com/extra-docs" className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100" />
                      ) : (
                        <input type="file" accept=".pdf,.md,.txt,.doc,.docx,.json,.csv" onChange={(event) => updateAdditionalFile(source.id, event)} className="mt-2 w-full rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-sm text-slate-700 file:mr-4 file:rounded-md file:border-0 file:bg-slate-950 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" />
                      )}
                      {source.type === "file" && source.file && (
                        <p className="mt-2 text-xs text-slate-500">{source.file.name} ({Math.ceil(source.file.size / 1024)} KB)</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

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
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Allowed Source Material</h2>
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
              <p>GitHub OAuth app client ID for NEXT_PUBLIC_GITHUB_CLIENT_ID.</p>
              <p>POST /agent/run accepts multipart form data with title, idea, github_auth_code, primary_rules_url, additional_urls, additional_files, and source.</p>
              <p>Person 1&apos;s backend exchanges github_auth_code for a GitHub token using the OAuth app client secret.</p>
              <p>Response returns task_id so the UI can display live progress.</p>
            </div>
            {taskId && <p className="mt-4 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-semibold text-cyan-700">Task ID: {taskId}</p>}
          </div>
        </section>
      </div>
    </main>
  );
}




