# Guía de Pruebas de Usuario — Sprint 3 y Sprint 4

## Objetivo

Dar una guía visual/funcional de qué debe probar un usuario final por sprint, por rol y por escenario, para validar que la experiencia operativa está correcta sin enfocarse en detalle técnico interno.

Referencias:

- [`HubGH Wave 3 Design`](./hubgh-wave-3-design.md)
- [`HubGH Wave 4 Design`](./hubgh-wave-4-design.md)
- [`Guía diseño bandejas`](../plans/guia-diseno-bandejas-operativas.md)

---

## Sprint 3 (Persona 360 v2) — Qué testear como usuario

### 1) Checklist rápido visual

- [ ] La página carga sin errores y muestra bloques esperados (info + timeline).
- [ ] El timeline muestra eventos ordenados por fecha descendente.
- [ ] El color/tipo del evento es entendible (Novedad, SST, Disciplinario, Bienestar, Ingreso).
- [ ] No se rompen textos ni tarjetas en resoluciones comunes (laptop estándar).

### 2) Flujos funcionales por rol

#### Rol GH / RRLL
- Entrar a Persona 360 de un empleado activo.
- Verificar que puede ver historial completo según permisos.
- Confirmar que evento de ingreso (si existe) aparece en timeline.

#### Rol SST
- Entrar a Persona 360.
- Confirmar visibilidad de contexto SST y consistencia de indicadores de alertas/radar.

#### Rol Jefe de punto
- Entrar a colaborador de su PDV.
- Verificar que accede solo a su alcance operativo.

#### Rol Empleado
- Entrar a su propia Persona 360.
- Verificar que no ve información restringida (disciplinaria/sensible) fuera de su alcance.

### 3) Casos de validación recomendados

1. **Timeline con múltiples fuentes**
   - Debe mezclar eventos de varias fuentes sin duplicados confusos.
2. **Datos sensibles**
   - Deben ocultarse para roles no autorizados.
3. **Evento ingreso**
   - Si existe evento desde contratación, debe verse como hito claro.

### 4) Señales de falla para reportar

- Pantalla en blanco/error al abrir Persona 360.
- Eventos fuera de orden o sin fecha.
- Usuario ve datos que no debería ver por rol.
- Desaparición de bloques que antes existían.

---

## Sprint 4 (Punto 360 v2) — Qué testear como usuario

### 1) Checklist rápido visual

- [ ] La cabecera del punto muestra nombre/zona/planta.
- [ ] KPIs cargan sin quedarse en cero incorrectamente.
- [ ] Listados (novedades, disciplinarios, SST, feedback) renderizan sin romper layout.
- [ ] Badges/estados mantienen consistencia visual operativa.

### 2) Flujos funcionales por rol

#### Rol GH / RRLL / SST
- Abrir Punto 360 de al menos 2 PDV distintos.
- Validar que KPIs coinciden con datos esperados del punto.
- Confirmar que novedades activas y alertas son consistentes.

#### Rol Jefe de punto
- Abrir su PDV.
- Confirmar que no accede a PDV no autorizados.
- Verificar que headcount activo del punto es razonable.

### 3) Casos de validación recomendados

1. **Headcount activo**
   - Debe considerar solo empleados activos.
2. **Novedades activas**
   - Deben respetar estados operativos definidos.
3. **KPI de ingresos formalizados (si aplica)**
   - Debe reflejar eventos recientes sin afectar KPIs legacy.

### 4) Señales de falla para reportar

- KPIs no cargan o muestran valores imposibles.
- Conteos inconsistentes entre vistas del mismo punto.
- Filtros/permisos permiten acceso a punto no autorizado.
- Navegación punto→persona falla o lleva a registro incorrecto.

---

## Formato de reporte sugerido para usuario

Usar este formato por incidencia:

1. Sprint: (3 o 4)
2. Pantalla: (Persona 360 / Punto 360)
3. Rol con el que probó
4. Pasos exactos
5. Resultado esperado
6. Resultado actual
7. Evidencia (captura/video)
8. Severidad (Alta/Media/Baja)

