# CRYPTO GO

> **Go. Collect. Level Up.**\
> Explora el mundo real, encuentra criptomonedas virtuales y conviértete
> en leyenda.

**Estado del proyecto:** implementación inicial del cliente React y API; pendiente de despliegue integrado\
**Versión del documento:** 1.0\
**Plataforma inicial:** Telegram Mini App\
**Territorio de lanzamiento:** Ecuador\
**Modalidad de lanzamiento:** beta privada\
**Modelo de recompensas:** puntos y experiencia virtuales, sin valor
monetario\
**Arquitectura actual:** Create React App + React/JavaScript, MapLibre GL JS,
FastAPI, SQLAlchemy/Alembic, PostgreSQL/PostGIS, Redis y worker de apariciones

------------------------------------------------------------------------

## Índice

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Visión, objetivos y alcance](#2-visión-objetivos-y-alcance)
3. [Decisiones de producto](#3-decisiones-de-producto)
4. [Experiencia de juego](#4-experiencia-de-juego)
5. [Mapa y distribución geográfica](#5-mapa-y-distribución-geográfica)
6. [Economía virtual, puntos y
    progresión](#6-economía-virtual-puntos-y-progresión)
7. [Misiones, logros y funciones
    sociales](#7-misiones-logros-y-funciones-sociales)
8. [Diseño de interfaz](#8-diseño-de-interfaz)
9. [Arquitectura técnica](#9-arquitectura-técnica)
10. [Estructura del repositorio](#10-estructura-del-repositorio)
11. [Modelo de datos](#11-modelo-de-datos)
12. [API y contratos](#12-api-y-contratos)
13. [Autenticación e integración con
    Telegram](#13-autenticación-e-integración-con-telegram)
14. [Geolocalización y recolección](#14-geolocalización-y-recolección)
15. [Seguridad y prevención de
    trampas](#15-seguridad-y-prevención-de-trampas)
16. [Privacidad, seguridad física y
    cumplimiento](#16-privacidad-seguridad-física-y-cumplimiento)
17. [Panel administrativo](#17-panel-administrativo)
18. [Infraestructura y despliegue](#18-infraestructura-y-despliegue)
19. [Configuración del entorno](#19-configuración-del-entorno)
20. [Pruebas y criterios de
    aceptación](#20-pruebas-y-criterios-de-aceptación)
21. [Plan de implementación](#21-plan-de-implementación)
22. [Métricas de la beta](#22-métricas-de-la-beta)
23. [Presupuesto orientativo](#23-presupuesto-orientativo)
24. [Riesgos y mitigaciones](#24-riesgos-y-mitigaciones)
25. [Decisiones pendientes](#25-decisiones-pendientes)
26. [Definición de terminado](#26-definición-de-terminado)
27. [Glosario](#27-glosario)
28. [Referencias oficiales](#28-referencias-oficiales)

------------------------------------------------------------------------

## 1. Resumen ejecutivo

**Crypto Go** es un videojuego de exploración geográfica inspirado en
la dinámica de juegos como Pokémon GO. Los jugadores abren una Mini App
dentro de Telegram, consultan un mapa de su entorno y se desplazan
físicamente para encontrar objetos virtuales inspirados en
criptomonedas.

Los objetos pueden representar BTC, ETH, BNB, SOL y otros activos
conocidos. Encontrarlos permite ganar puntos, experiencia (XP),
completar misiones, desbloquear insignias y subir de nivel.

La primera versión no utilizará blockchain para recompensas, custodia,
depósitos, retiros ni transacciones. El inicio de sesión puede hacerse
mediante Telegram o con una firma de billetera EVM/Telegram Wallet; esa
firma solo verifica la identidad y no envía transacciones ni requiere gas.
Los puntos serán unidades internas de juego, no transferibles, sin valor
monetario y no canjeables por dinero.

El lanzamiento se realizará mediante una **beta privada en Ecuador**. La
aplicación tendrá capacidad técnica para cubrir el país, pero
inicialmente solo estarán habilitadas las zonas que hayan sido
verificadas y aprobadas por el equipo administrador.

## Propuesta de valor

- Convertir la exploración del mundo real en una experiencia de juego.
- Ofrecer una experiencia accesible desde Telegram, sin exigir
    instalar una aplicación nativa.
- Incentivar la exploración segura, las colecciones y los desafíos.
- Crear una comunidad de cazadores que compita mediante rankings y
    eventos.
- Construir una plataforma modular que pueda ampliarse a otras
    ciudades y países.

## Estado actual

El estado verificado de cada módulo está en
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md). La SPA
conserva su identidad visual y se conecta a una API FastAPI con sesiones
HttpOnly, perfiles persistentes, mapa MapLibre, consultas PostGIS,
recolección transaccional e inventario. Los tests locales usan SQLite para
probar las reglas de aplicación; la integración concurrente/PostGIS requiere
un servicio PostgreSQL real. El flujo de producción aún necesita credenciales
de Telegram, URL HTTPS, zonas seguras aprobadas y apariciones provisionadas.
No se incluyen ubicaciones de juego de demostración en producción. Los plazos,
costos y parámetros de balance son estimaciones sujetas a pruebas.

------------------------------------------------------------------------

## 2. Visión, objetivos y alcance

## 2.1 Visión

Crear una experiencia de búsqueda de tesoros digitales en la que el mapa
del mundo real sea el tablero de juego y las criptomonedas virtuales
sean los objetos coleccionables.

## 2.2 Objetivos del MVP

1. Permitir que un usuario se autentique mediante Telegram o una billetera.
2. Mostrar un mapa centrado en su ubicación cuando conceda permiso.
3. Mostrar monedas virtuales disponibles dentro de zonas habilitadas.
4. Permitir recoger una moneda al encontrarse dentro del radio
    permitido.
5. Validar la recolección en el servidor.
6. Acreditar puntos y XP de manera atómica y auditable.
7. Mostrar el inventario, nivel, misiones y ranking.
8. Administrar ubicaciones, zonas y apariciones desde un panel
    protegido.
9. Detectar patrones de fraude y evitar recompensas duplicadas.
10. Ejecutar una beta privada con un grupo limitado de usuarios.

## 2.3 Fuera del alcance inicial

No se desarrollará en el MVP:

- Token propio ni criptomoneda negociable.
- Integración con exchanges.
- Depósitos, retiros o transferencias de fondos.
- Custodia, depósitos, retiros o transacciones con billeteras blockchain.
- NFT comercializables.
- Premios en dinero o activos financieros.
- Compras dentro de la aplicación.
- Seguimiento GPS continuo en segundo plano.
- Aplicaciones nativas independientes para Android o iOS.
- Microservicios distribuidos o Kubernetes.
- Chat interno complejo o sistema avanzado de mensajería.

Estas funciones solo podrán evaluarse en fases futuras, con análisis
técnico, legal, de seguridad y de sostenibilidad.

------------------------------------------------------------------------

## 3. Decisiones de producto

Las siguientes decisiones constituyen la línea base del proyecto.

  Decisión               Definición
  ---------------------- ------------------------------------------------------
  Nombre                 Crypto Go
  Lema                   Go. Collect. Level Up.
  Plataforma             Telegram Mini App
  País inicial           Ecuador
  Cobertura              Preparada para todo Ecuador
  Disponibilidad real    Solo zonas habilitadas
  Distribución           Híbrida: puntos fijos y apariciones dinámicas
  Lanzamiento            Beta privada
  Recompensas            Puntos y XP internos
  Blockchain             No se utiliza en el MVP
  Frontend               Next.js, React y TypeScript
  Backend                Python y FastAPI
  Base de datos          PostgreSQL y PostGIS
  Caché                  Redis
  Procesos programados   Workers
  Mapas                  MapLibre GL JS con proveedor cartográfico compatible

## 3.1 Cobertura nacional y zonas piloto

La plataforma podrá mostrar el mapa en cualquier ubicación de Ecuador,
pero el motor de juego solo entregará objetos en zonas habilitadas.

La expansión se realizará por ciudad, cantón o área geográfica. No se
debe interpretar "Ecuador" como autorización para generar monedas en
todas las coordenadas del país.

## 3.2 Modalidad beta privada

Etapas orientativas:

  Etapa                   Usuarios objetivo
  --------------------- -------------------
  Pruebas internas                    5--10
  Beta cerrada                      50--100
  Beta ampliada                    300--500
  Lanzamiento público      Según resultados

Las cantidades son objetivos de planificación, no límites técnicos.

------------------------------------------------------------------------

## 4. Experiencia de juego

## 4.1 Flujo principal

1. El jugador abre el bot de Crypto Go en Telegram.
2. Pulsa el botón para abrir la Mini App.
3. El frontend obtiene los datos de inicialización de Telegram.
4. El backend verifica la autenticidad de esos datos.
5. Se carga el perfil del jugador.
6. El usuario concede permiso de ubicación.
7. El mapa muestra su posición y los objetos cercanos.
8. El jugador se desplaza hacia un objeto.
9. Al acercarse, se habilita la acción **RECOGER**.
10. El frontend envía la solicitud al backend.
11. El backend verifica identidad, distancia, precisión, disponibilidad
    y reglas antitrampas.
12. Si la operación es válida, registra la colección y acredita los
    puntos/XP en una única transacción.
13. La interfaz muestra la recompensa y actualiza el inventario.

## 4.2 Objetos coleccionables

Los objetos son representaciones visuales de criptomonedas. No
representan propiedad, saldo, inversión ni tenencia de la criptomoneda
real.

Catálogo inicial sugerido:

  Objeto           Rareza inicial     Puntos de ejemplo
  ---------------- ---------------- -------------------
  BTC              Común                             10
  ETH              Poco común                        25
  BNB              Raro                              50
  SOL              Épico                            100
  BTC Legendario   Legendario                       500

Los valores son configurables y deberán balancearse durante las pruebas.
El nombre o logotipo de un activo no implica asociación oficial con el
proyecto ni patrocinio de su emisor.

## 4.3 Rarezas

- **Común:** aparición frecuente.
- **Poco común:** aparición moderada.
- **Raro:** aparición limitada.
- **Épico:** aparición escasa.
- **Legendario:** aparición extraordinaria o vinculada a eventos.

La rareza, el valor de puntos, la disponibilidad y la frecuencia deben
configurarse desde el backend o el panel administrativo; nunca depender
de valores enviados por el cliente.

------------------------------------------------------------------------

## 5. Mapa y distribución geográfica

El mapa es el componente central de Crypto Go.

## 5.1 Tecnología cartográfica

- MapLibre GL JS para renderizar el mapa.
- Datos cartográficos de OpenStreetMap u otro proveedor compatible.
- Un proveedor de teselas con condiciones de uso apropiadas para
    producción.
- PostGIS para consultas espaciales.
- H3 como opción para indexar y agrupar áreas geográficas.

No se debe utilizar el servidor público de teselas estándar de
OpenStreetMap como infraestructura gratuita ilimitada de producción.
Deben revisarse sus políticas, atribución, capacidad y condiciones.

## 5.2 Distribución híbrida

El motor combinará:

### A. Tesoros fijos

Puntos geográficos aprobados manualmente por administradores.

Ejemplos de posibles ubicaciones:

- Parques públicos autorizados.
- Plazas.
- Espacios peatonales.
- Áreas recreativas accesibles.
- Zonas públicas verificadas.

Cada punto fijo debe contar con estado de aprobación, restricciones,
radio, capacidad y horario cuando corresponda.

### B. Tesoros dinámicos

Objetos generados por el servidor dentro de áreas geográficas
habilitadas.

El proceso deberá:

1. Consultar celdas o zonas activas.
2. Verificar que la ubicación esté dentro de una geocerca permitida.
3. Descartar áreas restringidas o no verificadas.
4. Comprobar la densidad máxima.
5. Seleccionar el tipo de objeto según reglas configurables.
6. Crear una aparición con identificador único.
7. Definir expiración.
8. Publicar el objeto en las consultas del mapa.

## 5.3 Proporción inicial

Configuración de partida:

  Tipo                            Proporción
  ----------------------------- ------------
  Apariciones en puntos fijos            40%
  Apariciones dinámicas                  60%

Estos porcentajes representan una configuración de prueba. Se podrán
modificar según la experiencia real, disponibilidad de lugares y
seguridad.

## 5.4 Zonas y geocercas

Cada zona debe incluir, como mínimo:

- Identificador.
- País, provincia, cantón y ciudad.
- Geometría geográfica.
- Estado: borrador, pendiente, aprobada, pausada o bloqueada.
- Tipo de zona.
- Densidad permitida.
- Horarios, si aplica.
- Motivo de bloqueo, si aplica.
- Administrador responsable.
- Fecha de creación y actualización.

No se habilitarán ubicaciones en propiedades privadas, carreteras
peligrosas, vías rápidas, instalaciones sensibles, zonas restringidas o
espacios sin acceso público autorizado.

## 5.5 Consulta del mapa

El frontend no descargará el mapa completo del país. Consultará objetos
cercanos a la ubicación actual, con límites de radio, cantidad,
paginación o agrupación según el nivel de zoom.

Las coordenadas exactas de objetos raros no deben exponerse antes de que
el jugador esté dentro de una distancia de descubrimiento definida por
el servidor. La ubicación mostrada puede ser aproximada para evitar
filtraciones y abuso.

------------------------------------------------------------------------

## 6. Economía virtual, puntos y progresión

## 6.1 Puntos y XP

La economía del MVP utiliza puntos internos y experiencia.

- Los **puntos** representan el saldo de juego.
- La **XP** determina el progreso de nivel.
- Ambos se acreditan exclusivamente desde el backend.
- No son transferibles entre jugadores.
- No se pueden retirar, vender ni convertir en dinero.
- No son una promesa de recompensa económica futura.

En el MVP, una recolección puede acreditar puntos y XP en la misma
cantidad, pero los dos conceptos deben mantenerse separados en el modelo
de datos para permitir balancearlos posteriormente.

## 6.2 Niveles sugeridos

  Nivel   Nombre         XP acumulada
  ------- ------------ --------------
  1       Novato                    0
  2       Explorador              100
  3       Cazador                 300
  4       Experto                 700
  5       Maestro               1.500
  6       Élite                 3.000
  7       Leyenda               6.000

Los umbrales son valores iniciales y configurables. La XP acumulada debe
ser monotónica y calcularse desde eventos válidos del servidor.

## 6.3 Desbloqueos

El progreso podrá desbloquear:

- Avatares.
- Marcos de perfil.
- Insignias.
- Efectos visuales.
- Misiones adicionales.
- Elementos cosméticos.

Los elementos cosméticos no deben otorgar ventajas injustas de
recolección.

## 6.4 Libro de movimientos de puntos

Toda modificación de puntos debe generar un registro inmutable en
`point_transactions`.

No se debe editar directamente el saldo desde el frontend ni permitir
que un administrador cambie puntos sin dejar un registro de auditoría.

Las operaciones deben tener una clave de idempotencia para impedir
acreditaciones duplicadas.

------------------------------------------------------------------------

## 7. Misiones, logros y funciones sociales

## 7.1 Misiones diarias

Ejemplos:

- Encuentra 3 monedas.
- Encuentra una moneda ETH.
- Explora dos ubicaciones distintas.
- Recoge una moneda rara.

## 7.2 Misiones semanales

- Encuentra 20 monedas.
- Completa 5 misiones.
- Descubre 3 zonas diferentes.

## 7.3 Eventos

- **Bitcoin Go:** evento temporal de BTC especiales.
- **Ethereum Weekend:** evento temático de ETH.
- **Crypto Festival:** evento regional o nacional.

Los eventos tendrán fechas, zonas, reglas, límites y recompensas
configurables.

## 7.4 Logros

- Primera moneda encontrada.
- Primera moneda legendaria.
- 100 monedas recolectadas.
- Siete días de actividad.
- Primera misión completada.

## 7.5 Rankings

- Mundial.
- Nacional.
- Local, por ciudad o zona habilitada.

El ranking debe tener reglas de periodo y desempate claramente
definidas. La ubicación del usuario no debe mostrarse públicamente con
precisión.

## 7.6 Equipos y referidos

Los equipos y el sistema avanzado de invitaciones pueden quedar para una
fase posterior. En el MVP se priorizarán recolección, inventario,
misiones y ranking individual.

------------------------------------------------------------------------

## 8. Diseño de interfaz

## 8.1 Identidad visual

Dirección visual sugerida:

- Fondo azul marino oscuro.
- Dorado para BTC y recompensas.
- Azul eléctrico para navegación.
- Morado para objetos épicos.
- Animaciones suaves.
- Efectos de descubrimiento y subida de nivel.
- Diseño mobile-first.

## 8.2 Navegación principal

La Mini App tendrá cinco secciones:

  Sección      Función
  ------------ -------------------------------------
  Mapa         Explorar y recoger objetos
  Inventario   Ver monedas y colecciones
  Misiones     Consultar desafíos y progreso
  Ranking      Competir con otros jugadores
  Perfil       Nivel, XP, estadísticas e insignias

## 8.3 Requisitos de experiencia

- Adaptación a pantallas pequeñas.
- Estados de carga y error.
- Indicador claro de permiso de ubicación.
- Mensajes para GPS impreciso.
- Modo de mapa vacío cuando no existan objetos cercanos.
- Confirmación visual de recolección.
- Prevención de doble pulsación.
- Compatibilidad con los temas de Telegram cuando sea conveniente.
- No depender de animaciones para transmitir información crítica.

------------------------------------------------------------------------

## 9. Arquitectura técnica

## 9.1 Principios

- Monolito modular para el backend inicial.
- Frontend independiente.
- API versionada.
- Separación de reglas de negocio, acceso a datos y presentación.
- Base de datos como fuente de verdad.
- Validación de operaciones sensibles en el servidor.
- Procesos programados desacoplados mediante workers.
- Infraestructura reproducible con Docker.
- Pruebas automatizadas desde el comienzo.

No se recomienda iniciar con microservicios ni Kubernetes para la beta.

## 9.2 Stack

  Componente             Tecnología
  ---------------------- --------------------------------
  Frontend               Create React App + React (existente)
  Lenguaje frontend      JavaScript (existente)
  Estilos                CSS (existente)
  Mapas                  MapLibre GL JS
  Backend                Python + FastAPI
  Base de datos          PostgreSQL
  Extensión geográfica   PostGIS
  ORM                    SQLAlchemy
  Migraciones            Alembic
  Caché y límites        Redis
  Workers                Procesos Python independientes
  Bot                    Telegram Bot API
  Contenedores           Docker
  Proxy HTTPS            Nginx o equivalente
  Pruebas frontend       Jest y Testing Library (existentes)
  Pruebas backend        Pytest

El repositorio existente se conserva en Create React App/JavaScript; Next.js y
TypeScript son una opción de evolución documentada, no requisitos para este
primer flujo. Las dependencias actuales están declaradas en `package.json` y
`yarn.lock`; las del API están en `backend/requirements.txt`.

## 9.3 Diagrama lógico

``` mermaid
flowchart TD
    A[Usuario] --> B[Telegram]
    B --> C[Telegram Mini App]
    C --> D[React / MapLibre]
    D --> E[FastAPI]
    E --> F[Autenticación y reglas del juego]
    F --> G[(PostgreSQL + PostGIS)]
    F --> H[(Redis)]
    I[Worker de apariciones] --> G
    J[Worker de misiones y eventos] --> G
    K[Panel administrativo] --> E
    L[Telegram Bot API] <--> M[Bot de Crypto Go]
    M --> B
```

## 9.4 Responsabilidades

### Frontend

- Interfaz de la Mini App.
- Integración con Telegram Web Apps SDK.
- Solicitud de ubicación.
- Renderizado del mapa.
- Visualización de objetos.
- Inventario y misiones.
- Presentación de resultados de API.

No decide recompensas ni valida definitivamente las recolecciones.

### Backend

- Verificación de Telegram.
- Gestión de usuarios.
- Reglas de juego.
- Consultas geográficas.
- Validación de recolecciones.
- Acreditación de puntos y XP.
- Misiones, niveles y rankings.
- Auditoría y controles antitrampas.
- Administración.

### Workers

- Generación y expiración de apariciones.
- Actualización de eventos.
- Reinicio de misiones periódicas.
- Procesos que no deben ejecutarse dentro de una petición HTTP.

------------------------------------------------------------------------

## 10. Estructura del repositorio

La estructura propuesta a continuación es un diseño objetivo y no refleja el
árbol real existente. Para esta entrega no se trasladó ni reemplazó el
frontend Create React App. El código añadido usa `backend/` y mantiene la
aplicación web en la raíz:

```text
src/App.js                 # Interfaz conectada a la API
src/MapView.js             # Mapa MapLibre y capas/markers
src/api.js                 # Cliente HTTP con cookies de sesión
backend/app/               # FastAPI, modelos, seguridad, geografía, worker
backend/migrations/        # Migraciones Alembic
backend/tests/             # Pruebas API/reglas y concurrencia PostGIS
docker-compose.yml         # PostgreSQL/PostGIS, Redis, API y worker
docs/IMPLEMENTATION_STATUS.md
```

La estructura futura propuesta para una evolución mayor sería:

``` text
crypto-Go/
├── apps/
│   ├── web/                    # Telegram Mini App
│   │   ├── src/
│   │   │   ├── app/
│   │   │   ├── components/
│   │   │   ├── features/
│   │   │   │   ├── map/
│   │   │   │   ├── inventory/
│   │   │   │   ├── missions/
│   │   │   │   ├── leaderboard/
│   │   │   │   └── profile/
│   │   │   ├── hooks/
│   │   │   ├── services/
│   │   │   └── lib/
│   │   └── package.json
│   │
│   ├── api/                    # FastAPI
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── core/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── services/
│   │   │   ├── repositories/
│   │   │   └── security/
│   │   ├── tests/
│   │   └── requirements.txt
│   │
│   ├── bot/
│   │   ├── handlers/
│   │   ├── keyboards/
│   │   └── main.py
│   │
│   └── admin/                  # Panel administrativo
│
├── workers/
│   ├── spawn_engine/
│   ├── mission_scheduler/
│   └── event_scheduler/
│
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   └── database/
│
├── docs/
│   ├── architecture.md
│   ├── database.md
│   ├── api.md
│   ├── security.md
│   └── deployment.md
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

El panel administrativo podrá compartir componentes visuales con la Mini
App, pero deberá tener rutas, permisos y controles de acceso
independientes.

------------------------------------------------------------------------

## 11. Modelo de datos

El esquema definitivo se construirá mediante migraciones Alembic. Las
tablas iniciales recomendadas son:

  Tabla                   Responsabilidad
----------------------- -----------------------------------------------
  `users`                 Identidad interna y datos mínimos de Telegram
  `player_profiles`       Nivel, XP y estadísticas
  `collectibles`          Catálogo de objetos y rarezas
  `zones`                 Zonas geográficas habilitadas
  `spawn_points`          Ubicaciones fijas aprobadas
  `spawn_instances`       Apariciones activas o expiradas
  `collections`           Registro de objetos recogidos
  `point_transactions`    Libro de movimientos de puntos
  `missions`              Definición de misiones
  `player_missions`       Progreso individual
  `achievements`          Catálogo de logros
  `player_achievements`   Logros desbloqueados
  `events`                Eventos temporales
  `teams`                 Equipos, en fase posterior
  `team_members`          Integrantes, en fase posterior
  `anti_cheat_logs`       Alertas de seguridad
  `admin_users`           Administradores
  `admin_audit_logs`      Historial de acciones administrativas
  `idempotency_keys`      Control de solicitudes repetidas

## 11.1 Campos esenciales

### users

- `id`: UUID interno.
- `telegram_id`: identificador único de Telegram.
- `username`: opcional.
- `first_name`: opcional.
- `country_code`: código de país.
- `status`: estado de cuenta.
- `created_at`.

No se debe almacenar información de Telegram que no sea necesaria para
el funcionamiento.

### player_profiles

- `user_id`.
- `level`.
- `total_xp`.
- `available_points`.
- `coins_collected`.

### collectibles

- `id`.
- `symbol`.
- `name`.
- `rarity`.
- `reward_points`.
- `reward_xp`.
- `active`.

### zones

- `id`.
- `name`.
- `country_code`.
- `province`.
- `city`.
- `boundary`: geometría geográfica.
- `status`.
- `density_limit`.
- `created_by`.

### spawn_instances

- `id`.
- `collectible_id`.
- `location`: punto geográfico.
- `source`: fixed o dynamic.
- `status`: available, collected, expired o disabled.
- `expires_at`.
- `created_at`.

### collections

- `id`.
- `user_id`.
- `spawn_id`.
- `collected_at`.
- `points_awarded`.
- `xp_awarded`.

Debe existir una restricción que impida recoger dos veces la misma
aparición.

### point_transactions

- `id`.
- `user_id`.
- `amount`.
- `transaction_type`.
- `reference_id`.
- `idempotency_key`.
- `created_at`.

Los registros de transacciones no se editan ni eliminan para corregir
saldos; se crean movimientos compensatorios auditables cuando
corresponda.

## 11.2 Reglas de integridad

- UUID como identificadores internos.
- Claves foráneas.
- Índices espaciales GiST.
- Restricciones únicas para prevenir duplicados.
- Validación de valores de rareza y estados.
- Transacciones ACID para recolección y acreditación.
- Fechas almacenadas en UTC.
- Consultas y presentación de horarios según la zona correspondiente.

------------------------------------------------------------------------

## 12. API y contratos

La API utilizará el prefijo `/api/v1`.

## 12.1 Endpoints previstos

### Autenticación y perfil

  Método   Ruta               Descripción
  -------- ------------------ ------------------------------
  POST     `/auth/telegram`   Autenticar mediante initData
  POST     `/auth/evm/challenge` Crear reto de firma EVM
  POST     `/auth/evm/verify` Verificar firma e iniciar sesión EVM
  POST     `/auth/ton/challenge` Crear reto TON Connect
  POST     `/auth/ton/verify` Verificar ton_proof e iniciar sesión
  POST     `/auth/refresh`    Renovar sesión, si aplica
  POST     `/auth/logout`     Cerrar sesión
  GET      `/players/me`      Perfil actual

### Mapa y objetos

  Método   Ruta                      Descripción
  -------- ------------------------- -------------------------
  GET      `/map/nearby`             Objetos cercanos
  GET      `/collectibles/catalog`   Catálogo
  POST     `/collectibles/collect`   Intentar recoger objeto

### Progreso

  Método   Ruta                         Descripción
  -------- ---------------------------- ----------------------------
  GET      `/inventory`                 Colección del usuario
  GET      `/missions`                  Misiones disponibles
  POST     `/missions/{id}/claim`       Reclamar misión completada
  GET      `/players/me/achievements`   Logros
  GET      `/leaderboard`               Ranking
  GET      `/events/active`             Eventos activos

### Administración

  Método   Ruta                  Descripción
  -------- --------------------- -------------------
  GET      `/admin/dashboard`    Métricas
  POST     `/admin/spawns`       Crear punto fijo
  POST     `/admin/zones`        Crear zona
  PATCH    `/admin/zones/{id}`   Modificar zona
  POST     `/admin/events`       Crear evento
  GET      `/admin/anti-cheat`   Consultar alertas

Todos los endpoints administrativos exigirán autenticación y
autorización específica.

## 12.2 Ejemplo de solicitud de recolección

``` json
{
  "spawn_id": "uuid-de-aparicion",
  "latitude": -2.170998,
  "longitude": -79.922359,
  "accuracy": 12,
  "client_timestamp": "2026-11-03T14:00:00Z"
}
```

La petición real deberá incluir una clave de idempotencia y una sesión
autenticada.

## 12.3 Ejemplo de respuesta

``` json
{
  "success": true,
  "collectible": {
    "symbol": "BTC",
    "rarity": "common"
  },
  "rewards": {
    "points": 10,
    "xp": 10
  },
  "player": {
    "total_points": 260,
    "total_xp": 260,
    "level": 2
  },
  "message": "¡Bitcoin encontrado!"
}
```

Los valores son ilustrativos. El backend calcula y devuelve los importes
reales; el cliente nunca puede elegir la recompensa.

------------------------------------------------------------------------

## 13. Autenticación e integración con Telegram

## 13.1 Bot y Mini App

El bot oficial es `@controller00068856bot`; la Mini App contendrá el juego.

Para habilitarla en BotFather:

1. Publica el frontend con un certificado HTTPS válido.
2. Abre `@BotFather`, selecciona el bot y configura su **Main Mini App** con
   la URL pública de la aplicación web, incluyendo su ruta
   publicada cuando corresponda (por ejemplo, `https://<dominio>/<ruta>/`).
   No uses aquí la URL del API.
3. Si se desea un botón permanente en el menú del chat, configura también
   `/setmenubutton` o **Bot Settings → Menu Button** con la misma URL HTTPS.
4. Prueba la Mini App desde Telegram. El dominio y la ruta deben corresponder
   a la publicación disponible.

El `homepage` actual de Create React App apunta a
`https://airpulsecorman-dev.github.io/cryptogo`. Configura esa URL en BotFather
solo si ese es el despliegue HTTPS que se usará; si se elige otro hosting o
dominio, usa la URL pública real de la Mini App.

El backend y el frontend deben usar orígenes HTTPS de producción. Configura
`CORS_ORIGINS` con el origen exacto del frontend (esquema, host y puerto, sin
ruta), y `REACT_APP_API_BASE_URL` con la URL HTTPS del API y su prefijo
`/api/v1`. La petición desde el navegador usa credenciales (`credentials: "include"`), por lo que CORS debe permitir explícitamente ese origen y las
credenciales; no uses `*`.

Mantén `TELEGRAM_BOT_TOKEN` únicamente en el entorno del backend o en un gestor
de secretos. No lo pongas en variables `REACT_APP_*`, en el bundle, en el
repositorio ni en logs. Si un token se comparte accidentalmente, revócalo y
genera uno nuevo en BotFather antes de continuar.

Para cookies, producción exige `SESSION_COOKIE_SECURE=true`. Usa
`SESSION_COOKIE_SAMESITE=lax` si el frontend y el API son del mismo sitio
(incluidos subdominios del mismo dominio registrable); usa `none` solamente si
son cross-site, siempre con HTTPS. Los navegadores pueden restringir cookies de
terceros en ese caso; se recomienda publicar frontend y API bajo el mismo
dominio registrable o servir el API mediante un proxy del mismo origen.

Funciones iniciales del bot:

- Comando `/start`.
- Mensaje de bienvenida.
- Botón para abrir Crypto Go.
- Enlace de invitación beta, cuando se habilite.
- Mensajes informativos de mantenimiento o eventos.

## 13.2 Validación de initData

El backend debe verificar criptográficamente los datos de inicialización
de Telegram utilizando el procedimiento oficial.

Reglas:

- Validar la firma en el servidor.
- Construir `data_check_string` con todos los campos recibidos excepto `hash`,
  ordenados por clave, y validar el HMAC-SHA-256 según la documentación oficial
  de [Telegram Mini Apps](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
- Verificar `auth_date` y rechazar datos antiguos según una ventana de
    validez definida.
- No utilizar `initDataUnsafe` como prueba de identidad.
- No confiar en un `telegram_id` enviado de manera independiente por
    el cliente.
- Rechazar campos repetidos y validar que el usuario firmado tenga un
  identificador entero positivo.
- No registrar el token del bot ni datos de autenticación en logs.
- Establecer una sesión aleatoria después de autenticar; persistir solo su hash,
  limitar su vigencia y revocarla al cerrar sesión.

El frontend envía `Telegram.WebApp.initData` a `POST /api/v1/auth/telegram`.
`initDataUnsafe` puede servir para mostrar información provisional en UI, pero
nunca para autenticar. Configura el secreto del bot como `TELEGRAM_BOT_TOKEN`
en el entorno del backend; el código no incluye un token por defecto.

La app actual permite la autenticación local `/api/v1/auth/dev` solo cuando
`APP_ENV=development` y `DEV_AUTH_ENABLED=true`. La ruta devuelve 404 en otros
entornos, incluida producción; la configuración de producción también rechaza
que ese interruptor esté habilitado.

## 13.3 Inicio de sesión con billeteras

El juego puede abrirse en un navegador normal y permite iniciar sesión sin
Telegram. Las opciones disponibles son:

- **EVM:** una billetera de navegador compatible con EIP-1193; el cliente
  solicita un reto al servidor y lo firma con `personal_sign`.
- **TON:** Telegram Wallet mediante TON Connect y `ton_proof`. El backend
  valida el reto, dominio, dirección, StateInit, firma y estado de la billetera
  usando TON Center. Solo se admiten billeteras Telegram Wallet verificables.

Ambos métodos crean o recuperan una cuenta independiente. No vinculan una
identidad de billetera con una cuenta de Telegram ni ejecutan transacciones.
Tras una autenticación exitosa se usa la misma sesión de aplicación mediante
cookie HttpOnly.

Configura `public/tonconnect-manifest.json` con la URL HTTPS pública del
frontend antes del despliegue. El backend usa TON Center para validar TON;
`TONCENTER_API_URL`, `TONCENTER_TESTNET_API_URL` y `TONCENTER_API_KEY` permiten
configurar los proveedores para cada red. La verificación TON requiere acceso
al proveedor configurado; no se puede completar si está indisponible. Antes de
desplegar el backend, aplica las migraciones desde `backend/` con
`python -m alembic upgrade head`.

## 13.4 Sesiones

La implementación podrá usar cookies seguras o tokens de sesión. Si
utiliza cookies:

- `HttpOnly`.
- `Secure`.
- `SameSite` adecuado.
- Protección CSRF cuando corresponda.
- Caducidad y revocación.

La configuración final debe probarse en los clientes oficiales de
Telegram y en los navegadores compatibles.

## 13.5 Ubicación en Telegram

Se utilizará Telegram Web Apps SDK y su `LocationManager` cuando esté
disponible. Se podrá implementar una alternativa mediante la Geolocation
API del navegador.

La aplicación solicitará permiso cuando el usuario quiera utilizar el
mapa o recoger un objeto. No realizará seguimiento continuo en segundo
plano.

------------------------------------------------------------------------

## 14. Geolocalización y recolección

## 14.1 Radio inicial

Radio inicial de prueba: **35 metros**.

No es una garantía de precisión. Se deberá ajustar con pruebas reales en
diferentes teléfonos, entornos urbanos y condiciones de señal.

## 14.2 Datos de ubicación

El cliente puede enviar:

- Latitud.
- Longitud.
- Precisión horizontal reportada.
- Marca temporal de la lectura.
- Identificador de aparición.
- Clave de idempotencia.

El backend debe validar rangos, antigüedad, coherencia y permisos. Una
marca temporal enviada por el cliente no es prueba confiable por sí
sola.

## 14.3 Protocolo de recolección

1. Recibir solicitud autenticada.
2. Validar formato y límites.
3. Recuperar la aparición.
4. Verificar que esté disponible y no haya expirado.
5. Validar zona y geocerca.
6. Calcular distancia en el servidor.
7. Evaluar precisión y señales antitrampas.
8. Iniciar transacción.
9. Bloquear la aparición para evitar concurrencia.
10. Verificar nuevamente disponibilidad.
11. Insertar la colección.
12. Insertar movimientos de puntos y XP.
13. Actualizar perfil y misiones.
14. Marcar la aparición como recogida.
15. Confirmar la transacción.
16. Devolver resultado.

Si cualquier operación crítica falla, la transacción debe revertirse.

## 14.4 Concurrencia e idempotencia

Si dos usuarios intentan recoger la misma aparición al mismo tiempo,
solo uno podrá obtenerla.

Se utilizarán bloqueos de fila, restricciones únicas y transacciones de
base de datos. Una solicitud repetida con la misma clave de idempotencia
no debe volver a acreditar recompensas.

## 14.5 Limitaciones del GPS

Una Mini App web no puede garantizar que una coordenada provenga de un
sensor GPS auténtico. Las señales de ubicación pueden ser manipuladas.

Las medidas antitrampas reducen el fraude, pero no lo eliminan por
completo.

------------------------------------------------------------------------

## 15. Seguridad y prevención de trampas

La seguridad debe implementarse desde las primeras fases.

## 15.1 Controles

- Verificación de identidad Telegram.
- Validación de sesión.
- Rate limiting.
- Validación de coordenadas.
- Cálculo de distancia en backend.
- Detección de desplazamientos físicamente imposibles.
- Control de frecuencia de recolección.
- Detección de patrones anómalos.
- Restricciones por geocerca.
- Protección frente a solicitudes duplicadas.
- Auditoría de acciones administrativas.
- Backups y recuperación.
- Gestión segura de secretos.

## 15.2 Señales antitrampas

Se pueden evaluar:

- Precisión de ubicación excesivamente baja.
- Saltos geográficos incompatibles con el tiempo transcurrido.
- Recolecciones demasiado frecuentes.
- Solicitudes repetidas.
- Uso de coordenadas idénticas de manera anómala.
- Inconsistencias entre ubicación y zona.

No se debe banear automáticamente por una sola señal. Las anomalías
pueden deberse a GPS impreciso, conectividad o características del
dispositivo.

## 15.3 Respuesta ante anomalías

Estados sugeridos:

- Normal.
- Revisión.
- Recolección rechazada.
- Cuenta temporalmente limitada.
- Cuenta suspendida tras revisión.

Cada decisión sensible debe dejar registro auditable.

------------------------------------------------------------------------

## 16. Privacidad, seguridad física y cumplimiento

La ubicación geográfica es información sensible desde el punto de vista
de la privacidad. El proyecto deberá aplicar minimización de datos y
protección desde el diseño.

## 16.1 Privacidad

- Solicitar ubicación solo cuando sea necesaria.
- Explicar para qué se usa.
- No rastrear en segundo plano.
- No publicar la ubicación precisa del jugador.
- No conservar recorridos GPS completos si no son necesarios.
- Definir periodos de retención.
- Restringir el acceso administrativo.
- Proteger datos en tránsito y en reposo.
- Facilitar el ejercicio de derechos aplicables.

Antes de la beta debe existir una política de privacidad clara y un
procedimiento para solicitudes de acceso o eliminación de datos.

## 16.2 Seguridad física

- No incentivar correr ni ingresar a lugares peligrosos.
- No colocar objetos en vías rápidas.
- No usar propiedades privadas sin autorización.
- No crear objetivos que exijan entrar a instalaciones restringidas.
- No exigir desplazamientos nocturnos.
- Utilizar horarios y geocercas cuando corresponda.
- Mostrar recordatorios para prestar atención al entorno y no jugar
    mientras se conduce.
- Permitir bloquear inmediatamente una zona insegura.

## 16.3 Ecuador

Antes de operar la beta se debe revisar la normativa ecuatoriana
aplicable, incluyendo la Ley Orgánica de Protección de Datos Personales
y sus disposiciones relacionadas, así como las obligaciones que
correspondan al tratamiento de ubicación y datos de usuarios.

La beta debe contar con términos de uso, política de privacidad, reglas
de comunidad y un canal de contacto.

Los puntos serán exclusivamente elementos virtuales de juego. Si en el
futuro se incorporan premios reales, activos digitales, pagos o canjes,
se requerirá un análisis legal y regulatorio independiente antes de
implementar esas funciones.

------------------------------------------------------------------------

## 17. Panel administrativo

El panel administrativo permitirá controlar el mundo de juego.

## 17.1 Funciones

- Consultar usuarios registrados.
- Consultar actividad y estadísticas.
- Crear y editar puntos fijos.
- Crear y editar zonas.
- Aprobar, pausar o bloquear zonas.
- Configurar densidad de apariciones.
- Configurar rarezas y recompensas.
- Crear misiones y eventos.
- Consultar alertas antitrampas.
- Moderar cuentas.
- Consultar movimientos de puntos.
- Consultar historial de acciones administrativas.

## 17.2 Seguridad administrativa

- Roles y permisos.
- Acceso restringido.
- Autenticación reforzada.
- Registro de acciones.
- Confirmación para operaciones destructivas.
- Separación entre administrador y jugador.
- Ninguna acción de administración debe modificar saldos sin generar
    un movimiento auditable.

------------------------------------------------------------------------

## 18. Infraestructura y despliegue

## 18.1 Entornos

  Entorno       Uso
  ------------- -------------------------------------
  Development   Desarrollo local
  Staging       Pruebas de integración y aceptación
  Production    Beta privada

Cada entorno tendrá sus propias credenciales, base de datos y
configuración.

## 18.2 Servicios

  Servicio             Implementación inicial
  -------------------- ----------------------------------------------
  Frontend             Hosting compatible con Next.js
  API                  VPS con Docker
  PostgreSQL/PostGIS   Servicio administrado o contenedor protegido
  Redis                Contenedor privado
  Workers              Contenedores independientes
  Proxy                Nginx o equivalente
  HTTPS                Certificados válidos
  Backups              Copias automáticas cifradas
  Logs                 Registro centralizado

## 18.3 Docker

El entorno local debe permitir levantar:

- API.
- PostgreSQL con PostGIS.
- Redis.
- Worker.
- Servicios auxiliares necesarios.

El frontend puede ejecutarse localmente con el gestor de paquetes
elegido.

## 18.4 Backups

- Copias automáticas de base de datos.
- Retención definida.
- Almacenamiento separado del servidor principal.
- Cifrado.
- Pruebas periódicas de restauración.
- Procedimiento documentado de recuperación.

## 18.5 Observabilidad

Registrar:

- Errores de API.
- Latencia.
- Fallos de autenticación.
- Errores de base de datos.
- Fallos de workers.
- Recolecciones aceptadas y rechazadas.
- Alertas antitrampas.
- Estado de los backups.

No registrar tokens, contraseñas, coordenadas precisas ni datos
personales innecesarios en logs.

------------------------------------------------------------------------

## 19. Configuración del entorno

El archivo raíz `.env.example` contiene las variables de configuración local
de esta implementación y no incluye credenciales reales. Para iniciar el
entorno se requiere Docker Compose y ejecutar los pasos descritos después del
bloque heredado de referencia.

``` dotenv
APP_ENV=development
APP_NAME=Crypto Go
APP_URL=https://example.com
API_BASE_URL=https://api.example.com

TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
TELEGRAM_WEBAPP_URL=

DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/crypto_Go
REDIS_URL=redis://localhost:6379/0

SESSION_SECRET=
CORS_ORIGINS=

MAP_STYLE_URL=
MAP_PROVIDER_API_KEY=

SPAWN_ENGINE_ENABLED=false
DEFAULT_COLLECTION_RADIUS_METERS=35
DEFAULT_LOCATION_MAX_AGE_SECONDS=60

LOG_LEVEL=INFO
```

Los valores son ilustrativos. La configuración definitiva debe validar
las variables obligatorias y fallar de manera segura si falta un
secreto.

Ese bloque es una referencia heredada y no es la configuración activa. No
subir `.env` al repositorio.

### Entorno local implementado

1. Copia el `.env.example` de la raíz a `.env` y sustituye
   `POSTGRES_PASSWORD`.
2. Ejecuta `docker compose up --build`. El API aplica las migraciones al
   arrancar y expone `/api/v1`; PostgreSQL usa PostGIS y Redis controla el
   límite de solicitudes.
3. Ejecuta `yarn start` o `npm start`. La configuración local apunta a
   `http://localhost:8000/api/v1`; el acceso de desarrollo aparece solo si
   `REACT_APP_ENABLE_DEV_AUTH=true` y el API tiene `APP_ENV=development` más
   `DEV_AUTH_ENABLED=true`.
4. Para probar recolección, primero registra una zona GeoJSON segura,
   verificada y de acceso público desde `backend/`, y crea un punto dentro de
   ella con `python -m app.cli create-zone` y
   `python -m app.cli create-spawn`. Los comandos requieren coordenadas reales
   y una zona habilitada. Los puntos `--dynamic` se generan por el worker;
   los fijos crean una aparición al provisionarse.
5. Si se usa Telegram, configura `TELEGRAM_BOT_TOKEN` fuera del repositorio y
   registra el dominio HTTPS de la Mini App con el bot.

`docker-compose.yml` no proporciona ubicaciones de juego iniciales. Sin una
zona y un punto aprobados, el mapa real se muestra sin coleccionables, no con
un resultado ficticio.

### Producción

Configura `APP_ENV=production`, `TELEGRAM_BOT_TOKEN`,
`SESSION_COOKIE_SECURE=true`, `SESSION_COOKIE_SAMESITE=none` si el frontend y
el API son cross-site, y `CORS_ORIGINS` con los dominios HTTPS exactos. El API
rechaza el login de desarrollo en producción. El frontend necesita
`REACT_APP_API_BASE_URL` en el momento de compilar; si falta, informa que no
hay API configurada. GitHub Pages es hosting estático: para sesiones con
cookies, usa dominios compatibles con las políticas de cookies de terceros o
un frontend/API bajo el mismo sitio.

------------------------------------------------------------------------

## 20. Pruebas y criterios de aceptación

## 20.1 Pruebas unitarias

- Verificación de initData.
- Cálculo de distancia.
- Cálculo de niveles.
- Cálculo de recompensas.
- Expiración de apariciones.
- Validación de misiones.
- Reglas de rareza.
- Validación de geocercas.

## 20.2 Pruebas de integración

- Registro de usuario.
- Consulta de mapa.
- Recolección válida.
- Recolección fuera de radio.
- Recolección de objeto expirado.
- Recolección duplicada.
- Acreditación de puntos.
- Actualización de misiones.
- Consulta de inventario.
- Ranking.
- Administración de zonas.

## 20.3 Pruebas de concurrencia

Simular al menos 20 usuarios intentando recoger simultáneamente la misma
aparición. Solo una operación debe confirmarse.

También se probarán solicitudes duplicadas y reintentos después de
pérdida de conexión.

## 20.4 Pruebas de dispositivos

- Telegram Android.
- Telegram iOS.
- Telegram Desktop, con limitaciones de ubicación documentadas.
- Navegadores móviles compatibles.

La experiencia principal de recolección debe probarse en teléfonos
reales.

## 20.5 Criterios de aceptación del MVP

  Área            Criterio
  --------------- ------------------------------------------------
  Autenticación   Identidad verificada en servidor
  Mapa            Objetos visibles en zonas activas
  GPS             Permiso solicitado correctamente
  Recolección     Radio validado en backend
  Duplicados      Una sola recompensa por aparición
  Economía        Movimientos auditables
  Inventario      Colección correcta
  Misiones        Progreso consistente
  Ranking         Orden y periodo correctos
  Anticheat       Manipulaciones básicas detectadas o rechazadas
  Privacidad      Sin seguimiento continuo innecesario
  Recuperación    Backup restaurable

## 20.6 Pruebas de campo

Antes de ampliar la beta:

- Verificar puntos fijos físicamente.
- Comprobar accesibilidad pública.
- Probar GPS en diferentes dispositivos.
- Medir precisión en zonas abiertas y urbanas.
- Revisar densidad y distribución.
- Evaluar si el radio de recolección es razonable.
- Recoger comentarios de los participantes.

------------------------------------------------------------------------

## 21. Plan de implementación

Plan de referencia de ocho semanas para una persona con dedicación
importante o un equipo pequeño. El plazo real dependerá de la
experiencia, disponibilidad, alcance final y resultados de pruebas.

## CH-001 --- Fundamentos (Semana 1)

- Crear repositorio.
- Definir estructura.
- Configurar Git.
- Configurar Docker.
- Levantar PostgreSQL/PostGIS.
- Levantar Redis.
- Inicializar Next.js.
- Inicializar FastAPI.
- Crear documentación de arquitectura.
- Configurar entornos.

**Entregable:** proyecto ejecutable localmente y estructura base.

## CH-002 --- Autenticación (Semana 2)

- Crear bot.
- Configurar Mini App.
- Integrar Telegram Web Apps SDK.
- Validar initData.
- Crear sesiones.
- Registrar usuarios.
- Crear perfiles.
- Implementar permisos básicos.

**Entregable:** usuario autenticado y perfil consultable.

## CH-003 --- Mapa (Semana 3)

- Integrar MapLibre.
- Configurar proveedor cartográfico.
- Solicitar ubicación.
- Mostrar posición.
- Crear modelo de zonas.
- Crear consultas geográficas.
- Mostrar objetos cercanos.

**Entregable:** mapa funcional con objetos de prueba.

## CH-004 --- Motor geográfico (Semana 4)

- Crear puntos fijos.
- Crear apariciones dinámicas.
- Implementar geocercas.
- Configurar densidad.
- Implementar expiración.
- Crear herramientas administrativas básicas.

**Entregable:** monedas distribuidas por el servidor.

## CH-005 --- Recolección y economía (Semana 5)

- Validar distancia.
- Implementar idempotencia.
- Implementar bloqueo de apariciones.
- Crear colecciones.
- Crear movimientos de puntos.
- Actualizar XP y niveles.
- Crear inventario.
- Añadir controles antitrampas iniciales.

**Entregable:** ciclo completo de búsqueda y recompensa.

## CH-006 --- Gamificación (Semana 6)

- Misiones diarias.
- Progreso de misiones.
- Logros.
- Ranking.
- Notificaciones.
- Animaciones.
- Compartir descubrimientos.

**Entregable:** experiencia de juego completa del MVP.

## CH-007 --- Administración y pruebas (Semana 7)

- Dashboard.
- Configuración de zonas.
- Gestión de apariciones.
- Gestión de rarezas.
- Auditoría.
- Pruebas de concurrencia.
- Pruebas de seguridad.
- Pruebas de dispositivos.

**Entregable:** sistema listo para beta controlada.

## CH-008 --- Beta privada (Semana 8)

- Despliegue de producción.
- Configuración de dominio y HTTPS.
- Habilitación de zonas piloto.
- Invitación de usuarios.
- Monitoreo.
- Corrección de errores.
- Evaluación de métricas.

**Entregable:** primera beta privada operativa.

------------------------------------------------------------------------

## 22. Métricas de la beta

No se debe medir el éxito únicamente por registros.

Indicadores principales:

  Métrica                     Qué mide
  --------------------------- ----------------------------------------
  DAU                         Usuarios activos diarios
  MAU                         Usuarios activos mensuales
  Retención D1                Regreso al día siguiente
  Retención D7                Regreso después de siete días
  Retención D30               Regreso después de treinta días
  Primera recolección         Usuarios que completan el primer ciclo
  Recolecciones por usuario   Actividad de juego
  Misiones completadas        Participación
  Invitaciones                Crecimiento orgánico
  Rechazos antitrampas        Calidad y posibles falsos positivos
  Errores                     Estabilidad

Los objetivos numéricos de retención y actividad se definirán después de
obtener una línea base con usuarios reales. No deben inventarse metas de
éxito sin datos.

------------------------------------------------------------------------

## 23. Presupuesto orientativo

Estimación inicial de infraestructura para una beta pequeña:

  Concepto                                             Estimación mensual
  ---------------------------------------- ------------------------------
  VPS                                                          USD 10--25
  Base de datos/almacenamiento adicional                        USD 0--15
  Redis adicional                                                USD 0--5
  Mapas                                            USD 0--20 inicialmente
  Dominio                                    USD 1--2 equivalente mensual

**Rango orientativo:** aproximadamente USD 15--40 al mes, dependiendo de
los proveedores, consumo, almacenamiento y arquitectura elegida.

No incluye:

- Tiempo de desarrollo.
- Diseño e identidad de marca.
- Servicios profesionales.
- Costos legales.
- Impuestos.
- Crecimiento de tráfico.
- Herramientas comerciales opcionales.

Antes de contratar un proveedor se deben revisar sus precios, límites,
políticas y condiciones vigentes.

------------------------------------------------------------------------

## 24. Riesgos y mitigaciones

  -----------------------------------------------------------------------
  Riesgo                              Mitigación
  ----------------------------------- -----------------------------------
  GPS manipulado                      Señales antitrampas y validación de
                                      servidor

  GPS impreciso                       Umbrales configurables y mensajes
                                      claros

  Recompensas duplicadas              Transacciones, bloqueos e
                                      idempotencia

  Ubicación peligrosa                 Geocercas y aprobación manual

  Baja actividad                      Misiones, eventos y balance

  Costos cartográficos                Proveedor adecuado y límites de
                                      consumo

  Filtración de coordenadas           Ubicaciones aproximadas y consultas
                                      controladas

  Exposición de datos                 Minimización, permisos y cifrado

  Fraude en rankings                  Auditoría y reglas de clasificación

  Caídas del servidor                 Monitoreo, backups y recuperación

Dependencia de Telegram             Separación entre lógica de juego y
                                      capa de presentación
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 25. Decisiones pendientes

Estas decisiones no bloquean el diseño general, pero deben resolverse
antes de las fases correspondientes.

  Decisión                            Estado
  ----------------------------------- -------------------------------------
  Ciudad o ciudades piloto exactas    Pendiente
  Puntos fijos concretos              Pendiente de inspección
  Proveedor cartográfico              Pendiente de evaluación
  Dominio oficial                     Pendiente
  Hosting definitivo                  Pendiente
  Diseño gráfico final                Pendiente
  Radio definitivo de recolección     Pendiente de pruebas
  Frecuencia de aparición             Pendiente de balance
  Retención de datos GPS              Pendiente de política de privacidad
  Reglas de ranking                   Pendiente de implementación
  Términos y política de privacidad   Pendiente de revisión

La ciudad inicial de operación no cambia la decisión de cobertura
nacional: Ecuador sigue siendo el territorio objetivo, con activación
progresiva de zonas.

------------------------------------------------------------------------

## 26. Definición de terminado

Una funcionalidad no se considerará terminada solo porque funcione
visualmente.

Debe cumplir:

1. Implementación en la capa correspondiente.
2. Validación de datos.
3. Autorización en servidor cuando corresponda.
4. Manejo de errores.
5. Pruebas automatizadas.
6. Pruebas de integración si afectan otros módulos.
7. Documentación actualizada.
8. Logs sin datos sensibles.
9. Revisión de seguridad.
10. Aceptación funcional.

Una versión se considera lista para beta cuando los criterios de
aceptación del MVP se hayan superado y exista un procedimiento de
recuperación y soporte.

------------------------------------------------------------------------

## 27. Glosario

  -----------------------------------------------------------------------
  Término                             Significado
  ----------------------------------- -----------------------------------
  Mini App                            Aplicación web que se ejecuta
                                      dentro de Telegram

  XP                                  Experiencia acumulada del jugador

  Spawn                               Aparición de un objeto en el mundo
                                      del juego

  Spawn point                         Punto geográfico de aparición

  Geocerca                            Límite geográfico que define una
                                      zona

  PostGIS                             Extensión geográfica de PostgreSQL

  H3                                  Sistema de indexación geográfica
                                      basado en celdas hexagonales

  Idempotencia                        Garantía de que repetir una
                                      operación no duplica su efecto

  Anticheat                           Sistema de detección y prevención
                                      de trampas

  Worker                              Proceso que ejecuta tareas en
                                      segundo plano

  DAU                                 Usuarios activos diarios

  MAU                                 Usuarios activos mensuales

  MVP                                 Producto mínimo viable

Beta privada                        Prueba con un grupo limitado de
                                      usuarios
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 28. Referencias oficiales

Consultar la documentación vigente antes de implementar cada
integración:

- [Telegram Mini Apps](https://core.telegram.org/bots/webapps)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Telegram Web Apps SDK](https://core.telegram.org/bots/webapps)
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev/)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostGIS Documentation](https://postgis.net/documentation/)
- [Redis Documentation](https://redis.io/docs/latest/)
- [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/)
- [OpenStreetMap Copyright and
    License](https://www.openstreetmap.org/copyright)
- [H3 Documentation](https://h3geo.org/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Ecuador --- Superintendencia de Protección de Datos
    Personales](https://www.spdp.gob.ec/)

------------------------------------------------------------------------

## Próximo paso: CH-001

Una vez creado el repositorio, el primer objetivo será preparar el
entorno de desarrollo y verificar que todos los servicios base arranquen
correctamente.

**No se debe comenzar implementando el mapa, el motor de apariciones o
las recompensas antes de contar con una estructura funcional,
configuración segura y base de datos preparada.**

------------------------------------------------------------------------

*Crypto Go --- Go. Collect. Level Up.*\
*Documento de especificación técnica y planificación. Versión 1.0.*
