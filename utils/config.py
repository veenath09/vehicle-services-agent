from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
load_dotenv()


def get_llm():
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-04-17")
    #llm = ChatGoogleGenerativeAI(model= "gemini-2.5-pro-preview-03-25")
    return llm

