# 🏛️ Terminal Cuantitativo Institucional

Bienvenido al repositorio central de tu infraestructura de inversión cuantitativa. Este sistema no es un simple tracker de precios; es un **motor probabilístico** diseñado bajo estándares institucionales para gestionar tu capital con disciplina, proteger tu liquidez y maximizar tu esperanza matemática.

---

## 🛠 Arquitectura del Sistema

La plataforma está construida sobre Python, utilizando **Streamlit** como frontend y motor reactivo, y **PostgreSQL (Supabase)** / **SQLite** como backend dual.

```mermaid
graph TD
    A[app.py / Streamlit] --> B(Módulos Cuantitativos)
    B --> C{Signal Engine Bayesiano}
    B --> D{Risk Manager}
    B --> E{Scanner & Valuation}
    C --> F[(Supabase / SQLite)]
    D --> F
    F --> A
```

### Capas del Proyecto:
1. **Infraestructura Contable:** Transacciones y Flujos de Efectivo por partida doble (`modules/db.py`).
2. **Motor Probabilístico (Bayes & Kelly):** Evaluación de señales y dimensionamiento de posiciones (`modules/signal_engine.py`).
3. **Scanner y Automatización:** Búsqueda asíncrona de empresas infravaloradas (`modules/scanner.py`).
4. **Gestor de Riesgo y Macro:** Adaptación del régimen (Bull/Bear) basado en la SMA200 y VIX (`modules/risk_manager.py`).
5. **Reporting PDF:** Emisión de Tear Sheets descargables (`modules/reporting.py`).

---

## 📐 Matemáticas y Algoritmos Implementados

### 1. Inferencia Bayesiana para Señales de Mercado
El algoritmo base no opera en blancos y negros. Asigna una **probabilidad a priori** (e.g. 50%) y la actualiza (*posterior*) basándose en la nueva evidencia:
- Margen de seguridad (Fair Value vs Price).
- Z-Score de la acción (Distancia a sus medias).
- Puntuaciones de calidad del balance.

Si la probabilidad *posterior* supera el 65%, el sistema emite una señal de **COMPRA**.

### 2. Criterio de Kelly (Dimensionamiento)
Nunca arriesgamos capital a ciegas. El sistema calcula la cantidad óptima a invertir para maximizar la tasa compuesta de crecimiento utilizando la fórmula:
`f* = p - (q / b)`
Donde `p` es la probabilidad de éxito (Bayesiana) y `b` es la relación riesgo/recompensa.

### 3. Modelo Macro y Dynamic Cash
El nivel mínimo de efectivo exigido **no es estático**. Depende de:
- `SPY` vs `SMA 200`: Si el mercado general entra en tendencia bajista, el requerimiento de liquidez sube.
- `VIX`: Volatilidades extremas imponen *penalizaciones* a la exposición en renta variable.

---

## 🚀 Despliegue en Producción (Streamlit Cloud)

Para levantar esta app en un entorno en la nube, sigue estos pasos:

1. **Sincroniza el repositorio** con GitHub.
2. Ingresa a **Streamlit Cloud** y conecta este repositorio.
3. En la sección **Advanced Settings** de Streamlit, configura los `secrets`:
```toml
[connections.supabase]
url = "postgresql://user:password@aws-0-region.pooler.supabase.com:6543/postgres"
```
4. El código detectará la URL automáticamente en `modules/db.py` y levantará las tablas sin intervención humana.

---

## 🧪 Pruebas y CI/CD
El sistema cuenta con un pipeline de Integración Continua (CI) en GitHub Actions (`.github/workflows/ci.yml`). Cada vez que haces `push` a `main`, se corren los **tests unitarios** que aseguran la consistencia de:
- Cálculos Bayesianos.
- Reglas de Riesgo.
- Lógica Contable.

Para ejecutar los tests en local:
```bash
pytest tests/ -v
```

---

*Desarrollado para operar con disciplina estricta y riesgo asimétrico positivo.*
