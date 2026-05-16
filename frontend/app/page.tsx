"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

type StepStatus = "Ready" | "Running" | "Pending" | "Complete" | "Failed";
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

const flightStops: AgentStep[] = [
  { phase: "PREFLIGHT", title: "Capture brief", detail: "Package the title, idea, GitHub connection, rules URL, and extra source material.", status: "Ready" },
  { phase: "RAG SCAN", title: "Retrieve rules", detail: "Index hackathon rules, NVIDIA docs, uploaded files, and additional URLs.", status: "Pending" },
  { phase: "SCOPE", title: "Plan MVP", detail: "Nemotron narrows the broad idea into a realistic hackathon build.", status: "Pending" },
  { phase: "SYNTH", title: "Generate repo", detail: "OpenClaw coordinates repo creation, code generation, commits, and build logs.", status: "Pending" },
  { phase: "QA", title: "Verify build", detail: "The agent detects blockers, verifies outputs, and records fixes.", status: "Pending" },
  { phase: "LANDING", title: "Deliver MVP", detail: "Final README, demo script, pitch, and GitHub repo are ready for review.", status: "Pending" },
];

const sourceTypes = [
  "Primary hackathon rules URL",
  "Additional OpenClaw or Nemotron documentation URLs",
  "Optional uploaded README, PDF, TXT, or Markdown files",
];

function readGithubConnectionId() {
  if (typeof window === "undefined") return null;

  const params = new URLSearchParams(window.location.search);
  const connectionId = params.get("github_connection_id");
  const status = params.get("github_status");

  if (connectionId && status === "ready") {
    window.sessionStorage.setItem("mvpilot_github_connection_id", connectionId);
    return connectionId;
  }

  return window.sessionStorage.getItem("mvpilot_github_connection_id");
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    Ready: "border-[#3a494b] bg-[#1c1f29] text-[#b9cacb]",
    Running: "border-[#00f2ff]/40 bg-[#00f2ff]/10 text-[#00f2ff] shadow-[0_0_12px_rgba(0,242,255,0.18)]",
    Pending: "border-[#3a494b] bg-[#181b25] text-[#849495]",
    Complete: "border-[#4edea3]/40 bg-[#4edea3]/10 text-[#4edea3] shadow-[0_0_12px_rgba(78,222,163,0.18)]",
    Failed: "border-[#ffb4ab]/50 bg-[#93000a]/40 text-[#ffb4ab]",
  };

  return (
    <span className={`rounded-full border px-2.5 py-1 font-mono text-[11px] font-bold uppercase tracking-widest ${styles[status] ?? styles.Pending}`}>
      {status}
    </span>
  );
}

function PlaneMarker({ progress }: { progress: number }) {
  return (
    <div className="absolute top-0 z-20 -translate-x-1/2 transition-all duration-700" style={{ left: `${progress}%` }}>
      <div className="flex items-center gap-1 rounded-full border border-[#00f2ff]/50 bg-[#00f2ff] px-2 py-1 text-[10px] font-black tracking-widest text-[#00363a] shadow-[0_0_18px_rgba(0,242,255,0.55)]">
        <span className="h-0 w-0 border-y-[5px] border-l-[9px] border-y-transparent border-l-[#00363a]" />
        MVP
      </div>
    </div>
  );
}

