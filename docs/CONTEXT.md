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

Los datos serán inventados y generados mediante un script reproducible (con semilla fija); no se usarán datos personales reales. La primera población objetivo será de aproximadamente **20.000–30.000 registros por sistema** (A y B), repartidos entre las entidades que definamos. El volumen exacto y su distribución por entidad se decidirán al diseñar la generación. Primero se validará el modelo y las reglas con una ejecución pequeña; después se generará la población objetivo.

El modelo relacional está por definir. Como hipótesis de trabajo se podrían necesitar clientes, cuentas de crédito, pagos y saldos. Antes de diseñar tablas aclararemos qué representa cada fila (granularidad), las claves, las relaciones y las reglas de negocio. La estructura del repositorio también se creará gradualmente, cuando cada etapa la necesite.

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
5. **Generar los datos:** crear datos sintéticos relacionados y reproducibles con el generador; validar primero una ejecución pequeña y luego producir unos 20.000–30.000 registros por sistema.
6. **Aprender SQL y perfilar:** explorar los datos y comprobar sus características antes de inyectar defectos.
7. **Reconciliar y probar:** comparar A y B, convertir reglas en casos de prueba e investigar resultados.
8. **Ampliar y optimizar:** solo cuando las pruebas básicas sean correctas, aumentar volumen y estudiar rendimiento.
9. **Preparar la entrevista:** practicar ejercicios y explicar decisiones, resultados y límites con claridad.

La prioridad inicial es comprender el escenario y acordar el modelo; todavía no corresponde generar los datos ni escribir un conjunto completo de consultas.
