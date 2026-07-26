#!/usr/bin/env python3
"""Simple CLI todo app that persists to ~/.todo.json"""

import argparse
import json
import os
import sys

TODO_FILE = os.path.expanduser("~/.todo.json")


def load_todos():
    """Load todos from JSON file, creating it if missing."""
    if os.path.exists(TODO_FILE):
        with open(TODO_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_todos(todos):
    """Persist todos to the JSON file."""
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f, indent=2)


def cmd_add(args):
    """Add a new todo item."""
    todos = load_todos()
    todos.append({"id": len(todos) + 1, "text": args.text, "done": False})
    save_todos(todos)
    print(f"Added: {args.text}")


def cmd_list(args):
    """List all todo items."""
    todos = load_todos()
    if not todos:
        print("No todos.")
        return
    for todo in todos:
        status = "[x]" if todo["done"] else "[ ]"
        print(f"{todo['id']:>3}. {status} {todo['text']}")


def cmd_done(args):
    """Mark a todo item as done."""
    todos = load_todos()
    if not (1 <= args.n <= len(todos)):
        print(f"Error: Invalid item number {args.n}. There are {len(todos)} item(s).")
        sys.exit(1)
    todos[args.n - 1]["done"] = True
    save_todos(todos)
    print(f"Marked {args.n} as done: {todos[args.n - 1]['text']}")


def main():
    parser = argparse.ArgumentParser(description="CLI todo app")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # add subcommand
    add_parser = subparsers.add_parser("add", help="Add a new todo")
    add_parser.add_argument("text", help="Description of the todo item")
    add_parser.set_defaults(func=cmd_add)

    # list subcommand
    list_parser = subparsers.add_parser("list", help="List all todos")
    list_parser.set_defaults(func=cmd_list)

    # done subcommand
    done_parser = subparsers.add_parser("done", help="Mark a todo as done")
    done_parser.add_argument("n", type=int, help="Index of the todo item (1-based)")
    done_parser.set_defaults(func=cmd_done)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
