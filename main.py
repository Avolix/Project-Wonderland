import os

import litellm
import sqlite3


from typing import Annotated, List
from typing_extensions import TypedDict
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine


"""
class Params(TypedDict):
    model: str
    endpoint: str | None = None
    api_key: str
    api_version: str | None = None
    api_base: str
    timeout: int | None = 10

class Model(BaseModel):
    model_name: str
    litellm_params: Params
    model_info: dict
"""

# EXTREMELY basic key storage and endpoint storage for custom endpoints
# Solely for use in early dev
class Keybase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    provider_name: str = Field(index=True)
    api_key: str
    api_base: str | None = Field(default=None, index=True)
    
# The messages JSON object required for
# CompletionRequest

class Message(TypedDict):
    content: str
    role: str

# Using the Pydantic/FastAPI BaseModel
# to define the CompletionRequest detailed
# here: https://docs.litellm.ai/docs/completion/input

class CompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: int | None = 256

# SQL block
DB_FILE = 'warren.db'
DB_URL = f"sqlite:///{DB_FILE}"
DB_ARGS = {"check_same_thread": False}

engine = create_engine(DB_URL, connect_args = DB_ARGS)

def create_db_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]
# End of SQL block 

app = FastAPI(title="Project Wonderland", 
              summary="And down the rabbit hole we go...")

@app.on_event("startup")
async def startup_db_client():
    create_db_tables()

@app.post("/keybase")
async def add_keybase(keybase: Keybase, session: SessionDep) -> Keybase:
    session.add(keybase)
    session.commit()
    session.refresh(keybase)
    return keybase


@app.post("/chat/completions")
async def api_completion(request: CompletionRequest, session: SessionDep):
       parse_request(request, session)
       message_dict = [message for message in request.messages]
       try:
           response = await litellm.acompletion(model=request.model,
                                                messages=message_dict,
                                                max_tokens=request.max_tokens)
       except Exception as e:
           response = e
       return response



# Helper function for request parsing
# Currently a proof of concept
# This is also a terrible way of doing this don't @ me 
def parse_request(request: CompletionRequest, session: SessionDep):
    if "openrouter" in request.model:
        request.model = "openrouter/" + request.model
        keybase: Keybase = session.get(Keybase, 0)
        os.environ["OPENROUTER_API_KEY"] = keybase.api_key