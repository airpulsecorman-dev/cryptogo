import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";
import MapView from "./MapView";
import { api, developmentAuthEnabled } from "./api";

const sections = [
  { id: "map", icon: "⌖", label: "Mapa" },
  { id: "inventory", icon: "▦", label: "Inventario" },
  { id: "missions", icon: "✳", label: "Misiones" },
  { id: "leaderboard", icon: "♛", label: "Ranking" },
  { id: "profile", icon: "◉", label: "Perfil" },
];

function App() {
  const [activeSection, setActiveSection] = useState("map");
  const [player, setPlayer] = useState(null);
  const [authenticationError, setAuthenticationError] = useState("");
  const [authenticating, setAuthenticating] = useState(true);
  const [position, setPosition] = useState(null);
  const [locationMessage, setLocationMessage] = useState("");
  const [discoveries, setDiscoveries] = useState([]);
  const [zones, setZones] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [mapZoom, setMapZoom] = useState(5);
  const [inventory, setInventory] = useState(null);
  const [missions, setMissions] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [loadingSection, setLoadingSection] = useState(false);
  const [pageError, setPageError] = useState("");
  const [collecting, setCollecting] = useState(false);
  const [notice, setNotice] = useState("");

  const selectedDiscovery = useMemo(
    () => discoveries.find(({ id }) => id === selectedId),
    [discoveries, selectedId],
  );
  const handleZoomChange = useCallback((zoom) => setMapZoom(zoom), []);

  useEffect(() => {
    let active = true;
    async function initializeSession() {
      try {
        const existingPlayer = await api.profile();
        if (active) setPlayer(existingPlayer);
      } catch (error) {
        if (error.status !== 401) {
          if (active) setAuthenticationError(error.message);
          return;
        }
        const initData = window.Telegram?.WebApp?.initData;
        if (!initData) {
          if (active)
            setAuthenticationError(
              "Abre Crypto Go desde Telegram para iniciar sesión.",
            );
          return;
        }
        try {
          window.Telegram?.WebApp?.ready();
          const authenticatedPlayer = await api.authenticateTelegram(initData);
          if (active) setPlayer(authenticatedPlayer);
        } catch (authError) {
          if (active) setAuthenticationError(authError.message);
        }
      } finally {
        if (active) setAuthenticating(false);
      }
    }

    initializeSession();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!player || !position) return undefined;
    let active = true;
    setLocationMessage("Buscando objetos y zonas habilitadas…");
    Promise.all([api.nearby(position), api.zones(position)])
      .then(([nearby, enabledZones]) => {
        if (!active) return;
        setDiscoveries(nearby.items);
        setZones(enabledZones.items);
        setSelectedId((current) =>
          nearby.items.some(({ id }) => id === current)
            ? current
            : nearby.items[0]?.id || "",
        );
        setLocationMessage(
          nearby.message ||
            (nearby.items.length
              ? `${nearby.items.length} objetos disponibles en esta zona.`
              : "No hay objetos disponibles cerca."),
        );
      })
      .catch((error) => {
        if (active) setLocationMessage(error.message);
      });
    return () => {
      active = false;
    };
  }, [player, position]);

  useEffect(() => {
    if (!player || activeSection === "map") return undefined;
    let active = true;
    setLoadingSection(true);
    setPageError("");
    const loaders = {
      inventory: api.inventory,
      missions: api.missions,
      leaderboard: api.leaderboard,
      profile: api.profile,
    };
    loaders[activeSection]()
      .then((result) => {
        if (!active) return;
        if (activeSection === "inventory") setInventory(result);
        if (activeSection === "missions") setMissions(result.items);
        if (activeSection === "leaderboard") setLeaderboard(result.items);
        if (activeSection === "profile") setPlayer(result);
      })
      .catch((error) => {
        if (active) setPageError(error.message);
      })
      .finally(() => {
        if (active) setLoadingSection(false);
      });
    return () => {
      active = false;
    };
  }, [activeSection, player]);

  function signInAsDeveloper() {
    setAuthenticating(true);
    setAuthenticationError("");
    api
      .authenticateDevelopment()
      .then(setPlayer)
      .catch((error) => setAuthenticationError(error.message))
      .finally(() => setAuthenticating(false));
  }

  function locatePlayer() {
    if (!navigator.geolocation) {
      setLocationMessage("Este navegador no permite consultar la ubicación.");
      return;
    }
    setLocationMessage("Solicitando permiso para usar tu ubicación…");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const nextPosition = {
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy: coords.accuracy,
          timestamp: new Date().toISOString(),
        };
        setPosition(nextPosition);
        setLocationMessage("Ubicación GPS detectada. Consultando el mapa…");
      },
      (error) => {
        const messages = {
          1: "Permiso de ubicación denegado. Habilítalo en tu navegador para consultar el mapa.",
          2: "No se pudo determinar tu ubicación. Comprueba la señal GPS e inténtalo de nuevo.",
          3: "La solicitud de ubicación expiró. Inténtalo de nuevo.",
        };
        setLocationMessage(
          messages[error.code] || "No se pudo obtener tu ubicación.",
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  async function collectDiscovery() {
    if (!selectedDiscovery || !position || collecting) return;
    setCollecting(true);
    setPageError("");
    try {
      const result = await api.collect(position, selectedDiscovery.id);
      setPlayer(result.player);
      setNotice(
        `${result.message} · +${result.rewards.points} puntos · +${result.rewards.xp} XP`,
      );
      const [nearby, enabledZones] = await Promise.all([
        api.nearby(position),
        api.zones(position),
      ]);
      setDiscoveries(nearby.items);
      setZones(enabledZones.items);
      setSelectedId(nearby.items[0]?.id || "");
      setLocationMessage(
        nearby.message ||
          (nearby.items.length
            ? `${nearby.items.length} objetos disponibles en esta zona.`
            : "No hay objetos disponibles cerca."),
      );
      if (activeSection === "inventory") setInventory(await api.inventory());
    } catch (error) {
      setPageError(error.message);
    } finally {
      setCollecting(false);
    }
  }

  if (authenticating)
    return <LoadingScreen message="Conectando con Crypto Go…" />;
  if (!player) {
    return (
      <AuthenticationScreen
        error={authenticationError}
        onDevelopmentLogin={signInAsDeveloper}
        showDevelopmentLogin={developmentAuthEnabled}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a
          className="brand"
          href="#inicio"
          aria-label="Crypto Go, inicio"
          onClick={(event) => {
            event.preventDefault();
            setActiveSection("map");
          }}
        >
          <span className="brand-mark">
            C<span>G</span>
          </span>
          <span className="brand-name">
            CRYPTO<span>GO</span>
          </span>
        </a>
        <div className="topbar-right">
          <div
            className="points-pill"
            aria-label={`${player.points.toLocaleString("es-EC")} puntos`}
          >
            <span className="points-star">✦</span>
            <span>
              {player.points.toLocaleString("es-EC")} <small>PTS</small>
            </span>
          </div>
          <button
            className="avatar-button"
            onClick={() => setActiveSection("profile")}
            aria-label="Abrir perfil"
          >
            <span>{initials(player.first_name)}</span>
            <i aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="Navegación principal">
          <div className="sidebar-label">JUEGO</div>
          <nav>
            {sections.map((section) => (
              <button
                key={section.id}
                className={`nav-item ${activeSection === section.id ? "active" : ""}`}
                onClick={() => setActiveSection(section.id)}
                aria-current={activeSection === section.id ? "page" : undefined}
              >
                <span className="nav-icon" aria-hidden="true">
                  {section.icon}
                </span>
                <span>{section.label}</span>
              </button>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="level-card">
              <div className="level-top">
                <span>NIVEL {String(player.level).padStart(2, "0")}</span>
                <span>
                  {player.xp_into_level} / {player.xp_for_next_level} XP
                </span>
              </div>
              <div className="xp-track">
                <span
                  style={{
                    width: `${Math.min(100, (player.xp_into_level / player.xp_for_next_level) * 100)}%`,
                  }}
                />
              </div>
              <p>¡Sigue explorando!</p>
            </div>
            <div className="beta-label">
              <span /> BETA PRIVADA <b>EC</b>
            </div>
          </div>
        </aside>

        <main className="main-content">
          {activeSection === "map" && (
            <MapSection
              discoveries={discoveries}
              selectedDiscovery={selectedDiscovery}
              selectedId={selectedId}
              locationMessage={locationMessage}
              position={position}
              zones={zones}
              mapZoom={mapZoom}
              collecting={collecting}
              pageError={pageError}
              onSelect={setSelectedId}
              onLocate={locatePlayer}
              onCollect={collectDiscovery}
              onZoomChange={handleZoomChange}
            />
          )}
          {activeSection === "inventory" && (
            <LoadedSection loading={loadingSection} error={pageError}>
              {inventory && (
                <InventorySection
                  inventory={inventory}
                  points={player.points}
                />
              )}
            </LoadedSection>
          )}
          {activeSection === "missions" && (
            <LoadedSection loading={loadingSection} error={pageError}>
              {missions && <MissionsSection missions={missions} />}
            </LoadedSection>
          )}
          {activeSection === "leaderboard" && (
            <LoadedSection loading={loadingSection} error={pageError}>
              {leaderboard && <LeaderboardSection players={leaderboard} />}
            </LoadedSection>
          )}
          {activeSection === "profile" && (
            <LoadedSection loading={loadingSection} error={pageError}>
              <ProfileSection player={player} />
            </LoadedSection>
          )}
        </main>
      </div>

      {notice && (
        <div className="toast" role="status">
          <span>✓</span>
          {notice}
        </div>
      )}
      <nav className="mobile-nav" aria-label="Navegación móvil">
        {sections.map((section) => (
          <button
            key={section.id}
            className={activeSection === section.id ? "active" : ""}
            onClick={() => setActiveSection(section.id)}
            aria-current={activeSection === section.id ? "page" : undefined}
          >
            <span aria-hidden="true">{section.icon}</span>
            <small>{section.label}</small>
          </button>
        ))}
      </nav>
    </div>
  );
}

function AuthenticationScreen({
  error,
  onDevelopmentLogin,
  showDevelopmentLogin,
}) {
  return (
    <main className="auth-screen">
      <div className="auth-card">
        <span className="brand-mark">
          C<span>G</span>
        </span>
        <p className="eyebrow">GO. COLLECT. LEVEL UP.</p>
        <h1>
          Crypto<span>Go</span>
        </h1>
        <p className="subheading">
          Inicia sesión con Telegram para continuar tu aventura.
        </p>
        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}
        {showDevelopmentLogin && (
          <button className="collect-button" onClick={onDevelopmentLogin}>
            Entrar como jugador local (solo desarrollo)
          </button>
        )}
      </div>
    </main>
  );
}

function LoadingScreen({ message }) {
  return (
    <main className="auth-screen" role="status">
      <p>{message}</p>
    </main>
  );
}

function LoadedSection({ loading, error, children }) {
  if (loading) return <LoadingScreen message="Cargando datos del servidor…" />;
  if (error)
    return (
      <p className="section-error" role="alert">
        {error}
      </p>
    );
  return children;
}

function MapSection({
  discoveries,
  selectedDiscovery,
  selectedId,
  locationMessage,
  position,
  zones,
  mapZoom,
  collecting,
  pageError,
  onSelect,
  onLocate,
  onCollect,
  onZoomChange,
}) {
  const canCollect =
    selectedDiscovery &&
    position &&
    selectedDiscovery.distance_meters <=
      selectedDiscovery.collection_radius_meters;
  return (
    <>
      <div className="page-heading map-heading">
        <div>
          <p className="eyebrow">
            <span className="live-dot" />{" "}
            {zones.length ? "ZONA HABILITADA" : "UBICACIÓN ACTUAL"}
          </p>
          <h1>
            Sal a explorar<span>.</span>
          </h1>
          <p className="subheading">
            Consulta objetos disponibles en zonas verificadas.
          </p>
        </div>
        <button className="location-button" onClick={onLocate}>
          <span aria-hidden="true">⌖</span> Mi ubicación
        </button>
      </div>
      {locationMessage && (
        <p className="location-message" role="status">
          {locationMessage}
        </p>
      )}
      {pageError && (
        <p className="location-message error-message" role="alert">
          {pageError}
        </p>
      )}

      <div className="map-layout">
        <section className="map-panel" aria-label="Mapa de Crypto Go">
          <div className="map-canvas maplibre-canvas">
            <MapView
              position={position}
              discoveries={discoveries}
              zones={zones}
              selectedId={selectedId}
              onSelect={onSelect}
              zoom={mapZoom}
              onZoomChange={onZoomChange}
            />
          </div>
          <div className="map-footer">
            <span>
              {position ? (
                <>
                  <i className="legend-player" /> Tu ubicación GPS
                </>
              ) : (
                "La ubicación se solicita solo cuando la pides"
              )}
            </span>
            <span>
              <i className="legend-coin" /> {discoveries.length} objetos
              cercanos
            </span>
          </div>
        </section>

        <aside className="discovery-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">A TU ALREDEDOR</p>
              <h2>Objetos cercanos</h2>
            </div>
            <span className="count-badge">{discoveries.length}</span>
          </div>
          {discoveries.length > 0 ? (
            <div className="discovery-list">
              {discoveries.map((discovery) => (
                <button
                  key={discovery.id}
                  className={`discovery-card ${selectedId === discovery.id ? "selected" : ""}`}
                  onClick={() => onSelect(discovery.id)}
                  aria-pressed={selectedId === discovery.id}
                >
                  <span
                    className={`coin-icon ${markerClass(discovery.ticker)}`}
                  >
                    {discovery.symbol}
                  </span>
                  <span className="discovery-info">
                    <strong>{discovery.name}</strong>
                    <small>
                      {formatRarity(discovery.rarity)} <i />{" "}
                      {formatDistance(discovery.distance_meters)}
                    </small>
                  </span>
                  <span className="discovery-points">{discovery.ticker}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-discoveries">
              <span>✦</span>
              <strong>
                {position
                  ? "No hay objetos disponibles"
                  : "Activa tu ubicación"}
              </strong>
              <p>
                {position
                  ? "No se encontraron apariciones habilitadas en tu zona."
                  : "Solicita GPS para consultar zonas y objetos cercanos."}
              </p>
            </div>
          )}
          {selectedDiscovery ? (
            <div className="collect-card">
              <div className="collect-copy">
                <span className="collect-ready">
                  <i /> {canCollect ? "DENTRO DEL RADIO" : "ACÉRCATE AL OBJETO"}
                </span>
                <p>
                  Distancia GPS:{" "}
                  <strong>
                    {formatDistance(selectedDiscovery.distance_meters)}
                  </strong>
                </p>
              </div>
              <button
                className="collect-button"
                onClick={onCollect}
                disabled={!canCollect || collecting}
              >
                <span aria-hidden="true">✦</span>
                {collecting
                  ? "Recogiendo…"
                  : `Recoger ${selectedDiscovery.ticker}`}
              </button>
              <p className="demo-note">
                La distancia y la recompensa se validan en el servidor.
              </p>
            </div>
          ) : (
            <div className="collect-card all-collected">
              <p>No hay objetos seleccionados.</p>
              <span>
                Las apariciones aparecen aquí cuando una zona habilitada tiene
                objetos disponibles.
              </span>
            </div>
          )}
          <div className="safe-explore">
            <span aria-hidden="true">◎</span>
            <p>
              <strong>Explora con cuidado</strong>
              <br />
              Presta atención a tu entorno mientras juegas.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}

function SectionHeading({ eyebrow, title, description }) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>
          {title}
          <span>.</span>
        </h1>
        <p className="subheading">{description}</p>
      </div>
    </div>
  );
}

function InventorySection({ inventory, points }) {
  const items = inventory.items || [];
  return (
    <>
      <SectionHeading
        eyebrow="TU COLECCIÓN"
        title="Inventario"
        description="Objetos obtenidos en tus aventuras."
      />
      <div className="stat-grid">
        <StatCard
          label="TESOROS ENCONTRADOS"
          value={inventory.total_collected}
          icon="✦"
        />
        <StatCard label="MONEDAS DESCUBIERTAS" value={items.length} icon="◈" />
        <StatCard
          label="PUNTOS TOTALES"
          value={points.toLocaleString("es-EC")}
          icon="✧"
        />
      </div>
      <section className="collection-section">
        <div className="section-title">
          <h2>Tus monedas</h2>
          <span>{inventory.total_collected} objetos</span>
        </div>
        {items.length ? (
          <div className="coin-grid">
            {items.map((coin) => (
              <article className="collection-card" key={coin.ticker}>
                <span className={`coin-icon large ${markerClass(coin.ticker)}`}>
                  {coin.symbol}
                </span>
                <span className="rarity-label">
                  {formatRarity(coin.rarity)}
                </span>
                <h3>{coin.name}</h3>
                <p>{coin.ticker}</p>
                <div className="collection-count">
                  <span>En tu colección</span>
                  <strong>× {coin.count}</strong>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">Todavía no has recogido objetos.</p>
        )}
        {inventory.history.length > 0 && (
          <div className="collection-history">
            <div className="section-title">
              <h2>Historial reciente</h2>
              <span>{inventory.history.length} movimientos</span>
            </div>
            {inventory.history.map((entry) => (
              <div className="history-row" key={entry.collection_id}>
                <span>
                  {entry.name} · {entry.ticker}
                </span>
                <small>
                  {new Date(entry.collected_at).toLocaleString("es-EC")}
                </small>
                <strong>
                  +{entry.points} PTS · +{entry.xp} XP
                </strong>
              </div>
            ))}
          </div>
        )}
        <p className="disclaimer">
          Los objetos son coleccionables virtuales y no representan
          criptomonedas reales.
        </p>
      </section>
    </>
  );
}

function MissionsSection({ missions }) {
  return (
    <>
      <SectionHeading
        eyebrow="DESAFÍOS"
        title="Misiones"
        description="Consulta los desafíos habilitados para tu cuenta."
      />
      {missions.length ? (
        <div className="mission-list">
          {missions.map((mission) => (
            <article className="mission-card" key={mission.id}>
              <span className="mission-icon">{mission.icon || "✦"}</span>
              <div className="mission-main">
                <div className="mission-title">
                  <h2>{mission.title}</h2>
                  <span>{mission.reward_points} PTS</span>
                </div>
                <p>{mission.description}</p>
                <div className="mission-progress">
                  <span>
                    <i
                      style={{
                        width: `${Math.min(100, (mission.progress / mission.target) * 100)}%`,
                      }}
                    />
                  </span>
                  <small>
                    {mission.progress}/{mission.target}
                  </small>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">
          No hay misiones habilitadas en este momento.
        </p>
      )}
    </>
  );
}

function LeaderboardSection({ players }) {
  return (
    <>
      <SectionHeading
        eyebrow="COMUNIDAD CRYPTO GO"
        title="Ranking"
        description="Clasificación calculada con los puntos registrados."
      />
      {players.length ? (
        <div className="leaderboard-card">
          <div className="leaderboard-header">
            <span>POSICIÓN</span>
            <span>EXPLORADOR</span>
            <span>PUNTOS</span>
          </div>
          {players.map((entry) => (
            <div
              className={`leaderboard-row ${entry.is_current_player ? "own" : ""}`}
              key={`${entry.rank}-${entry.first_name}`}
            >
              <span className={`rank-number rank-${entry.rank}`}>
                {entry.rank <= 3 ? "♛" : entry.rank}
              </span>
              <span className="player-identity">
                <i>{initials(entry.first_name)}</i>
                <strong>
                  {entry.is_current_player ? "Tú" : entry.first_name}
                </strong>
                {entry.is_current_player && <small>TÚ</small>}
              </span>
              <strong className="leaderboard-score">
                {entry.points.toLocaleString("es-EC")} <small>PTS</small>
              </strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-state">Aún no hay jugadores en el ranking.</p>
      )}
    </>
  );
}

function ProfileSection({ player }) {
  const xpRemaining = player.xp_for_next_level - player.xp_into_level;
  return (
    <>
      <SectionHeading
        eyebrow="TU AVENTURA"
        title="Perfil"
        description="Progreso sincronizado con tu cuenta."
      />
      <section className="profile-card">
        <div className="profile-avatar">{initials(player.first_name)}</div>
        <div className="profile-info">
          <p>EXPLORADOR</p>
          <h2>{player.first_name}</h2>
          <span>
            En Crypto Go desde{" "}
            {new Date(player.registered_at).toLocaleDateString("es-EC")}
          </span>
        </div>
        <div className="profile-level">
          <span>NIVEL</span>
          <strong>{String(player.level).padStart(2, "0")}</strong>
        </div>
      </section>
      <div className="stat-grid profile-stats">
        <StatCard
          label="PUNTOS"
          value={player.points.toLocaleString("es-EC")}
          icon="✦"
        />
        <StatCard label="TESOROS" value={player.collected_count} icon="◈" />
        <StatCard
          label="EXPERIENCIA TOTAL"
          value={player.total_xp.toLocaleString("es-EC")}
          icon="⚡"
        />
      </div>
      <section className="progress-card">
        <div className="section-title">
          <h2>Progreso al nivel {player.level + 1}</h2>
          <span>
            {player.xp_into_level} / {player.xp_for_next_level} XP
          </span>
        </div>
        <div className="xp-track wide">
          <span
            style={{
              width: `${Math.min(100, (player.xp_into_level / player.xp_for_next_level) * 100)}%`,
            }}
          />
        </div>
        <p>
          Te faltan <strong>{xpRemaining} XP</strong> para subir de nivel.
        </p>
      </section>
    </>
  );
}

function StatCard({ label, value, icon }) {
  return (
    <div className="stat-card">
      <span className="stat-icon">{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function initials(name = "") {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "CG"
  );
}

function formatDistance(meters) {
  return meters < 1_000
    ? `${Math.round(meters)} m`
    : `${(meters / 1_000).toFixed(1)} km`;
}

function formatRarity(rarity) {
  return (
    {
      common: "Común",
      uncommon: "Poco común",
      rare: "Raro",
      epic: "Épico",
      legendary: "Legendario",
    }[rarity] || rarity
  );
}

function markerClass(ticker) {
  return (
    {
      BTC: "bitcoin",
      ETH: "ethereum",
      BNB: "bnb",
      SOL: "solana",
    }[ticker] || "bitcoin"
  );
}

export default App;
