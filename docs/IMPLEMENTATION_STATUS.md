# Crypto Go — Verificación técnica de la primera entrega

**Verificado:** 2026-11-04
**Alcance:** código del cliente React, API FastAPI, modelos, migración, Compose y pruebas del repositorio.
**Regla de estado:** solo se usan los estados autorizados. «Probado» distingue las pruebas ejecutadas con SQLite de la integración PostgreSQL/PostGIS, que no estuvo disponible.

## Entorno y resultados de ejecución

- `docker info`: Docker no disponible. No se pudo iniciar Docker Compose.
- PostgreSQL en `127.0.0.1:5432`: no accesible; `psql` no está instalado.
- Redis en `127.0.0.1:6379`: no accesible.
- `POSTGRES_TEST_DATABASE_URL`: no configurada.
- Node.js: `v23.7.0`.
- `yarn build`: correcto; CRA informa una advertencia de dependencia dinámica, no un fallo de compilación.
- `CI=true yarn test --watchAll=false --runInBand`: **7 pruebas aprobadas**.
- `.venv/bin/python -m pytest backend/tests -q`: **13 aprobadas, 1 omitida**. La omitida es la prueba concurrente que necesita PostgreSQL/PostGIS.
- `cd backend && ../.venv/bin/python -m alembic upgrade head --sql`: **correcto**; generó SQL PostgreSQL para 12 tablas de la aplicación y `alembic_version`. Esto no ejecuta la migración en una base de datos.
- `git diff --check`: correcto.

Las pruebas del backend usan FastAPI `TestClient` y SQLite real con SQLAlchemy; no sustituyen la prueba de PostGIS ni verifican bloqueos de filas de PostgreSQL. Las pruebas React sustituyen el cliente API con mocks y, por tanto, no prueban una conexión HTTP entre los dos procesos.

## Verificación por funcionalidad

### Integración React → API

- **Estado:** Implementado sin prueba de integración.
- **Archivos:** `src/api.js`, `src/App.js`, `src/MapView.js`, `package.json`.
- **Endpoints:** `/api/v1/auth/*`, `/api/v1/players/me`, `/api/v1/collectibles/*`, `/api/v1/zones/nearby`, `/api/v1/inventory`, `/api/v1/missions`, `/api/v1/leaderboard`.
- **Tablas:** las que correspondan a cada endpoint; ninguna accedida desde React.
- **Prueba ejecutada:** build y 7 pruebas React. El build pasó; las pruebas verifican estados de UI, pero `src/App.test.js` simula `./api`.
- **Pendiente:** ejecutar cliente y API juntos con `REACT_APP_API_BASE_URL` real, sesión/cookie y servicios disponibles. En producción, si falta esa variable, el cliente muestra error; no hay fallback de datos simulados.

### FastAPI y capa HTTP

- **Estado:** Implementado y probado.
- **Archivos:** `backend/app/main.py`, `backend/app/routers/auth.py`, `backend/app/routers/game.py`, `backend/app/schemas.py`.
- **Endpoints:** `GET /health/live`, `GET /api/v1/health/live`, `GET /api/v1/health/ready` y rutas `/api/v1/*`.
- **Tablas:** depende de la ruta; comprobación de salud usa la conexión configurada.
- **Prueba ejecutada:** `TestClient` en la suite backend; autenticación, perfil, geografía, colección e inventario respondieron con los resultados esperados en pruebas.
- **Pendiente:** readiness con PostgreSQL y Redis reales; no se inició el servicio integrado.

### SQLAlchemy y persistencia de aplicación

