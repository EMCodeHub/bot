from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import admin_tables, chat, health, lead, form_chat
from app.routes.chat_messages import router as chat_messages_router

app = FastAPI(title="Medifestructuras Chatbot API", version="0.1.0")

# For now allow all origins (for local frontend testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict to our domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(lead.router)
app.include_router(form_chat.router)
app.include_router(chat_messages_router)
app.include_router(admin_tables.router)
