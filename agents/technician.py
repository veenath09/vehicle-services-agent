from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
import sys
import os

# Add the project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import get_llm
from tools.technician_tools import find_technicians, check_technician_availability

llm = get_llm()
technician_agent_tools = [find_technicians, check_technician_availability]
technician_agent = create_react_agent(llm.bind_tools(technician_agent_tools), tools=[find_technicians,check_technician_availability])


