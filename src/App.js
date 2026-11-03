import { useState } from 'react';
import './App.css';

const initialDiscoveries = [
  { id: 'btc', symbol: '₿', name: 'Bitcoin', ticker: 'BTC', rarity: 'Común', points: 10, distance: '42 m', className: 'bitcoin' },
  { id: 'eth', symbol: '◆', name: 'Ethereum', ticker: 'ETH', rarity: 'Poco común', points: 25, distance: '180 m', className: 'ethereum' },
  { id: 'sol', symbol: '◎', name: 'Solana', ticker: 'SOL', rarity: 'Épico', points: 100, distance: '320 m', className: 'solana' },
];

const sections = [
  { id: 'map', icon: '⌖', label: 'Mapa' },
  { id: 'inventory', icon: '▦', label: 'Inventario' },
  { id: 'missions', icon: '✳', label: 'Misiones' },
  { id: 'leaderboard', icon: '♛', label: 'Ranking' },
  { id: 'profile', icon: '◉', label: 'Perfil' },
];

const initialInventory = { BTC: 7, ETH: 5, BNB: 3, SOL: 3 };

function App() {
  const [activeSection, setActiveSection] = useState('map');
  const [discoveries, setDiscoveries] = useState(initialDiscoveries);
  const [selectedId, setSelectedId] = useState('btc');
  const [inventory, setInventory] = useState(initialInventory);
  const [points, setPoints] = useState(1280);
  const [collectedCount, setCollectedCount] = useState(18);
  const [locationMessage, setLocationMessage] = useState('');
  const [notice, setNotice] = useState('');

  const selectedDiscovery = discoveries.find(({ id }) => id === selectedId);

  function locatePlayer() {
    if (!navigator.geolocation) {
      setLocationMessage('Este navegador no permite consultar la ubicación.');
      return;
    }

    setLocationMessage('Solicitando permiso de ubicación…');
    navigator.geolocation.getCurrentPosition(
      () => setLocationMessage('Ubicación detectada. El mapa aún usa datos de demostración.'),
      (error) => {
        const message = error.code === error.PERMISSION_DENIED
          ? 'Permiso de ubicación denegado. Puedes explorar la demostración.'
          : 'No se pudo obtener tu ubicación. Inténtalo de nuevo cuando estés listo.';
        setLocationMessage(message);
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
  }

  function collectDiscovery() {
    if (!selectedDiscovery) return;

    setPoints((current) => current + selectedDiscovery.points);
    setCollectedCount((current) => current + 1);
    setInventory((current) => ({
      ...current,
      [selectedDiscovery.ticker]: (current[selectedDiscovery.ticker] || 0) + 1,
    }));
    setDiscoveries((current) => current.filter(({ id }) => id !== selectedDiscovery.id));
    const nextDiscovery = discoveries.find(({ id }) => id !== selectedDiscovery.id);
    setSelectedId(nextDiscovery?.id || '');
    setNotice(`${selectedDiscovery.ticker} añadido a tu colección · +${selectedDiscovery.points} puntos`);
    window.setTimeout(() => setNotice(''), 3500);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#inicio" aria-label="Crypto Hunt, inicio" onClick={(event) => event.preventDefault()}>
          <span className="brand-mark">C<span>H</span></span>
          <span className="brand-name">CRYPTO<span>HUNT</span></span>
        </a>
        <div className="topbar-right">
          <div className="points-pill" aria-label={`${points.toLocaleString('es-EC')} puntos`}>
            <span className="points-star">✦</span>
            <span>{points.toLocaleString('es-EC')} <small>PTS</small></span>
          </div>
          <button className="avatar-button" onClick={() => setActiveSection('profile')} aria-label="Abrir perfil">
            <span>AH</span><i aria-hidden="true" />
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
                className={`nav-item ${activeSection === section.id ? 'active' : ''}`}
                onClick={() => setActiveSection(section.id)}
                aria-current={activeSection === section.id ? 'page' : undefined}
              >
                <span className="nav-icon" aria-hidden="true">{section.icon}</span>
                <span>{section.label}</span>
                {section.id === 'missions' && <span className="nav-dot" aria-label="Nuevas misiones" />}
              </button>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="level-card">
              <div className="level-top"><span>NIVEL 04</span><span>340 / 500 XP</span></div>
              <div className="xp-track"><span /></div>
              <p>¡Sigue explorando!</p>
            </div>
            <div className="beta-label"><span /> BETA PRIVADA <b>EC</b></div>
          </div>
        </aside>

        <main className="main-content">
          {activeSection === 'map' && (
            <MapSection
              discoveries={discoveries}
              selectedId={selectedId}
              selectedDiscovery={selectedDiscovery}
              locationMessage={locationMessage}
              onSelect={setSelectedId}
              onLocate={locatePlayer}
              onCollect={collectDiscovery}
            />
          )}
          {activeSection === 'inventory' && <InventorySection inventory={inventory} collectedCount={collectedCount} points={points} />}
          {activeSection === 'missions' && <MissionsSection />}
          {activeSection === 'leaderboard' && <LeaderboardSection points={points} />}
          {activeSection === 'profile' && <ProfileSection points={points} collectedCount={collectedCount} />}
        </main>
      </div>

      {notice && <div className="toast" role="status"><span>✓</span>{notice}</div>}
      <nav className="mobile-nav" aria-label="Navegación móvil">
        {sections.map((section) => (
          <button
            key={section.id}
            className={activeSection === section.id ? 'active' : ''}
            onClick={() => setActiveSection(section.id)}
            aria-current={activeSection === section.id ? 'page' : undefined}
          >
            <span aria-hidden="true">{section.icon}</span>
            <small>{section.label}</small>
          </button>
        ))}
      </nav>
    </div>
  );
}

function MapSection({ discoveries, selectedId, selectedDiscovery, locationMessage, onSelect, onLocate, onCollect }) {
  return (
    <>
      <div className="page-heading map-heading">
        <div>
          <p className="eyebrow"><span className="live-dot" /> ZONA ACTIVA · QUITO, EC</p>
          <h1>Sal a explorar<span>.</span></h1>
          <p className="subheading">Hay tesoros esperándote cerca.</p>
        </div>
        <button className="location-button" onClick={onLocate}><span aria-hidden="true">⌖</span> Mi ubicación</button>
      </div>
      {locationMessage && <p className="location-message" role="status">{locationMessage}</p>}

      <div className="map-layout">
        <section className="map-panel" aria-label="Mapa de demostración">
          <div className="map-canvas">
            <div className="map-water" />
            <div className="map-park park-one"><span>PARQUE</span><i>✳</i></div>
            <div className="map-park park-two"><i>✳</i></div>
            <div className="map-road road-one" />
            <div className="map-road road-two" />
            <div className="map-road road-three" />
            <div className="map-road road-four" />
            <div className="map-road road-five" />
            <span className="street-label street-one">Av. República</span>
            <span className="street-label street-two">Av. 6 de Diciembre</span>
            <div className="player-marker" aria-label="Tu ubicación aproximada"><span /></div>
            {discoveries.map((discovery, index) => (
              <button
                key={discovery.id}
                className={`map-coin ${discovery.className} coin-${index + 1} ${selectedId === discovery.id ? 'selected' : ''}`}
                onClick={() => onSelect(discovery.id)}
                aria-label={`Seleccionar ${discovery.name}, a ${discovery.distance}`}
                aria-pressed={selectedId === discovery.id}
              >
                {discovery.symbol}
              </button>
            ))}
            <div className="map-control-stack">
              <button aria-label="Acercar mapa" title="Acercar">+</button>
              <button aria-label="Alejar mapa" title="Alejar">−</button>
            </div>
            <div className="map-attribution">Mapa ilustrativo · Ubicaciones ficticias</div>
          </div>
          <div className="map-footer">
            <span><i className="legend-player" /> Tu ubicación aproximada</span>
            <span><i className="legend-coin" /> {discoveries.length} tesoros cercanos</span>
          </div>
        </section>

        <aside className="discovery-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">A TU ALREDEDOR</p><h2>Tesoros cercanos</h2></div>
            <span className="count-badge">{discoveries.length}</span>
          </div>
          {discoveries.length > 0 ? (
            <div className="discovery-list">
              {discoveries.map((discovery) => (
                <button
                  key={discovery.id}
                  className={`discovery-card ${selectedId === discovery.id ? 'selected' : ''}`}
                  onClick={() => onSelect(discovery.id)}
                  aria-pressed={selectedId === discovery.id}
                >
                  <span className={`coin-icon ${discovery.className}`}>{discovery.symbol}</span>
                  <span className="discovery-info">
                    <strong>{discovery.name}</strong>
                    <small>{discovery.rarity} <i /> {discovery.distance}</small>
                  </span>
                  <span className="discovery-points">+{discovery.points}<small>PTS</small></span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-discoveries"><span>✦</span><strong>¡Los encontraste todos!</strong><p>Vuelve pronto para buscar nuevos tesoros.</p></div>
          )}
          {selectedDiscovery ? (
            <div className="collect-card">
              <div className="collect-copy">
                <span className="collect-ready"><i /> LISTO PARA RECOGER</span>
                <p>Estás a <strong>{selectedDiscovery.distance}</strong> de un {selectedDiscovery.ticker}</p>
              </div>
              <button className="collect-button" onClick={onCollect}>
                <span aria-hidden="true">✦</span> Recoger {selectedDiscovery.ticker}
              </button>
              <p className="demo-note">Acción de demostración · sin recompensas reales</p>
            </div>
          ) : (
            <div className="collect-card all-collected">
              <p>No quedan tesoros en esta zona.</p>
              <span>La ubicación y las apariciones son datos de demostración.</span>
            </div>
          )}
          <div className="safe-explore"><span aria-hidden="true">◎</span><p><strong>Explora con cuidado</strong><br />Presta atención a tu entorno mientras juegas.</p></div>
        </aside>
      </div>
    </>
  );
}

function SectionHeading({ eyebrow, title, description }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}<span>.</span></h1><p className="subheading">{description}</p></div></div>;
}

function InventorySection({ inventory, collectedCount, points }) {
  const coins = [
    { ticker: 'BTC', name: 'Bitcoin', symbol: '₿', className: 'bitcoin', rarity: 'Común' },
    { ticker: 'ETH', name: 'Ethereum', symbol: '◆', className: 'ethereum', rarity: 'Poco común' },
    { ticker: 'BNB', name: 'BNB', symbol: '⬡', className: 'bnb', rarity: 'Raro' },
    { ticker: 'SOL', name: 'Solana', symbol: '◎', className: 'solana', rarity: 'Épico' },
  ];
  return (
    <>
      <SectionHeading eyebrow="TU COLECCIÓN" title="Inventario" description="Cada hallazgo cuenta una historia." />
      <div className="stat-grid">
        <StatCard label="TESOROS ENCONTRADOS" value={collectedCount} icon="✦" />
        <StatCard label="MONEDAS DESCUBIERTAS" value={`${Object.values(inventory).filter(Boolean).length} / 12`} icon="◈" />
        <StatCard label="PUNTOS TOTALES" value={points.toLocaleString('es-EC')} icon="✧" />
      </div>
      <section className="collection-section">
        <div className="section-title"><h2>Tus monedas</h2><span>{Object.values(inventory).reduce((total, count) => total + count, 0)} objetos</span></div>
        <div className="coin-grid">
          {coins.map((coin) => (
            <article className="collection-card" key={coin.ticker}>
              <span className={`coin-icon large ${coin.className}`}>{coin.symbol}</span>
              <span className="rarity-label">{coin.rarity}</span>
              <h3>{coin.name}</h3>
              <p>{coin.ticker}</p>
              <div className="collection-count"><span>En tu colección</span><strong>× {inventory[coin.ticker] || 0}</strong></div>
            </article>
          ))}
        </div>
        <p className="disclaimer">Los objetos son coleccionables virtuales y no representan criptomonedas reales.</p>
      </section>
    </>
  );
}

function MissionsSection() {
  const missions = [
    { icon: '⌖', title: 'Primeros pasos', description: 'Explora el mapa y encuentra tu primer tesoro.', progress: 0, target: 1, reward: 25 },
    { icon: '₿', title: 'Cazador de Bitcoin', description: 'Encuentra 3 monedas BTC.', progress: 2, target: 3, reward: 50 },
    { icon: '✳', title: 'Paseo diario', description: 'Descubre 5 tesoros en tu aventura.', progress: 3, target: 5, reward: 75 },
  ];
  return (
    <>
      <SectionHeading eyebrow="DESAFÍOS DIARIOS" title="Misiones" description="Pequeños retos, grandes aventuras." />
      <div className="mission-banner"><span>✦</span><div><strong>Nuevas misiones cada día</strong><p>Completa desafíos para ganar puntos extra.</p></div><b>HOY</b></div>
      <div className="mission-list">
        {missions.map((mission) => (
          <article className="mission-card" key={mission.title}>
            <span className="mission-icon">{mission.icon}</span>
            <div className="mission-main"><div className="mission-title"><h2>{mission.title}</h2><span>+{mission.reward} PTS</span></div><p>{mission.description}</p><div className="mission-progress"><span><i style={{ width: `${(mission.progress / mission.target) * 100}%` }} /></span><small>{mission.progress}/{mission.target}</small></div></div>
          </article>
        ))}
      </div>
      <p className="disclaimer">El progreso de las misiones es ilustrativo durante esta demostración.</p>
    </>
  );
}

function LeaderboardSection({ points }) {
  const players = [
    { rank: 1, initials: 'MV', name: 'María V.', points: 2450 },
    { rank: 2, initials: 'CR', name: 'Carlos R.', points: 2180 },
    { rank: 3, initials: 'LP', name: 'Lucía P.', points: 1940 },
    { rank: 4, initials: 'AH', name: 'Tú', points, own: true },
    { rank: 5, initials: 'DS', name: 'Diego S.', points: 1160 },
  ];
  return (
    <>
      <SectionHeading eyebrow="COMUNIDAD CRYPTO HUNT" title="Ranking" description="Los exploradores más activos de esta semana." />
      <div className="leaderboard-card">
        <div className="leaderboard-header"><span>POSICIÓN</span><span>EXPLORADOR</span><span>PUNTOS</span></div>
        {players.map((player) => (
          <div className={`leaderboard-row ${player.own ? 'own' : ''}`} key={player.rank}>
            <span className={`rank-number rank-${player.rank}`}>{player.rank <= 3 ? '♛' : player.rank}</span>
            <span className="player-identity"><i>{player.initials}</i><strong>{player.name}</strong>{player.own && <small>TÚ</small>}</span>
            <strong className="leaderboard-score">{player.points.toLocaleString('es-EC')} <small>PTS</small></strong>
          </div>
        ))}
      </div>
      <p className="disclaimer">Clasificación de demostración · los datos no corresponden a jugadores reales.</p>
    </>
  );
}

function ProfileSection({ points, collectedCount }) {
  return (
    <>
      <SectionHeading eyebrow="TU AVENTURA" title="Perfil" description="Tu progreso como explorador." />
      <section className="profile-card">
        <div className="profile-avatar">AH</div>
        <div className="profile-info"><p>EXPLORADOR</p><h2>Aventurero</h2><span>En Crypto Hunt desde hoy</span></div>
        <div className="profile-level"><span>NIVEL</span><strong>04</strong></div>
      </section>
      <div className="stat-grid profile-stats">
        <StatCard label="PUNTOS" value={points.toLocaleString('es-EC')} icon="✦" />
        <StatCard label="TESOROS" value={collectedCount} icon="◈" />
        <StatCard label="RACHA ACTUAL" value="2 días" icon="⚡" />
      </div>
      <section className="progress-card"><div className="section-title"><h2>Progreso al nivel 5</h2><span>340 / 500 XP</span></div><div className="xp-track wide"><span /></div><p>Te faltan <strong>160 XP</strong> para subir de nivel.</p></section>
      <p className="disclaimer">Perfil de demostración · los datos se reinician al recargar la página.</p>
    </>
  );
}

function StatCard({ label, value, icon }) {
  return <div className="stat-card"><span className="stat-icon">{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div>;
}

export default App;
