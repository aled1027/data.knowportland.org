import click
import sqlite_utils
import llm
import dotenv
import os
from llm_tools_datasette import Datasette

dotenv.load_dotenv()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]


@click.command()
@click.option("-p", "--prompt", required=True, help="Prompt to ask the model")
@click.option("--rag", is_flag=True, help="Use RAG mode")
def cli(prompt: str, rag: bool):
    if rag:
        rag_mode(prompt)
    else:
        tool_mode(prompt)


def rag_mode(prompt: str):
    """RAG version"""
    db = sqlite_utils.Database("data/portland.db")
    collection = llm.Collection("pdx", db=db)

    similar_resp = collection.similar(prompt, number=5)

    full_prompt = ""
    for item in similar_resp:
        full_prompt += "<minutes>{}</minutes>\n".format(item.content)
    full_prompt += "\n\nUsing the minutes above, answer the following: {}".format(
        prompt
    )

    model = llm.get_model("gpt-4o-mini")
    response = model.prompt(full_prompt, key=OPENAI_API_KEY)
    print(response.text())


def tool_mode(prompt: str):
    model = llm.get_model("gpt-4o-mini")
    response = model.chain(
        prompt, key=OPENAI_API_KEY, tools=[Datasette("http://localhost:8001/portland")]
    )
    print(response.text())


if __name__ == "__main__":
    cli()
