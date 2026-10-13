// Baseline traffic driver for the tutorial demo agent app (CrewAI + DeepSeek).
//
// Goal: a clean, steady OPEN-model arrival process so the workload-model skill can derive
// pace / CoV / per-turn baseline from the resulting traces in YOUR observability backend —
// with BOTH archetypes present (tool-using turns -> `execute_tool` spans -> Agentic;
// pure-LLM turns -> Conversational).
//
// Why constant-arrival-rate: it decouples arrivals from response latency (LLM turns are
// slow and variable), so the arrival curve the skill reconstructs is the one we specified,
// not one distorted by closed-loop think-time — the methodology's open-model stance.
//
// Tunables (env):
//   BASE_URL     default http://localhost:8080   (port-forward or in-cluster Service)
//   RATE_PER_MIN default 20                       (turns/min; 20 * 45m ~= 900 turns)
//   DURATION     default 45m
//   TOOL_RATIO   default 0.30                     (fraction of turns that force tool use)
//   PRE_ALLOC    default 20                       (VUs pre-allocated for the arrival rate)
import http from "k6/http";
import { check, sleep } from "k6";
import { SharedArray } from "k6/data";

const RATE_PER_MIN = parseInt(__ENV.RATE_PER_MIN || "20", 10);
const DURATION = __ENV.DURATION || "45m";
const TOOL_RATIO = parseFloat(__ENV.TOOL_RATIO || "0.30");
const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const PRE_ALLOC = parseInt(__ENV.PRE_ALLOC || "20", 10);

const prompts = new SharedArray("prompts", () => JSON.parse(open("./prompts.json")));

export const options = {
  scenarios: {
    agent_turns: {
      executor: "constant-arrival-rate",
      rate: RATE_PER_MIN,
      timeUnit: "1m",
      duration: DURATION,
      preAllocatedVUs: PRE_ALLOC,
      maxVUs: PRE_ALLOC * 4,
    },
  },
  thresholds: {
    // Keep the window clean: fail loud if the app starts erroring under load.
    http_req_failed: ["rate<0.05"],
  },
};

function pick(pool) {
  return pool[Math.floor(Math.random() * pool.length)];
}

export default function () {
  const useTool = Math.random() < TOOL_RATIO;
  const turnType = useTool ? "tool" : "chat";
  const bank = prompts.filter((p) => p.turn_type === turnType);
  const prompt = pick(bank.length ? bank : prompts).prompt;

  const res = http.post(
    `${BASE_URL}/request`,
    JSON.stringify({ prompt, turn_type: turnType }),
    { headers: { "Content-Type": "application/json" }, timeout: "120s", tags: { turn_type: turnType } }
  );

  check(res, {
    "status 200": (r) => r.status === 200,
    "answer present": (r) => {
      try { return !!r.json("answer"); } catch (_e) { return false; }
    },
  });

  // Small jitter avoids lock-step VU reuse artifacts; arrival timing is owned by the executor.
  sleep(Math.random() * 0.5);
}
