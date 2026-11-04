# Auditoría integral de APIs FastAPI — Crypto Go

**Fecha:** 2026-11-04  
**Alcance:** API FastAPI, routers, esquemas, seguridad, persistencia, configuración, migración, pruebas y llamadas del cliente React.  
**Resultado resumido:** las rutas de juego implementadas usan SQLAlchemy y las pruebas locales con SQLite pasan. La integración con PostgreSQL/PostGIS y Redis no se pudo comprobar: ambos servicios locales están inaccesibles y el readiness de la instancia en `127.0.0.1:8000` responde 503. Misiones siguen siendo un estado vacío explícito, no una funcionalidad persistida.

La auditoría se hizo sobre el estado de trabajo encontrado. Antes de crear este informe ya existía una modificación de formato en `backend/app/main.py` y el archivo sin seguimiento `backend/guia.txt`; no se modificaron ni se inspeccionó el contenido de este último.

## 1. Resumen general

- `app.routes` registra **13 operaciones de API bajo `/api/v1`** y una ruta de liveness en `/health/live`, oculta de OpenAPI. No existe una ruta raíz `/` ni una ruta para `/api/v1` como índice.
- `/api/v1/health/live` y `/health/live` funcionan. `/api/v1/health/ready` devuelve 503 en el servidor local porque no están disponibles PostgreSQL y Redis.
- Swagger está publicado intencionalmente en `/api/docs`; `/docs` y `/redoc` devuelven 404. `/openapi.json` sigue activo y contiene las 13 rutas `/api/v1`.
- Los endpoints privados probados devuelven 401 sin cookie y funcionan con sesión válida. La identidad proviene de la cookie de sesión validada, no de un ID de jugador enviado por el cliente.
- Las pruebas SQLite ejecutan persistencia SQLAlchemy real (sin mocks de base de datos) para registro, perfil, inventario, libro contable y recolección. No demuestran compatibilidad, índices espaciales, bloqueo concurrente ni despliegue PostgreSQL/PostGIS.
- No se encontraron datos de producción simulados como colecciones en memoria. `/missions` devuelve deliberadamente `items: []` y un mensaje; no consulta persistencia ni implementa misiones.
- Hay brechas entre lo descrito como previsto en el README y lo registrado, y faltan esquemas de respuesta y declaraciones de autenticación en buena parte del OpenAPI.

## 2. Inventario completo de endpoints

El inventario se obtuvo de `app.routes` y se contrastó con `app.openapi()` y el `/openapi.json` servido en `http://127.0.0.1:8000`. Los códigos de la columna «HTTP» incluyen los observados o posibles por validación/dependencias; OpenAPI actualmente no los describe todos.

### Autenticación

