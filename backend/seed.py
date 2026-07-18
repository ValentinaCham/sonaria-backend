"""
Seed data para Supabase via SQLAlchemy (misma conexion que el backend).

Uso:
  cd backend
  python seed.py
"""

from app.database import SessionLocal
from app.models.user import User
from app.models.registered_voice import RegisteredVoice
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.registered_sound import RegisteredSound, SoundCategory, SoundEvent
from app.security.password import hash_password

db = SessionLocal()

try:
    existing = db.query(User).filter(User.email == "test@ejemplo.com").first()
    if existing:
        print("Seed data already exists, skipping.")
        print(f"  User:    test@ejemplo.com / password123")
        print(f"  User ID: {existing.id}")
        db.close()
        exit(0)

    user = User(
        email="test@ejemplo.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    voice1 = RegisteredVoice(user_id=user.id, name="Carlos", is_prioritized=True)
    voice2 = RegisteredVoice(user_id=user.id, name="Maria", is_prioritized=False)
    db.add_all([voice1, voice2])
    db.commit()

    conv = Conversation(user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    msg1 = ConversationMessage(
        conversation_id=conv.id, registered_voice_id=voice1.id,
        speaker_label="Carlos", transcription="Hola, como estas?",
    )
    msg2 = ConversationMessage(
        conversation_id=conv.id, registered_voice_id=voice2.id,
        speaker_label="Maria", transcription="Muy bien! Vamos a la tienda?",
    )
    db.add_all([msg1, msg2])
    db.commit()

    sound1 = RegisteredSound(
        user_id=user.id, category=SoundCategory.doorbell,
        custom_name="Timbre Principal",
    )
    sound2 = RegisteredSound(
        user_id=user.id, category=SoundCategory.alarm,
        custom_name="Alarma de Incendio",
        notification_preference={"vibration": True, "visual": True},
    )
    db.add_all([sound1, sound2])
    db.commit()

    event = SoundEvent(
        user_id=user.id, registered_sound_id=sound1.id,
        context_message="Alguien toco el timbre a las 3:00 PM",
    )
    db.add(event)
    db.commit()

    print("Seed data created successfully!")
    print(f"  User:    test@ejemplo.com / password123")
    print(f"  User ID: {user.id}")
    print(f"  Voices:  {voice1.name}, {voice2.name}")
    print(f"  Conv:    {conv.id}")
    print(f"  Sounds:  {sound1.custom_name}, {sound2.custom_name}")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
