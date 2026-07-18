# Backend Implementation - AI Inclusive Assistant

## 1. Objetivo del Backend

El backend será desarrollado con FastAPI y será responsable de:

- Recibir audio en tiempo real desde la aplicación Expo.
- Procesar audio mediante modelos de Inteligencia Artificial.
- Gestionar usuarios y configuraciones.
- Guardar conversaciones y eventos en Supabase PostgreSQL.
- Generar respuestas procesadas para la aplicación móvil.

Supabase será utilizado únicamente como base de datos PostgreSQL.

La lógica de negocio, autenticación, procesamiento de audio y comunicación con IA estarán en FastAPI.

---

# 2. Arquitectura General


Expo Mobile App
|
| HTTP / WebSocket
|
v
FastAPI Backend
|
|---- Deepgram
| Speech To Text
|
|---- YAMNet
| Sound Detection
|
|---- Gemini
| Summaries / Context
|
|
v
Supabase PostgreSQL


---

# 3. Tecnologías

## Backend

- Python 3.12
- FastAPI
- Uvicorn
- SQLAlchemy
- Alembic
- Pydantic
- WebSockets

## Base de datos

Supabase PostgreSQL.

Uso:

- Usuarios.
- Voces registradas.
- Conversaciones.
- Mensajes.
- Sonidos configurados.
- Eventos detectados.

## Inteligencia Artificial

### Deepgram

Responsabilidad:

- Convertir audio en texto.
- Procesar conversaciones en tiempo real.
- Separar hablantes mediante diarización si está disponible.

Entrada:

Audio streaming.

Salida:

Texto transcrito.

Ejemplo:

