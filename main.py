import os

from attr import validate
import litellm


from typing import Annotated, List
from typing_extensions import TypedDict
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

class ProviderBase(SQLModel):
    provider_name: str = Field(index=True)
    provider_syntax: str | None
    endpoint: str | None = None
    api_base: str | None = Field(default=None, index=True)

class Provider(ProviderBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    provider_name: str = Field(index=True)
    provider_syntax: str | None = Field(default="openai")
    endpoint: str | None = None
    api_key: str
    api_base: str | None = Field(default=None, index=True)

class ProviderPublic(ProviderBase):
    id: int

class ProviderUpdate(ProviderBase):
    provider_name: str | None = Field(default=None, index=True)
    provider_syntax: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    api_base: str | None = Field(default=None, index=True)

# The messages JSON object required for
# CompletionRequest

class Message(TypedDict):
    content: str
    role: str

# Using the Pydantic/FastAPI BaseModel
# to define the CompletionRequest detailed
# here: https://docs.litellm.ai/docs/completion/input

class CompletionReqBase(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: int | None = 256

class CompletionReq(CompletionReqBase):
    provider_id: int

# SQL Initialization block
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
# End of SQL Initialization block

app = FastAPI(title="Project Wonderland",
              summary="And down the rabbit hole we go...")

@app.on_event("startup")
async def startup_db_client():
    create_db_tables()

# Provider block
@app.post("/providers")
async def add_provider(provider: Provider, session: SessionDep):
    if is_provider_listed(provider.provider_id, session):
        provider.provider_syntax = provider.provider_name
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return {"message": f"{provider.provider_name} has been added as a provider!"}

@app.get("/providers/{provider_id}", response_model=ProviderPublic)
def get_provider(provider_id: int, session: SessionDep):
    provider: Provider = session.get(Provider, provider_id)
    if not provider:
            raise HTTPException(status_code=404, detail="Provider with id: " + str(provider_id) + " not found.")
    response: ProviderPublic = provider
    return response

@app.get("/providers/{provider_id}/listed")
def is_provider_listed(provider_id: int, session: SessionDep):
    provider = session.get(Provider, provider_id)
    response = provider.provider_name in litellm.provider_list
    return response

@app.get("/providers", response_model=list[ProviderPublic])
async def list_providers(session: SessionDep):
    query = select(Provider)
    providers = session.exec(query)
    if not providers:
            raise HTTPException(status_code=404, detail="Provider not found.")
    return providers

@app.patch("/providers/{provider_id}", response_model=ProviderPublic)
def update_provider(provider_id: int, provider_update: ProviderUpdate, session: SessionDep):
    provider_db = session.get(Provider, provider_id)
    if not provider_db:
         raise HTTPException(status_code = 404, detail="Provider not found.")
    provider_data = provider_update.model_dump(exclude_unset=True)
    provider_db.sqlmodel_update(provider_data)
    session.add(provider_db)
    session.commit()
    session.refresh(provider_db)
    return provider_db

@app.delete("/providers")
async def delete_provider(provider_name: str, session: SessionDep):
    response = [{"message": f"{provider_name} has been removed from the database. Remaining providers:"}]
    response2 = await list_providers(session)
    response += response2
    return response
# End of Provider Block

@app.get("/models/{provider_id}")
async def get_models_by_provider_id(provider_id: int, session: SessionDep):
    models = litellm.get_valid_models(check_provider_endpoint = True)
    return models


@app.post("/chat/completions")
async def api_completion(rawrequest: CompletionReq, session: SessionDep):
       set_provider_keys(session)
       provider = get_provider(rawrequest.provider_id, session)
       request: CompletionReqBase = parse_request(rawrequest, provider)
       try:
           response = await litellm.acompletion(**(request.model_dump(exclude_unset=True)))
       except Exception as e:
           response = os.environ["OPENROUTER_API_KEY"]
       return response

# Text Completions
# @app.post("/completions")

# Lists available tools from provider
# Filling for now
# @app.get("/tools")

# "Count prompt tokens with supported backends"(?)
# @app.post("/tokens")

# Filling for now
# @app.post("/embeddings")

def parse_request(request: CompletionReq, provider: ProviderPublic) -> CompletionReqBase:
    response = CompletionReqBase.validate(request.model_dump(exclude_unset=True))
    response.model = provider.provider_syntax + '/' + response.model
    if provider.endpoint: 
        response.model += provider.endpoint
    if provider.api_base:
        response.api_base = provider.api_base
    return response
    
    

def set_provider_keys(session: SessionDep):
    providers: list[Provider] = session.exec(select(Provider))
    for provider in providers:
        provider.provider_name = provider.provider_name.upper() + "_API_KEY"
        os.environ[provider.provider_name] = provider.api_key