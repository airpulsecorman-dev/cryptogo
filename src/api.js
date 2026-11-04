const configuredApiUrl = process.env.REACT_APP_API_BASE_URL;
const apiBaseUrl =
  configuredApiUrl ||
  (process.env.NODE_ENV === "development"
    ? "http://localhost:8000/api/v1"
    : "");

async function request(path, options = {}) {
  if (!apiBaseUrl) {
    throw new Error(
      "La API no está configurada. Define REACT_APP_API_BASE_URL para este entorno.",
    );
  }

  let response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...options,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(
      "No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.",
    );
  }

  if (response.status === 204) return null;
  const responseBody = await response.text();
  let result = {};
  if (responseBody) {
    try {
      result = JSON.parse(responseBody);
    } catch {
      throw new Error("El servidor devolvió una respuesta no válida.");
    }
  } else if (response.ok) {
    throw new Error("El servidor devolvió una respuesta vacía.");
  }
  if (!response.ok) {
    const error = new Error(
      result.detail || "La solicitud no pudo completarse.",
    );
    error.status = response.status;
    throw error;
  }
  return result;
}

export function createIdempotencyKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

export const api = {
  profile: () => request("/players/me"),
  authenticateTelegram: (initData) =>
    request("/auth/telegram", {
      method: "POST",
      body: JSON.stringify({ init_data: initData }),
    }),
  authenticateDevelopment: () =>
    request("/auth/dev", {
      method: "POST",
      body: JSON.stringify({
        telegram_id: 1,
        first_name: "Jugador local",
        username: null,
      }),
    }),
  nearby: (position) =>
    request(
      `/collectibles/nearby?latitude=${encodeURIComponent(position.latitude)}&longitude=${encodeURIComponent(position.longitude)}&radius_meters=5000`,
    ),
  zones: (position) =>
    request(
      `/zones/nearby?latitude=${encodeURIComponent(position.latitude)}&longitude=${encodeURIComponent(position.longitude)}`,
    ),
  collect: (position, spawnInstanceId, key = createIdempotencyKey()) =>
    request("/collectibles/collect", {
      method: "POST",
      headers: { "Idempotency-Key": key },
      body: JSON.stringify({
        spawn_instance_id: spawnInstanceId,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracy_meters: position.accuracy,
        client_timestamp: position.timestamp,
      }),
    }),
  inventory: () => request("/inventory"),
  missions: () => request("/missions"),
  leaderboard: () => request("/leaderboard"),
};

export const developmentAuthEnabled =
  process.env.REACT_APP_ENABLE_DEV_AUTH === "true";
