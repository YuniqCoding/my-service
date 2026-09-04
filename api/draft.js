/* 답장 초안을 써 주는 자리입니다.
 *
 * 이 파일은 브라우저가 아니라 Vercel 서버에서 돕니다.
 * 그래서 열쇠(GEMINI_API_KEY)는 서버 안에만 있고,
 * 화면 소스를 아무리 열어 봐도 열쇠는 나오지 않습니다.
 *
 * 화면(index.html) → 여기(/api/draft) → Gemini → 다시 화면
 *
 * 부르는 방법은 공식 문서(Interactions API)를 따랐습니다.
 *   POST https://generativelanguage.googleapis.com/v1beta/interactions
 *   헤더 x-goog-api-key, Api-Revision: 2026-05-20
 *   본문 { model, system_instruction, input, generation_config }
 *   답 steps[].content[].text
 *   https://ai.google.dev/gemini-api/docs/interactions/text-generation
 */

const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions";
const MODEL = "gemini-3.8-flash";
const API_REVISION = "2026-05-20";

/* 초안을 쓸 때 지켜야 할 것 */
const SYSTEM = [
  "당신은 한국의 교육과정 운영 담당자입니다.",
  "강사님께 보낼 답장 메일의 본문 초안을 씁니다.",
  "",
  "지킬 것",
  "- 다섯 줄을 넘기지 마세요. 한 줄은 한 문장입니다.",
  "- 마지막에 강사님이 보내신 메일에 대한 답이어야 합니다. 물어보신 것에 빠짐없이 답하세요.",
  "- 바로 복사해 메일에 붙일 수 있는 말투로 씁니다. 정중한 존댓말을 쓰세요.",
  "- 인사 → 용건 → 필요하면 요청 → 맺음 순서로 씁니다.",
  "- 확실하지 않은 것은 지어내지 말고 확인해서 알려드리겠다고 쓰세요.",
  "- 날씨나 계절 같은 겉치레 인사는 넣지 마세요.",
  "",
  "쓰지 말 것",
  "- '받는 사람', '제목' 같은 머리말",
  "- 별표나 우물정자 같은 꾸미는 기호, 목록 기호",
  "- 초안에 대한 설명이나 인사말 밖의 군더더기"
].join("\n");

/* 말풍선과 강사님 정보를 하나의 글로 묶습니다 */
function buildInput(d) {
  const mails = (d.mails || []).map(function (m) {
    const who = m.from === "나" ? "담당자(나)" : (d.name + " 강사님");
    const body = (m.lines || []).join(" ");
    return "[" + m.date + "] " + who + " — " + (m.subject || "") + "\n" + body;
  }).join("\n\n");

  return [
    "다음은 강사님 한 분과 지금까지 주고받은 메일입니다.",
    "",
    "강사님 성함: " + d.name,
    "담당 모듈: " + d.module,
    "일정: " + d.when,
    "장소: " + d.place,
    "현재 상태: " + d.status,
    "",
    "----- 주고받은 메일 (오래된 것부터) -----",
    mails,
    "----------------------------------------",
    "",
    "맨 마지막 메일은 " + d.name + " 강사님이 보내신 것이고, 지금 제 답장을 기다리고 계십니다.",
    "그 메일에 답하는 메일 본문을 다섯 줄 안쪽으로 써 주세요."
  ].join("\n");
}

/* 답에서 글자만 꺼냅니다 */
function pickText(json) {
  if (typeof json.output_text === "string" && json.output_text.trim()) {
    return json.output_text;
  }
  const steps = json.steps || [];
  const texts = [];
  for (const step of steps) {
    for (const c of (step.content || [])) {
      if (c.type === "text" && c.text) texts.push(c.text);
    }
  }
  return texts.join("\n");
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "POST로만 부를 수 있습니다." });
  }

  const key = process.env.GEMINI_API_KEY;
  if (!key) {
    return res.status(500).json({
      error: "열쇠(GEMINI_API_KEY)가 서버에 없습니다. Vercel 환경 변수에 넣어 주세요."
    });
  }

  let d = req.body;
  if (typeof d === "string") {
    try { d = JSON.parse(d); } catch { d = null; }
  }
  if (!d || !d.name || !Array.isArray(d.mails) || d.mails.length === 0) {
    return res.status(400).json({ error: "강사님 정보나 메일 내용이 오지 않았습니다." });
  }

  try {
    const r = await fetch(ENDPOINT, {
      method: "POST",
      headers: {
        "x-goog-api-key": key,
        "Content-Type": "application/json",
        "Api-Revision": API_REVISION
      },
      body: JSON.stringify({
        model: MODEL,
        system_instruction: SYSTEM,
        input: buildInput(d),
        generation_config: {
          max_output_tokens: 600,
          thinking_level: "low"
        }
      })
    });

    const json = await r.json().catch(function () { return {}; });

    if (!r.ok) {
      /* 무엇이 잘못됐는지 한 줄로 돌려줍니다. 열쇠는 절대 담지 않습니다 */
      const why = (json.error && (json.error.message || json.error.status)) || ("HTTP " + r.status);
      return res.status(502).json({ error: "Gemini가 거절했습니다 — " + String(why).slice(0, 200) });
    }

    const text = pickText(json).trim();
    if (!text) {
      return res.status(502).json({
        error: "Gemini가 빈 답을 보냈습니다" + (json.status ? " (" + json.status + ")" : "") + "."
      });
    }

    /* 혹시 길게 오더라도 다섯 줄까지만 씁니다 */
    const lines = text.split("\n").map(s => s.trim()).filter(Boolean).slice(0, 5);

    return res.status(200).json({ draft: lines.join("\n") });

  } catch (e) {
    return res.status(502).json({ error: "Gemini를 부르지 못했습니다 — " + String(e.message || e).slice(0, 200) });
  }
};
