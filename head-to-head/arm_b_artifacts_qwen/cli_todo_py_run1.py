#!/usr/bin/env python3
import argparse
import json
import os
import sys

TODO_FILE = os.path.expanduser("~/.todo.json")


def load_todos():
    if os.path.exists(TODO_FILE):
        with open(TODO_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_todos(todos):
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f, indent=2)


def add_todo(args):
    todos = load_todos()
    todos.append({"id": len(todos) + 1, "text": args.text, "done": False})
    save_todos(todos)
    print(f"Added: {args.text}")


def list_todos(args):
    todos = load_todos()
    if not todos:
        print("No todos found.")
        return
    for i, todo in enumerate(todos, 1):
        status = "[x]" if todo["done"] else "[ ]"
        print(f"{i}. {status} {todo['text']}")


def done_todo(args):
    todos = load_todos()
    if args.n < 1 or args.n > len(todos):
        print(f"Invalid todo number: {args.n}")
        sys.exit(1)
    todos[args.n - 1]["done"] = True
    save_todos(todos)
    print(f"Marked #{args.n} as done: {todos[args.n - 1]['text']}")


def main():
    parser = argparse.ArgumentParser(description="Simple CLI Todo App")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    add_parser = subparsers.add_parser("add", help="Add a new todo")
    add_parser.add_argument("text", help="Todo text")

    subparsers.add_parser("list", help="List all todos")

    done_parser = subparsers.add_parser("done", help="Mark a todo as done")
    done_parser.add_argument("n", type=int, help="Todo number to mark done")

    args = parser.parse_args()

    if args.command == "add":
        add_todo(args)
    elif args.command == "list":
        list_todos(args)
    elif args.command == "done":
        done_todo(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
