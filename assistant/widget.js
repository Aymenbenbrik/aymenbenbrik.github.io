// Bulle flottante « Assistant du dossier » — présente sur tout le site,
// sauf sur la page /assistant (qui offre la version pleine page).
(function () {
  if (location.pathname.endsWith("/assistant.html")) return;

  const WELCOME = "Bonjour — posez-moi vos questions sur le dossier EFS " +
    "d'Aymen Ben Brik. Je réponds uniquement à partir des livrables, en citant mes sources.";

  const bubble = document.createElement("button");
  bubble.className = "efs-bubble";
  bubble.setAttribute("aria-label", "Ouvrir l'assistant du dossier");
  bubble.innerHTML = '<i class="bi bi-chat-dots" aria-hidden="true"></i>';

  const panel = document.createElement("div");
  panel.className = "efs-panel";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Assistant du dossier");
  panel.innerHTML =
    '<div class="efs-head"><span>Assistant du dossier</span>' +
    '<span><a href="/assistant.html">page complète</a> ' +
    '<button class="efs-close" aria-label="Fermer">✕</button></span></div>' +
    '<div class="efs-msgs"></div>' +
    '<div class="efs-row">' +
    '<input class="efs-input" type="text" placeholder="Votre question…" ' +
    'aria-label="Votre question sur le dossier">' +
    '<button class="efs-send">➤</button></div>';

  document.body.appendChild(bubble);
  document.body.appendChild(panel);

  const msgs = panel.querySelector(".efs-msgs");
  const input = panel.querySelector(".efs-input");
  const send = panel.querySelector(".efs-send");
  const history = [];

  function addMsg(cls, html) {
    const div = document.createElement("div");
    div.className = "efs-msg " + cls;
    div.innerHTML = html;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  addMsg("efs-bot", EFSRag.esc(WELCOME));

  function toggle(open) {
    panel.hidden = !open;
    bubble.setAttribute("aria-expanded", String(open));
    if (open) input.focus();
  }

  bubble.addEventListener("click", () => toggle(panel.hidden));
  panel.querySelector(".efs-close").addEventListener("click", () => toggle(false));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !panel.hidden) toggle(false);
  });

  async function ask(q) {
    addMsg("efs-user", EFSRag.esc(q));
    input.value = "";
    send.disabled = true;
    const wait = addMsg("efs-bot efs-typing", "Je consulte le dossier…");
    try {
      const answer = await EFSRag.ask(q, history);
      wait.classList.remove("efs-typing");
      wait.innerHTML = EFSRag.md(answer);
      history.push({ role: "user", content: q }, { role: "assistant", content: answer });
    } catch (e) {
      wait.classList.remove("efs-typing");
      wait.textContent = "Service momentanément indisponible — réessayez dans un instant.";
    }
    send.disabled = false;
    input.focus();
    msgs.scrollTop = msgs.scrollHeight;
  }

  send.addEventListener("click", () => { if (input.value.trim()) ask(input.value.trim()); });
  input.addEventListener("keydown", e => {
    if (e.key === "Enter" && input.value.trim()) ask(input.value.trim());
  });
})();
