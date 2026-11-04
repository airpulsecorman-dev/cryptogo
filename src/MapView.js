import { useEffect, useRef, useState } from "react";
import { Map as MapLibre, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const MAP_STYLE =
  process.env.REACT_APP_MAP_STYLE_URL ||
  "https://tiles.openfreemap.org/styles/dark";

function MapView({
  position,
  discoveries,
  zones,
  selectedId,
  onSelect,
  onMapMove,
  zoom,
  onZoomChange,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const playerMarkerRef = useRef(null);
  const mapMoveHandlerRef = useRef(onMapMove);
  const [loaded, setLoaded] = useState(false);
  mapMoveHandlerRef.current = onMapMove;

  useEffect(() => {
    const map = new MapLibre({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [-78.1834, -1.8312],
      zoom: 5,
      attributionControl: true,
    });
    mapRef.current = map;
    map.on("load", () => setLoaded(true));
    map.on("zoomend", () => onZoomChange(map.getZoom()));
    map.on("moveend", () => {
      const center = map.getCenter();
      mapMoveHandlerRef.current?.({
        latitude: center.lat,
        longitude: center.lng,
      });
    });

    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      playerMarkerRef.current?.remove();
      playerMarkerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [onZoomChange]);

  useEffect(() => {
    if (!loaded || !mapRef.current || !position) return;
    mapRef.current.flyTo({
      center: [position.longitude, position.latitude],
      zoom: Math.max(mapRef.current.getZoom(), 15),
      essential: true,
    });
  }, [loaded, position]);

  useEffect(() => {
    if (!loaded || !mapRef.current) return;
    if (!position) {
      playerMarkerRef.current?.remove();
      playerMarkerRef.current = null;
      return;
    }
    if (!playerMarkerRef.current) {
      const element = document.createElement('div');
      element.className = 'player-marker map-player-marker';
      element.setAttribute('role', 'img');
      element.setAttribute('aria-label', 'Tu ubicación GPS');
      element.append(document.createElement('span'));
      playerMarkerRef.current = new Marker({ element, anchor: 'center' })
        .setLngLat([position.longitude, position.latitude])
        .addTo(mapRef.current);
      return;
    }
    playerMarkerRef.current.setLngLat([position.longitude, position.latitude]);
  }, [loaded, position]);

  useEffect(() => {
    if (!loaded || !mapRef.current) return;
    const map = mapRef.current;
    const featureCollection = {
      type: "FeatureCollection",
      features: zones.map((zone) => ({
        type: "Feature",
        geometry: zone.boundary,
        properties: { id: zone.id, name: zone.name },
      })),
    };
    if (map.getSource("enabled-zones")) {
      map.getSource("enabled-zones").setData(featureCollection);
      return;
    }
    map.addSource("enabled-zones", {
      type: "geojson",
      data: featureCollection,
    });
    map.addLayer({
      id: "enabled-zones-fill",
      type: "fill",
      source: "enabled-zones",
      paint: { "fill-color": "#c5f36b", "fill-opacity": 0.08 },
    });
    map.addLayer({
      id: "enabled-zones-outline",
      type: "line",
      source: "enabled-zones",
      paint: { "line-color": "#c5f36b", "line-width": 2, "line-opacity": 0.7 },
    });
  }, [loaded, zones]);

  useEffect(() => {
    if (!loaded || !mapRef.current) return;
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = discoveries.map((discovery) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = `map-coin ${markerClass(discovery.ticker)} ${selectedId === discovery.id ? "selected" : ""}`;
      element.textContent = discovery.symbol;
      element.setAttribute(
        "aria-label",
        `Seleccionar ${discovery.name}, a ${Math.round(discovery.distance_meters)} metros`,
      );
      element.addEventListener("click", () => onSelect(discovery.id));
      return new Marker({ element, anchor: "center" })
        .setLngLat([discovery.longitude, discovery.latitude])
        .addTo(mapRef.current);
    });
  }, [discoveries, loaded, onSelect, selectedId]);

  function changeZoom(amount) {
    if (!mapRef.current) return;
    mapRef.current.zoomTo(
      Math.max(3, Math.min(20, mapRef.current.getZoom() + amount)),
    );
  }

  return (
    <>
      <div
        className="maplibre-container"
        ref={containerRef}
        aria-label="Mapa de Crypto Go"
      />
      {position && (
        <div className="map-location-label" aria-label="Ubicación GPS activa">
          <span className="legend-player" /> Tu ubicación GPS
        </div>
      )}
      <div className="map-control-stack">
        <button
          aria-label="Acercar mapa"
          title="Acercar mapa"
          onClick={() => changeZoom(1)}
          disabled={zoom >= 20}
        >
          +
        </button>
        <button
          aria-label="Alejar mapa"
          title="Alejar mapa"
          onClick={() => changeZoom(-1)}
          disabled={zoom <= 3}
        >
          −
        </button>
      </div>
      <div className="map-zoom-level" aria-live="polite">
        Zoom {Math.round(zoom)}
      </div>
    </>
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

export default MapView;
