# Paso 1. Iniciar únicamente el worker

Ejecuta:
docker compose up -d spawn-worker

Esto iniciará el servicio sin reconstruir ni eliminar tus datos. Como actualmente tienes cero spawn_points, el worker no tendrá puntos dinámicos que procesar.
Paso 2. Comprobar su estado
Después ejecuta:
docker compose ps

Y:
docker compose logs --tail=80 spawn-worker

Resultado esperado
Queremos comprobar que el worker aparece como Up y que no presenta errores de conexión con PostgreSQL.

## 3. Antes de crear la zona, hagamos dos comprobaciones

Ejecuta estos comandos:

A. Ayuda de creación de zonas:
docker compose exec api python -m app.cli create-zone --help

B. Ayuda de creación de puntos:
docker compose exec api python -m app.cli create-spawn --help

C. Comprobar si el worker está funcionando:
docker compose ps spawn-worker

## 4. Qué vamos a construir

La configuración inicial debería contemplar esta relación:

Zona geográfica habilitada
Polígono GeoJSON que cubre el área de juego

Puntos de aparición
Coordenadas válidas dentro de la zona

Instancias de coleccionables
Objetos disponibles, activos y no expirados

Jugador encuentra objetos en el mapa