- **Estado:** Implementado y probado.
- **Archivos:** `backend/app/database.py`, `backend/app/models.py`, `backend/tests/conftest.py`, `backend/tests/test_game.py`.
- **Endpoints:** rutas de autenticación y juego bajo `/api/v1`.
- **Tablas:** `users`, `player_profiles`, `auth_sessions`, `zones`, `collectibles`, `spawn_points`, `spawn_instances`, `collections`, `point_transactions`, `xp_transactions`, `idempotency_records`, `anti_cheat_events`.
- **Prueba ejecutada:** suite backend sobre SQLite: escritura, consulta, colección, inventario, libro contable y recuperación del perfil tras autenticar de nuevo; 13 aprobadas.
- **Pendiente:** validar las mismas operaciones contra PostgreSQL/PostGIS; la prueba con SQLite no certifica el dialecto ni el bloqueo de filas PostgreSQL.

### PostgreSQL y PostGIS

- **Estado:** Bloqueado por configuración externa.
- **Archivos:** `docker-compose.yml`, `backend/app/config.py`, `backend/app/database.py`, `backend/app/geo.py`, `backend/app/routers/game.py`, `backend/migrations/versions/0001_game_core.py`.
- **Endpoints:** `GET /api/v1/collectibles/nearby`, `GET /api/v1/zones/nearby`, `POST /api/v1/collectibles/collect`, `GET /api/v1/health/ready`.
- **Tablas:** las tablas de SQLAlchemy anteriores; la migración crea PostGIS y un índice espacial GiST para apariciones.
- **Prueba ejecutada:** comprobación de puerto y configuración, y generación offline del SQL de Alembic. No hay servidor local; la prueba `test_only_one_player_collects_a_spawn_concurrently` se omitió por falta de `POSTGRES_TEST_DATABASE_URL`.
- **Resultado y pendiente:** no se verificó conexión, extensión PostGIS, consulta espacial real, migración aplicada ni concurrencia. Hace falta un PostgreSQL con PostGIS accesible y una URL de prueba dedicada.

### Alembic y migraciones

- **Estado:** Implementado sin prueba de integración.
- **Archivos:** `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_game_core.py`, `Dockerfile.api`, `docker-compose.yml`.
- **Endpoints:** no aplica.
- **Tablas:** 12 tablas de aplicación y `alembic_version`.
- **Prueba ejecutada:** `cd backend && ../.venv/bin/python -m alembic upgrade head --sql`; Alembic renderizó la migración para PostgreSQL y enumeró la revisión `0001_game_core`.
- **Pendiente:** ejecutar `alembic upgrade head` en PostgreSQL/PostGIS y comparar el esquema creado con los modelos. El modo `--sql` no prueba permisos, extensiones ni ejecución.

### Redis

- **Estado:** Bloqueado por configuración externa.
- **Archivos:** `docker-compose.yml`, `.env.example`, `backend/app/main.py`, `backend/app/routers/auth.py`, `backend/app/routers/game.py`.
- **Endpoints:** `POST /api/v1/auth/telegram`, `POST /api/v1/collectibles/collect`, `GET /api/v1/health/ready`.
- **Tablas:** ninguna; Redis almacena contadores temporales de limitación de solicitudes.
- **Prueba ejecutada:** inspección de conexión local; Redis no escucha en `127.0.0.1:6379`. La configuración de prueba usa `APP_ENV=test`, que omite el rate limit y el ping de Redis.
- **Pendiente:** verificar rate limiting, disponibilidad y readiness contra Redis real. La aplicación falla explícitamente con 503 cuando Redis no está disponible en esos flujos.

### Docker Compose

- **Estado:** Bloqueado por configuración externa.
- **Archivos:** `docker-compose.yml`, `Dockerfile.api`, `.env.example`.
- **Endpoints:** API expone el puerto 8000 en la configuración Compose.
- **Tablas:** PostgreSQL/PostGIS administra las tablas de aplicación; Redis no usa tablas SQL.
- **Prueba ejecutada:** inspección de la configuración y `docker info`; el daemon Docker no está disponible.
- **Pendiente:** no se pudieron validar `compose config`, arranque, healthchecks, migración inicial ni worker en contenedores. Se requiere Docker operativo y `POSTGRES_PASSWORD` local configurada; `.env.example` contiene solo un marcador, no una credencial.

