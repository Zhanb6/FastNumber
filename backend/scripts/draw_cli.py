"""Run a draw from the server shell (emergency mode). Uses the same services as the API.

    python -m scripts.draw_cli list
    python -m scripts.draw_cli start <draw>
    python -m scripts.draw_cli redraw <draw> --reason "..."
    python -m scripts.draw_cli confirm <draw>
    python -m scripts.draw_cli idle

<draw> is a UUID, a position number (e.g. 1) or a title prefix.
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import Draw
from app.services import draw as draw_service
from app.services.draw import current_result

CLI_LOGIN = "cli"


async def resolve_draw(session: AsyncSession, ref: str) -> Draw:
    ref = ref.strip()
    try:
        draw = await session.get(Draw, uuid.UUID(ref))
        if draw is not None:
            return draw
    except ValueError:
        pass
    if ref.isdigit():
        draws = list(
            (await session.execute(select(Draw).where(Draw.position == int(ref)))).scalars()
        )
        if len(draws) == 1:
            return draws[0]
        if len(draws) > 1:
            raise SystemExit(f"Ambiguous position {ref}: {len(draws)} draws; use the UUID")
    draws = list((await session.execute(select(Draw).where(Draw.title.ilike(f"{ref}%")))).scalars())
    if len(draws) == 1:
        return draws[0]
    if len(draws) > 1:
        raise SystemExit(f"Ambiguous title prefix {ref!r}; use the UUID")
    raise SystemExit(f"Draw not found: {ref}")


def print_draw(draw: Draw) -> None:
    result = current_result(draw)
    winner = ""
    if result is not None:
        p = result.participant
        winner = f"  -> [{result.status.value}] #{p.number} {p.first_name} {p.last_name}"
    head = f"{draw.position:>3}  {draw.status.value:<20} {draw.id}"
    print(f"{head}  {draw.title} / {draw.prize}{winner}")


async def cmd_list(session: AsyncSession, _args) -> None:
    draws = await draw_service.list_draws(session)
    if not draws:
        print("No draws")
    for d in draws:
        print_draw(d)


async def cmd_start(session: AsyncSession, args) -> None:
    draw = await resolve_draw(session, args.draw)
    draw = await draw_service.start_draw(session, draw.id, admin_login=CLI_LOGIN, ip=None)
    print("Draw started; winner selected (pending confirmation):")
    print_draw(draw)


async def cmd_redraw(session: AsyncSession, args) -> None:
    draw = await resolve_draw(session, args.draw)
    draw = await draw_service.redraw(
        session, draw.id, reason=args.reason, admin_login=CLI_LOGIN, ip=None
    )
    print("Redraw done; new winner selected (pending confirmation):")
    print_draw(draw)


async def cmd_confirm(session: AsyncSession, args) -> None:
    draw = await resolve_draw(session, args.draw)
    draw = await draw_service.confirm(session, draw.id, admin_login=CLI_LOGIN, ip=None)
    print("Winner confirmed:")
    print_draw(draw)


async def cmd_idle(session: AsyncSession, _args) -> None:
    await draw_service.set_idle(session, admin_login=CLI_LOGIN, ip=None)
    print("Live screen set to IDLE")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="draw_cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list draws").set_defaults(func=cmd_list)
    p = sub.add_parser("start", help="start a draw (select a winner)")
    p.add_argument("draw")
    p.set_defaults(func=cmd_start)
    p = sub.add_parser("redraw", help="reject the current winner and pick a new one")
    p.add_argument("draw")
    p.add_argument("--reason", default=None)
    p.set_defaults(func=cmd_redraw)
    p = sub.add_parser("confirm", help="confirm the selected winner")
    p.add_argument("draw")
    p.set_defaults(func=cmd_confirm)
    sub.add_parser("idle", help="return the live screen to IDLE").set_defaults(func=cmd_idle)
    return parser


async def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    from app.db import async_session, engine

    try:
        async with async_session() as session:
            await args.func(session, args)
        return 0
    except ApiError as exc:
        details = f" {exc.details}" if exc.details else ""
        print(f"Error {exc.code}: {exc.message}{details}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
