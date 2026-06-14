from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_gigachat import GigaChat, GigaChatEmbeddings


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
POLICY_INDEX_DIR = DATA / "indexes" / "policy_chroma"
POLICY_COLLECTION_NAME = "policy_docs"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


TABLES = {
    "travelers": read_csv(DATA / "travelers" / "travelers.csv"),
    "preferences": read_csv(DATA / "travelers" / "traveler_preferences.csv"),
    "groups": read_csv(DATA / "travelers" / "travel_groups.csv"),
    "members": read_csv(DATA / "travelers" / "group_members.csv"),
    "flights": read_csv(DATA / "travelers" / "flights.csv"),
    "hotels": read_csv(DATA / "travelers" / "hotels.csv"),
    "tours": read_csv(DATA / "travelers" / "tours.csv"),
}
POLICY_VECTORSTORE = None


def compact(rows: list[dict[str, Any]], limit: int = 20) -> str:
    return json.dumps(rows[:limit], ensure_ascii=False, indent=2)


@tool
def get_group_context(group_id: str) -> str:
    """Вернуть группу, участников и предпочтения по group_id."""
    group = next((row for row in TABLES["groups"] if row["group_id"] == group_id), None)
    members = [row for row in TABLES["members"] if row["group_id"] == group_id]
    traveler_ids = {row["traveler_id"] for row in members}
    travelers = [row for row in TABLES["travelers"] if row["traveler_id"] in traveler_ids]
    preferences = [row for row in TABLES["preferences"] if row["traveler_id"] in traveler_ids]
    return json.dumps(
        {
            "group": group,
            "members": members,
            "travelers": travelers,
            "preferences": preferences,
        },
        ensure_ascii=False,
        indent=2,
    )


@tool
def search_flights(origin_city: str | None = None, destination: str | None = None) -> str:
    """Найти перелеты по городу отправления и направлению."""
    rows = TABLES["flights"]
    if origin_city:
        rows = [row for row in rows if row["origin_city"].lower() == origin_city.lower()]
    if destination:
        rows = [row for row in rows if row["destination"].lower() == destination.lower()]
    return compact(rows)


@tool
def search_hotels(destination: str) -> str:
    """Найти отели по направлению."""
    return compact([row for row in TABLES["hotels"] if row["destination"].lower() == destination.lower()])


@tool
def search_tours(destination: str) -> str:
    """Найти пакетные туры по направлению."""
    return compact([row for row in TABLES["tours"] if row["destination"].lower() == destination.lower()])


@tool
def retrieve_policy_docs(query: str, limit: int = 3) -> str:
    """Найти релевантные правила сервиса через vector RAG по markdown-документам."""
    if POLICY_VECTORSTORE is None:
        raise RuntimeError("Policy index is not loaded. Run: python agent/scripts/build_policy_index.py")
    docs = POLICY_VECTORSTORE.similarity_search(query, k=limit)
    return "\n\n".join(
        f"[{doc.metadata.get('source')}:{doc.metadata.get('section')}]\n{doc.page_content}"
        for doc in docs
    )


def load_qa() -> list[dict[str, Any]]:
    path = DATA / "qa" / "qa.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_agent():
    global POLICY_VECTORSTORE

    load_dotenv(ROOT / ".env")
    credentials = os.getenv("GIGACHAT_CREDENTIALS")
    if not credentials:
        raise RuntimeError("GIGACHAT_CREDENTIALS не найден. Создай .env по .env.example.")
    if not POLICY_INDEX_DIR.exists():
        raise RuntimeError("Policy RAG index not found. Run: python agent/scripts/build_policy_index.py")

    llm = GigaChat(
        credentials=credentials,
        scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        model=os.getenv("GIGACHAT_MODEL", "GigaChat-2-Max"),
        verify_ssl_certs=False,
        temperature=0,
    )
    embeddings = GigaChatEmbeddings(
        credentials=credentials,
        scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        model=os.getenv("GIGACHAT_EMBEDDINGS_MODEL", "EmbeddingsGigaR"),
        verify_ssl_certs=False,
    )
    chroma_client = chromadb.PersistentClient(path=str(POLICY_INDEX_DIR))
    POLICY_VECTORSTORE = Chroma(
        client=chroma_client,
        collection_name=POLICY_COLLECTION_NAME,
        embedding_function=embeddings,
    )

    return create_agent(
        model=llm,
        tools=[get_group_context, search_flights, search_hotels, search_tours, retrieve_policy_docs],
        system_prompt=(
            "Ты baseline travel-planning agent. "
            "Сначала используй tools для данных группы, перелетов, отелей, туров и правил. "
            "Не придумывай flight_id, hotel_id или tour_id: используй только значения из tools. "
            "Если не хватает дат, направления, состава группы или бюджета, верни clarification. "
            "Если есть визовый риск, ребенок или опасное подтверждение без проверки, верни escalation. "
            "Если жесткие требования невозможно выполнить без нарушения бюджета, верни clarification или rejection. "
            "Если в ответе выбран или упомянут flight_id, hotel_id или tour_id, обязательно положи его в entities. "
            "Для escalation можно вернуть предварительно найденные подходящие flight_id/hotel_id/tour_id, но не подтверждай бронирование. "
            "Финальный ответ верни только как minified JSON object в одну строку: без markdown, без переносов строк, без текста до или после JSON. "
            "Поле answer тоже должно быть одной строкой. "
            "Формат: "
            "{\"outcome_type\":\"recommendation|clarification|escalation|rejection|info\","
            "\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},"
            "\"answer\":\"...\"}"
        ),
    )


def run_case(agent, case: dict[str, Any]) -> str:
    payload = {
        "case_id": case["case_id"],
        "category": case["category"],
        "group_id": case.get("group_id"),
        "user_request": case["user_request"],
    }
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Реши кейс. Используй tools перед финальным ответом.\n\n"
                        + json.dumps(payload, ensure_ascii=False, indent=2)
                    )
                )
            ]
        }
    )
    return str(result["messages"][-1].content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    qa = load_qa()
    agent = build_agent()

    if args.case_id:
        case = next(item for item in qa if item["case_id"] == args.case_id)
        print(run_case(agent, case))
        return

    if args.all:
        for case in qa:
            print(json.dumps({"case_id": case["case_id"], "prediction": run_case(agent, case)}, ensure_ascii=False))
        return

    print("Укажи --case-id Q-001 или --all")


if __name__ == "__main__":
    main()
