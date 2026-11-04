import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import App from "./App";
import { api, createIdempotencyKey } from "./api";

jest.mock(
  "./MapView",
  () =>
    function TestMapView({ discoveries, onSelect }) {
      return (
        <div aria-label="Mapa de Crypto Go">
          {discoveries.map((discovery) => (
            <button key={discovery.id} onClick={() => onSelect(discovery.id)}>
              Seleccionar {discovery.name}
            </button>
          ))}
        </div>
      );
    },
);

jest.mock(
  "./WalletLogin",
  () =>
    function TestWalletLogin() {
      return (
        <div>
          <button>Conectar billetera EVM</button>
          <button>Conectar Telegram Wallet</button>
        </div>
      );
    },
);

jest.mock("./api", () => ({
  api: {
    profile: jest.fn(),
    authenticateTelegram: jest.fn(),
    authenticateDevelopment: jest.fn(),
    nearby: jest.fn(),
    zones: jest.fn(),
    collect: jest.fn(),
    inventory: jest.fn(),
    missions: jest.fn(),
    leaderboard: jest.fn(),
  },
  createIdempotencyKey: jest.fn(() => "test-idempotency-key"),
  developmentAuthEnabled: false,
}));

const player = {
  id: "player-1",
  telegram_id: 123,
  first_name: "Ada Lovelace",
  username: "ada",
  points: 0,
  total_xp: 0,
  level: 1,
  xp_into_level: 0,
  xp_for_next_level: 500,
  collected_count: 0,
  registered_at: "2026-01-01T00:00:00Z",
};

const collectible = {
  id: "spawn-1",
  ticker: "BTC",
  name: "Bitcoin",
  symbol: "₿",
  rarity: "common",
  latitude: 0,
  longitude: 0,
  distance_meters: 10,
  collection_radius_meters: 35,
  expires_at: "2026-12-01T00:00:00Z",
};

function openSection(label) {
  fireEvent.click(screen.getAllByRole("button", { name: label })[0]);
}

beforeEach(() => {
  jest.clearAllMocks();
  createIdempotencyKey.mockReturnValue("test-idempotency-key");
  api.profile.mockResolvedValue(player);
  api.nearby.mockResolvedValue({ items: [], message: null });
  api.zones.mockResolvedValue({ items: [] });
  api.inventory.mockResolvedValue({
    items: [],
    history: [],
    total_collected: 0,
  });
  api.missions.mockResolvedValue({ items: [] });
  api.leaderboard.mockResolvedValue({ items: [] });
});

test("offers Telegram or wallet login and authenticates with Telegram initData", async () => {
  api.profile.mockRejectedValueOnce({ status: 401 });
  api.authenticateTelegram.mockResolvedValue(player);
  Object.defineProperty(window, "Telegram", {
    configurable: true,
    value: {
      WebApp: {
        initData: "signed-init-data",
        initDataUnsafe: { user: { id: 999 } },
        ready: jest.fn(),
      },
    },
  });

  render(<App />);

  expect(await screen.findByRole("button", { name: /continuar con telegram/i }))
    .toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /conectar billetera evm/i }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /conectar telegram wallet/i }),
  ).toBeInTheDocument();
  expect(api.authenticateTelegram).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: /continuar con telegram/i }));
  await waitFor(() =>
    expect(api.authenticateTelegram).toHaveBeenCalledWith("signed-init-data"),
  );
  expect(
    await screen.findByRole("heading", { name: /sal a explorar/i }),
  ).toBeInTheDocument();
});

test("a player without a Telegram session sees an authentication state, not demo data", async () => {
  api.profile.mockRejectedValue({ status: 401 });
  delete window.Telegram;

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: /crypto go/i }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/acceso con telegram está disponible/i),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /conectar billetera evm/i }),
  ).toBeInTheDocument();
  expect(screen.queryByText(/btc añadido/i)).not.toBeInTheDocument();
});

test("GPS lookup loads actual nearby items and collecting uses the server reward", async () => {
  api.nearby.mockResolvedValueOnce({ items: [collectible], message: null });
  api.collect.mockResolvedValue({
    success: true,
    collection_id: "collection-1",
    collectible: { ticker: "BTC", name: "Bitcoin", rarity: "common" },
    rewards: { points: 10, xp: 10 },
    player: {
      ...player,
      points: 10,
      total_xp: 10,
      xp_into_level: 10,
      collected_count: 1,
    },
    message: "Bitcoin añadido a tu colección.",
  });
  const getCurrentPosition = jest.fn((success) =>
    success({
      coords: { latitude: 0, longitude: 0, accuracy: 5 },
    }),
  );
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition },
  });
  render(<App />);
  await screen.findByRole("heading", { name: /sal a explorar/i });

  fireEvent.click(screen.getByRole("button", { name: /mi ubicación/i }));
  expect(getCurrentPosition).toHaveBeenCalledWith(
    expect.any(Function),
    expect.any(Function),
    expect.objectContaining({ enableHighAccuracy: true, maximumAge: 0 }),
  );
  fireEvent.click(await screen.findByRole("button", { name: /recoger btc/i }));

  await waitFor(() =>
    expect(api.collect).toHaveBeenCalledWith(
      expect.objectContaining({ latitude: 0, longitude: 0, accuracy: 5 }),
      "spawn-1",
      expect.any(String),
    ),
  );
  expect(await screen.findByText(/\+10 puntos · \+10 xp/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/10 puntos/i)).toBeInTheDocument();
});

test("inventory and mission screens load real empty states", async () => {
  render(<App />);
  await screen.findByRole("heading", { name: /sal a explorar/i });

  openSection("Inventario");
  expect(
    await screen.findByText(/todavía no has recogido objetos/i),
  ).toBeInTheDocument();
  expect(api.inventory).toHaveBeenCalled();

  openSection("Misiones");
  expect(
    await screen.findByText(/no hay misiones habilitadas/i),
  ).toBeInTheDocument();
  expect(api.missions).toHaveBeenCalled();
});

test("the profile reads persisted player values from the API", async () => {
  render(<App />);
  await screen.findByRole("heading", { name: /sal a explorar/i });
  openSection("Perfil");

  expect(
    await screen.findByRole("heading", { name: /ada lovelace/i }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("0 / 500 XP")).toHaveLength(2);
  expect(api.profile).toHaveBeenCalledTimes(2);
});

test("location permission errors are announced to the player", async () => {
  const getCurrentPosition = jest.fn((_success, error) => error({ code: 1 }));
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition },
  });
  render(<App />);
  await screen.findByRole("heading", { name: /sal a explorar/i });
  fireEvent.click(screen.getByRole("button", { name: /mi ubicación/i }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    /permiso de ubicación denegado/i,
  );
});

test("mobile navigation opens the real ranking section", async () => {
  api.leaderboard.mockResolvedValue({ items: [] });
  render(<App />);
  await screen.findByRole("heading", { name: /sal a explorar/i });
  const mobileNavigation = within(
    screen.getByRole("navigation", { name: "Navegación móvil" }),
  );
  fireEvent.click(mobileNavigation.getByRole("button", { name: "Ranking" }));

  expect(
    await screen.findByRole("heading", { name: /ranking/i }),
  ).toBeInTheDocument();
  expect(screen.getByText(/aún no hay jugadores/i)).toBeInTheDocument();
});