### Autenticación de Telegram

- **Estado:** Implementado sin prueba de integración.
- **Archivos:** `backend/app/security.py`, `backend/app/routers/auth.py`, `backend/app/config.py`, `backend/app/schemas.py`, `backend/tests/conftest.py`, `backend/tests/test_game.py`, `src/App.js`, `src/api.js`.
- **Endpoints:** `POST /api/v1/auth/telegram`, `POST /api/v1/auth/dev`.
- **Tablas:** `users`, `player_profiles`, `auth_sessions`.
- **Verificación del protocolo:** el backend excluye `hash`, ordena los campos firmados y compara HMAC-SHA-256 con `hmac.compare_digest`, siguiendo el procedimiento oficial de Telegram. Valida `auth_date`, firma y un `user.id` entero positivo; rechaza campos duplicados. React envía `Telegram.WebApp.initData`; no autentica con `initDataUnsafe`.
- **Pruebas locales:** `18 passed, 1 skipped` en backend (`backend/tests/test_concurrency_postgres.py` omitida por falta de PostGIS) y `7 passed` en React. Incluyen initData sintético firmado, firma/usuario alterados, datos incompletos o expirados, campos duplicados, cookie HttpOnly/Secure y hash de sesión almacenado, expiración/revocación de sesión, configuración CORS HTTPS con credenciales y rechazo de `/auth/dev` en producción. Estas pruebas no conectan con Telegram.
- **Pendiente externo:** `TELEGRAM_BOT_TOKEN` queda vacío en `.env.example`; debe configurarse solo en el entorno secreto del backend. Configurar en BotFather la URL HTTPS publicada del frontend (no la URL del API), `CORS_ORIGINS` con su origen exacto y `REACT_APP_API_BASE_URL` con la URL HTTPS del API. No se validó una firma `initData` auténtica ni se considera conectado el bot.
- **Desarrollo:** `/auth/dev` requiere simultáneamente `APP_ENV=development` y `DEV_AUTH_ENABLED=true`; la app rechaza ese interruptor en producción y la ruta responde 404 fuera de desarrollo.

### Sesiones

- **Estado:** Implementado y probado.
- **Archivos:** `backend/app/security.py`, `backend/app/routers/auth.py`, `backend/app/config.py`, `backend/tests/test_game.py` y `backend/tests/conftest.py`.
- **Endpoints:** `POST /api/v1/auth/telegram`, `POST /api/v1/auth/logout`; las rutas de juego validan la cookie.
- **Tablas:** `auth_sessions`, `users`, `player_profiles`.
- **Prueba ejecutada:** además de persistir al reiniciar la API sobre SQLite y ser revocada por logout, una sesión expirada se rechaza y elimina; el valor aleatorio de la cookie no se guarda en claro en la base. Se comprueban atributos HttpOnly, Secure y SameSite en la respuesta de prueba.
- **Pendiente:** las cookies, CORS y dominio no se validaron desde Telegram ni en un despliegue HTTPS real. Producción requiere cookie Secure, token de bot y orígenes CORS explícitos HTTPS.

### Perfil del jugador

- **Estado:** Implementado y probado.
- **Archivos:** `backend/app/routers/auth.py`, `backend/app/routers/game.py`, `backend/app/models.py`, `src/api.js`, `src/App.js`.
- **Endpoints:** `GET /api/v1/players/me`, autenticación en `/api/v1/auth/telegram`.
- **Tablas:** `users`, `player_profiles`.
- **Prueba ejecutada:** registro/recuperación del mismo usuario, perfil protegido, persistencia de puntos/XP tras renovar sesión y recuperación tras reiniciar la API con SQLite.
- **Pendiente:** comprobarlo con datos de PostgreSQL y una sesión real de Telegram.

### MapLibre

