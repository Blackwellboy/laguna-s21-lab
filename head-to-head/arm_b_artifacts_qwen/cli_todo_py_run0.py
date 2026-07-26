#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

DATA_FILE = Path.home() / ".todo.json"


def load_todos():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_todos(todos):
    with open(DATA_FILE, "w") as f:
        json.dump(todos, f, indent=2)


def add_todos(todos, args):
    text = " ".join(args.text)
    todo = {"id": len(todos) + 1, "text": text, "done": False}
    todos.append(todo)
    save_todos(todos)
    print(f"Added: {text}")


def list_todos(todos, args):
    if not todos:
        print("No todos.")
        return
    for todo in todos:
        status = "[x]" if todo["done"] else "[ ]"
        print(f"{todo['id']}. {status} {todo['text']}")


def done_todos(todos, args):
    n = args.n
    if n < 1 or n > len(todos):
        print(f"Invalid todo number: {n}")
        sys.exit(1)
    todos[n - 1]["done"] = True
    save_todos(todos)
    print(f"Marked #{n} as done")


def main():
    parser = argparse.ArgumentParser(description="Simple CLI Todo App")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new todo")
    add_parser.add_argument("text", nargs="+", help="Todo text")

    subparsers.add_parser("list", help="List all todos")

    done_parser = subparsers.add_parser("done", help="Mark a todo as done")
    done_parser.add_argument("n", type=int, help="Todo number")

    args = parser.parse_args()
    todos = load_todos()

    commands = {
        "add": add_todos,
        "list": list_todos,
        "done": done_todos,
    }
    commands[args.command](todos, args)


if __name__ == "__main__":
    main()