| Método y ruta | Router / función | Entrada | Respuesta | Autenticación / permiso | Persistencia | HTTP y estado |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /api/v1/auth/telegram` | `auth` / `authenticate_telegram` | `TelegramAuthRequest`: `init_data` requerido, 1–8192 caracteres | Datos del jugador equivalentes a `PlayerResponse` y cookie de sesión; sin `response_model` declarado | Pública; crea sesión únicamente tras validar la firma y fecha de `initData` | Lee/crea `users`, crea o consulta `player_profiles`, inserta `auth_sessions` | 200; 401 firma/datos inválidos; 422 cuerpo inválido; 429 límite; 503 token/configuración, Redis o SQL. **Implementado y probado** con datos firmados sintéticos |
| `POST /api/v1/auth/dev` | `auth` / `authenticate_development` | `DevelopmentAuthRequest`: `telegram_id > 0`, `first_name` requerido (1–128), `username` opcional (máx. 64) | Datos del jugador y cookie; sin `response_model` declarado | Pública solo si `APP_ENV=development` y `DEV_AUTH_ENABLED=true`; en caso contrario responde 404 | Igual que autenticación Telegram | 200 habilitada; 404 deshabilitada; 422 entrada inválida; 503 error SQL. **Implementado y probado** en las ramas deshabilitadas; la rama habilitada no se verificó en este ciclo |
| `POST /api/v1/auth/logout` | `auth` / `logout` | Cookie de sesión; sin cuerpo | Sin cuerpo, borra cookie; `204` | Requiere sesión válida; revoca solo la sesión actual | Elimina fila de `auth_sessions` y hace commit | 204; 401 sin sesión/no válida; 503 error SQL. **Implementado y probado** |

### Juego, perfil y datos

| Método y ruta | Router / función | Entrada | Respuesta | Autenticación / permiso | Persistencia | HTTP y estado |
| --- | --- | --- | --- | --- | --- | --- |
| `GET /api/v1/players/me` | `game` / `get_profile` | Ninguna | `PlayerResponse` | Sesión requerida; solo perfil asociado a la sesión | `auth_sessions`, `users`, `player_profiles` | 200; 401 sesión inválida/expirada; 503 error SQL. **Implementado y probado** |
| `GET /api/v1/players/me/ledger` | `game` / `get_ledger` | Ninguna | `{points: [...], xp: [...]}`; sin esquema de respuesta declarado | Sesión requerida; filtra por el usuario de la sesión | `auth_sessions`, `users`, `player_profiles`, `point_transactions`, `xp_transactions` | 200; 401; 503 error SQL. **Implementado y probado**; sin paginación |
| `GET /api/v1/zones/nearby` | `game` / `get_nearby_zones` | `latitude` y `longitude` requeridas; rangos −90..90 y −180..180 | `{items: [{id, name, boundary}]}`; sin esquema de respuesta declarado | Sesión requerida; devuelve zonas habilitadas que contienen el punto consultado | `auth_sessions`, `users`, `player_profiles`, `zones`; PostGIS en PostgreSQL o prueba de polígono en SQLite | 200; 401; 422 parámetros faltantes/fuera de rango; 503 error SQL. **Implementado y probado** |
| `GET /api/v1/collectibles/nearby` | `game` / `get_nearby_collectibles` | `latitude`/`longitude` requeridas y acotadas; `radius_meters` opcional, default 1500, rango 1–5000 | `{items: [NearbyCollectible], message: string | null}`; no se declara`response_model` | Sesión requerida; resultados limitados por zona, estado y radio | `auth_sessions`, `users`, `player_profiles`, `zones`, `spawn_instances`, `collectibles`; distancia PostGIS o Haversine SQLite | 200 incluso si la lista está vacía; 401; 422 parámetros inválidos; 503 error SQL. **Implementado y probado** |
| `POST /api/v1/collectibles/collect` | `game` / `collect` | `CollectRequest` (UUID, latitud/longitud acotadas, precisión >0, timestamp con zona horaria) y `Idempotency-Key` obligatorio de 16–128 caracteres | `CollectResponse` | Sesión requerida; jugador identificado por la sesión; ubicación y estado de aparición validados en servidor | Lee sesiones, perfil, zonas, aparición y catálogo; escribe `collections`, `player_profiles`, `point_transactions`, `xp_transactions`, `idempotency_records`; registra anomalías en `anti_cheat_events` | 200; 401; 403 fuera de zona/radio; 404 aparición inexistente; 409 ya recogida/clave reutilizada con distinto cuerpo; 410 expirada; 422 entrada/fecha/precisión inválida; 429 límite; 503 Redis/SQL. **Implementado y probado** en SQLite |
| `GET /api/v1/inventory` | `game` / `get_inventory` | Ninguna | `InventoryResponse` (`items`, `history`, `total_collected`) | Sesión requerida; datos limitados al usuario de sesión | `auth_sessions`, `users`, `player_profiles`, `collections`, `collectibles`, `point_transactions`, `xp_transactions` | 200; 401; 503 error SQL. **Implementado y probado**; el historial está limitado a 50, sin paginación |
| `GET /api/v1/missions` | `game` / `get_missions` | Ninguna | `{items: [], message: ...}` | Sesión requerida | No consulta tablas de misiones; la autenticación lee las tablas de sesión/usuario/perfil | 200; 401. **Parcial**: estado vacío explícito, sin persistencia ni lógica de misión/reclamo |
| `GET /api/v1/leaderboard` | `game` / `get_leaderboard` | `limit` opcional, default 50, rango 1–100 | `{items: [{rank, first_name, points, level, is_current_player}]}`; sin esquema declarado | Sesión requerida; lista global, sin exponer username o ID de otros jugadores | `auth_sessions`, `users`, `player_profiles` | 200; 401; 422 `limit` inválido; 503 error SQL. **Implementado y probado**; tope de 100, sin paginación |

### Salud y endpoints generados por FastAPI

| Método y ruta | Router / función | Entrada / respuesta | Autenticación | Dependencias | HTTP y estado |
| --- | --- | --- | --- | --- | --- |
| `GET /health/live` | `main` / `root_liveness` | Sin entrada; `{"status":"ok"}` | Pública | Ninguna; no verifica dependencias | 200. **Implementado y probado**; excluido de OpenAPI |
| `GET /api/v1/health/live` | `game` / `liveness` | Sin entrada; `{"status":"ok"}` | Pública | Ninguna; no verifica dependencias | 200. **Implementado y probado** |
| `GET /api/v1/health/ready` | `game` / `readiness` | Sin entrada; `{"status":"ready"}` si puede ejecutar `SELECT 1` y, fuera de `APP_ENV=test`, `Redis.ping()` | Pública | SQLAlchemy y Redis en ejecución normal; Redis se omite deliberadamente en test | 200 o 503. **Bloqueado por configuración externa** en la instancia auditada |
| `GET, HEAD /openapi.json` | FastAPI / OpenAPI automático | Sin entrada; documento OpenAPI | Pública | Ninguna | 200. **Implementado y probado** |
| `GET, HEAD /api/docs` | FastAPI / Swagger UI | Sin entrada; HTML Swagger que consume OpenAPI | Pública | Ninguna | 200 fuera de producción; deshabilitado en producción. **Implementado y probado** |
| `GET, HEAD /docs/oauth2-redirect` | FastAPI / redirección de Swagger | Endpoint auxiliar de Swagger | Pública | Ninguna | Registrado por FastAPI |

FastAPI no registra `/docs` ni `/redoc` en esta aplicación. Tampoco hay operación para `GET /`, `GET /api/v1` o `GET /api/v1/health/live` bajo una ruta alternativa. El prefijo común de las rutas funcionales es `/api/v1`, excepto el liveness raíz.

## 3. Documentación y contrato OpenAPI

| URL | Resultado observado | Evaluación |
| --- | ---: | --- |
| `/docs` | 404 | La UI estándar está reemplazada intencionalmente por `/api/docs`. |
| `/redoc` | 404 | ReDoc está deshabilitado explícitamente (`redoc_url=None`). |
| `/api/docs` | 200 | Swagger UI configurado en desarrollo. |
| `/openapi.json` | 200; 13 paths | Esquema OpenAPI estándar generado por FastAPI. No incluye `/health/live` porque se marca `include_in_schema=False`. |

En producción, `docs_url=None` deshabilita la UI de Swagger, pero no se configura `openapi_url=None`; por tanto `/openapi.json` permanece expuesto. Es una elección de configuración a confirmar, no evidencia de exposición de secretos.

El documento OpenAPI está incompleto como contrato:

- No declara autenticación por cookie ni marca como protegidas las rutas privadas, porque `get_current_player` lee la cookie desde `Request` en lugar de una dependencia de seguridad OpenAPI.
- Para rutas que responden 401/403/404/409/410/429/503, las operaciones normalmente solo documentan 200 y 422 (o solo 200). Los errores de negocio y dependencia no aparecen en `responses`.
- Solo `/players/me`, `/collectibles/collect` e `/inventory` tienen `response_model`. Respuestas de auth, zonas, resultados cercanos, misiones, ranking y ledger carecen de modelos declarados.
- `MissionResponse` en `schemas.py` declara `missions`, mientras que el endpoint real y el frontend consumen `items`; el esquema no se usa y no representa el contrato actual.

## 4. Seguridad

### Controles verificados

- Todas las rutas de perfil/juego consultadas (`players/me`, ledger, cercanos, colección, inventario, misiones y ranking) requieren una sesión. TestClient y un probe independiente devolvieron 401 sin cookie.
- `get_current_player` obtiene el token de la cookie configurada, busca su SHA-256 en `auth_sessions`, valida expiración y resuelve `User`/`PlayerProfile`. El cliente no puede seleccionar el usuario de perfil mediante parámetros.
- `/auth/telegram` valida `init_data` en backend: campos duplicados, hash HMAC con comparación constante, `auth_date`, edad máxima y `user.id` entero positivo. El cliente React envía `Telegram.WebApp.initData`; no usa `initDataUnsafe` para autenticar.
- `/auth/dev` responde 404 si `APP_ENV` no es `development` o `DEV_AUTH_ENABLED` no está habilitado. La configuración de producción rechaza el interruptor habilitado; las pruebas cubren rechazo en test y producción.
- La sesión es aleatoria, se almacena como digest, tiene TTL y cookie `HttpOnly`; la expiración y el logout eliminan la sesión. Producción exige cookie `Secure`, token de Telegram y orígenes HTTPS explícitos. Las pruebas cubren digest, expiración, logout y configuración.
- La respuesta de perfil incluye el Telegram ID del propio usuario. El ranking no devuelve usernames ni identificadores de otros usuarios.
- Los datos de colección validan coordenadas, precisión, timestamp con zona horaria, radio, estado y clave idempotente. La consulta de cercanos acota latitud, longitud y radio.
- El middleware limita orígenes no permitidos para mutaciones cuando el navegador envía `Origin`; CORS usa lista explícita de orígenes y credenciales.

### Observaciones y riesgos

- OpenAPI no describe la autenticación de cookie ni los errores de autorización. Esto dificulta generar clientes seguros y verificar desde el contrato qué rutas son privadas.
- `/openapi.json` continúa disponible en producción aunque las interfaces gráficas estén deshabilitadas. Confirmar si se desea conservar el esquema público en ese entorno.
- No hay roles/permisos administrativos en la API; las operaciones de provisión de zonas y apariciones existen como CLI, no como endpoints REST.
- `GET /api/v1/players/me/ledger` no limita ni pagina sus transacciones. El endpoint de zonas carga todas las zonas habilitadas y evalúa cada polígono una por una; puede escalar mal y no limita el volumen GeoJSON devuelto.
- El middleware de origen permite solicitudes sin cabecera `Origin`; esto es compatible con clientes no navegador y se complementa con cookie `SameSite` y CORS. No se verificó una prueba dedicada de CSRF en navegador.

## 5. Persistencia y datos

Las entidades persistidas son `users`, `player_profiles`, `auth_sessions`, `zones`, `collectibles`, `spawn_points`, `spawn_instances`, `collections`, `point_transactions`, `xp_transactions`, `idempotency_records` y `anti_cheat_events`.

- Perfil, autenticación, cercanos, inventario, ranking, ledger y colección usan SQLAlchemy. Los endpoints de juego consultan usando el identificador de usuario validado de la sesión.
- `/missions` no simula resultados persistidos: responde con una lista vacía literal y mensaje de estado. No existe modelo/tabla ni operación para reclamar misiones; el feature está parcial.
- No se encontró un catálogo de producción precargado en la migración ni un endpoint REST de catálogo. `cli.py create-spawn` requiere que el `Collectible` ya exista. Los registros Bitcoin de las pruebas son datos de fixture, no catálogo productivo.
- Las apariciones y zonas deben provisionarse explícitamente; el CLI valida GeoJSON con PostGIS. El worker genera apariciones dinámicas desde `spawn_points`.
- La suite usa SQLite real y crea fixtures persistentes. Para SQLite, geo utiliza Haversine y comprobación de polígonos local; PostgreSQL usa funciones PostGIS.
- No fue posible comprobar filas ni consultas contra PostgreSQL local: la conexión falla con `OperationalError`. Redis falla con `ConnectionError`. No se inspeccionó ni se incluyó el contenido de `.env`.

## 6. Validación funcional ejecutada

Comandos/comprobaciones:

1. `cd backend && ../.venv/bin/python -m pytest -q`  
   **18 passed, 1 skipped**, dos advertencias deprecadas de Starlette/httpx y estado HTTP 422. La prueba omitida es `test_only_one_player_collects_a_spawn_concurrently`, que exige `POSTGRES_TEST_DATABASE_URL` y PostGIS.
2. Inspección de rutas desde `app.routes`, `app.openapi()` y petición HTTP real a `/openapi.json`. Se contaron 13 operaciones OpenAPI bajo `/api/v1`.
3. GETs HTTP reales a health y documentación en `127.0.0.1:8000`: ambos liveness 200, readiness 503, `/docs` y `/redoc` 404, `/api/docs` y `/openapi.json` 200.
4. Probes TestClient con SQLite: endpoints privados sin cookie 401; autenticación Telegram con initData de prueba válido 200; auth dev deshabilitada 404; endpoints privados con cookie válida y health ready en modo test 200; latitud fuera de rango, coordenadas faltantes y clave de idempotencia ausente 422.
5. Se provocó un fallo SQLAlchemy real en SQLite eliminando la tabla de perfiles durante un probe: la ruta de perfil respondió 503 a través del manejador global. Esto valida el manejo de error en SQLite, no la recuperación ante fallos de PostgreSQL.
6. La suite contiene pruebas de autenticación inválida/expirada/tamperada y duplicados, protección de sesión, límites geográficos, expiración de apariciones, idempotencia/reintento, doble colección, inventario/ledger y estados vacíos de misiones.

No se ejecutó una integración completa de React contra el servidor: el contrato se comparó estáticamente con `src/api.js` y `src/App.js`. Las pruebas React no forman parte de esta ejecución.

## 7. Consistencia con frontend y documentación

- `src/api.js` consume rutas implementadas para perfil, auth Telegram/dev, collectibles cercanos, zonas cercanas, recolección, inventario, misiones y ranking. Usa `credentials: "include"` e `Idempotency-Key`; concuerda con cookies y el contrato de recolección.
- El frontend pasa radio 5000 (máximo permitido), envía latitud/longitud y `position.timestamp`, y renderiza `items` para misiones, como devuelve la implementación.
- El frontend no llama al ledger ni al logout; esos endpoints no tienen pantalla/flujo conectado en el cliente actual.
- El README describe además `GET /collectibles/catalog`, `POST /missions/{id}/claim` y otras rutas previstas que no están registradas. El código tampoco registra un endpoint de catálogo ni de administración. No confundir endpoints previstos en documentación con endpoints implementados.
- La ruta base `/api/v1` no es una página ni un health check y responde 404; para Swagger de desarrollo usar `/api/docs`.

## 8. Errores encontrados y problemas críticos

### Problemas críticos

1. **No se pudo confirmar la disponibilidad de producción**: la instancia local devuelve readiness 503 y las conexiones locales a PostgreSQL y Redis fallan. PostgreSQL/PostGIS y rate limiting Redis deben validarse antes de afirmar que están operativos.
2. **La prueba más relevante de concurrencia está omitida**: SQLite no reproduce `SELECT ... FOR UPDATE`, consultas PostGIS ni la exclusión mutua de PostgreSQL. La idempotencia sí se prueba en SQLite, pero la atomicidad/concurrencia productiva permanece sin verificar.

No se identificó un bypass de sesión, confianza en `initDataUnsafe` ni uso de IDs suministrados por el cliente para leer perfiles durante las rutas revisadas.

### Errores y brechas funcionales

- El readiness de la instancia activa devuelve `503`; el detalle es deliberadamente genérico. Las pruebas de `APP_ENV=test` omiten Redis y usan SQLite, por lo que su 200 no equivale a readiness productivo.
- Misiones es solo un estado vacío; no hay progreso ni reclamo persistente.
- Rutas previstas de catálogo y reclamo de misión no están implementadas.
- Las rutas con errores de negocio carecen de respuestas declaradas en OpenAPI.
- Consultas de zonas y ledger no están paginadas; zonas evalúa polígonos con carga y recorridos por zona.
- Las advertencias de prueba indican uso de una integración httpx/Starlette deprecada y de `HTTP_422_UNPROCESSABLE_ENTITY`; no causaron fallo en esta ejecución.

## 9. Mejoras recomendadas (sin aplicar)

1. Provisionar PostgreSQL con PostGIS y Redis, ejecutar migraciones y repetir readiness; ejecutar además `test_concurrency_postgres.py` contra una base de pruebas dedicada.
2. Declarar esquemas Pydantic para todas las respuestas, corregir `MissionResponse` o eliminarlo si no representa el contrato, y documentar códigos 401/403/404/409/410/429/503 y seguridad cookie en OpenAPI.
3. Decidir si se debe deshabilitar también `/openapi.json` en producción.
4. Implementar catálogo y misiones/reclamos solo si siguen dentro del alcance; mantener el estado vacío actual explícito hasta entonces.
5. Aplicar paginación a ledger y a consultas de zonas, y resolver la consulta de zonas con una operación espacial acotada en vez de cargar/iterar todos los polígonos.
6. Sincronizar README con rutas realmente registradas o etiquetar claramente las rutas como previstas.
7. Ejecutar una prueba E2E React–FastAPI con origen CORS real, cookie persistida y credenciales Telegram de un entorno seguro de prueba.

## 10. Dependencias externas por endpoint

| Endpoint / flujo | PostgreSQL / PostGIS | Redis | Telegram real |
| --- | --- | --- | --- |
| `/auth/telegram` | SQLAlchemy guarda/actualiza usuario, perfil y sesión; puede operar con SQLAlchemy compatible | Necesario en entorno no-test para límite de intentos; falla explícitamente 503 si no disponible | Requiere `TELEGRAM_BOT_TOKEN` real para validar `initData`; no hace una llamada de red a Telegram |
| `/auth/dev`, `/auth/logout`, `/players/me`, `/players/me/ledger`, `/inventory`, `/leaderboard`, `/missions` | Persistencia SQLAlchemy; no requieren funciones PostGIS | No requieren Redis salvo la comprobación independiente de readiness | No |
| `/zones/nearby`, `/collectibles/nearby` | PostGIS ejecuta `ST_Covers`, `ST_DWithin`/`ST_Distance`; SQLite tiene fallback real pero distinto | No | No |
| `/collectibles/collect` | En PostgreSQL usa distancia geography y bloqueo de fila; SQLite usa Haversine sin las mismas garantías concurrentes | Necesario para rate limit en no-test | No |
| `/health/ready` | Ejecuta `SELECT 1` | Hace `PING` salvo en test | No |
| `cli.py create-zone` y worker dinámico | `create-zone` requiere funciones PostGIS; worker persiste apariciones en DB | No | No |

**Conclusión:** las rutas implementadas funcionan en el entorno de prueba con SQLite y tienen controles básicos de sesión, validación e idempotencia. La API no debe declararse completamente validada para producción hasta probar PostgreSQL/PostGIS y Redis reales y cerrar las brechas de contrato documentadas.
