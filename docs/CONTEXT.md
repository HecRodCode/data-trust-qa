# DataTrust QA — contexto del proyecto

## Propósito

Este repositorio es un laboratorio de aprendizaje para prepararnos para una entrevista de Analista QA / Datos Jr Plus. El objetivo es entender y poder explicar cómo se valida la calidad de datos y cómo se comparan dos fuentes, principalmente con SQL y PostgreSQL. Python será una herramienta auxiliar, no el foco.

El escenario será ficticio: un **Sistema A** envía información financiera y un **Sistema B** la recibe. Practicaremos cómo comprobar que los registros esperados llegaron, que sus valores y relaciones son coherentes y cómo documentar diferencias. No representa procesos ni datos reales de ninguna empresa.

## Cómo vamos a trabajar

- Avanzaremos por partes, en orden y al ritmo necesario para entender cada concepto.
- En cada paso se explicará qué haremos, por qué importa para QA o SQL y qué resultado buscamos; las indicaciones deben ser concretas, no genéricas.
- Se distinguirán las decisiones confirmadas de las propuestas pendientes. No se dará por definitiva una tabla, regla o arquitectura hasta revisarla.
- No se generarán consultas SQL, código ni soluciones completas salvo que el usuario lo pida explícitamente. Se pueden explicar conceptos y plantear ejercicios sin resolverlos.
- No se saltará a grandes volúmenes, optimización ni tecnologías adicionales antes de tener claros el problema, las reglas y el modelo.

## Datos y modelo inicial

Los datos serán inventados y generados mediante un script reproducible (con semilla fija); no se usarán datos personales reales. La primera población acordada es de **25.000 registros por sistema** (A y B): 4.000 clientes, 6.000 cuentas, 12.000 pagos y 3.000 saldos. Se validará con una ejecución pequeña antes de generar la población completa.

El modelo relacional sigue siendo una propuesta. La primera iteración usa clientes, cuentas de crédito, pagos y saldos. Para reconciliar A y B, clientes se identifican por tipo y número de documento; cuentas y pagos tienen claves de negocio estables adicionales a sus IDs internos. Saldos se emparejan por clave de cuenta y fecha de corte. Estas elecciones deben revisarse junto con la granularidad, las relaciones y las reglas de negocio.

El proyecto usa Python 3.13.12, `uv` y un entorno virtual local administrado con `uv sync`. Las dependencias se declaran en `pyproject.toml` y sus versiones resueltas se fijan en `uv.lock`. Los scripts cargan configuración local desde `.env` mediante `python-dotenv`; ese archivo no se comparte ni se sube a Git.

## Conceptos que debemos dominar

**QA de datos** consiste en convertir reglas acordadas en verificaciones reproducibles y analizar sus resultados, no solo en encontrar valores extraños. Practicaremos:

- Dimensiones de calidad: completitud, unicidad, integridad, validez, consistencia, exactitud y oportunidad.
- Reglas de negocio, criterios de aceptación, casos de prueba, evidencia, hallazgos y falsos positivos.
- Reconciliación entre origen y destino: conteos, registros faltantes o adicionales, diferencias de atributos, duplicados, agregados y relaciones huérfanas.
- SQL desde fundamentos (`SELECT`, filtros, `NULL`, joins y agregaciones) hasta subconsultas, CTE, funciones de ventana y, cuando corresponda, análisis de planes y optimización.
- Comunicación responsable: separar hechos observados, hipótesis y causas confirmadas; explicar población, regla y evidencia de cada resultado.

Una diferencia no es automáticamente un defecto. Primero se debe establecer la población comparable, su clave, fecha o lote, los atributos esperados y las excepciones permitidas. Cada prueba debe tener una regla y un resultado esperado verificable.

## Ruta de trabajo

1. **Alinear el escenario:** entender el problema del cargo y qué se va a reconciliar.
2. **Acordar el modelo:** definir entidades, granularidad, claves y relaciones.
3. **Definir reglas:** precisar qué significa que cada dato sea válido y qué excepciones existen.
4. **Preparar la base:** diseñar la estructura y documentarla antes de implementarla.
5. **Generar los datos:** crear datos sintéticos relacionados y reproducibles con el generador; validar primero una ejecución pequeña y luego producir los 25.000 registros acordados por sistema. La primera iteración produce tablas CSV para A y un lote crudo para `landing_b`; todavía no introduce defectos.
6. **Cargar y procesar:** cargar A y la llegada cruda de B; pasar el lote limpio de `landing_b` a las tablas tipadas de `source_b`, conservando el estado y la evidencia del procesamiento.
7. **Aprender SQL y perfilar:** explorar ambas fuentes y comprobar conteos, relaciones, claves y valores antes de inyectar defectos.
8. **Reconciliar y probar:** comparar A y B, acordar las reglas de negocio, convertirlas en casos de prueba e investigar resultados.
9. **Ampliar y optimizar:** solo cuando las pruebas básicas sean correctas, aumentar volumen y estudiar rendimiento.
10. **Preparar la entrevista:** practicar ejercicios y explicar decisiones, resultados y límites con claridad.

El conjunto sintético ya está generado y cargado en `source_a` y `landing_b`. El comando para procesar el lote de B hacia `source_b` también está implementado. El siguiente paso es ejecutar ese procesamiento y luego verificar en PostgreSQL los conteos, relaciones y resultados antes de comenzar la reconciliación con SQL.