- **Estado:** Implementado sin prueba de integración.
- **Archivos:** `src/MapView.js`, `src/App.js`, `src/App.css`, `package.json`.
- **Endpoints:** zonas y apariciones se consumen desde `/api/v1/zones/nearby` y `/api/v1/collectibles/nearby`; el estilo cartográfico usa OpenFreeMap por defecto o `REACT_APP_MAP_STYLE_URL`.
- **Tablas:** `zones`, `spawn_instances`, `collectibles`.
- **Prueba ejecutada:** build de producción pasó. Las pruebas React reemplazan `MapView`; no probaron WebGL, proveedor de tiles ni renderizado de navegador.
- **Pendiente:** validar el mapa en navegador y la disponibilidad/uso del proveedor cartográfico.

### Geolocalización y consulta de zonas/apariciones

- **Estado:** Parcial.
- **Archivos:** `src/App.js`, `src/api.js`, `src/MapView.js`, `backend/app/routers/game.py`, `backend/app/geo.py`, `backend/app/models.py`.
- **Endpoints:** `GET /api/v1/zones/nearby`, `GET /api/v1/collectibles/nearby`.
- **Tablas:** `zones`, `spawn_instances`, `spawn_points`, `collectibles`.
- **Prueba ejecutada:** tests backend verifican una aparición guardada y una zona habilitada mediante SQLite; tests UI simulan permisos GPS. El cliente envía coordenadas a las consultas y al POST de recolección.
- **Pendiente:** permiso GPS real, consulta de geografía PostGIS y ubicación real no se probaron. En producción no hay zonas ni apariciones iniciales: un operador debe provisionar polígonos y puntos aprobados. No se crean coordenadas de juego por defecto.

### Recolección

- **Estado:** Parcial.
- **Archivos:** `src/api.js`, `src/App.js`, `backend/app/routers/game.py`, `backend/app/geo.py`, `backend/app/models.py`, `backend/app/schemas.py`, `backend/tests/test_game.py`.
- **Endpoints:** `POST /api/v1/collectibles/collect`.
- **Tablas:** `spawn_instances`, `collectibles`, `zones`, `collections`, `player_profiles`, `point_transactions`, `xp_transactions`, `idempotency_records`, `anti_cheat_events`.
- **Prueba ejecutada:** SQLite verifica recolección válida, rechazo por expiración (410), rechazo fuera del radio (403), validación de edad/precisión y acreditación de recompensas.
- **Pendiente:** no se probó la operación sobre PostgreSQL/PostGIS ni con GPS real. La prueba de concurrencia está omitida por no disponer de PostGIS.

### Transacciones e idempotencia

- **Estado:** Parcial.
- **Archivos:** `backend/app/routers/game.py`, `backend/app/models.py`, `backend/tests/test_game.py`, `backend/tests/test_concurrency_postgres.py`, `src/api.js`, `src/App.js`.
- **Endpoints:** `POST /api/v1/collectibles/collect` con `Idempotency-Key`.
- **Tablas:** `spawn_instances`, `collections`, `player_profiles`, `point_transactions`, `xp_transactions`, `idempotency_records`.
- **Prueba ejecutada:** con SQLite, una repetición idéntica devuelve la misma respuesta sin duplicar movimientos; una misma clave con otro cuerpo se rechaza; otro jugador no recoge el objeto ya reclamado. La prueba PostGIS que exige una sola recompensa simultánea se omitió.
- **Pendiente:** no certificar concurrencia con SQLite. Ejecutar `backend/tests/test_concurrency_postgres.py` contra una base PostGIS dedicada antes de afirmar atomicidad bajo sesiones simultáneas.

### Inventario

