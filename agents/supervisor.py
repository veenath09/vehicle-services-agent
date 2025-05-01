from typing import List, Optional, Literal, TypedDict
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, trim_messages
from technician import technician_agent
import sys
import os

# Add the project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import get_llm
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
checkpointer = InMemorySaver()
store = InMemoryStore
members = ["service_centers","technicians"]

llm = get_llm()

class State(MessagesState):
    next: str


def make_supervisor_node(llm: BaseChatModel, members: list[str]) -> str:
    options = ["FINISH"] + members
    system_prompt = (
        "You are servio and you work as  a supervisor tasked with managing a conversation between the"
        f" following workers: {members}. Given the following user request,"
        " respond with the worker to act next. Each worker will perform a"
        " task and respond with their results and status. When finished,"
        " if a worker needs more information, ask to supervisor and the more infomration should be provided by the user to navigate to end"
        "make sure to provide the final output in a conversational format." 
        "if user want to make a reservation or appointment please ask the user to provide the nessary information and if any information is missing request for that infromation and proceed with making the request"
        "if any information is missing from the user to make the reservation or appointment request those information from the user and make the reservation"
        "you're responsible for managing the conversation and ensuring all the requestes handles smoothly."
        " respond with FINISH."
    )

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""

        next: Literal[*options]

    def supervisor_node(state: State) -> Command[Literal[*members, "__end__"]]:
        """An LLM-based router."""
        messages = [
            {"role": "system", "content": system_prompt},
        ] + state["messages"]
        response = llm.with_structured_output(Router).invoke(messages)
        goto = response["next"]
        if goto == "FINISH":
            goto = END

        return Command(goto=goto, update={"next": goto})

    return supervisor_node


def technician_node(state: State) -> Command[Literal["supervisor"]]:
    result = technician_agent.invoke(state)
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="search")
            ]
        },
        # We want our workers to ALWAYS "report back" to the supervisor when done
        goto="supervisor",
    )


supervisor_node = make_supervisor_node(llm, ["technicians"])


research_builder = StateGraph(State)
research_builder.add_node("supervisor", supervisor_node)
research_builder.add_node("technicians", technician_node)

research_builder.add_edge(START, "supervisor")
research_graph = research_builder.compile(checkpointer=checkpointer)


# for s in research_graph.stream(
#     {"messages": [("user", "provide me the all the technicians names who are from colombo and if any matches my critiria I would Like to resove him")]},
#     config={
#         "recursion_limit": 100,
#         "configurable": {
#             "thread_id": 1
#         }
#     }
# ):
#     print(s)
#     print("---")



while True:
    user_input = input("User: ")
    if user_input.lower() == "exit":
        break

    # Add the user input to the messages
    #research_graph.add_message({"role": "user", "content": user_input})

    # Process the graph and get the response
    for s in research_graph.stream(
        {"messages": [("user", user_input)]},
        config={
            "recursion_limit": 100,
            "configurable": {
                "thread_id": 1
            }
        }
    ):
        print(s)
        print("---")