

import curses
import random

def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    sh, sw = stdscr.getmaxyx()

    if sh < 10 or sw < 30:
        stdscr.addstr(0, 0, "Terminal too small!")
        stdscr.refresh()
        stdscr.nodelay(False)
        stdscr.getch()
        return

    start_y = 1
    start_x = 1
    play_area_h = sh - 2
    play_area_w = sw - 2

    snake = [(start_y, start_x)]
    direction = curses.KEY_RIGHT
    next_direction = curses.KEY_RIGHT
    score = 0

    def place_food():
        while True:
            y = random.randint(1, play_area_h - 1)
            x = random.randint(1, play_area_w - 1)
            if (y, x) not in snake:
                return (y, x)

    food = place_food()
    stdscr.addch(food[0], food[1], curses.CHARACTER_SQUARE, curses.A_BOLD)

    tick_delay = 100

    while True:
        stdscr.timeout(tick_delay)
        key = stdscr.getch()

        if key == ord('q') or key == ord('Q'):
            break
        elif key == curses.KEY_UP and direction != curses.KEY_DOWN:
            next_direction = curses.KEY_UP
        elif key == curses.KEY_DOWN and direction != curses.KEY_UP:
            next_direction = curses.KEY_DOWN
        elif key == curses.KEY_LEFT and direction != curses.KEY_RIGHT:
            next_direction = curses.KEY_LEFT
        elif key == curses.KEY_RIGHT and direction != curses.KEY_LEFT:
            next_direction = curses.KEY_RIGHT

        direction = next_direction

        head_y, head_x = snake[0]

        if direction == curses.KEY_UP:
            head_y -= 1
        elif direction == curses.KEY_DOWN:
            head_y += 1
        elif direction == curses.KEY_LEFT:
            head_x -= 1
        elif direction == curses.KEY_RIGHT:
            head_x += 1

        if head_y <= 0 or head_y >= play_area_h or head_x <= 0 or head_x >= play_area_w:
            break

        if (head_y, head_x) in snake:
            break

        snake.insert(0, (head_y, head_x))

        if (head_y, head_x) == food:
            score += 10
            food = place_food()
            stdscr.addch(food[0], food[1], curses.CHARACTER_SQUARE, curses.A_BOLD)
            if tick_delay > 40:
                tick_delay -= 2
        else:
            tail = snake.pop()
            stdscr.addch(tail[0], tail[1], ' ')

        stdscr.addch(head_y, head_x, curses.ACS_CKBOARD)

        for sy, sx in snake:
            stdscr.addch(sy, sx, ord('O'))
        stdscr.addch(snake[0][0], snake[0][1], ord('@'))

        stdscr.move(0, 0)
        stdscr.addstr(f" Score: {score}  |  Length: {len(snake)}  |  q=quit")
        stdscr.clrtoeol()
        stdscr.refresh()

    stdscr.timeout(-1)
    stdscr.clear()
    stdscr.refresh()

    msg = f"GAME OVER! Score: {score}  |  Length: {len(snake)}"
    msg_y = sh // 2
    msg_x = (sw - len(msg)) // 2
    stdscr.addstr(msg_y - 1, msg_x, "  Game Over!  ", curses.A_BOLD | curses.A_REVERSE)
    stdscr.addstr(msg_y, msg_x, msg, curses.A_BOLD)
    stdscr.addstr(msg_y + 1, msg_x, "  Press 'r' to restart or 'q' to quit  ", curses.A_BOLD | curses.A_REVERSE)
    stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key == ord('q') or key == ord('Q'):
            return
        elif key == ord('r') or key == ord('R'):
            break

    curses.endwin()
    stdscr.keypad(True)
    stdscr.nodelay(False)

    snake = [(start_y, start_x)]
    direction = curses.KEY_RIGHT
    next_direction = curses.KEY_RIGHT
    score = 0
    tick_delay = 100
    food = place_food()

    stdscr.clear()
    while True:
        stdscr.timeout(tick_delay)
        key = stdscr.getch()

        if key == ord('q') or key == ord('Q'):
            break
        elif key == curses.KEY_UP and direction != curses.KEY_DOWN:
            next_direction = curses.KEY_UP
        elif key == curses.KEY_DOWN and direction != curses.KEY_UP:
            next_direction = curses.KEY_DOWN
        elif key == curses.KEY_LEFT and direction != curses.KEY_RIGHT:
            next_direction = curses.KEY_LEFT
        elif key == curses.KEY_RIGHT and direction != curses.KEY_LEFT:
            next_direction = curses.KEY_RIGHT

        direction = next_direction

        head_y, head_x = snake[0]

        if direction == curses.KEY_UP:
            head_y -= 1
        elif direction == curses.KEY_DOWN:
            head_y += 1
        elif direction == curses.KEY_LEFT:
            head_x -= 1
        elif direction == curses.KEY_RIGHT:
            head_x += 1

        if head_y <= 0 or head_y >= play_area_h or head_x <= 0 or head_x >= play_area_w:
            break

        if (head_y, head_x) in snake:
            break

        snake.insert(0, (head_y, head_x))

        if (head_y, head_x) == food:
            score += 10
            food = place_food()
            stdscr.addch(food[0], food[1], curses.CHARACTER_SQUARE, curses.A_BOLD)
            if tick_delay > 40:
                tick_delay -= 2
        else:
            tail = snake.pop()
            stdscr.addch(tail[0], tail[1], ' ')

        for sy, sx in snake:
            stdscr.addch(sy, sx, ord('O'))
        stdscr.addch(snake[0][0], snake[0][1], ord('@'))

        stdscr.move(0, 0)
        stdscr.addstr(f" Score: {score}  |  Length: {len(snake)}  |  q=quit")
        stdscr.clrtoeol()
        stdscr.refresh()

    stdscr.timeout(-1)
    stdscr.clear()
    stdscr.refresh()
    stdscr.addstr(sh // 2, (sw - 5) // 2, "  Thanks for playing!  ", curses.A_BOLD | curses.A_REVERSE)
    stdscr.refresh()

if __name__ == "__main__":
    curses.wrapper(main)