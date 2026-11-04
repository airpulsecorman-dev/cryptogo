# Crypto Go — Estado de implementación

## Alcance de la auditoría

Revisión del repositorio en su estado inicial. La aplicación es una SPA de
Create React App con una única pantalla principal, sin servicios de API ni
backend. `README.md` describe una arquitectura prevista, no una arquitectura
implementada. Las pruebas existentes verifican el comportamiento de
demostración y no prueban persistencia ni operaciones de servidor.

## Estado por módulo

| Módulo | Estado actual | Problemas encontrados | Archivos involucrados | Trabajo necesario | Pruebas requeridas |
| --- | --- | --- | --- | --- | --- |
| Aplicación web y navegación | Parcial: React permite navegar entre cinco pantallas | Las pantallas muestran saldos, perfiles y estadísticas estáticos; la navegación cambia estado local | `src/App.js`, `src/App.css`, `src/index.js` | Conservar el diseño y conectar las pantallas a respuestas reales; mostrar carga, error y vacío | Pruebas de navegación, carga, errores y datos de API |
| Mapa y ubicación | No implementado: el mapa es una ilustración CSS | Coordenadas y marcadores ficticios; la geolocalización solo presenta un mensaje de demostración | `src/App.js`, `src/App.css`, `package.json` | Sustituir la ilustración por MapLibre; pedir GPS solo tras acción del usuario; consultar apariciones dentro de zonas habilitadas | GPS permitido/denegado, mapa, búsqueda geográfica PostGIS y zonas |
| Autenticación | No implementada | No hay validación de Telegram, sesión ni rutas privadas | `src/App.js`, `README.md` | Verificar `initData` en servidor, expirar datos antiguos y emitir sesión HttpOnly; mantener una ruta de desarrollo aislada | Firma válida/inválida, expiración, sesión, registro y rechazo del login de desarrollo en producción |
| API | No existe | No hay aplicación HTTP, contrato versionado ni validación compartida | Repositorio; contrato previsto en `README.md` | Crear FastAPI modular bajo `/api/v1`, validación de entradas y manejo central de errores | Pruebas de endpoints, autorización, errores y esquema OpenAPI |
| Persistencia | No existe | No hay PostgreSQL, modelos ni migraciones | Repositorio; diseño previsto en `README.md` | PostgreSQL/PostGIS, SQLAlchemy y Alembic para usuarios, perfiles, zonas, catálogo, apariciones, colecciones y libro contable | Migraciones, creación/recuperación del perfil y persistencia tras reiniciar |
| Zonas y apariciones | No implementado | Los tesoros se declaran en un arreglo local; no hay expiración, densidad ni estado compartido | `src/App.js`, `README.md` | Consultar apariciones disponibles desde la base de datos; provisionar zonas verificadas y puntos fijos; generar dinámicas en un proceso servidor con límites | Visibilidad, geocerca, densidad, expiración y cambios de estado |
| Recolección y antifraude | No implementado | El clic acredita puntos en React sin comprobar identidad, distancia, disponibilidad o duplicados | `src/App.js`, `README.md` | Hacer la operación atómica en backend con bloqueo de fila, distancia PostGIS, precisión, anomalías e idempotencia | Radio máximo, expiración, idempotencia, doble recolección y concurrencia |
| Inventario, puntos y XP | No implementado | Conteos y saldo se inicializan en memoria; no hay historial auditable ni progresión persistente | `src/App.js`, `README.md` | Derivar el inventario de colecciones; registrar puntos y XP como movimientos inmutables; calcular nivel en backend | Recompensas, nivel, inventario, historial y persistencia entre sesiones |
| Misiones y ranking | No implementado | Misiones y jugadores están hardcodeados en el componente | `src/App.js` | Consultar datos del backend; presentar claramente un estado vacío cuando no existan misiones o jugadores | Respuestas vacías, orden del ranking y datos de jugador |
| Configuración y despliegue | No implementado | No hay Docker Compose, configuración de entorno ni proceso de despliegue del API | `package.json`, `.gitignore`, `README.md` | Documentar variables sin secretos y añadir servicios reproducibles de API, PostgreSQL/PostGIS y Redis | Arranque local, readiness, migraciones y comprobación de secretos |
| Pruebas automatizadas | Parcial: 11 pruebas de UI de demostración pasan | No prueban autenticación, APIs, base de datos, mapas reales ni concurrencia | `src/App.test.js`, `src/setupTests.js` | Añadir pruebas de backend y adaptar las de UI al contrato conectado; ejecutar integraciones PostGIS al disponer de PostgreSQL | Pytest, pruebas React y, con el entorno disponible, integración PostgreSQL/PostGIS concurrente |

## Observaciones del entorno

- La raíz existente es Create React App/JavaScript, no Next.js/TypeScript. Se
  conserva para evitar una sustitución de tecnología no necesaria.
- El repositorio de trabajo incluye un `src.zip` sin seguimiento. La auditoría
  no lo modifica.
- En esta auditoría no se encontraron `Docker`, `psql`, servicios de base de
  datos ni variables de Telegram. Por ello, las pruebas locales no pueden
  afirmar que una instancia real de PostgreSQL/PostGIS o Telegram esté
  operativa.
- No se crearán zonas ni posiciones geográficas ficticias. La búsqueda real
  devolverá vacío hasta que un operador proporcione y habilite zonas y puntos
  verificados.

## Entrega incremental

La primera entrega implementa el contrato de autenticación, perfil, mapa,
recolección e inventario, además de infraestructura local y pruebas. Misiones
reales requieren definiciones de producto persistidas y se mostrarán vacías en
lugar de inventar progreso. La activación operativa aún requiere credenciales
de entorno, aprovisionar puntos seguros y ejecutar las verificaciones de
integración con PostgreSQL/PostGIS.
