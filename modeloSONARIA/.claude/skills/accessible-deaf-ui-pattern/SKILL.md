---
name: accessible-deaf-ui-patterns
description: Construir interfaces React Native accesibles para personas sordas o con pérdida auditiva. Úsala SIEMPRE que el trabajo toque la UI de la app de accesibilidad: tarjetas de hablante / conversación por canales, "Guardar voz", Focus Mode (elegir a quién seguir y atenuar el resto), y notificaciones de sonidos con vibración distintiva. Cubre patrones visuales (alto contraste, texto grande, color no como único indicador), firmas de vibración/haptics por tipo de evento, y reglas WCAG para accesibilidad auditiva.
---

# UI React Native accesible para usuarios sordos

Principio rector: **nada depende del oído**. Toda información llega por **vista + tacto**
(texto, color, iconos, movimiento, vibración). El usuario decide a quién/qué atender.

## Reglas base (WCAG orientado a sordera)

- **Nunca solo-audio**: cada alerta tiene equivalente visual + háptico.
- **El color no es el único indicador**: acompaña siempre con nombre/icono/forma (daltonismo).
- Contraste texto/fondo ≥ **4.5:1**; texto grande y escalable (respeta `fontScale` del sistema).
- Objetivos táctiles ≥ **44×44 pt**. Etiquetas `accessibilityLabel`/`accessibilityRole` en todo control.
- Movimiento/parpadeo: nunca >3 flashes/s (riesgo de convulsiones); usa transiciones suaves.

## Flujo 1.1 — Conversación por tarjetas/canales de hablante

Una tarjeta por hablante, color estable por persona, nombre grande arriba, texto debajo. La última
en hablar sube/pulsa suavemente. Ejemplo:

```
┌─────────────────────────────┐
│ ● Carlos                    │   ← color fijo por persona + punto de estado "hablando"
│ ¿Ya terminaste el informe?  │
└─────────────────────────────┘
```

- Asigna un color de una paleta accesible (distinguible en daltonismo) por `speaker`/nombre.
- Voces sin identificar → "Persona N" en gris con botón **Guardar voz**.
- Usa `FlatList` con auto-scroll al final; resalta el turno nuevo ~1.5 s.

## Flujo 1.2 — Guardar voz

Al tocar "Guardar voz" en una tarjeta: pedir nombre (modal con teclado), enviar `enroll_start`,
mostrar progreso de captura (~20 s con barra), luego `enroll_stop`. Confirmar visualmente ("✓ Carlos
registrado"). A partir de ahí la tarjeta muestra el nombre en vez de "Persona N".

## Flujo 1.4 — Focus Mode

Selector con checkboxes de personas activas. Las NO seleccionadas se **atenúan/minimizan** (opacidad
baja, colapsadas), reduciendo ruido visual. Comunica "yo decido a quién escuchar".

```
✓ Carlos      ✓ María      ──────────      Luis (oculto)   Andrea (oculta)
```

- Enviar `focus_set` al backend con la lista elegida.
- Persistir la selección; botón claro para "mostrar a todos".

## Flujo 2.2/2.3 — Notificaciones de sonido con vibración distintiva

Cada evento de sonido = tarjeta/banner grande con emoji + mensaje contextual + **firma de vibración
única por tipo**, para que el usuario reconozca el evento sin mirar.

```js
import { Vibration } from "react-native";
// patrones = [espera, vibra, espera, vibra, ...] en ms. Uno DISTINTO por evento:
const VIBRATION = {
  Doorbell:  [0, 300, 150, 300],          // dos toques cortos
  "Smoke detector, smoke alarm": [0, 600, 200, 600, 200, 600], // urgente, largo x3
  "Baby cry, infant cry": [0, 200, 100, 200, 100, 200, 100, 200], // rápido insistente
  Microwave: [0, 400],                    // un toque medio
};
Vibration.vibrate(VIBRATION[sound] ?? [0, 300]);
```

- Alarmas de seguridad (humo/incendio): banner **rojo a pantalla completa**, vibración larga y
  repetida hasta descartar, prioridad máxima sobre cualquier otra UI.
- Para haptics más ricos, `react-native-haptic-feedback` (iOS/Android). `Vibration` es el mínimo viable.
- Emitir también notificación del sistema (push local) para cuando la app esté en segundo plano.

## Historial / asistente de contexto (Flujo transversal)

Pantalla de línea de tiempo con conversaciones y eventos de sonido sellados con hora, y un campo para
preguntar ("¿qué dijo Carlos?", "¿qué pasó mientras dormía?") que consulta al backend.

## Componentes sugeridos

`SpeakerCard`, `SaveVoiceModal`, `FocusModeSelector`, `SoundAlertBanner`, `EmergencyOverlay`,
`TimelineScreen`. Todos con props de accesibilidad y colores por token (tema claro/oscuro y alto contraste).

## Prueba

Verificar con lector de pantalla (TalkBack/VoiceOver) que todo control es alcanzable y etiquetado,
que las vibraciones difieren por evento, y que Focus Mode realmente atenúa a los no seleccionados.
