# 📘 Proyecto: Hub de Información de Gestión Humana (HubGH) - Roadmap

## 1. Contexto y Objetivos
**Objetivo MVP:** Crear un sistema centralizado de información de GH (HubGH) sobre Frappe Framework.

## 2. Estado del Proyecto
- [x] **Configuración de Entorno**
    - [x] Verificar instalación de Frappe y Bench
    - [x] Crear App `hubgh`
    - [x] Instalar App en el sitio

- [x] **Modelado de Datos (DocTypes)**
    - [x] **Punto de Venta** (Entidad base)
    - [x] **Empleado** (Entidad base)
    - [x] **Novedades Laborales** (Incapacidades, licencias, vacaciones, abandono)
    - [x] **Casos Disciplinarios**
    - [x] **Casos SST**
    - [x] **Feedback / Bienestar**
    - [x] **Renuncias y Vacantes**

- [ ] **Vistas 360**
    - [x] **Vista Punto 360** (Dashboard por Punto de Venta)
        - [x] Estructura Page (JS/Py)
        - [x] Lógica de Backend (KPIs y Tablas)
        - [x] Corrección de assets y sidebar
    - [ ] **Vista Persona 360** (Dashboard por Empleado)
        - [ ] Crear Page `persona_360`
        - [ ] Backend: Obtener historial completo (Novedades, Disciplinarios, SST)
        - [ ] Frontend: Ficha resumen del empleado (Foto, Cargo, Estado)
        - [ ] Frontend: Línea de tiempo (Timeline) de eventos

- [ ] **Importación de Datos**
    - [ ] **Plantillas Excel:**
        - [ ] Diseñar plantilla Maestra de Empleados
        - [ ] Diseñar plantilla de Novedades
    - [ ] **Data Import Tool:**
        - [ ] Validar mapeo de columnas (CSV -> DocType)
        - [ ] Prueba de carga masiva (100+ registros)
    - [ ] **Scripts de Limpieza:** (Opcional) Script para normalizar nombres/cédulas.

- [ ] **Infraestructura & Despliegue**
    - [ ] **Preparación Producción:**
        - [ ] Script de "setup inicial" para servidor limpio
        - [ ] Configuración de Nginx/Certbot (SSL)
    - [ ] **Backup & Restore:**
        - [ ] Configurar backups automáticos (S3/Dropbox)
        - [ ] Documentar proceso de restauración ante desastres

- [ ] **Infraestructura**
    - [ ] Configuración para despliegue (Futuro)

## 3. Notas
- Stack: Frappe Framework + Docker
- Enfoque: MVP local primero
