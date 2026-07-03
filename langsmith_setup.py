from dotenv import load_dotenv
import os
load_dotenv()
os.environ["LANGSMITH_TRACING"]="true"
os.environ["LANGSMITH_PROJECT"]="finai"