- **Estado:** Implementado y probado.
- **Archivos:** `backend/app/routers/game.py`, `backend/app/models.py`, `backend/app/schemas.py`, `src/api.js`, `src/App.js`, `backend/tests/test_game.py`.
- **Endpoints:** `GET /api/v1/inventory`.
- **Tablas:** `collections`, `collectibles`, `player_profiles`, `point_transactions`, `xp_transactions`.
- **Prueba ejecutada:** una recolección válida aparece en el inventario, el conteo, historial y totales se leen de SQLAlchemy/SQLite.
- **Pendiente:** repetir en PostgreSQL; el navegador no tuvo prueba contra una API viva.

### Libro de puntos y sistema de XP

- **Estado:** Implementado y probado.
- **Archivos:** `backend/app/routers/game.py`, `backend/app/routers/auth.py`, `backend/app/models.py`, `backend/tests/test_game.py`, `src/api.js`, `src/App.js`.
- **Endpoints:** `GET /api/v1/players/me`, `GET /api/v1/players/me/ledger`, respuesta de `POST /api/v1/collectibles/collect`.
- **Tablas:** `player_profiles`, `point_transactions`, `xp_transactions`, `collections`, `collectibles`.
- **Prueba ejecutada:** recompensas se leen del catálogo del servidor, se guardan en ambos libros y actualizan perfil/inventario; el test verifica 10 puntos, 10 XP y persistencia en SQLite.
- **Pendiente:** concurrencia y persistencia en PostgreSQL no verificadas. El nivel se deriva en backend del XP persistido; el frontend solo presenta los valores recibidos.

### Misiones y ranking

- **Estado:** Parcial.
- **Archivos:** `backend/app/routers/game.py`, `backend/app/schemas.py`, `src/api.js`, `src/App.js`, `src/App.test.js`.
- **Endpoints:** `GET /api/v1/missions`, `GET /api/v1/leaderboard`.
- **Tablas:** las misiones no tienen modelo ni tabla; ranking consulta `player_profiles` y `users`.
- **Prueba ejecutada:** test backend confirma respuesta vacía explícita de misiones; test UI verifica el estado vacío usando API simulada. No hay test backend específico del ranking.
- **Pendiente:** no existe persistencia/progreso de misiones. El endpoint de ranking está implementado como consulta SQL, pero no se verificó con jugadores reales ni se debe interpretar el estado vacío de UI como prueba del endpoint.

## Datos estáticos y simulados que permanecen

- La migración inserta un catálogo inicial de BTC, ETH, BNB y SOL en `collectibles`. Son definiciones persistentes del catálogo, no apariciones geográficas. No inserta zonas, coordenadas ni `spawn_instances`.
- `src/MapView.js` inicia el mapa con un centro fijo `[-78.1834, -1.8312]` y zoom 5 antes de obtener GPS. No se muestra como marcador GPS ni crea coleccionables, pero es una vista inicial estática.
- El login local es deliberadamente simulado, condicionado a variables de desarrollo y bloqueado por el backend fuera del entorno `development`.
- No se encontró fallback de perfil, inventario, saldo o apariciones ficticias para producción. La API debe estar configurada; misiones vacías se presentan como vacías.

## Cambios realizados durante la verificación

- Se añadieron `test_game_endpoints_require_an_authenticated_session` y `test_session_and_player_survive_application_restart` en `backend/tests/test_game.py`.
- Se verificó que todas las rutas de juego requieren sesión y que la cookie/sesión y el perfil SQLite sobreviven al reinicio de la instancia API; logout invalida la cookie persistida.
- No se reemplazaron las pruebas de producción por mocks ni se añadieron coordenadas o coleccionables de juego.

## Resultado pendiente para cerrar la verificación de producción

Se requiere una instancia accesible de PostgreSQL con PostGIS, Redis y Docker operativo para: aplicar la migración real, validar el esquema y funciones espaciales, iniciar Compose, probar readiness/rate limit y ejecutar la prueba concurrente. También se requiere una configuración de Telegram válida y un navegador con GPS concedido para verificar el flujo de producción completo. Hasta entonces, esas integraciones permanecen bloqueadas o parciales según se indica arriba.