export default function Home() {
  const [projectTitle, setProjectTitle] = useState(defaultTitle);
  const [idea, setIdea] = useState(defaultIdea);
  const [primaryRulesUrl, setPrimaryRulesUrl] = useState("https://developer.nvidia.com/");
  const [additionalSources, setAdditionalSources] = useState<AdditionalSource[]>([]);
  const [nextSourceType, setNextSourceType] = useState<AdditionalSourceType>("url");
  const [githubConnectionId, setGithubConnectionId] = useState<string | null>(null);
  const [githubMessage, setGithubMessage] = useState("Connect GitHub so MVPilot can create or update the project repo through the backend.");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [repoUrl, setRepoUrl] = useState<string | null>(null);
  const [submitState, setSubmitState] = useState<"idle" | "sending" | "sent" | "mocked" | "error">("idle");
  const [message, setMessage] = useState("Ready for preflight. Add the build brief and launch MVPilot.");

  useEffect(() => {
    Promise.resolve().then(() => {
      const connectionId = readGithubConnectionId();

      if (connectionId) {
        setGithubConnectionId(connectionId);
        setGithubMessage("GitHub connection ready. The backend will exchange it when the run starts.");
        window.history.replaceState({}, "", window.location.pathname);
      }
    });
  }, []);

  const payloadPreview = useMemo(
    () => ({
      title: projectTitle.trim() || "Untitled MVP idea",
      idea,
      github_connected: Boolean(githubConnectionId),
      github_connection_id: githubConnectionId,
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
    [additionalSources, githubConnectionId, idea, primaryRulesUrl, projectTitle],
  );

  const hasLaunched = submitState !== "idle" && submitState !== "error";
  const progressPercent = submitState === "sent" ? 58 : hasLaunched ? 34 : 0;
  const activeStopIndex = submitState === "sent" ? 3 : hasLaunched ? 1 : 0;
  const completedStops = submitState === "sent" ? 3 : hasLaunched ? 1 : 0;
  const additionalUrlCount = payloadPreview.additional_urls.length;
  const additionalFileCount = payloadPreview.additional_files.length;

  const steps = flightStops.map((step, index) => {
    if (submitState === "error" && index === 0) return { ...step, status: "Failed" as StepStatus };
    if (!hasLaunched && index === 0) return { ...step, status: "Ready" as StepStatus };
    if (index < completedStops) return { ...step, status: "Complete" as StepStatus };
    if (index === activeStopIndex) return { ...step, status: "Running" as StepStatus };
    return { ...step, status: "Pending" as StepStatus };
  });

  function connectGitHub() {
    const apiBaseUrl = process.env.NEXT_PUBLIC_AGENT_API_URL;

    if (!apiBaseUrl) {
      setGithubMessage("Missing NEXT_PUBLIC_AGENT_API_URL. Start the FastAPI backend URL before connecting GitHub.");
      return;
    }

    const params = new URLSearchParams({
      return_to: window.location.origin,
    });

    window.location.href = `${apiBaseUrl}/github/connect?${params.toString()}`;
  }

  function disconnectGitHub() {
    setGithubConnectionId(null);
    window.sessionStorage.removeItem("mvpilot_github_connection_id");
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
    setMessage("Flight plan filed. Sending the build brief to Person 1's orchestrator...");

    const apiBaseUrl = process.env.NEXT_PUBLIC_AGENT_API_URL;

    if (!apiBaseUrl) {
      const mockTaskId = `mock-${Date.now()}`;
      setTaskId(mockTaskId);
      setSubmitState("mocked");
      setMessage("No backend URL is configured yet, so MVPilot is showing a mock flight path. Add NEXT_PUBLIC_AGENT_API_URL when Person 1's FastAPI service is ready.");
      return;
    }

    const formData = new FormData();
    formData.append("title", payloadPreview.title);
    formData.append("idea", idea);
    formData.append("primary_rules_url", primaryRulesUrl.trim());
    formData.append("source", "mvpilot_frontend");

    if (githubConnectionId) {
      formData.append("github_connected", "true");
      formData.append("github_connection_id", githubConnectionId);
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
      setRepoUrl(data.repo_url ?? data.github_repo_url ?? null);
      setSubmitState("sent");
      setMessage("MVPilot is airborne. Next step: subscribe to task updates or poll GET /agent/tasks/{task_id}.");
    } catch (error) {
      setSubmitState("error");
      setMessage(error instanceof Error ? error.message : "Could not reach the agent endpoint.");
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0e17] text-[#dfe2ef] [background-image:linear-gradient(rgba(0,242,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,242,255,0.03)_1px,transparent_1px)] [background-size:20px_20px]">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-5 lg:px-8">
        <header className="flex h-auto flex-col gap-4 border-b border-[#3a494b]/50 bg-[#0f131c]/80 pb-5 backdrop-blur-xl lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-[#00f2ff]/30 bg-[#00f2ff]/10 font-mono text-sm font-black text-[#00f2ff] shadow-[0_0_15px_rgba(0,242,255,0.16)]">MP</div>
              <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#4edea3]">Mission Control</p>
            </div>
            <h1 className="mt-3 max-w-4xl text-4xl font-bold tracking-normal text-[#e1fdff] lg:text-5xl">
              MVPilot Flight Control
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-[#b9cacb]">
              File a build brief, connect GitHub, and fly the project through retrieval, scoping, repo synthesis, verification, and final delivery.
            </p>
          </div>
          <div className="rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/70 p-4 backdrop-blur-xl">
            <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#849495]">System</p>
            <div className="mt-2 flex items-center gap-3">
              <span className="h-2.5 w-2.5 rounded-full bg-[#4edea3] shadow-[0_0_10px_rgba(78,222,163,0.9)]" />
              <p className="font-mono text-sm font-semibold text-[#4edea3]">FRONTEND STABLE</p>
            </div>
            <p className="mt-2 font-mono text-xs text-[#b9cacb]">Task: {taskId ? taskId : "NOT LAUNCHED"}</p>
          </div>
        </header>

        <section className="overflow-hidden rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl">
          <div className="relative min-h-[560px] p-5 lg:p-7">
            <div className="pointer-events-none absolute -left-48 -top-72 h-[620px] w-[620px] rounded-full bg-[conic-gradient(from_0deg_at_50%_50%,rgba(0,242,255,0.12)_0deg,transparent_90deg)]" />

            {!hasLaunched ? (
              <form onSubmit={handleSubmit} className="relative z-10 grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
                <section className="rounded-lg border border-[#00f2ff]/15 bg-[#0f131c]/80 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Preflight Brief</p>
                      <h2 className="mt-2 text-2xl font-semibold tracking-normal text-[#dfe2ef]">Launch Parameters</h2>
                    </div>
                    <StatusPill status={submitState === "error" ? "Failed" : "Ready"} />
                  </div>

                  <label className="mt-5 block font-mono text-[11px] font-bold uppercase tracking-widest text-[#b9cacb]" htmlFor="project-title">Project title</label>
                  <input id="project-title" type="text" required value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} placeholder="Healthcare Referral Coordinator" className="mt-2 w-full rounded border border-[#3a494b] bg-[#0a0e17] px-3 py-2 font-mono text-sm leading-6 text-[#e1fdff] outline-none transition focus:border-[#00f2ff] focus:ring-1 focus:ring-[#00f2ff]/40" />

                  <label className="mt-4 block font-mono text-[11px] font-bold uppercase tracking-widest text-[#b9cacb]" htmlFor="idea">Project idea</label>
                  <textarea id="idea" value={idea} onChange={(event) => setIdea(event.target.value)} rows={4} className="mt-2 w-full resize-none rounded border border-[#3a494b] bg-[#0a0e17] px-3 py-2 font-mono text-sm leading-6 text-[#e1fdff] outline-none transition focus:border-[#00f2ff] focus:ring-1 focus:ring-[#00f2ff]/40" />

                  <section className="mt-5 rounded-lg border border-[#3a494b]/70 bg-[#1c1f29]/70 p-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#4edea3]">GitHub Link</p>
                        <p className="mt-1 text-sm leading-5 text-[#b9cacb]">Backend owns OAuth and stores the token server-side. No GitHub secret is stored in the browser.</p>
                      </div>
                      {githubConnectionId ? (
                        <button type="button" onClick={disconnectGitHub} className="rounded border border-[#00f2ff]/50 px-3 py-2 font-mono text-xs font-bold uppercase tracking-widest text-[#00f2ff] transition hover:bg-[#00f2ff]/10">Disconnect</button>
                      ) : (
                        <button type="button" onClick={connectGitHub} className="rounded bg-[#00f2ff] px-3 py-2 font-mono text-xs font-bold uppercase tracking-widest text-[#00363a] transition hover:shadow-[0_0_15px_rgba(0,242,255,0.28)]">Connect</button>
                      )}
                    </div>
                    <div className="mt-3 flex items-start justify-between gap-3 rounded border border-[#3a494b] bg-[#0a0e17] px-3 py-2">
                      <p className="text-sm leading-6 text-[#b9cacb]">{githubMessage}</p>
                      <StatusPill status={githubConnectionId ? "Complete" : "Ready"} />
                    </div>
                  </section>

                  <label className="mt-4 block font-mono text-[11px] font-bold uppercase tracking-widest text-[#b9cacb]" htmlFor="primary-rules-url">Primary rules URL</label>
                  <input id="primary-rules-url" type="url" required value={primaryRulesUrl} onChange={(event) => setPrimaryRulesUrl(event.target.value)} placeholder="https://example.com/hackathon-rules" className="mt-2 w-full rounded border border-[#3a494b] bg-[#0a0e17] px-3 py-2 font-mono text-sm leading-6 text-[#e1fdff] outline-none transition focus:border-[#00f2ff] focus:ring-1 focus:ring-[#00f2ff]/40" />

                  <div className="mt-5 rounded-lg border border-[#3a494b]/70 bg-[#1c1f29]/70 p-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                      <div>
                        <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#b9cacb]">Additional sources</p>
                        <p className="mt-1 text-sm leading-5 text-[#849495]">Add extra URLs or files only when the agent needs more context.</p>
                      </div>
                      <div className="flex gap-2">
                        <select value={nextSourceType} onChange={(event) => setNextSourceType(event.target.value as AdditionalSourceType)} className="rounded border border-[#3a494b] bg-[#0a0e17] px-3 py-2 font-mono text-xs font-bold uppercase tracking-widest text-[#dfe2ef] outline-none focus:border-[#00f2ff]">
                          <option value="url">URL</option>
                          <option value="file">File</option>
                        </select>
                        <button type="button" onClick={addSource} className="rounded bg-[#00f2ff] px-3 py-2 font-mono text-xs font-black text-[#00363a] transition hover:shadow-[0_0_15px_rgba(0,242,255,0.28)]" aria-label="Add additional source">+</button>
                      </div>
                    </div>

                    {additionalSources.length > 0 && (
                      <div className="mt-3 grid gap-3">
                        {additionalSources.map((source) => (
                          <div key={source.id} className="rounded border border-[#3a494b] bg-[#0a0e17] p-3">
                            <div className="flex items-center justify-between gap-3">
                              <p className="font-mono text-xs font-bold uppercase tracking-widest text-[#00f2ff]">Additional {source.type}</p>
                              <button type="button" onClick={() => removeSource(source.id)} className="rounded border border-[#3a494b] px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-widest text-[#b9cacb] transition hover:border-[#00f2ff]/50">Remove</button>
                            </div>
                            {source.type === "url" ? (
                              <input type="url" value={source.value} onChange={(event) => updateAdditionalUrl(source.id, event.target.value)} placeholder="https://example.com/extra-docs" className="mt-2 w-full rounded border border-[#3a494b] bg-[#181b25] px-3 py-2 font-mono text-sm leading-6 text-[#e1fdff] outline-none transition focus:border-[#00f2ff]" />
                            ) : (
                              <input type="file" accept=".pdf,.md,.txt,.doc,.docx,.json,.csv" onChange={(event) => updateAdditionalFile(source.id, event)} className="mt-2 w-full rounded border border-dashed border-[#3a494b] bg-[#181b25] px-3 py-3 text-sm text-[#b9cacb] file:mr-4 file:rounded file:border-0 file:bg-[#00f2ff] file:px-3 file:py-2 file:font-mono file:text-xs file:font-bold file:uppercase file:tracking-widest file:text-[#00363a]" />
                            )}
                            {source.type === "file" && source.file && (
                              <p className="mt-2 font-mono text-xs text-[#849495]">{source.file.name} ({Math.ceil(source.file.size / 1024)} KB)</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <button type="submit" className="mt-5 w-full rounded bg-[#00f2ff] px-4 py-3 font-mono text-xs font-black uppercase tracking-widest text-[#00363a] transition hover:shadow-[0_0_18px_rgba(0,242,255,0.35)] disabled:cursor-not-allowed disabled:bg-[#31353f] disabled:text-[#849495]">
                    Launch MVPilot
                  </button>

                  <p className="mt-3 rounded border border-[#3a494b] bg-[#0a0e17] px-3 py-2 font-mono text-xs leading-5 text-[#b9cacb]">{message}</p>
                </section>

                <section className="relative min-h-[500px] overflow-hidden rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/50 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                  <div className="absolute inset-0 opacity-70 [background-image:linear-gradient(rgba(0,242,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(0,242,255,0.04)_1px,transparent_1px)] [background-size:20px_20px]" />
                  <div className="relative z-10">
                    <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Flight Path</p>
                    <h2 className="mt-2 text-2xl font-semibold tracking-normal text-[#e1fdff]">Parameters staged on runway</h2>
                    <p className="mt-2 max-w-xl text-sm leading-6 text-[#b9cacb]">After launch, this panel becomes the live checkpoint bar. The plane advances as the Person 1 orchestrator reports progress.</p>
                  </div>
                  <div className="absolute left-8 right-8 top-1/2 h-px bg-[#3a494b]" />
                  <div className="absolute left-8 right-8 top-1/2 flex -translate-y-1/2 justify-between">
                    {flightStops.map((stop) => (
                      <div key={stop.phase} className="flex flex-col items-center gap-3">
                        <div className="h-4 w-4 rounded-full border-4 border-[#0f131c] bg-[#31353f]" />
                        <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#849495]">{stop.phase}</p>
                      </div>
                    ))}
                  </div>
                  <PlaneMarker progress={2} />
                </section>
              </form>
            ) : (
              <section className="relative z-10 grid gap-5">
                <div className="rounded-lg border border-[#00f2ff]/15 bg-[#0f131c]/85 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Autopilot Active</p>
                      <h2 className="mt-2 text-2xl font-semibold tracking-normal text-[#e1fdff]">{payloadPreview.title}</h2>
                      <p className="mt-2 max-w-3xl font-mono text-xs leading-5 text-[#b9cacb]">{message}</p>
                    </div>
                    <div className="text-left lg:text-right">
                      <p className="font-mono text-4xl font-bold text-[#00f2ff]">{progressPercent}%</p>
                      <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#849495]">Completion</p>
                    </div>
                  </div>

                  <div className="mt-12 overflow-x-auto px-2 pb-5 pt-12">
                    <div className="relative min-w-[900px]">
                      <div className="absolute left-0 right-0 top-8 h-0.5 bg-[#3a494b]" />
                      <div className="absolute left-0 top-8 h-0.5 bg-[#4edea3] shadow-[0_0_10px_rgba(78,222,163,0.65)] transition-all duration-700" style={{ width: `calc(${progressPercent}% - 12px)` }} />
                      <PlaneMarker progress={progressPercent} />
                      <div className="grid grid-cols-6 gap-4">
                        {steps.map((step) => (
                          <div key={step.phase} className="relative flex flex-col items-center pt-3 text-center">
                            <div className={`z-10 h-5 w-5 rounded-full border-4 border-[#0f131c] ${step.status === "Complete" ? "bg-[#4edea3] shadow-[0_0_12px_rgba(78,222,163,0.65)]" : step.status === "Running" ? "bg-[#00f2ff] shadow-[0_0_20px_rgba(0,242,255,0.7)]" : "bg-[#31353f]"}`} />
                            <p className={`mt-4 font-mono text-[11px] font-bold uppercase tracking-widest ${step.status === "Running" ? "text-[#00f2ff]" : step.status === "Complete" ? "text-[#4edea3]" : "text-[#849495]"}`}>{step.phase}</p>
                            <p className="mt-1 text-xs leading-5 text-[#b9cacb]">{step.title}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid gap-5 lg:grid-cols-3">
                  <div className="rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/75 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                    <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Radar Evidence</p>
                    <h3 className="mt-2 text-xl font-semibold text-[#dfe2ef]">Source manifest</h3>
                    <div className="mt-4 grid gap-2 font-mono text-xs text-[#b9cacb]">
                      <p>Primary URL: {primaryRulesUrl}</p>
                      <p>Extra URLs: {additionalUrlCount}</p>
                      <p>Extra files: {additionalFileCount}</p>
                      <p>GitHub: {githubConnectionId ? "CONNECTED" : "NOT CONNECTED"}</p>
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/75 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                    <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Active Stop</p>
                    <h3 className="mt-2 text-xl font-semibold text-[#dfe2ef]">{steps[activeStopIndex].title}</h3>
                    <p className="mt-3 text-sm leading-6 text-[#b9cacb]">{steps[activeStopIndex].detail}</p>
                  </div>

                  <div className="rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/75 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                    <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Landing Zone</p>
                    <h3 className="mt-2 text-xl font-semibold text-[#dfe2ef]">{repoUrl ? "GitHub repo ready" : "GitHub repo pending"}</h3>
                    {repoUrl ? (
                      <a href={repoUrl} target="_blank" rel="noreferrer" className="mt-4 inline-flex rounded bg-[#00f2ff] px-3 py-2 font-mono text-xs font-black uppercase tracking-widest text-[#00363a]">Open repo</a>
                    ) : (
                      <p className="mt-3 text-sm leading-6 text-[#b9cacb]">When Person 1 returns repo_url, this card links to the generated project, README, demo script, and pitch.</p>
                    )}
                    {taskId && <p className="mt-4 rounded border border-[#00f2ff]/20 bg-[#00f2ff]/10 px-3 py-2 font-mono text-xs font-bold text-[#00f2ff]">Task ID: {taskId}</p>}
                  </div>
                </div>
              </section>
            )}
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-3">
          <div className="rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/70 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl">
            <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Run Summary</p>
            <h2 className="mt-2 text-xl font-semibold text-[#dfe2ef]">{payloadPreview.title}</h2>
            <p className="mt-3 text-sm leading-6 text-[#b9cacb]">{idea}</p>
          </div>

          <div className="rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/70 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl">
            <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">RAG Inputs</p>
            <h2 className="mt-2 text-xl font-semibold text-[#dfe2ef]">Allowed source material</h2>
            <div className="mt-3 grid gap-2">
              {sourceTypes.map((source) => (
                <div key={source} className="rounded border border-[#3a494b] bg-[#0f131c] px-3 py-2 text-sm text-[#b9cacb]">{source}</div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-[#00f2ff]/15 bg-[#181b25]/70 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl">
            <p className="font-mono text-[11px] font-bold uppercase tracking-widest text-[#00f2ff]">Person 1 Handoff</p>
            <h2 className="mt-2 text-xl font-semibold text-[#dfe2ef]">Payload unchanged</h2>
            <div className="mt-3 space-y-2 text-sm leading-6 text-[#b9cacb]">
              <p>POST /agent/run receives title, idea, github_connection_id, primary_rules_url, additional_urls, additional_files, and source.</p>
              <p>Backend returns task_id and can later return repo_url for the landing zone.</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
