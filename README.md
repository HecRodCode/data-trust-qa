# DataTrust QA

Laboratorio de QA de datos para practicar carga, perfilado y reconciliación entre dos sistemas simulados con PostgreSQL y SQL. Usa datos completamente sintéticos.

## Arquitectura

- `source_a`: conjunto de referencia relacional.
- `landing_b`: registros recibidos por B en formato crudo JSONB.
- `source_b`: registros de B aceptados y transformados al modelo relacional.

El flujo actual carga los CSV de A en `source_a` y el lote crudo de B en `landing_b`. Un comando separado procesa el lote pendiente hacia `source_b`.

La población predeterminada contiene 25.000 registros por sistema: 4.000 clientes, 6.000 cuentas, 12.000 pagos y 3.000 saldos. El modelo y las reglas de negocio todavía son propuestas de trabajo.

## Estructura del proyecto

```text
data-trust-qa/
├── database/schemas/       # Esquemas PostgreSQL
├── generator/src/
│   └── data_trust_qa/
│       ├── commands/       # Entradas de línea de comandos
│       ├── config/         # Configuración local
│       ├── database/       # Bootstrap y procesamiento de B
│       ├── domain/         # Modelos de datos
│       └── generation/     # Generación y exportación CSV
├── generator/tests/        # Pruebas automatizadas
├── data/generated/         # Archivos generados; excluidos de Git
├── sql/                    # Consultas de perfilado y reconciliación
└── qa/                     # Casos de prueba y resultados
```

## Requisitos

- Python 3.13.12
- [`uv`](https://docs.astral.sh/uv/)
- PostgreSQL y `psql` para cargar o procesar datos

## Preparación

Desde la raíz del repositorio:

```bash
uv sync --frozen
cp -n .env.example .env
```

`uv sync --frozen` crea `.venv` e instala las dependencias de `uv.lock`. Los comandos `uv run` usan ese entorno sin activarlo manualmente.

La configuración local se carga desde `.env` con `python-dotenv`. El archivo no se versiona. Para la contraseña de PostgreSQL, se recomienda usar `.pgpass`.

## Comandos

**Generar los archivos predeterminados:**

```bash
uv run data-trust-generate
```

Escribe las tablas CSV de A y el lote CSV de B en `data/generated/seed-20261110/`.

**Generar una muestra pequeña:**

```bash
uv run data-trust-generate --customers 8 --accounts 12 --payments 24 --balances 16
```

**Ejecutar las pruebas:**

```bash
uv run python -m unittest discover -s generator/tests
```

**Ver el plan de carga sin conectarse a PostgreSQL:**

```bash
uv run data-trust-bootstrap
```

**Cargar A y el lote crudo de B:**

```bash
uv run data-trust-bootstrap --load
```

Carga los CSV relacionales de A en `source_a` y los registros recibidos de B en `landing_b`. No carga `source_b`. Reutiliza esquemas completos existentes, pero exige que las tablas de destino estén vacías para evitar duplicados. Si encuentra tablas con datos o esquemas incompletos, se detiene sin cargar.

**Procesar un lote pendiente de B hacia `source_b`:**

```bash
uv run data-trust-process-b --batch-reference BATCH-0001
```

Transforma clientes, cuentas, pagos y saldos en ese orden. Si la operación falla, la transacción se revierte. Esta versión procesa los registros sintéticos estructuralmente válidos; todavía no aplica reglas de negocio ni rechaza filas individualmente.

## Base de datos local

Si todavía no existen el rol y la base del proyecto:

```bash
sudo -u postgres createuser --pwprompt datatrust_qa
sudo -u postgres createdb --owner=datatrust_qa datatrust_qa
```

Configura `PGHOST`, `PGPORT`, `PGDATABASE` y `PGUSER` en `.env` según tu instalación local. Los esquemas se crean mediante el comando de bootstrap cuando faltan.

Para más contexto de aprendizaje y la ruta de trabajo, consulta [docs/CONTEXT.md](docs/CONTEXT.md).
