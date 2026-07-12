// Cœur RAG partagé — utilisé par la page /assistant et la bulle flottante.
// Dépend de PROXY_URL (assistant/config.js). Index chargé paresseusement.
window.EFSRag = (function () {
  const TOP_K = 6, DIM = 768;

  const SYSTEM = `Tu es l'assistant officiel du dossier de candidature d'Aymen BEN BRIK
au grade d'Enseignant Formateur Sénior (EFS), session 2026-2027, à Esprit School of
Business. Tes interlocuteurs sont les membres du jury.
Règles impératives :
1. Tu réponds UNIQUEMENT à partir des extraits du dossier fournis ci-dessous, sans
   jamais compléter avec des connaissances externes ni des suppositions.
2. Chaque affirmation cite sa source entre parenthèses : (L1/L2/L3 ou Présentation, p. N).
3. Si l'information n'est pas dans les extraits, réponds exactement : « Je ne trouve pas
   cette information dans le dossier — je vous invite à consulter les livrables ou à poser
   la question au candidat. »
4. Tu réponds dans la langue de la question (français ou anglais).
5. Tu restes factuel, concis et professionnel ; hors sujet, tu déclines poliment.
6. Tu ne donnes jamais d'avis sur la valeur de la candidature.`;

  let chunks = null, emb = null, nRows = 0;

  async function proxy(payload) {
    const r = await fetch(PROXY_URL, { method: "POST", body: JSON.stringify(payload) });
    if (!r.ok) throw new Error("proxy " + r.status);
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    return data;
  }

  async function loadIndex() {
    if (chunks) return;
    const [cj, eb] = await Promise.all([
      fetch("/assistant/chunks.json").then(r => r.json()),
      fetch("/assistant/emb.bin").then(r => r.arrayBuffer()),
    ]);
    chunks = cj;
    nRows = new Uint32Array(eb, 0, 2)[0];
    emb = new Int8Array(eb, 8);
  }

  async function embedQuery(q) {
    const data = await proxy({ action: "embed", text: q });
    const v = data.embedding.values;
    const n = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
    return v.map(x => x / n);
  }

  function topK(q) {
    const scores = [];
    for (let i = 0; i < nRows; i++) {
      let dot = 0;
      const off = i * DIM;
      for (let j = 0; j < DIM; j++) dot += q[j] * emb[off + j];
      scores.push([dot, i]);
    }
    scores.sort((a, b) => b[0] - a[0]);
    return scores.slice(0, TOP_K).map(s => chunks[s[1]]);
  }

  async function generate(prompt) {
    const data = await proxy({ action: "generate", prompt: prompt });
    const parts = (data.candidates && data.candidates[0] &&
                   data.candidates[0].content && data.candidates[0].content.parts) || [];
    const text = parts.map(p => p.text || "").join("");
    if (!text) throw new Error("réponse vide");
    return text;
  }

  // Pose une question ; history = [{role:'user'|'assistant', content}]
  async function ask(question, history) {
    await loadIndex();
    const q = await embedQuery(question);
    const ctx = topK(q).map(c => `[${c.s}, p. ${c.p}]\n${c.t}`).join("\n\n---\n\n");
    const convo = (history || []).slice(-4)
      .map(h => (h.role === "user" ? "Jury : " : "Assistant : ") + h.content).join("\n");
    const prompt = `${SYSTEM}\n\n=== EXTRAITS DU DOSSIER ===\n${ctx}\n\n=== CONVERSATION ===\n${convo}\nJury : ${question}\nAssistant :`;
    return generate(prompt);
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function md(s) {
    return esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/^\s*[-*] (.+)$/gm, "• $1")
      .replace(/\n/g, "<br>");
  }

  return { ask: ask, md: md, esc: esc };
})();
