// Shows the release the channel actually offers (same signed manifest the app uses).
(async () => {
  const box = document.getElementById("release");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  try {
    const r = await fetch("/releases/latest.json", { cache: "no-store" });
    if (!r.ok) throw new Error(String(r.status));
    const m = await r.json();
    const mb = (m.installer.size / 1048576).toFixed(0);
    box.innerHTML = `<p><b>Versão ${esc(m.version)}</b> · Windows 11 x64 · ${mb} MB</p>
      ${m.notes ? `<p>${esc(m.notes)}</p>` : ""}
      <p><a class="btn" href="/releases/${encodeURIComponent(m.installer.file)}" download>Baixar instalador completo</a></p>
      <p class="mono">SHA-256: ${esc(m.installer.sha256)}</p>
      <p class="muted">Publicado em ${esc(m.published_at)}. O manifesto é assinado; o aplicativo instalado só aceita atualizações assinadas.</p>`;
  } catch (e) {
    box.textContent = "Nenhuma versão disponível para download neste momento.";
  }
})();
