# HubGH Shell – Fase 2 (Home Feed real)

## Resumen de implementación

En esta fase se integró el Home Feed real al App Shell existente, eliminando fallback demo para feed/home y manteniendo contrato backend listo para siguientes fases.

### Incluye

- Feed real desde `GH Post` (publicado, vigente, filtrado por audiencia de roles).
- Respuesta vacía explícita cuando no hay publicaciones visibles.
- Columna derecha en Home con widgets:
  - Alertas personales (fuente no configurada -> vacío explícito, no demo).
  - Cumpleaños próximos (fuente real desde `Datos Contratacion.fecha_nacimiento`).
  - Cursos LMS pendientes (real si LMS existe; vacío explícito si no está disponible).
  - Completitud de perfil (real con `Ficha Empleado` + `Datos Contratacion`).

## Validación manual breve

1. Ingresar con usuario HubGH y abrir `/app/hubgh_shell`.
2. Confirmar que en Home aparece sección **Home Feed** y columna derecha con 4 widgets.
3. Verificar feed vacío controlado cuando no hay `GH Post` vigentes/audiencia.
4. Crear/editar un `GH Post` publicado para el rol del usuario y confirmar que aparece sin datos demo.
5. Confirmar en widget LMS:
   - mensaje de no disponibilidad cuando tablas LMS no existan,
   - o cursos pendientes reales cuando sí existan.
6. Confirmar en widget de perfil que el porcentaje cambia según datos reales de `Ficha Empleado`/`Datos Contratacion`.

## Pruebas básicas ejecutadas

- `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_feed_api`
- Resultado esperado: OK (3 pruebas):
  - feed sin fallback demo en vacío,
  - feed real con `GH Post`,
  - contrato Home Feed Fase 2 con widgets y meta.