```json
{
"text":"Hola, ¿cómo estás?"
}
YAMNet

Responsabilidad:

Detectar sonidos del ambiente.

Ejemplos:

Timbre.
Alarma.
Microondas.
Perro.
Bebé llorando.
Hervidor.

Entrada:

Audio ambiente.

Salida:

Evento detectado.

Ejemplo:

{
"event":"doorbell",
"confidence":0.95
}
Gemini

Responsabilidad:

Procesamiento inteligente del historial.

Funciones:

Crear resúmenes.
Responder preguntas sobre conversaciones.
Generar contexto.

Ejemplo:

Pregunta:

"¿Qué dijo Carlos?"

Proceso:

FastAPI consulta conversaciones en Supabase.

Envía contexto a Gemini.

Gemini genera respuesta.

4. Estructura del Proyecto
backend/

├── app/
│
├── main.py
├── config.py
├── database.py
├── dependencies.py
│
├── routers/
│
├── services/
│
├── repositories/
│
├── models/
│
├── schemas/
│
├── security/
│
├── utils/
│
├── websocket/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
5. Descripción de Componentes
main.py

Responsabilidad:

Crear instancia FastAPI.
Registrar routers.
Configurar middleware.
Iniciar aplicación.

No contiene lógica de negocio.

config.py

Responsabilidad:

Manejar variables de entorno.

Ejemplo:

DATABASE_URL=
DEEPGRAM_API_KEY=
GEMINI_API_KEY=
JWT_SECRET=
database.py

Responsabilidad:

Crear conexión con Supabase PostgreSQL.

Usará:

SQLAlchemy.
Pool de conexiones.
models/

Contiene los modelos de base de datos.

Representan tablas de Supabase.

Ejemplo:

models/

user.py

registered_voice.py

conversation.py

conversation_message.py

registered_sound.py

sound_event.py

user_device.py
schemas/

Contiene los modelos de entrada y salida usando Pydantic.

Ejemplo:

Entrada:

Registrar usuario.

Salida:

Información del usuario.

routers/

Contiene únicamente endpoints.

No contiene IA ni consultas directas a la base de datos.

auth.py

Endpoints:

POST /auth/register
POST /auth/login
GET /auth/me

Responsabilidad:

Crear usuarios.
Validar usuarios.
Generar JWT.
voices.py

Endpoints:

POST /voices/register
GET /voices
PUT /voices/{id}
DELETE /voices/{id}

Responsabilidad:

Gestionar voces registradas.

Flujo:

Audio usuario

↓

voice_service

↓

Guardar información en Supabase.

conversations.py

Endpoints:

POST /conversation/start
POST /conversation/end
GET /conversation/history
GET /conversation/{id}

Responsabilidad:

Gestionar sesiones de conversación.

sounds.py

Endpoints:

GET /sounds
POST /sounds/config

Responsabilidad:

Configurar sonidos que el usuario desea monitorear.

events.py

Endpoint:

GET /events

Responsabilidad:

Consultar eventos detectados.

websocket/

Maneja comunicación en tiempo real.

audio_stream.py

Endpoint:

WS /ws/audio

Responsabilidad:

Recibir audio desde Expo.

Flujo:

Audio

↓

Conversation Service

↓

Deepgram

↓

Guardar mensaje

↓

Enviar resultado.

sound_stream.py

Endpoint:

WS /ws/sounds

Responsabilidad:

Recibir audio ambiental.

Flujo:

Audio

↓

YAMNet

↓

Guardar evento

↓

Enviar notificación.

services/

Contiene la lógica principal del sistema.

conversation_service.py

Responsabilidad:

Orquestar conversaciones.

Proceso:

Recibe audio.
Envía audio a Deepgram.
Obtiene texto.
Identifica hablante.
Guarda mensaje.
Devuelve resultado.
sound_service.py

Responsabilidad:

Procesar sonidos ambientales.

Proceso:

Recibe audio.
Ejecuta YAMNet.
Determina evento.
Guarda evento.
Genera notificación.
summary_service.py

Responsabilidad:

Trabajar con Gemini.

Proceso:

Obtener historial.
Construir contexto.
Enviar a Gemini.
Retornar resumen.
voice_service.py

Responsabilidad:

Gestionar voces.

Funciones:

Registrar voz.
Actualizar nombre.
Buscar voz.
services/ai/

Contiene integración directa con IA.

ai/

deepgram_service.py

yamnet_service.py

gemini_service.py

Cada archivo únicamente se comunica con un modelo de IA.

repositories/

Única capa que accede a Supabase.

Ejemplo:

user_repository.py

voice_repository.py

conversation_repository.py

message_repository.py

sound_repository.py

event_repository.py

Responsabilidad:

Crear registros.
Buscar información.
Actualizar datos.
6. Flujo de Conversación en Tiempo Real
Expo

↓

WebSocket

↓

FastAPI

↓

audio_stream.py

↓

conversation_service.py

↓

Deepgram

↓

Guardar en Supabase

↓

Enviar JSON a Expo

Respuesta:

{
"speaker":"Carlos",
"text":"Hola"
}
7. Flujo de Sonidos Ambientales
Expo

↓

WebSocket

↓

FastAPI

↓

sound_service

↓

YAMNet

↓

Guardar evento

↓

Enviar alerta

Ejemplo:

{
"type":"alarm",
"message":"La alarma de humo se activó"
}
8. Dockerización

El backend debe ejecutarse mediante Docker.

Servicios:

fastapi

No se crea contenedor PostgreSQL porque Supabase ya administra la base de datos.

docker-compose.yml

Debe:

Crear contenedor FastAPI.
Instalar dependencias.
Cargar variables .env.
Exponer puerto 8000.

Comando:

docker compose up --build
9. Variables de entorno

Archivo:

.env

DATABASE_URL=

SUPABASE_URL=

SUPABASE_KEY=

DEEPGRAM_API_KEY=

GEMINI_API_KEY=

JWT_SECRET=

PORT=8000
10. Orden de Implementación
Fase 1

Backend base:

Crear FastAPI.
Crear estructura.
Conectar Supabase.
Crear modelos.
Fase 2

Usuarios:

Registro.
Login.
JWT.
Fase 3

Conversaciones:

WebSocket.
Integrar Deepgram.
Guardar mensajes.
Fase 4

Sonidos:

Integrar YAMNet.
Crear eventos.
Notificaciones.
Fase 5

Inteligencia:

Integrar Gemini.
Crear resúmenes.
Consultas al historial.
11. Regla principal del proyecto

Los routers reciben peticiones.

Los services contienen la lógica.

Los repositories manejan la base de datos.

Los servicios de IA solamente contienen integración con modelos.

Nunca mezclar:

Router + IA + Base de datos.


Esta estructura ya está alineada con:
- FastAPI como backend principal.
- Supabase solo como PostgreSQL.
- Expo como cliente móvil.
- Deepgram para conversación.
- YAMNet para sonidos.
- Gemini para inteligencia contextual.
- Docker para despliegue en VPS.


Para agregarlo al BACKEND_IMPLEMENTATION.md, puedes poner este apartado:

# Docker Compose

Generar un entorno dockerizado para ejecutar el backend utilizando Python 3.12. El objetivo es que cualquier desarrollador pueda levantar el proyecto con un único comando (`docker compose up --build`) sin necesidad de instalar dependencias manualmente en su máquina.

El contenedor del backend debe utilizar una imagen basada en Python 3.12, instalar todas las dependencias definidas en `requirements.txt`, cargar las variables de entorno desde el archivo `.env` y ejecutar FastAPI mediante Uvicorn.

El proyecto debe incluir:

- Dockerfile para construir la imagen del backend.
- docker-compose.yml para administrar los servicios.
- Archivo `.env` para configuración.
- Volúmenes para mantener configuraciones y archivos temporales.
- Red interna para comunicación entre servicios.
- Reinicio automático del contenedor en caso de fallo.

El backend debe incluir las siguientes dependencias:

- FastAPI para la creación de la API.
- Uvicorn como servidor ASGI.
- SQLAlchemy para comunicación con PostgreSQL.
- Alembic para migraciones.
- Psycopg2/PostgreSQL Driver para conexión con Supabase.
- Pydantic para validación de datos.
- Python-dotenv para variables de entorno.
- WebSockets para comunicación en tiempo real.
- Cliente oficial de Deepgram para procesamiento de voz.
- Cliente de Gemini para inteligencia contextual.
- TensorFlow/TensorFlow Lite para ejecución de modelos como YAMNet.
- Librerías necesarias para procesamiento de audio.

El archivo `docker-compose.yml` debe levantar el servicio principal:


services:

backend:
build:
context: .
dockerfile: Dockerfile

container_name: inclusive-ai-backend

ports:
  - "8000:8000"

env_file:
  - .env

volumes:
  - ./app:/app/app

restart: always

networks:
  - backend-network

networks:

backend-network:
driver: bridge


El `Dockerfile` debe:

1. Utilizar Python 3.12 como imagen base.
2. Definir el directorio de trabajo `/app`.
3. Copiar `requirements.txt`.
4. Instalar dependencias.
5. Copiar el código fuente.
6. Exponer el puerto 8000.
7. Ejecutar FastAPI automáticamente.

Comando de inicio:


docker compose up --build


El backend debe quedar disponible en:


http://localhost:8000


y la documentación automática de FastAPI en:


http://localhost:8000/docs


La base de datos PostgreSQL no será creada dentro de Docker, ya que será administrada por Supabase. El contenedor únicamente debe conectarse mediante la variable `DATABASE_URL`.

También agregaría una aclaración:

# Nota sobre Supabase

Supabase no será ejecutado dentro de Docker.

La arquitectura utiliza:

FastAPI (Docker)
        |
        |
        v
Supabase PostgreSQL (Cloud)

El contenedor únicamente consume la base de datos mediante SQLAlchemy. La autenticación, lógica de negocio, procesamiento de IA y WebSockets pertenecen exclusivamente al backend FastAPI.