const API = "/api";

async function request(url, options = {}) {
  const res = await fetch(API + url, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Erro");
  return body;
}

async function listarLixeiras() {
  return request("/lixeiras");
}

async function atualizarNivel(id, nivel) {
  return request(`/lixeiras/${id}/nivel`, {
    method: "PATCH",
    body: JSON.stringify({ nivel }),
  });
}
