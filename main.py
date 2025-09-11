import os

import litellm


from typing import Annotated, List
from typing_extensions import TypedDict
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

class Model(BaseModel):
    model_name: str
    litellm_params: Params
    model_info: dict

class Provider(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    provider_name: str = Field(index=True)
    provider_syntax: str | None = "openai"
    endpoint: str
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
    set_provider_keys(SessionDep)

@app.post("/provider")
async def add_provider(provider: Provider, session: SessionDep) -> Provider:
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider

@app.post("/chat/completions")
async def api_completion(request: CompletionRequest):
       message_dict = [message for message in request.messages]
       try:
           response = await litellm.acompletion(model=request.model,
                                                messages=message_dict,
                                                max_tokens=request.max_tokens)
       except Exception as e:
           response = e
       return response

# Text Completions
@app.post("/completions")

# Lists available tools from provider
# Filling for now
@app.get("/tools")

# List of models (per provider?)
@app.get("/models")

# "Count prompt tokens with supported backends"(?)
@app.post("/tokens")

# Filling for now
@app.post("/embeddings")


def set_provider_keys(session: SessionDep):
    statement = select(Provider)
    providers = session.exec(statement)
    for provider in providers:
        exec("litellm.%s_key = %s" % (provider.name, provider.key))