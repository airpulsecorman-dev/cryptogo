import { useEffect, useRef, useState } from "react";
import { Map as MapLibre, Marker, setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

setWorkerUrl(
  new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString(),
);

const MAP_STYLE =
  process.env.REACT_APP_MAP_STYLE_URL ||
  "https://tiles.openfreemap.org/styles/dark";

function MapView({
  position,
  discoveries,
  securityZones,
  selectedId,
  onSelect,
  onMapMove,
  onViewportChange,
  onSecurityZoneSelect,
  zoom,
  onZoomChange,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const playerMarkerRef = useRef(null);
  const mapMoveHandlerRef = useRef(onMapMove);
  const viewportHandlerRef = useRef(onViewportChange);
  const securityZoneHandlerRef = useRef(onSecurityZoneSelect);
  const [loaded, setLoaded] = useState(false);
  mapMoveHandlerRef.current = onMapMove;
  viewportHandlerRef.current = onViewportChange;
  securityZoneHandlerRef.current = onSecurityZoneSelect;

  useEffect(() => {
    const map = new MapLibre({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [-78.1834, -1.8312],
      zoom: 5,
      attributionControl: true,
    });
    mapRef.current = map;
    const reportViewport = () => {
      const bounds = map.getBounds();
      const rawWest = bounds.getWest();
      const rawEast = bounds.getEast();
      const wrapLongitude = (longitude) =>
        ((longitude + 180) % 360 + 360) % 360 - 180;
      viewportHandlerRef.current?.({
        west:
          Math.abs(rawEast - rawWest) >= 360
            ? -180
            : wrapLongitude(rawWest),
        south: bounds.getSouth(),
        east:
          Math.abs(rawEast - rawWest) >= 360
            ? 180
            : wrapLongitude(rawEast),
        north: bounds.getNorth(),
      });
    };
    const handleLoad = () => {
      setLoaded(true);
      reportViewport();
    };
    const handleZoom = () => onZoomChange(map.getZoom());
    const handleMove = () => {
      const center = map.getCenter();
      mapMoveHandlerRef.current?.({
        latitude: center.lat,
        longitude: center.lng,
      });
      reportViewport();
    };
    map.on("load", handleLoad);
    map.on("zoomend", handleZoom);
    map.on("zoomend", reportViewport);
    map.on("moveend", handleMove);

    return () => {
      map.off("load", handleLoad);
      map.off("zoomend", handleZoom);
      map.off("zoomend", reportViewport);
      map.off("moveend", handleMove);
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
    if (!map.getSource("security-zones")) {
      map.addSource("security-zones", {
        type: "geojson",
        data: securityZones,
      });
      const firstSymbolLayer = map
        .getStyle()
        .layers.find((layer) => layer.type === "symbol")?.id;
      const colors = {
        safe: "#49d17d",
        caution: "#f4c542",
        restricted: "#f06464",
        unknown: "#a7b0bc",
      };
      Object.entries(colors).forEach(([status, color]) => {
        map.addLayer(
          {
            id: `security-zones-${status}-fill`,
            type: "fill",
            source: "security-zones",
            filter: ["==", ["get", "security_status"], status],
            paint: {
              "fill-color": color,
              "fill-opacity": 0.16,
            },
          },
          firstSymbolLayer,
        );
        map.addLayer(
          {
            id: `security-zones-${status}-outline`,
            type: "line",
            source: "security-zones",
            filter: ["==", ["get", "security_status"], status],
            paint: {
              "line-color": color,
              "line-width": 2,
              "line-opacity": 0.9,
            },
          },
          firstSymbolLayer,
        );
      });
    }
    map.getSource("security-zones").setData(securityZones);
  }, [loaded, securityZones]);

  useEffect(() => {
    if (!loaded || !mapRef.current) return undefined;
    const map = mapRef.current;
    const selectableLayers = [
      "restricted",
      "unknown",
      "caution",
      "safe",
    ].map((status) => `security-zones-${status}-fill`);
    const handleZoneClick = (event) => {
      const precedence = {
        safe: 0,
        caution: 1,
        unknown: 2,
        restricted: 3,
      };
      const feature = map
        .queryRenderedFeatures(event.point, { layers: selectableLayers })
        .sort(
          (first, second) =>
            precedence[second.properties.security_status] -
            precedence[first.properties.security_status],
        )[0];
      if (!feature) {
        securityZoneHandlerRef.current?.(null);
        return;
      }
      const properties = feature.properties;
      securityZoneHandlerRef.current?.({
        status: properties.security_status,
        allowsPlay: properties.allows_play,
      });
    };
    map.on("click", handleZoneClick);
    return () => map.off("click", handleZoneClick);
  }, [loaded]);

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
