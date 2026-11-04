
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.box import SQUARE

console = Console()


def display_board(board, valid_moves, current_player, black_score, white_score):

    console.clear()

    # Title
    console.print(
        Panel(
            "[bold cyan]O T H E L L O[/bold cyan]\n"
            "[dim]Human vs Human[/dim]",
            expand=False,
            border_style="green"
        ),
        justify="center"
    )

    # Scoreboard
    scores = Table.grid(expand=True)
    scores.add_column(justify="center")
    scores.add_column(justify="center")

    scores.add_row(
        f"[bold bright_white]BLACK: {black_score}[/bold bright_white]",
        f"[bold cyan]WHITE: {white_score}[/bold cyan]"
    )

    console.print(scores)
    console.print()

    # Board
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="green",
        box=SQUARE,
        padding=(1, 1),
        expand=False
    )

    table.add_column(" ", justify="center", width=3)

    for j in range(8):
        table.add_column(
            str(j),
            justify="center",
            width=5
        )

    for i in range(8):

        row = [f"[bold cyan]{i}[/bold cyan]"]

        for j in range(8):

            if board[i][j] == 1:
                cell = Text("●", style="bold black")

            elif board[i][j] == -1:
                cell = Text("●", style="bold bright_white")

            elif (i, j) in valid_moves:
                cell = Text("✦", style="bold bright_green")

            else:
                cell = Text("·", style="dim green")

            row.append(cell)

        table.add_row(*row)

    console.print(table, justify="center")

    # Turn indicator
    colour = (
        "BLACK" if current_player.colour == 1
        else "WHITE"
    )

    turn_style = (
        "bold bright_white" if current_player.colour == 1
        else "bold cyan"
    )

    console.print()

    console.print(
        Panel(
            f"[{turn_style}]{colour}'S TURN[/{turn_style}]\n"
            "[dim]Enter row and column (e.g. 2 4)[/dim]",
            border_style="green",
            expand=False
        ),
        justify="center"
    )

    # Legend
    console.print(
        "\n[dim]● Black piece    ● White piece    "
        "[bold bright_green]✦[/bold bright_green] Legal move[/dim]",
        justify="center"
    )
