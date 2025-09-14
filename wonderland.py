from contextlib import asynccontextmanager
import os
import uvicorn
import litellm


from typing import Annotated, List
from typing_extensions import TypedDict
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
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


ListedProviders = [provider.value for provider in litellm.provider_list]
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_tables()
    set_provider_keys()
    yield

app = FastAPI(title="Project Wonderland",
              summary="And down the rabbit hole we go...", lifespan=lifespan)

# A standard async context manager
# Executes code above the yield before startup. 
# Executes code below the yield after shutdown. 


# Provider block
@app.post("/providers")
def add_provider(provider: Provider, session: SessionDep):
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
def is_provider_listed(provider_id: int, session: SessionDep) -> bool:
    provider = session.get(Provider, provider_id)
    response = provider.provider_name in ListedProviders
    return response

@app.get("/providers", response_model=list[ProviderPublic])
def get_all_providers(session: SessionDep):
    query = select(Provider)
    providers = session.exec(query)
    if not providers:
            raise HTTPException(status_code=404, detail="No providers found.")
    return providers

@app.patch("/providers/{provider_id}", response_model=ProviderPublic)
def update_provider(provider_id: int, provider_update: ProviderUpdate, session: SessionDep):
    provider_db = session.get(Provider, provider_id)
    if not provider_db:
         raise HTTPException(status_code = 404, detail="Provider with id: " + str(provider_id) + " not found.")
    provider_data = provider_update.model_dump(exclude_unset=True)
    provider_db.sqlmodel_update(provider_data)
    session.add(provider_db)
    session.commit()
    session.refresh(provider_db)
    return provider_db

@app.delete("/providers/{provider_id}")
async def delete_provider(provider_id: int, session: SessionDep):
    provider = session.get(Provider, provider_id)
    if not provider:
            raise HTTPException(status_code=404, details="Provider with id: " + str(provider_id) + " not found.")
    session.delete(provider)
    session.commit()
    response = [{"message": f"{provider.provider_id}: {provider.provider_name} has been removed from the database."}]
    return response
# End of Provider Block

@app.get("/models/{provider_id}")
def get_models_by_provider_id(provider_id: int, session: SessionDep):
    provider = session.get(Provider, provider_id)
    provider_pub = ProviderPublic.model_validate(provider)
    if not provider:
            raise HTTPException(status_code=404, details="Provider with id: " + str(provider_id) + " not found.")
    provider_models = litellm.get_valid_models(check_provider_endpoint=True, custom_llm_provider=provider.provider_syntax)
    for model in provider_models:
        index = provider_models.index(model)
        model_pieces = model.split('/')
        model = ('/').join(model_pieces[1:])
        provider_models[index] = model
    provider_models.sort()
    models = []
    models.append({"provider": provider_pub, "provider_models": provider_models})
    return models

@app.get("/models")
def get_all_models(session: SessionDep):
    providers: List[ProviderPublic] = get_all_providers(session)
    models = []
    for provider in providers:
        provider_models = get_models_by_provider_id(provider.id, session)
        models.append(provider_models)
    return models

@app.post("/health")
def check_connection(model_name: str, session: SessionDep):
    response = litellm.validate_environment(model_name)
    return response[0]



@app.post("/chat/completions")
async def api_completion(rawrequest: CompletionReq, session: SessionDep):
       provider = get_provider(rawrequest.provider_id, session)
       request: CompletionReqBase = parse_request(rawrequest, provider)
       try:
           response = await litellm.acompletion(**(request.model_dump(exclude_unset=True)))
       except Exception as e:
           response = os.environ
       return response

# Lists available tools from provider
# Filling for now
# @app.get("/tools")

# "Count prompt tokens with supported backends"(?)
@app.post("/tokens")
def count_tokens(request: CompletionReqBase):
    return litellm.token_counter(model=request.model, messages=request.messages)

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

def set_provider_keys():
    with engine.begin() as connection:
        providers = connection.execute(select(Provider))
        
    for provider in providers:
        name = provider.provider_name.upper() + "_API_KEY"
        os.environ[name] = provider.api_key

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)