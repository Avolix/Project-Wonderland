import os

from typing_extensions import TypedDict
from fastapi import FastAPI
from pydantic import BaseModel

import litellm

# This key is a placeholder created for development
# It can only be used with free models because I'm not adding payment to this
# These are going to be set to values stored in SQLAlchemy later on
os.environ["OPENROUTER_API_KEY"] = "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"


# 
class Message(TypedDict):
    content: str
    role: str


# Using the Pydantic/FastAPI BaseModel
# to define the CompletionRequest detailed
# here: https://docs.litellm.ai/docs/completion/input

class CompletionRequest(BaseModel):
    model: str
    messages: Message
    max_tokens: int | None = 256

app = FastAPI(title="StrangeWarren", 
              summary="And down the rabbit hole we go...")

@app.post("/chat/completions")
async def api_completion(request: CompletionRequest):
       try:
           response = await litellm.acompletion(**request)
       except Exception as e:
           response = e
       return response