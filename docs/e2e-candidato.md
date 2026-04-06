# E2E candidato

Este flujo valida de punta a punta:

1. onboarding público en `/candidato`
2. captura de credenciales generadas
3. login del candidato
4. apertura de `mis_documentos_candidato`
5. carga de un PDF

## Requisitos

- aplicación disponible en `http://localhost` o definir `HUBGH_BASE_URL`
- backend migrado
- dependencias de Playwright instaladas

## Instalación

```bash
make e2e-install
```

## Ejecución

```bash
make e2e-candidato
```

## Variables útiles

- `HUBGH_BASE_URL` — cambia la URL base, por ejemplo `http://127.0.0.1`
- `HUBGH_E2E_HEADLESS=0` — corre Firefox visible
- `HUBGH_E2E_UPLOAD_FILE=/ruta/archivo.pdf` — fuerza el archivo a subir

Si no definís `HUBGH_E2E_UPLOAD_FILE`, la prueba intenta usar:

1. `~/Documents/RUT 2026 (Clave 901422345).pdf`
2. `tests/fixtures/sample-upload.pdf`

## Archivo de prueba por defecto

Se incluye `tests/fixtures/sample-upload.pdf` para que el flujo sea repetible también en despliegues limpios y no dependa de archivos manuales del operador.
