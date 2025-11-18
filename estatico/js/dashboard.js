document.addEventListener("DOMContentLoaded", carregar);

async function carregar() {
  try {
    const resposta = await listarLixeiras();
    montar(resposta.data);
  } catch (_) {
    alert("Erro ao carregar dados");
  }
}

function montar(lista) {
  const container = document.getElementById("grid");
  container.innerHTML = "";
  lista.forEach((item) => {
    const div = document.createElement("div");
    div.className = "lixeira " + item.status.toLowerCase();
    div.innerHTML = `
      <h3>${item.nome}</h3>
      <p>${item.nivel}%</p>
      <button data-id="${item.id}">+10%</button>
    `;
    div.querySelector("button").onclick = async () => {
      const novo = Math.min(item.nivel + 10, 100);
      await atualizarNivel(item.id, novo);
      carregar();
    };
    container.appendChild(div);
  });
}
